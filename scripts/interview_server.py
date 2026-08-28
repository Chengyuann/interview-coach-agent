#!/usr/bin/env python3
"""Minimal localhost service for AI 面试陪练官."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vevc.interview_asr import InterviewAsrRuntime  # noqa: E402
from vevc.interview_coach import CoachRequest, coach_interview, list_roles  # noqa: E402
from vevc.interview_report import build_interview_report  # noqa: E402


class BusyError(RuntimeError):
    """Raised when the single-worker service is busy."""


class InterviewService:
    def __init__(
        self,
        *,
        root: Path,
        queue_timeout_seconds: float = 120,
        asr_provider: str = "moonshine",
        openvino_model_dir: Path | None = None,
        openvino_device: str = "CPU",
    ) -> None:
        self.root = root.resolve()
        self.runtime = InterviewAsrRuntime(
            root=self.root,
            provider=asr_provider,
            openvino_model_dir=openvino_model_dir,
            openvino_device=openvino_device,
        )
        self.queue_timeout_seconds = queue_timeout_seconds
        self.started_at = time.time()
        self.state = "ready"
        self.active_operation: str | None = None
        self.request_count = 0
        self.error_count = 0
        self.last_operation: str | None = None
        self.last_latency_seconds: float | None = None
        self._lock = threading.Lock()
        self._state_lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            return {
                "ok": True,
                "service": "interview-coach-agent",
                "version": "0.1.0",
                "state": self.state,
                "active_operation": self.active_operation,
                "uptime_seconds": round(time.time() - self.started_at, 3),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "last_operation": self.last_operation,
                "last_latency_seconds": self.last_latency_seconds,
                "process_peak_rss_bytes": peak_rss_bytes(),
                "loaded_asr_languages": self.runtime.loaded_languages,
                "asr": self.runtime.metadata(),
                "capabilities": [
                    "interview-coach",
                    "interview-second-attempt-comparison",
                    "interview-practice-report",
                    "interview-role-library",
                    "local-transcription",
                ],
                "policy": {
                    "network": "loopback-only",
                    "side_effects": False,
                    "command_execution": False,
                    "rewrite_invents_experience": False,
                },
            }

    def close(self) -> None:
        self.runtime.close()

    def invoke(
        self,
        operation: str,
        function: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        acquired = self._lock.acquire(timeout=self.queue_timeout_seconds)
        if not acquired:
            raise BusyError(f"service remained busy for {self.queue_timeout_seconds}s")
        started = time.perf_counter()
        with self._state_lock:
            self.state = "processing"
            self.active_operation = operation
        try:
            result = function()
            with self._state_lock:
                self.request_count += 1
                self.last_operation = operation
                self.last_latency_seconds = round(time.perf_counter() - started, 6)
            return result
        except Exception:
            with self._state_lock:
                self.request_count += 1
                self.error_count += 1
                self.last_operation = operation
                self.last_latency_seconds = round(time.perf_counter() - started, 6)
            raise
        finally:
            with self._state_lock:
                self.state = "ready"
                self.active_operation = None
            self._lock.release()

    def interview_roles(self) -> dict[str, Any]:
        return {"ok": True, **list_roles()}

    def interview_coach(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = coach_interview(coach_request(payload))
        return {"ok": True, "result": result}

    def interview_report(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"ok": True, **build_interview_report(coach_request(payload))}

    def interview_transcribe(self, payload: dict[str, Any]) -> dict[str, Any]:
        encoded = payload["audio_base64"]
        if not isinstance(encoded, str) or not encoded:
            raise ValueError("audio_base64 must be a non-empty string")
        try:
            audio = base64.b64decode(encoded, validate=True)
        except Exception as exc:
            raise ValueError("audio_base64 is invalid") from exc
        if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
            raise ValueError("audio must be a PCM WAV file")
        if len(audio) > 4 * 1024 * 1024:
            raise ValueError("audio must be no larger than 4 MiB")
        digest = hashlib.sha256(audio).hexdigest()[:16]
        staging = self.root / "build" / ".interview-server" / digest
        staging.mkdir(parents=True, exist_ok=True)
        audio_path = staging / "answer.wav"
        transcript_path = staging / "transcript.jsonl"
        evidence_path = staging / "asr-evidence.json"
        audio_path.write_bytes(audio)
        evidence = self.runtime.transcribe_file(
            audio_path=audio_path,
            language=payload.get("language", "zh"),
            output_path=transcript_path,
            evidence_path=evidence_path,
        )
        return {
            "ok": True,
            "text": evidence["text"],
            "provider": evidence.get("provider", "moonshine"),
            "model": evidence.get("model"),
            "audio_sha256": evidence["audio"]["sha256"],
            "duration_ms": evidence["audio"]["duration_ms"],
            "inference_seconds": evidence["inference_seconds"],
            "real_time_factor": evidence["real_time_factor"],
        }


ROUTES: dict[str, tuple[str, Callable[[InterviewService, dict[str, Any]], dict[str, Any]]]] = {
    "/v1/interview/coach": (
        "interview-coach",
        lambda service, payload: service.interview_coach(payload),
    ),
    "/v1/interview/report": (
        "interview-report",
        lambda service, payload: service.interview_report(payload),
    ),
    "/v1/interview/transcribe": (
        "interview-transcribe",
        lambda service, payload: service.interview_transcribe(payload),
    ),
}


def coach_request(payload: dict[str, Any]) -> CoachRequest:
    return CoachRequest(
        role=payload["role"],
        question_id=payload.get("question_id"),
        answer=payload["answer"],
        second_answer=payload.get("second_answer"),
    )


def make_handler(
    service: InterviewService,
    server_ref: list[ThreadingHTTPServer],
):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/v1/status":
                self._send(200, service.status())
                return
            if path == "/v1/interview/roles":
                self._send(200, service.interview_roles())
                return
            if path == "/":
                self._send_static(service.root / "demo-web" / "index.html")
                return
            if path.startswith("/app/"):
                static_root = (service.root / "demo-web").resolve()
                candidate = (static_root / path.removeprefix("/app/")).resolve()
                if not is_relative_to(candidate, static_root):
                    self._send(400, error_payload("invalid_request", "invalid static path"))
                    return
                self._send_static(candidate)
                return
            self._send(404, error_payload("not_found", "route not found"))

        def do_OPTIONS(self) -> None:
            self._send(204, {})

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/v1/shutdown":
                self._send(200, {"ok": True, "state": "shutting_down"})
                threading.Thread(target=server_ref[0].shutdown, daemon=True).start()
                return
            route = ROUTES.get(path)
            if route is None:
                self._send(404, error_payload("not_found", "route not found"))
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 6 * 1024 * 1024:
                    raise ValueError("request body must be 1 byte to 6 MiB")
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                operation, function = route
                self._send(200, service.invoke(operation, lambda: function(service, payload)))
            except BusyError as exc:
                self._send(503, error_payload("busy", str(exc), retryable=True))
            except (KeyError, TypeError, ValueError) as exc:
                self._send(400, error_payload("invalid_request", str(exc)))
            except Exception as exc:
                self._send(500, error_payload("internal_error", str(exc)))

        def _send_static(self, path: Path) -> None:
            if not path.is_file():
                self._send(404, error_payload("not_found", "asset not found"))
                return
            body = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: Any) -> None:
            return

    return Handler


def error_payload(
    code: str,
    message: str,
    *,
    retryable: bool = False,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    }


def peak_rss_bytes() -> int:
    try:
        import resource
    except ImportError:
        return 0
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(value if sys.platform == "darwin" else value * 1024)


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--preload", choices=["none", "en", "zh"], default="none")
    parser.add_argument(
        "--asr-provider",
        choices=["moonshine", "openvino"],
        default="moonshine",
    )
    parser.add_argument("--openvino-model-dir", type=Path)
    parser.add_argument("--openvino-device", default="CPU")
    parser.add_argument("--queue-timeout-seconds", type=float, default=120)
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not args.allow_remote:
        raise SystemExit("non-loopback binding requires --allow-remote")
    service = InterviewService(
        root=ROOT,
        queue_timeout_seconds=args.queue_timeout_seconds,
        asr_provider=args.asr_provider,
        openvino_model_dir=args.openvino_model_dir,
        openvino_device=args.openvino_device,
    )
    if args.preload != "none":
        service.runtime.preload(args.preload)
    server_ref: list[ThreadingHTTPServer] = []
    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(service, server_ref),
    )
    server_ref.append(server)
    print(f"Interview Coach Agent service: http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        service.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
