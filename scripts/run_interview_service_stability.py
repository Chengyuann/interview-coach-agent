#!/usr/bin/env python3
"""Exercise the localhost coach endpoint repeatedly across all frozen roles."""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASES = ROOT / "eval" / "interview_coach_cases.json"
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "evidence"
    / "interview-service"
    / "stability-40.json"
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--port", type=int, default=18884)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.rounds < 1:
        raise SystemExit("--rounds must be at least 1")

    cases = json.loads(
        args.cases.expanduser().resolve().read_text(encoding="utf-8")
    )["cases"]
    base = f"http://127.0.0.1:{args.port}"
    process = subprocess.Popen(
        [
            sys.executable,
            "scripts/interview_server.py",
            "--port",
            str(args.port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    records = []
    try:
        wait_status(base)
        for round_number in range(1, args.rounds + 1):
            for case in cases:
                started = time.perf_counter()
                response = post_json(
                    base + "/v1/interview/coach",
                    {
                        "role": case["role"],
                        "question_id": case["question_id"],
                        "answer": case["first_answer"],
                        "second_answer": case["second_answer"],
                    },
                )
                elapsed = time.perf_counter() - started
                result = response["result"]
                checks = {
                    "ok": response["ok"] is True,
                    "verdict_improved": (
                        result["comparison"]["verdict"] == "improved"
                    ),
                    "minimum_delta": (
                        result["comparison"]["total_delta"]
                        >= case["minimum_total_delta"]
                    ),
                    "no_regressed_dimensions": (
                        result["comparison"]["regressed_dimensions"] == []
                    ),
                }
                records.append(
                    {
                        "round": round_number,
                        "case_id": case["case_id"],
                        "role": case["role"],
                        "status": (
                            "passed" if all(checks.values()) else "failed"
                        ),
                        "latency_seconds": round(elapsed, 6),
                        "first_total": result["first_answer"]["total_score"],
                        "second_total": result["second_answer"]["total_score"],
                        "total_delta": result["comparison"]["total_delta"],
                        "checks": checks,
                    }
                )
        status = get_json(base + "/v1/status")
    finally:
        try:
            post_json(base + "/v1/shutdown", {})
        except Exception:
            pass
        process.wait(timeout=20)

    latencies = [item["latency_seconds"] for item in records]
    passed = sum(item["status"] == "passed" for item in records)
    roles = {case["role"] for case in cases}
    questions = {case["question_id"] for case in cases}
    document = {
        "schema_version": "0.1.0",
        "status": "passed" if passed == len(records) else "failed",
        "service": "interview-coach-agent",
        "endpoint": "/v1/interview/coach",
        "rounds": args.rounds,
        "scenario_count": len(cases),
        "role_count": len(roles),
        "question_count": len(questions),
        "request_count": len(records),
        "passed_requests": passed,
        "success_rate": round(passed / len(records), 6),
        "error_count": status["error_count"],
        "server_request_count": status["request_count"],
        "latency_seconds": {
            "min": min(latencies),
            "median": round(statistics.median(latencies), 6),
            "mean": round(statistics.fmean(latencies), 6),
            "max": max(latencies),
        },
        "records": records,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document, ensure_ascii=False, indent=2))
    return 0 if document["status"] == "passed" else 1


def wait_status(base: str) -> dict:
    for _ in range(200):
        try:
            return get_json(base + "/v1/status")
        except Exception:
            time.sleep(0.05)
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
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(exc.read().decode("utf-8")) from exc


if __name__ == "__main__":
    raise SystemExit(main())
