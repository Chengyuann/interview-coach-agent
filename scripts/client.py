#!/usr/bin/env python3
"""Short-lived AIPC client plus legacy HTTP client compatibility."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from multiprocessing.connection import Client
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import model_manager  # noqa: E402

SKILL_NAME = "interview-coach-agent"
AUTHKEY = SKILL_NAME.encode("utf-8")
READY_WAIT_TIMEOUT = float(os.environ.get("LOCAL_SKILL_READY_WAIT_SECONDS", "60"))


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def pipe_address() -> str:
    if os.name == "nt":
        return rf"\\.\pipe\{SKILL_NAME}"
    import hashlib

    suffix = hashlib.sha256(
        str(model_manager.skill_home()).encode("utf-8")
    ).hexdigest()[:12]
    pipe_dir = Path("/tmp") if Path("/tmp").is_dir() else Path.cwd()
    pipe_dir.mkdir(parents=True, exist_ok=True)
    return str(pipe_dir / f"aipc-{suffix}.sock")


def log_dir() -> Path:
    path = model_manager.skill_home() / "log"
    path.mkdir(parents=True, exist_ok=True)
    return path


def server_python() -> str:
    candidates = [
        Path(sys.executable),
        ROOT / ".venv-moonshine" / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        ),
    ]
    for candidate in candidates:
        if candidate.is_file() and has_moonshine(candidate):
            return str(candidate)
    return sys.executable


def has_moonshine(python: Path) -> bool:
    result = subprocess.run(
        [
            str(python),
            "-c",
            "import moonshine_voice",
        ],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return (
                response.status,
                json.loads(response.read().decode("utf-8")),
            )
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        return 503, {
            "ok": False,
            "error": {
                "code": "connection_error",
                "message": str(exc.reason),
                "retryable": True,
            },
        }


def send_pipe(payload: dict[str, Any]) -> dict[str, Any]:
    with Client(pipe_address(), authkey=AUTHKEY) as conn:
        conn.send(payload)
        response = conn.recv()
    if not isinstance(response, dict):
        raise RuntimeError("server returned a non-object response")
    return response


def server_status() -> dict[str, Any] | None:
    try:
        response = send_pipe({"op": "status"})
        return response if response.get("ok") else None
    except Exception:
        return None


def ensure_server() -> None:
    status = server_status()
    if status is not None:
        if status.get("runtime_hash") == model_manager.runtime_hash():
            return
        try:
            send_pipe({"op": "shutdown"})
        except Exception:
            pass
        deadline = time.time() + 5
        while time.time() < deadline and server_status() is not None:
            time.sleep(0.1)
    stdout = (log_dir() / f"{SKILL_NAME}-server.out.log").open(
        "a",
        encoding="utf-8",
    )
    stderr = (log_dir() / f"{SKILL_NAME}-server.err.log").open(
        "a",
        encoding="utf-8",
    )
    subprocess.Popen(
        [
            server_python(),
            str(ROOT / "scripts" / "server.py"),
            "--pipe",
            pipe_address(),
            "--aipc-service",
        ],
        cwd=ROOT,
        stdout=stdout,
        stderr=stderr,
        close_fds=(os.name != "nt"),
    )


def wait_ready(original_request: dict[str, Any]) -> None:
    deadline = time.time() + READY_WAIT_TIMEOUT
    last_state = "starting"
    while time.time() < deadline:
        try:
            status = send_pipe({"op": "status"})
            last_state = str(status.get("state", "unknown"))
        except Exception:
            time.sleep(0.2)
            continue
        if last_state == "running":
            return
        if last_state == "error":
            print(f"服务初始化失败: {status.get('error')}")
            raise SystemExit(1)
        time.sleep(0.5)
    if not model_manager.model_status()["ok"]:
        model_manager.save_pending_request(original_request)
        print("模型正在准备，请运行 'scripts\\run.ps1 --continue' 继续。")
        raise SystemExit(3)
    print(f"服务未就绪: {last_state}")
    raise SystemExit(2)


def wait_for_connection() -> dict[str, Any]:
    deadline = time.time() + READY_WAIT_TIMEOUT
    while time.time() < deadline:
        try:
            return send_pipe({"op": "status"})
        except Exception:
            time.sleep(0.2)
    print("无法连接本地 Skill 服务。")
    raise SystemExit(2)


def build_pipe_request(args: argparse.Namespace) -> dict[str, Any]:
    if args.operation == "status":
        return {"op": "status"}
    if args.operation == "roles":
        return {"op": "request", "action": "roles"}
    if args.operation == "coach":
        return {
            "op": "request",
            "action": "coach",
            "role": args.role,
            "question_id": args.question_id,
            "answer": args.answer,
            "second_answer": args.second_answer,
        }
    if args.operation == "report":
        return {
            "op": "request",
            "action": "report",
            "input": str(args.input) if args.input else None,
            "role": args.role,
            "question_id": args.question_id,
            "answer": args.answer,
            "second_answer": args.second_answer,
            "output": str(args.output),
            "overwrite": args.overwrite,
        }
    if args.operation == "shutdown":
        return {"op": "shutdown"}
    raise ValueError(f"unsupported operation: {args.operation}")


def run_pipe_client(args: argparse.Namespace) -> int:
    payload = (
        model_manager.load_pending_request()
        if args.continue_request
        else build_pipe_request(args)
    )
    ensure_server()
    status = wait_for_connection()
    if payload.get("op") == "status":
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0 if status.get("ok") else 2
    if payload.get("op") == "request":
        wait_ready(payload)
    response = send_pipe(payload)
    print(json.dumps(response, ensure_ascii=False, indent=2))
    if response.get("ok"):
        if args.continue_request:
            model_manager.clear_pending_request()
        return 0
    if response.get("state") in {"starting", "downloading", "loading"}:
        return 2
    return 1


def add_http_parsers(subparsers: argparse._SubParsersAction) -> None:
    subparsers.add_parser("interview-roles")

    coach = subparsers.add_parser("interview-coach")
    coach.add_argument("--role", required=True)
    coach.add_argument("--question-id")
    coach.add_argument("--answer", required=True)
    coach.add_argument("--second-answer")

    transcribe = subparsers.add_parser("interview-transcribe")
    transcribe.add_argument("--audio", required=True)
    transcribe.add_argument("--language", choices=["en", "zh"], default="zh")

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("--transcript", required=True)
    compile_parser.add_argument("--workspace", required=True)
    compile_parser.add_argument("--logs", required=True)
    compile_parser.add_argument("--output", required=True)
    compile_parser.add_argument(
        "--mode",
        choices=["incident", "review", "triage"],
        default="incident",
    )
    compile_parser.add_argument("--overwrite", action="store_true")

    transcribe_parser = subparsers.add_parser("transcribe")
    source = transcribe_parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio")
    source.add_argument("--audio-manifest")
    transcribe_parser.add_argument("--language", choices=["en", "zh"], default="zh")
    transcribe_parser.add_argument("--output", required=True)
    transcribe_parser.add_argument("--evidence")

    workflow = subparsers.add_parser("audio-workflow")
    source = workflow.add_mutually_exclusive_group(required=True)
    source.add_argument("--audio")
    source.add_argument("--audio-manifest")
    workflow.add_argument("--language", choices=["en", "zh"], default="zh")
    workflow.add_argument("--workspace", required=True)
    workflow.add_argument("--logs", required=True)
    workflow.add_argument("--output", required=True)
    workflow.add_argument(
        "--mode",
        choices=["incident", "review", "triage"],
        default="incident",
    )
    workflow.add_argument("--corrections")
    workflow.add_argument("--overwrite", action="store_true")

    validate = subparsers.add_parser("validate")
    validate.add_argument("workpack")
    preview = subparsers.add_parser("command-preview")
    preview.add_argument("workpack")
    request = subparsers.add_parser("command-request")
    request.add_argument("workpack")
    request.add_argument("--claim-id", required=True)
    request.add_argument("--requester", required=True)
    request.add_argument("--ttl-minutes", type=int, default=15)
    request.add_argument("--output", required=True)
    request.add_argument("--overwrite", action="store_true")
    confirm = subparsers.add_parser("command-confirm")
    confirm.add_argument("request")
    confirm.add_argument("--approver", required=True)
    confirm.add_argument("--signature", required=True)
    confirm.add_argument("--output", required=True)
    confirm.add_argument("--overwrite", action="store_true")


def build_http_request(args: argparse.Namespace) -> tuple[str, dict[str, Any]]:
    if args.operation == "interview-coach":
        return "/v1/interview/coach", {
            "role": args.role,
            "question_id": args.question_id,
            "answer": args.answer,
            "second_answer": args.second_answer,
        }
    if args.operation == "interview-transcribe":
        import base64

        audio = Path(args.audio).expanduser().read_bytes()
        return "/v1/interview/transcribe", {
            "audio_base64": base64.b64encode(audio).decode("ascii"),
            "language": args.language,
        }
    if args.operation == "compile":
        return "/v1/compile", {
            "transcript": args.transcript,
            "workspace": args.workspace,
            "logs": args.logs,
            "output": args.output,
            "mode": args.mode,
            "overwrite": args.overwrite,
        }
    if args.operation == "transcribe":
        return "/v1/transcribe", {
            "audio": args.audio,
            "audio_manifest": args.audio_manifest,
            "language": args.language,
            "output": args.output,
            "evidence": args.evidence,
        }
    if args.operation == "audio-workflow":
        return "/v1/audio-workflow", {
            "audio": args.audio,
            "audio_manifest": args.audio_manifest,
            "language": args.language,
            "workspace": args.workspace,
            "logs": args.logs,
            "output": args.output,
            "mode": args.mode,
            "corrections": args.corrections,
            "overwrite": args.overwrite,
            "host_agent": "localhost-client",
        }
    if args.operation == "validate":
        return "/v1/validate", {"workpack": args.workpack}
    if args.operation == "command-preview":
        return "/v1/command/preview", {"workpack": args.workpack}
    if args.operation == "command-request":
        return "/v1/command/request", {
            "workpack": args.workpack,
            "claim_id": args.claim_id,
            "requester": args.requester,
            "ttl_minutes": args.ttl_minutes,
            "output": args.output,
            "overwrite": args.overwrite,
        }
    if args.operation == "command-confirm":
        return "/v1/command/confirm", {
            "request": args.request,
            "approver": args.approver,
            "signature": args.signature,
            "output": args.output,
            "overwrite": args.overwrite,
        }
    raise ValueError(f"unsupported operation: {args.operation}")


def run_http_client(args: argparse.Namespace) -> int:
    base = args.server.rstrip("/")
    if args.operation == "status":
        status, result = request_json(base + "/v1/status")
    elif args.operation == "interview-roles":
        status, result = request_json(base + "/v1/interview/roles")
    elif args.operation == "shutdown":
        status, result = request_json(base + "/v1/shutdown", payload={})
    else:
        endpoint, payload = build_http_request(args)
        status, result = request_json(base + endpoint, payload=payload)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if status < 400 else 2


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser()
    parser.add_argument("--server")
    parser.add_argument("--continue", action="store_true", dest="continue_request")
    subparsers = parser.add_subparsers(dest="operation")

    subparsers.add_parser("status")
    subparsers.add_parser("roles")
    subparsers.add_parser("shutdown")
    coach = subparsers.add_parser("coach")
    coach.add_argument("--role", required=True)
    coach.add_argument("--question-id")
    coach.add_argument("--answer", required=True)
    coach.add_argument("--second-answer")
    report = subparsers.add_parser("report")
    report.add_argument("--input", type=Path)
    report.add_argument("--role")
    report.add_argument("--question-id")
    report.add_argument("--answer")
    report.add_argument("--second-answer")
    report.add_argument("--output", type=Path, required=True)
    report.add_argument("--overwrite", action="store_true")
    add_http_parsers(subparsers)

    args = parser.parse_args()
    if args.server:
        if args.operation is None:
            parser.error("operation is required")
        return run_http_client(args)
    if args.operation is None and not args.continue_request:
        parser.error("operation is required")
    return run_pipe_client(args)


if __name__ == "__main__":
    raise SystemExit(main())
