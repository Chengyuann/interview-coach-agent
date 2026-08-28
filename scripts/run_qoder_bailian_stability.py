#!/usr/bin/env python3
"""Run repeated Qoder Skill invocations through Alibaba Cloud Model Studio."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = (
    Path(os.environ["QODER_BAILIAN_CREDENTIALS"]).expanduser()
    if os.environ.get("QODER_BAILIAN_CREDENTIALS")
    else None
)
DEFAULT_OUTPUT = (
    ROOT
    / "docs"
    / "evidence"
    / "qoder-interview-coach"
    / "qoder-bailian-stability-v1.1.30.json"
)
MODEL_KEY = "bailian/qwen3.8-max-pg"
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
    return f"""Use the interview-coach-agent skill from this repository.
Do not edit source files. The only permitted write is the report artifact below.
Run these exact local commands:
1. python3 scripts/interview.py roles
2. python3 scripts/interview.py coach --input examples/interview-coach/pm-second-answer.json
3. python3 scripts/interview.py report --input examples/interview-coach/pm-second-answer.json --output {report_path} --overwrite
Then report the first answer total, second answer total, total delta, verdict,
the first follow-up question, and the exact report path. Keep the response concise."""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--credentials", type=Path, default=DEFAULT_CREDENTIALS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    if args.runs < 1:
        raise SystemExit("--runs must be at least 1")
    if args.credentials is None:
        raise SystemExit(
            "set QODER_BAILIAN_CREDENTIALS or pass --credentials"
        )

    values = read_credentials(args.credentials.expanduser().resolve())
    credential = values.get("apiKey", "").strip()
    if not credential:
        raise SystemExit("CSV does not contain a non-empty apiKey field")
    qodercli = shutil.which("qodercli")
    if not qodercli:
        raise SystemExit("qodercli was not found on PATH")

    environment = os.environ.copy()
    environment["DASHSCOPE_API_KEY"] = credential
    if values.get("openAiCompatible"):
        environment["DASHSCOPE_BASE_URL"] = values["openAiCompatible"].strip()
    if values.get("workspaceId"):
        environment["BAILIAN_WORKSPACE_ID"] = values["workspaceId"].strip()

    runs = []
    for index in range(1, args.runs + 1):
        report_path = REPORT_ROOT / f"qoder-run-{index:02d}.md"
        prepare_report_path(report_path)
        report_relative = report_path.relative_to(ROOT).as_posix()
        source_sha256_before = source_fingerprint()
        started = time.perf_counter()
        completed = subprocess.run(
            [
                qodercli,
                "-p",
                "--cwd",
                str(ROOT),
                "--permission-mode",
                "bypass_permissions",
                "--no-session-persistence",
                "--max-output-tokens",
                "1800",
                "-m",
                MODEL_KEY,
                build_prompt(report_relative),
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            timeout=args.timeout,
        )
        stdout = redact(completed.stdout, credential)
        stderr = redact(completed.stderr, credential)
        report_artifact = inspect_report(report_path)
        source_sha256_after = source_fingerprint()
        checks = {
            "exit_zero": completed.returncode == 0,
            "first_total_4_2": contains_score(stdout, "4.2"),
            "second_total_6_7": contains_score(stdout, "6.7"),
            "delta_2_5": contains_score(stdout, "2.5"),
            "verdict_improved": "improved" in stdout.lower(),
            "followup_present": "具体提升了多少" in stdout,
            "report_path_mentioned": report_relative in stdout,
            "source_tree_unchanged": source_sha256_before == source_sha256_after,
            **report_artifact["checks"],
        }
        runs.append(
            {
                "run": index,
                "status": "passed" if all(checks.values()) else "failed",
                "exit_status": completed.returncode,
                "elapsed_seconds": round(time.perf_counter() - started, 6),
                "checks": checks,
                "report_artifact": report_artifact,
                "source_tree": {
                    "sha256_before": source_sha256_before,
                    "sha256_after": source_sha256_after,
                },
                "stdout_preview": stdout[:2400],
                "stderr_preview": stderr[:800],
            }
        )

    passed = sum(item["status"] == "passed" for item in runs)
    document = {
        "schema_version": "0.1.0",
        "status": "passed" if passed == args.runs else "failed",
        "qodercli_version": qoder_version(qodercli),
        "provider": "Alibaba Cloud Model Studio - China",
        "model_key": MODEL_KEY,
        "skill": "interview-coach-agent",
        "credential_source": "external CSV (not bundled)",
        "secret_persisted": False,
        "session_persistence": False,
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


def read_credentials(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"credential CSV was not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row[0].strip(): row[1].strip() if len(row) > 1 else ""
            for row in csv.reader(handle)
            if row
        }


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


def redact(text: str, credential: str) -> str:
    redacted = text.replace(credential, "<redacted>")
    return re.sub(r"sk-[A-Za-z0-9_-]+", "sk-<redacted>", redacted)


def qoder_version(qodercli: str) -> str:
    completed = subprocess.run(
        [qodercli, "--version"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    return completed.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
