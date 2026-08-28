#!/usr/bin/env python3
"""Run the complete offline interview Skill verification in one command."""

from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "interview-coach" / "pm-second-answer.json"
DEFAULT_OUTPUT = ROOT / "build" / "interview-submission-verification.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    build_root = ROOT / "build"
    build_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".verify-interview-",
        dir=build_root,
    ) as temporary:
        workdir = Path(temporary)
        result = verify(workdir)
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "passed" else 1


def verify(workdir: Path) -> dict[str, Any]:
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    report_path = workdir / "practice-report.md"
    archive_path = workdir / "interview-coach-agent.zip"
    audit_path = workdir / "archive-audit.json"
    checks: dict[str, dict[str, Any]] = {}

    roles = run_json(
        [sys.executable, "scripts/interview.py", "roles"],
    )
    checks["roles"] = check(
        len(roles["roles"]) == 4
        and all(item["questions"] for item in roles["roles"]),
        {"role_count": len(roles["roles"])},
    )

    coach = run_json(
        [
            sys.executable,
            "scripts/interview.py",
            "coach",
            "--input",
            str(FIXTURE),
        ],
    )
    checks["coach"] = check(
        coach["first_answer"]["total_score"] == 4.2
        and coach["second_answer"]["total_score"] == 6.7
        and coach["comparison"]["total_delta"] == 2.5
        and coach["comparison"]["verdict"] == "improved",
        {
            "first_total": coach["first_answer"]["total_score"],
            "second_total": coach["second_answer"]["total_score"],
            "total_delta": coach["comparison"]["total_delta"],
            "verdict": coach["comparison"]["verdict"],
        },
    )

    report_meta = run_json(
        [
            sys.executable,
            "scripts/interview.py",
            "report",
            "--input",
            str(FIXTURE),
            "--output",
            str(report_path),
            "--overwrite",
        ],
    )
    report_text = report_path.read_text(encoding="utf-8")
    checks["report"] = check(
        report_meta["status"] == "written"
        and "# 面试练习报告" in report_text
        and "## 第一次回答" in report_text
        and "## 第二次回答" in report_text
        and "| 4.2 / 7 | 6.7 / 7 | +2.5 | 有提升 |" in report_text
        and "## 注意事项" in report_text,
        {
            "path": "temporary/practice-report.md",
            "size_bytes": report_path.stat().st_size,
        },
    )

    service_result = verify_service(fixture)
    checks["localhost_report_api"] = check(
        service_result["ok"]
        and service_result["summary"]["total_delta"] == 2.5
        and "# 面试练习报告" in service_result["markdown"],
        {
            "filename": service_result["filename"],
            "total_delta": service_result["summary"]["total_delta"],
        },
    )

    package_validation = run_json(
        [sys.executable, "scripts/validate_package.py", "."],
    )
    checks["package_validation"] = check(
        package_validation["ok"]
        and package_validation["profile"] == "interview"
        and package_validation["under_5mb"],
        {
            "included_file_count": package_validation["included_file_count"],
            "source_size_bytes": package_validation["source_size_bytes"],
        },
    )

    build_result = run_json(
        [
            sys.executable,
            "scripts/build_package.py",
            "--output",
            str(archive_path),
        ],
    )
    archive_checks = inspect_archive(archive_path)
    checks["skill_archive"] = check(
        build_result["ok"]
        and build_result["under_5mb"]
        and all(archive_checks.values()),
        {
            "size_bytes": build_result["size_bytes"],
            "sha256": build_result["sha256"],
            **archive_checks,
        },
    )

    audit_result = run_json(
        [
            sys.executable,
            "scripts/release_audit.py",
            "--archive",
            str(archive_path),
            "--output",
            str(audit_path),
        ],
    )
    checks["release_audit"] = check(
        audit_result["status"] == "passed"
        and audit_result["checks"]["interview_practice_report_present"]
        and audit_result["checks"]["agent_report_host_validation_present"]
        and audit_result["checks"]["one_command_verifier_present"]
        and audit_result["checks"]["aipc_local_skill_contract_present"],
        {
            "archive_file_count": audit_result["archive"]["file_count"],
            "archive_sha256": audit_result["archive"]["sha256"],
        },
    )

    passed = sum(item["status"] == "passed" for item in checks.values())
    return {
        "schema_version": "0.1.0",
        "product": "interview-coach-agent",
        "status": "passed" if passed == len(checks) else "failed",
        "offline": True,
        "fixture": FIXTURE.relative_to(ROOT).as_posix(),
        "check_count": len(checks),
        "passed_checks": passed,
        "checks": checks,
    }


def verify_service(fixture: dict[str, Any]) -> dict[str, Any]:
    port = free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "scripts/interview_server.py",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        wait_for_status(port)
        return post_json(
            f"http://127.0.0.1:{port}/v1/interview/report",
            fixture,
        )
    finally:
        try:
            post_json(f"http://127.0.0.1:{port}/v1/shutdown", {})
        except Exception:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def inspect_archive(path: Path) -> dict[str, bool]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    return {
        "one_root_skill": names.count("SKILL.md") == 1,
        "report_module_present": "vevc/interview_report.py" in names,
        "report_sample_present": (
            "examples/interview-coach/pm-practice-report.md" in names
        ),
        "verifier_present": "scripts/verify_interview_submission.py" in names,
        "release_test_present": "tests/release/test_interview_core.py" in names,
        "aipc_entry_present": {
            "requirements.txt",
            "scripts/run.ps1",
            "scripts/install-env.ps1",
            "scripts/client.py",
            "scripts/server.py",
            "scripts/model_manager.py",
            "tests/test.ps1",
        }.issubset(names),
        "models_excluded": not any(name.startswith("models/") for name in names),
        "virtualenvs_excluded": not any(".venv" in name for name in names),
    }


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError(f"command did not return a JSON object: {command}")
    return payload


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_status(port: int) -> None:
    deadline = time.time() + 10
    url = f"http://127.0.0.1:{port}/v1/status"
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                payload = json.loads(response.read().decode("utf-8"))
            if payload.get("ok"):
                return
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            time.sleep(0.1)
    raise RuntimeError("localhost interview service did not become ready")


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError(f"endpoint did not return a JSON object: {url}")
    return result


def check(ok: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "passed" if ok else "failed",
        "evidence": evidence,
    }


if __name__ == "__main__":
    raise SystemExit(main())
