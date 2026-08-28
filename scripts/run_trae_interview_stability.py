#!/usr/bin/env python3
"""Run repeated read-only TRAE CLI invocations of the interview Skill."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "evidence"
    / "trae-interview-coach"
    / "trae-stability-v0.120.47.json"
)
REPORT_ROOT = ROOT / "build" / "agent-report-evidence"
SOURCE_PATHS = (
    ".qoder",
    ".trae",
    "README.md",
    "SKILL.md",
    "demo-web",
    "eval",
    "examples",
    "info.json",
    "meta.json",
    "pyproject.toml",
    "references",
    "requirements-minimal.txt",
    "requirements-moonshine.txt",
    "requirements-openvino-whisper.txt",
    "schemas",
    "scripts",
    "tests",
    "vevc",
)


def build_prompt(report_path: str) -> str:
    return f"""Use the interview-coach-agent skill in this repository.
Do not edit source files. The only permitted write is the report artifact below.
Run these commands as three separate Bash tool calls:
python3 scripts/interview.py roles
python3 scripts/interview.py coach --input examples/interview-coach/pm-second-answer.json
python3 scripts/interview.py report --input examples/interview-coach/pm-second-answer.json --output {report_path} --overwrite
Report first total, second total, total delta, verdict, and the exact report path.
Keep concise."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    traecli = shutil.which("traecli")
    if not traecli:
        raise SystemExit("traecli was not found on PATH")

    runs = []
    for index in range(1, args.runs + 1):
        report_path = REPORT_ROOT / f"trae-run-{index:02d}.md"
        prepare_report_path(report_path)
        report_relative = report_path.relative_to(ROOT).as_posix()
        source_sha256_before = source_fingerprint()
        session_id = str(uuid.uuid4())
        started = time.perf_counter()
        completed = subprocess.run(
            [
                traecli,
                "-p",
                "--output-format",
                "json",
                "--permission-mode",
                "bypass_permissions",
                "--session-id",
                session_id,
                "--query-timeout",
                f"{args.timeout}s",
                "--bash-tool-timeout",
                "120s",
                "--disallowed-tool",
                "Edit",
                "--disallowed-tool",
                "Write",
                "--disallowed-tool",
                "Replace",
                build_prompt(report_relative),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=args.timeout + 30,
        )
        payload = parse_payload(completed.stdout)
        final_text = final_message(payload)
        transcript = json.dumps(payload.get("agent_states", []), ensure_ascii=False)
        stats = payload.get("stats", {})
        tool_calls = stats.get("tool_calls", {})
        bash_calls = tool_calls.get("Bash", {})
        skill_calls = tool_calls.get("Skill", {})
        report_artifact = inspect_report(report_path)
        source_sha256_after = source_fingerprint()
        checks = {
            "exit_zero": completed.returncode == 0,
            "skill_invoked": '"name": "Skill"' in transcript
            and "interview-coach-agent" in transcript
            and skill_calls.get("count", 0) >= 1
            and skill_calls.get("error_count", 0) == 0,
            "three_bash_calls_succeeded": bash_calls.get("count", 0) >= 3
            and bash_calls.get("error_count", 0) == 0,
            "first_total_4_2": contains_score(final_text, "4.2"),
            "second_total_6_7": contains_score(final_text, "6.7"),
            "delta_2_5": contains_score(final_text, "2.5"),
            "verdict_improved": "improved" in final_text.lower(),
            "report_path_mentioned": report_relative in final_text,
            "no_source_file_edits": stats.get("lines_added") == 0
            and stats.get("lines_removed") == 0,
            "source_tree_unchanged": source_sha256_before == source_sha256_after,
            **report_artifact["checks"],
        }
        runs.append(
            {
                "run": index,
                "session_id": session_id,
                "status": "passed" if all(checks.values()) else "failed",
                "exit_status": completed.returncode,
                "elapsed_seconds": round(time.perf_counter() - started, 6),
                "checks": checks,
                "report_artifact": report_artifact,
                "source_tree": {
                    "sha256_before": source_sha256_before,
                    "sha256_after": source_sha256_after,
                },
                "final_message": final_text[:1200],
                "tool_calls": tool_calls,
                "stderr_preview": completed.stderr[:800],
            }
        )

    passed = sum(item["status"] == "passed" for item in runs)
    document = {
        "schema_version": "0.1.0",
        "status": "passed" if passed == args.runs else "failed",
        "traecli_version": trae_version(traecli),
        "skill": "interview-coach-agent",
        "session_reuse": False,
        "workflow": ["roles", "coach", "report"],
        "allowed_write_root": REPORT_ROOT.relative_to(ROOT).as_posix(),
        "run_count": args.runs,
        "passed_runs": passed,
        "success_rate": round(passed / args.runs, 6),
        "runs": runs,
    }
    output = args.output.expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(document, ensure_ascii=False, indent=2))
    return 0 if document["status"] == "passed" else 1


def parse_payload(stdout: str) -> dict:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("traecli did not return valid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("traecli JSON output is not an object")
    return payload


def final_message(payload: dict) -> str:
    message = payload.get("message")
    if not isinstance(message, dict):
        return ""
    return str(message.get("content") or "")


def contains_score(text: str, score: str) -> bool:
    return bool(re.search(rf"(?<!\d){re.escape(score)}(?!\d)", text))


def prepare_report_path(path: Path) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()


def inspect_report(path: Path) -> dict[str, object]:
    path = path.resolve()
    relative = path.relative_to(ROOT).as_posix()
    if not path.is_file():
        return {
            "path": relative,
            "exists": False,
            "size_bytes": 0,
            "sha256": None,
            "checks": {
                "report_file_created": False,
                "report_title_present": False,
                "report_two_attempts_present": False,
                "report_scores_present": False,
                "report_notes_present": False,
            },
        }
    text = path.read_text(encoding="utf-8")
    return {
        "path": relative,
        "exists": True,
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
        "checks": {
            "report_file_created": True,
            "report_title_present": "# 面试练习报告" in text,
            "report_two_attempts_present": (
                "## 第一次回答" in text and "## 第二次回答" in text
            ),
            "report_scores_present": (
                "| 4.2 / 7 | 6.7 / 7 | +2.5 | 有提升 |" in text
            ),
            "report_notes_present": "## 注意事项" in text,
        },
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_fingerprint() -> str:
    digest = hashlib.sha256()
    files = []
    for relative in SOURCE_PATHS:
        path = ROOT / relative
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                item
                for item in path.rglob("*")
                if item.is_file()
                and "__pycache__" not in item.parts
                and ".pytest_cache" not in item.parts
            )
    for path in sorted(files):
        relative = path.relative_to(ROOT).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def trae_version(traecli: str) -> str:
    completed = subprocess.run(
        [traecli, "--version"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    match = re.search(r"coco version ([^\s]+)", completed.stdout)
    return match.group(1) if match else completed.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
