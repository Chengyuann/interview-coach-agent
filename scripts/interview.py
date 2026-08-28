#!/usr/bin/env python3
"""Standalone entry point for AI 面试陪练官."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vevc.interview_coach import (  # noqa: E402
    CoachRequest,
    coach_interview,
    list_roles,
    load_request,
    write_coach_result,
)
from vevc.interview_report import write_interview_report  # noqa: E402


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Practice interview answers with local, structured coaching."
    )
    subparsers = parser.add_subparsers(dest="operation", required=True)

    subparsers.add_parser("roles")

    coach_parser = subparsers.add_parser("coach")
    coach_parser.add_argument("--input", type=Path)
    coach_parser.add_argument("--role")
    coach_parser.add_argument("--question-id")
    coach_parser.add_argument("--answer")
    coach_parser.add_argument("--second-answer")
    coach_parser.add_argument("--output", type=Path)
    coach_parser.add_argument("--overwrite", action="store_true")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--input", type=Path)
    report_parser.add_argument("--role")
    report_parser.add_argument("--question-id")
    report_parser.add_argument("--answer")
    report_parser.add_argument("--second-answer")
    report_parser.add_argument("--output", type=Path, required=True)
    report_parser.add_argument("--overwrite", action="store_true")

    service_parser = subparsers.add_parser("service")
    service_parser.add_argument("--host", default="127.0.0.1")
    service_parser.add_argument("--port", type=int, default=8876)
    service_parser.add_argument(
        "--preload",
        choices=["none", "en", "zh"],
        default="none",
    )
    service_parser.add_argument(
        "--asr-provider",
        choices=["moonshine", "openvino"],
        default="moonshine",
    )
    service_parser.add_argument("--openvino-model-dir", type=Path)
    service_parser.add_argument("--openvino-device", default="CPU")
    service_parser.add_argument("--allow-remote", action="store_true")

    transcribe_parser = subparsers.add_parser("transcribe")
    transcribe_parser.add_argument("--audio", type=Path, required=True)
    transcribe_parser.add_argument("--language", choices=["en", "zh"], default="zh")
    transcribe_parser.add_argument("--output", type=Path, required=True)
    transcribe_parser.add_argument("--evidence", type=Path, required=True)
    transcribe_parser.add_argument(
        "--asr-provider",
        choices=["moonshine", "openvino"],
        default="moonshine",
    )
    transcribe_parser.add_argument("--openvino-model-dir", type=Path)
    transcribe_parser.add_argument("--openvino-device", default="CPU")

    subparsers.add_parser("evaluate")

    args = parser.parse_args(argv)

    try:
        if args.operation == "roles":
            print(json.dumps(list_roles(), ensure_ascii=False, indent=2))
            return 0
        if args.operation == "coach":
            result = run_coach(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.operation == "report":
            result = run_report(args)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.operation == "service":
            return run_service(args)
        if args.operation == "transcribe":
            return run_transcribe(args)
        if args.operation == "evaluate":
            from evaluate_interview_coach import evaluate

            result = evaluate(ROOT / "eval" / "interview_coach_cases.json")
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if result["status"] == "passed" else 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 1


def run_coach(args: argparse.Namespace) -> dict:
    request = request_from_args(args)
    if args.output:
        return write_coach_result(
            request=request,
            output=args.output,
            output_root=ROOT / "build",
            overwrite=args.overwrite,
        )
    return coach_interview(request)


def run_report(args: argparse.Namespace) -> dict:
    return write_interview_report(
        request=request_from_args(args),
        output=args.output,
        output_root=ROOT / "build",
        overwrite=args.overwrite,
    )


def request_from_args(args: argparse.Namespace) -> CoachRequest:
    if args.input:
        return load_request(args.input.expanduser().resolve())
    if not args.role or not args.answer:
        raise ValueError("--role and --answer are required without --input")
    return CoachRequest(
        role=args.role,
        question_id=args.question_id,
        answer=args.answer,
        second_answer=args.second_answer,
    )


def run_service(args: argparse.Namespace) -> int:
    command = [
        sys.executable,
        str(ROOT / "scripts" / "interview_server.py"),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--preload",
        args.preload,
        "--asr-provider",
        args.asr_provider,
        "--openvino-device",
        args.openvino_device,
    ]
    if args.openvino_model_dir:
        command.extend(
            ["--openvino-model-dir", str(args.openvino_model_dir)]
        )
    if args.allow_remote:
        command.append("--allow-remote")
    return subprocess.run(command, cwd=ROOT).returncode


def run_transcribe(args: argparse.Namespace) -> int:
    from vevc.interview_asr import InterviewAsrRuntime

    runtime = InterviewAsrRuntime(
        root=ROOT,
        provider=args.asr_provider,
        openvino_model_dir=args.openvino_model_dir,
        openvino_device=args.openvino_device,
    )
    try:
        evidence = runtime.transcribe_file(
            audio_path=args.audio,
            language=args.language,
            output_path=args.output,
            evidence_path=args.evidence,
        )
    finally:
        runtime.close()
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
