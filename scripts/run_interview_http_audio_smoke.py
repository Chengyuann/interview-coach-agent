#!/usr/bin/env python3
"""Verify the localhost audio and coaching endpoints end to end."""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_interview_audio_smoke import reference_quality  # noqa: E402
from vevc.contracts import write_json  # noqa: E402

DEFAULT_MANIFEST = ROOT / "build" / "interview-audio-fixture" / "manifest.json"
DEFAULT_OUTPUT = ROOT / "build" / "interview-http-audio-smoke.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--port", type=int, default=18883)
    args = parser.parse_args()

    fixture = json.loads(
        args.manifest.expanduser().resolve().read_text(encoding="utf-8")
    )
    base = f"http://127.0.0.1:{args.port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "scripts/interview_server.py",
            "--port",
            str(args.port),
            "--preload",
            fixture["language"],
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        initial_status = wait_status(base)
        audio = (ROOT / fixture["audio"]).read_bytes()
        transcript = post_json(
            base + "/v1/interview/transcribe",
            {
                "audio_base64": base64.b64encode(audio).decode("ascii"),
                "language": fixture["language"],
            },
        )
        coach = post_json(
            base + "/v1/interview/coach",
            {
                "role": fixture["role"],
                "question_id": fixture["question_id"],
                "answer": transcript["text"],
            },
        )
        final_status = get_json(base + "/v1/status")
    finally:
        try:
            post_json(base + "/v1/shutdown", {})
        except Exception:
            pass
        process.wait(timeout=20)

    quality = reference_quality(
        reference=fixture["script_text"],
        transcript=transcript["text"],
    )
    issue_codes = [
        item["code"]
        for item in coach["result"]["first_answer"]["issues"]
    ]
    if quality["review_required"]:
        issue_codes.insert(0, "ASR_REVIEW_REQUIRED")
    result = {
        "schema_version": "0.1.0",
        "status": "passed",
        "service": initial_status["service"],
        "capabilities": initial_status["capabilities"],
        "loaded_asr_languages": initial_status["loaded_asr_languages"],
        "transcript_text": transcript["text"],
        "duration_ms": transcript["duration_ms"],
        "inference_seconds": transcript["inference_seconds"],
        "real_time_factor": transcript["real_time_factor"],
        "total_score": coach["result"]["first_answer"]["total_score"],
        "issue_codes": issue_codes,
        "asr_quality": quality,
        "request_count": final_status["request_count"],
        "error_count": final_status["error_count"],
    }
    write_json(args.output.expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def wait_status(base: str) -> dict:
    for _ in range(200):
        try:
            return get_json(base + "/v1/status")
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("interview service did not become ready")


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8")) from exc


if __name__ == "__main__":
    raise SystemExit(main())
