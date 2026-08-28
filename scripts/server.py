#!/usr/bin/env python3
"""Production localhost service for Interview Coach Agent."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import mimetypes
import os
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from multiprocessing.connection import Client as PipeClient
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vevc.interview_asr import InterviewAsrRuntime
from vevc.interview_coach import (
    CoachRequest,
    coach_interview,
    list_roles,
    load_request,
)
from vevc.interview_report import build_interview_report, write_interview_report
from vevc.moonshine_runtime import MoonshineRuntime


def load_legacy_http_dependencies() -> None:
    """Load the larger legacy HTTP surface only when that mode is requested."""
    global AudioWorkflowService
    global expand_logs
    global is_relative_to
    global list_command_previews
    global write_approval_request
    global write_confirmation_receipt
    global load_transcript
    global validate_workpack
    global extract_rule_candidates
    global compile_semantic

    from vevc.audio_workflow import (
        AudioWorkflowService as audio_workflow_service,
    )
    from vevc.audio_workflow import expand_logs as expand_log_paths
    from vevc.audio_workflow import is_relative_to as relative_check
    from vevc.command_gate import (
        list_command_previews as command_previews,
    )
    from vevc.command_gate import (
        write_approval_request as approval_request,
    )
    from vevc.command_gate import (
        write_confirmation_receipt as confirmation_receipt,
    )
    from vevc.contracts import load_transcript as transcript_loader
    from vevc.contracts import validate_workpack as workpack_validator
    from vevc.rule_semantics import (
        extract_rule_candidates as rule_candidates,
    )
    from vevc.semantic_compiler import compile_semantic as semantic_compiler

    AudioWorkflowService = audio_workflow_service
    expand_logs = expand_log_paths
    is_relative_to = relative_check
    list_command_previews = command_previews
    write_approval_request = approval_request
    write_confirmation_receipt = confirmation_receipt
    load_transcript = transcript_loader
    validate_workpack = workpack_validator
    extract_rule_candidates = rule_candidates
    compile_semantic = semantic_compiler


class BusyError(RuntimeError):
    """Raised when the single-worker service is busy past the queue timeout."""


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


class ProductionService:
    def __init__(
        self,
        *,
        root: Path,
        approval_secret_env: str,
        queue_timeout_seconds: float,
        interview_asr_provider: str = "moonshine",
        openvino_model_dir: Path | None = None,
        openvino_device: str = "CPU",
    ) -> None:
        self.root = root.resolve()
        self.runtime = MoonshineRuntime(self.root)
        self.interview_runtime = InterviewAsrRuntime(
            root=self.root,
            provider=interview_asr_provider,
            openvino_model_dir=openvino_model_dir,
            openvino_device=openvino_device,
            moonshine_runtime=(
                self.runtime
                if interview_asr_provider == "moonshine"
                else None
            ),
        )
        self.audio = AudioWorkflowService(root=self.root, runtime=self.runtime)
        self.approval_secret_env = approval_secret_env
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
                "version": "0.3.0",
                "state": self.state,
                "active_operation": self.active_operation,
                "uptime_seconds": round(time.time() - self.started_at, 3),
                "request_count": self.request_count,
                "error_count": self.error_count,
                "last_operation": self.last_operation,
                "last_latency_seconds": self.last_latency_seconds,
                "process_peak_rss_bytes": peak_rss_bytes(),
                "loaded_asr_languages": self.runtime.loaded_languages,
                "interview_asr": self.interview_runtime.metadata(),
                "capabilities": [
                    "interview-coach",
                    "interview-second-attempt-comparison",
                    "interview-practice-report",
                    "interview-role-library",
                    "local-transcription",
                    "semantic-compile",
                    "transcribe",
                    "audio-workflow",
                    "validate-workpack",
                    "command-preview",
                    "command-request",
                    "command-confirm",
                ],
                "policy": {
                    "network": "loopback-only",
                    "side_effects": False,
                    "command_execution": False,
                    "single_worker": True,
                    "rewrite_invents_experience": False,
                },
            }

    def close(self) -> None:
        self.runtime.close()
        self.interview_runtime.close()

    def invoke(
        self,
        operation: str,
        function: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        acquired = self._lock.acquire(timeout=self.queue_timeout_seconds)
        if not acquired:
            raise BusyError(
                f"service remained busy for {self.queue_timeout_seconds}s"
            )
        started = time.perf_counter()
        with self._state_lock:
            self.state = "processing"
            self.active_operation = operation
        try:
            result = function()
            with self._state_lock:
                self.request_count += 1
                self.last_operation = operation
                self.last_latency_seconds = round(
                    time.perf_counter() - started,
                    6,
                )
            return result
        except Exception:
            with self._state_lock:
                self.request_count += 1
                self.error_count += 1
                self.last_operation = operation
                self.last_latency_seconds = round(
                    time.perf_counter() - started,
                    6,
                )
            raise
        finally:
            with self._state_lock:
                self.state = "ready"
                self.active_operation = None
            self._lock.release()

    def compile(self, payload: dict[str, Any]) -> dict[str, Any]:
        transcript = self.audio.input_path(payload["transcript"])
        segments = load_transcript(transcript)
        candidates = extract_rule_candidates(segments)
        output = self.audio.output_path(payload["output"])
        manifest = compile_semantic(
            transcript_path=transcript,
            candidates=candidates,
            workspace_path=self.audio.input_path(payload["workspace"]),
            log_paths=expand_logs(self.audio.input_path(payload["logs"])),
            output_path=output,
            output_root=self.root / "build",
            overwrite=bool(payload.get("overwrite", False)),
            host_agent=payload.get("host_agent", "localhost-service"),
            host_version=payload.get("host_version"),
            candidate_provider="rule-baseline",
            mode=payload.get("mode", "incident"),
        )
        return {
            "ok": True,
            "output": relative(self.root, output),
            "run_id": manifest["run_id"],
            "validation": validate_workpack(output),
        }

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
        evidence = self.interview_runtime.transcribe_file(
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

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        workpack = self.audio.input_path(payload["workpack"])
        return {
            "ok": True,
            "workpack": relative(self.root, workpack),
            "validation": validate_workpack(workpack),
        }

    def command_preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        workpack = self.audio.input_path(payload["workpack"])
        return {
            "ok": True,
            "commands": list_command_previews(workpack),
        }

    def command_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = write_approval_request(
            workpack=self.audio.input_path(payload["workpack"]),
            claim_id=payload["claim_id"],
            requester=payload["requester"],
            ttl_minutes=int(payload.get("ttl_minutes", 15)),
            output=self.audio.output_file(payload["output"]),
            output_root=self.root / "build",
            overwrite=bool(payload.get("overwrite", False)),
        )
        return {"ok": True, "request": request}

    def command_confirm(self, payload: dict[str, Any]) -> dict[str, Any]:
        secret = os.environ.get(self.approval_secret_env)
        if not secret:
            raise ValueError(
                f"approval secret env is missing: {self.approval_secret_env}"
            )
        receipt = write_confirmation_receipt(
            request_path=self.audio.input_path(payload["request"]),
            approver=payload["approver"],
            signature=payload["signature"],
            secret=secret,
            output=self.audio.output_file(payload["output"]),
            output_root=self.root / "build",
            overwrite=bool(payload.get("overwrite", False)),
        )
        return {"ok": True, "receipt": receipt}


ROUTES: dict[str, tuple[str, Callable[[ProductionService, dict[str, Any]], dict[str, Any]]]] = {
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
    "/v1/compile": ("compile", lambda service, payload: service.compile(payload)),
    "/v1/transcribe": (
        "transcribe",
        lambda service, payload: service.audio.transcribe(payload),
    ),
    "/v1/audio-workflow": (
        "audio-workflow",
        lambda service, payload: service.audio.audio_workflow(payload),
    ),
    "/v1/validate": (
        "validate",
        lambda service, payload: service.validate(payload),
    ),
    "/v1/command/preview": (
        "command-preview",
        lambda service, payload: service.command_preview(payload),
    ),
    "/v1/command/request": (
        "command-request",
        lambda service, payload: service.command_request(payload),
    ),
    "/v1/command/confirm": (
        "command-confirm",
        lambda service, payload: service.command_confirm(payload),
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
    service: ProductionService,
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
                relative_path = path.removeprefix("/app/")
                static_root = (service.root / "demo-web").resolve()
                candidate = (static_root / relative_path).resolve()
                if not is_relative_to(candidate, static_root):
                    self._send(
                        400,
                        error_payload(
                            "invalid_request",
                            "static path escapes demo-web",
                        ),
                    )
                    return
                self._send_static(candidate)
                return
            self._send(404, error_payload("not_found", "route not found"))

        def do_OPTIONS(self) -> None:
            self._send(204, {})

        def _send_static(self, path: Path) -> None:
            if not path.is_file():
                self._send(404, error_payload("not_found", "asset not found"))
                return
            body = path.read_bytes()
            content_type = (
                mimetypes.guess_type(path.name)[0]
                or "application/octet-stream"
            )
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/v1/shutdown":
                self._send(200, {"ok": True, "state": "shutting_down"})
                threading.Thread(
                    target=server_ref[0].shutdown,
                    daemon=True,
                ).start()
                return
            route = ROUTES.get(path)
            if route is None:
                self._send(404, error_payload("not_found", "route not found"))
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 6 * 1024 * 1024:
                    raise ValueError("request body must be 1 byte to 6 MiB")
                payload = json.loads(
                    self.rfile.read(length).decode("utf-8")
                )
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                operation, function = route
                result = service.invoke(
                    operation,
                    lambda: function(service, payload),
                )
                status = 409 if result.get("status") == "blocked" else 200
                self._send(status, result)
            except BusyError as exc:
                self._send(503, error_payload("busy", str(exc), retryable=True))
            except (KeyError, TypeError, ValueError) as exc:
                self._send(400, error_payload("invalid_request", str(exc)))
            except Exception as exc:
                self._send(500, error_payload("internal_error", str(exc)))

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


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path.resolve())


def peak_rss_bytes() -> int:
    try:
        import resource

        value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(value if sys.platform == "darwin" else value * 1024)
    except ImportError:
        try:
            import psutil

            return int(psutil.Process().memory_info().rss)
        except ImportError:
            return 0


class AipcPipeService:
    """Reference-style local service using status/request/shutdown operations."""

    def __init__(self) -> None:
        self.state = "starting"
        self.error = ""
        self.started_at = time.time()
        self.last_used_at = self.started_at
        self.asr_fallback: str | None = None
        self.runtime: InterviewAsrRuntime | None = None
        self._lock = threading.Lock()

    def init_async(self) -> None:
        threading.Thread(target=self._initialize, daemon=True).start()

    def _initialize(self) -> None:
        try:
            from scripts import model_manager

            self.state = "downloading"
            model_manager.ensure_models()
            self.state = "loading"
            self.runtime = build_aipc_asr_runtime()
            try:
                self.runtime.preload("zh")
            except Exception:
                if os.environ.get("INTERVIEW_AIPC_ASR_PROVIDER", "auto").lower() == "auto":
                    self.runtime.close()
                    self.runtime = InterviewAsrRuntime(root=ROOT, provider="moonshine")
                    self.runtime.preload("zh")
                    self.asr_fallback = "openvino-unavailable-to-moonshine"
                else:
                    raise
            self.state = "running"
        except Exception:
            self.error = traceback.format_exc()
            self.state = "error"

    def close(self) -> None:
        if self.runtime is not None:
            self.runtime.close()
        self.runtime = None

    def status(self) -> dict[str, Any]:
        from scripts import model_manager

        return {
            "ok": True,
            "service": "interview-coach-agent",
            "transport": "named-pipe",
            "state": self.state,
            "pid": os.getpid(),
            "uptime_s": round(time.time() - self.started_at, 3),
            "error": self.error,
            "models": model_manager.model_status()["models"],
            "asr": self.runtime.metadata() if self.runtime is not None else None,
            "asr_fallback": self.asr_fallback,
            "runtime_hash": model_manager.runtime_hash(),
            "memory_rss_bytes": peak_rss_bytes(),
        }

    def handle(self, message: dict[str, Any]) -> dict[str, Any]:
        self.last_used_at = time.time()
        operation = message.get("op")
        if operation == "status":
            return self.status()
        if operation == "shutdown":
            return {"ok": True, "state": "shutting_down"}
        if operation != "request":
            return {"ok": False, "error": f"unknown op: {operation}"}
        if self.state != "running":
            return {
                "ok": False,
                "state": self.state,
                "error": self.error or f"service is not ready: {self.state}",
            }
        action = message.get("action")
        with self._lock:
            if action == "roles":
                return {"ok": True, **list_roles()}
            if action == "coach":
                result = coach_interview(
                    CoachRequest(
                        role=message["role"],
                        question_id=message.get("question_id"),
                        answer=message["answer"],
                        second_answer=message.get("second_answer"),
                    )
                )
                return {"ok": True, "result": result}
            if action == "report":
                result = write_interview_report(
                    request=pipe_report_request(message),
                    output=Path(message["output"]),
                    output_root=ROOT / "build",
                    overwrite=bool(message.get("overwrite", False)),
                )
                return {"ok": True, **result}
        return {"ok": False, "error": f"unknown action: {action}"}


def build_aipc_asr_runtime() -> InterviewAsrRuntime:
    requested = os.environ.get("INTERVIEW_AIPC_ASR_PROVIDER", "auto").lower()
    if requested not in {"auto", "moonshine", "openvino"}:
        raise ValueError(
            "INTERVIEW_AIPC_ASR_PROVIDER must be auto, moonshine, or openvino"
        )
    model_dir = find_openvino_model_dir()
    if requested == "openvino" and model_dir is None:
        raise RuntimeError("OpenVINO provider requested but no local model was found")
    if requested == "openvino" or (requested == "auto" and model_dir is not None):
        return InterviewAsrRuntime(
            root=ROOT,
            provider="openvino",
            openvino_model_dir=model_dir,
            openvino_device=pick_openvino_device(),
        )
    return InterviewAsrRuntime(root=ROOT, provider="moonshine")


def find_openvino_model_dir() -> Path | None:
    configured = os.environ.get("INTERVIEW_OPENVINO_MODEL_DIR")
    roots = []
    if configured:
        roots.append(Path(configured).expanduser())
    local_home = os.environ.get("LOCAL_SKILL_HOME")
    if local_home:
        roots.append(Path(local_home).expanduser() / "models" / "openvino")
    roots.append(ROOT / "models" / "openvino")
    for root in roots:
        resolved = root.resolve()
        if not resolved.exists():
            continue
        candidates = [resolved] if resolved.is_dir() else []
        candidates.extend(path for path in resolved.rglob("*") if path.is_dir())
        for candidate in candidates:
            if any(candidate.glob("*.xml")) and any(candidate.glob("*.bin")):
                return candidate
    return None


def pick_openvino_device() -> str:
    configured = os.environ.get("INTERVIEW_OPENVINO_DEVICE")
    if configured:
        return configured
    try:
        import openvino as ov

        devices = list(ov.Core().available_devices)
    except Exception:
        return "CPU"
    return next((device for device in devices if "GPU" in device.upper()), "CPU")


def pipe_report_request(message: dict[str, Any]) -> CoachRequest:
    if message.get("input"):
        candidate = Path(str(message["input"])).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        return load_request(candidate.resolve())
    if not message.get("role") or not message.get("answer"):
        raise ValueError("report requires input or role and answer")
    return CoachRequest(
        role=str(message["role"]),
        question_id=message.get("question_id"),
        answer=str(message["answer"]),
        second_answer=message.get("second_answer"),
    )


def run_aipc_pipe_server(address: str) -> int:
    configure_utf8()
    service = AipcPipeService()
    service.init_async()
    start_idle_monitor(service, address)
    pipe_path = Path(address) if os.name != "nt" else None
    if pipe_path is not None:
        pipe_path.parent.mkdir(parents=True, exist_ok=True)
        if pipe_path.exists():
            pipe_path.unlink()
    try:
        with Listener(address, authkey=b"interview-coach-agent") as listener:
            while True:
                with listener.accept() as connection:
                    message = connection.recv()
                    if not isinstance(message, dict):
                        response = {
                            "ok": False,
                            "error": "request must be a JSON-like object",
                        }
                    else:
                        try:
                            response = service.handle(message)
                        except (KeyError, TypeError, ValueError) as exc:
                            response = {"ok": False, "error": str(exc)}
                        except Exception:
                            response = {
                                "ok": False,
                                "error": traceback.format_exc(),
                            }
                    connection.send(response)
                    if isinstance(message, dict) and message.get("op") == "shutdown":
                        return 0
    finally:
        service.close()
        if pipe_path is not None and pipe_path.exists():
            pipe_path.unlink()


def start_idle_monitor(service: AipcPipeService, address: str) -> None:
    try:
        from scripts import model_manager

        timeout = float(
            model_manager.load_info().get("server_alive_timeout", 300)
        )
    except Exception:
        timeout = 300
    if timeout < 0:
        return

    def monitor() -> None:
        while True:
            time.sleep(min(5.0, max(0.5, timeout / 4)))
            if service.state in {"starting", "downloading", "loading"}:
                continue
            if time.time() - service.last_used_at <= timeout:
                continue
            try:
                with PipeClient(
                    address,
                    authkey=b"interview-coach-agent",
                ) as connection:
                    connection.send({"op": "shutdown"})
                    connection.recv()
            except Exception:
                pass
            return

    threading.Thread(target=monitor, daemon=True).start()


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--aipc-service", action="store_true")
    parser.add_argument("--pipe")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--preload", choices=["none", "en", "zh"], default="none")
    parser.add_argument(
        "--interview-asr-provider",
        choices=["moonshine", "openvino"],
        default="moonshine",
    )
    parser.add_argument("--openvino-model-dir", type=Path)
    parser.add_argument("--openvino-device", default="CPU")
    parser.add_argument("--queue-timeout-seconds", type=float, default=120)
    parser.add_argument(
        "--approval-secret-env",
        default="VEVC_APPROVAL_SECRET",
    )
    parser.add_argument("--allow-remote", action="store_true")
    args = parser.parse_args()
    if args.aipc_service:
        if not args.pipe:
            raise SystemExit("--pipe is required with --aipc-service")
        return run_aipc_pipe_server(args.pipe)
    load_legacy_http_dependencies()
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not args.allow_remote:
        raise SystemExit("non-loopback binding requires --allow-remote")
    service = ProductionService(
        root=ROOT,
        approval_secret_env=args.approval_secret_env,
        queue_timeout_seconds=args.queue_timeout_seconds,
        interview_asr_provider=args.interview_asr_provider,
        openvino_model_dir=args.openvino_model_dir,
        openvino_device=args.openvino_device,
    )
    if args.preload != "none":
        service.interview_runtime.preload(args.preload)
    server_ref: list[ThreadingHTTPServer] = []
    server = ThreadingHTTPServer(
        (args.host, args.port),
        make_handler(service, server_ref),
    )
    server_ref.append(server)
    print(
        f"Interview Coach Agent service: "
        f"http://{args.host}:{args.port}",
        flush=True,
    )
    try:
        server.serve_forever()
    finally:
        service.close()
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
