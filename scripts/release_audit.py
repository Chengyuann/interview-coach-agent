#!/usr/bin/env python3
"""Audit release contents, licenses, model provenance, and demo readiness."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = ROOT / "dist" / "interview-coach-agent-0.1.0.zip"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument(
        "--profile",
        choices=["interview", "legacy-incident"],
        default="interview",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "evidence" / "phase5" / "release-audit.json",
    )
    args = parser.parse_args()
    result = audit(args.archive.expanduser().resolve(), profile=args.profile)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "passed" else 1


def audit(archive: Path, profile: str = "interview") -> dict:
    info = json.loads((ROOT / "info.json").read_text(encoding="utf-8"))
    licenses = (
        ROOT / "references" / "third-party-licenses.md"
    ).read_text(encoding="utf-8")
    model_checks = []
    for model in info["models"]:
        files_present = all(
            any(
                path.name == required
                for path in (ROOT / "models").rglob(required)
            )
            for required in model["required_files"]
        )
        license_documented = model["model_id"] in licenses
        model_checks.append(
            {
                "model_id": model["model_id"],
                "revision": model["revision"],
                "files_present": files_present,
                "license_documented": license_documented,
            }
        )
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
    forbidden = [
        name
        for name in names
        if (
            name.startswith("models/")
            or ".venv" in name
            or name
            in {
                "scripts/transcribe_qwen3_asr.py",
                "scripts/transcribe_sensevoice.py",
                "scripts/transcribe_sherpa_zh.py",
                "requirements-phase1.txt",
            }
        )
    ]
    if profile == "interview":
        return audit_interview(archive, names, model_checks)

    demo_required = [
        ROOT / "docs" / "demo-script.md",
        ROOT / "docs" / "evidence" / "phase4" / "phase4-summary.svg",
        ROOT / "build" / "third-round-demo-workpack" / "manifest.json",
        ROOT / "build" / "third-round-demo-workpack" / "provenance.json",
        ROOT / "final_submission.mp4",
        ROOT / "work" / "demo-video-v1" / "qa" / "final-web-report.json",
        ROOT / "docs" / "limitations.md",
    ]
    checks = {
        "root_skill_count": names.count("SKILL.md") == 1,
        "archive_under_5mb": archive.stat().st_size <= 5 * 1024 * 1024,
        "forbidden_release_files_absent": not forbidden,
        "project_license_present": "LICENSE" in names,
        "third_party_licenses_present": "references/third-party-licenses.md" in names,
        "release_tests_present": {
            "tests/release/test_core_workflow.py",
            "tests/release/test_safety_gates.py",
        }.issubset(names),
        "model_provenance_complete": all(
            item["files_present"] and item["license_documented"]
            for item in model_checks
        ),
        "demo_assets_present": all(path.is_file() for path in demo_required),
    }
    return {
        "schema_version": "0.1.0",
        "profile": profile,
        "status": "passed" if all(checks.values()) else "failed",
        "archive": {
            "path": str(archive),
            "size_bytes": archive.stat().st_size,
            "sha256": sha256(archive),
            "file_count": len(names),
        },
        "checks": checks,
        "forbidden_files": forbidden,
        "models": model_checks,
        "manual_external_actions_complete": False,
    }


def audit_interview(
    archive: Path,
    names: list[str],
    model_checks: list[dict],
) -> dict:
    forbidden = [
        name
        for name in names
        if (
            name.startswith("models/")
            or ".venv" in name
            or name.startswith("docs/evidence/")
            or name.startswith("examples/incident-cache-regression/")
            or name
            in {
                "scripts/transcribe_qwen3_asr.py",
                "scripts/transcribe_sensevoice.py",
                "scripts/transcribe_sherpa_zh.py",
                "dist/local-voice-evidence-compiler-0.1.0.zip",
            }
        )
    ]
    skill = read_archive_text(archive, "SKILL.md")
    qoder_settings = read_archive_text(
        archive,
        ".qoder/settings.local.json",
    )
    checks = {
        "root_skill_count": names.count("SKILL.md") == 1,
        "archive_under_5mb": archive.stat().st_size <= 5 * 1024 * 1024,
        "forbidden_release_files_absent": not forbidden,
        "project_license_present": "LICENSE" in names,
        "third_party_licenses_present": "references/third-party-licenses.md" in names,
        "release_tests_present": {
            "tests/release/test_interview_core.py",
        }.issubset(names),
        "interview_skill_metadata": "name: interview-coach-agent" in skill,
        "browser_workbench_present": {
            "demo-web/index.html",
            "demo-web/app.js",
            "demo-web/styles.css",
            "demo-web/vendor/lucide.min.js",
            "demo-web/assets/fonts/NotoSansSC-Bold-subset.ttf",
            "demo-web/assets/fonts/NotoSansSC-Regular-subset.ttf",
            "demo-web/assets/fonts/SmileySans-Oblique.ttf",
            "demo-web/assets/visuals/interview-coach-hero.jpg",
        }.issubset(names),
        "interview_evaluation_present": "eval/interview_coach_cases.json" in names,
        "interview_audio_smoke_present": {
            "examples/interview-coach/audio-script.json",
            "scripts/generate_interview_audio.py",
            "scripts/run_interview_audio_smoke.py",
            "scripts/run_interview_http_audio_smoke.py",
        }.issubset(names),
        "interview_practice_report_present": {
            "examples/interview-coach/pm-practice-report.md",
            "vevc/interview_report.py",
        }.issubset(names)
        and "/v1/interview/report" in read_archive_text(
            archive,
            "demo-web/app.js",
        ),
        "agent_report_host_validation_present": {
            "scripts/run_qoder_bailian_stability.py",
            "scripts/run_trae_interview_stability.py",
        }.issubset(names)
        and "scripts/interview.py report" in read_archive_text(
            archive,
            "scripts/run_qoder_bailian_stability.py",
        )
        and "scripts/interview.py report" in read_archive_text(
            archive,
            "scripts/run_trae_interview_stability.py",
        ),
        "one_command_verifier_present": (
            "scripts/verify_interview_submission.py" in names
            and "localhost_report_api" in read_archive_text(
                archive,
                "scripts/verify_interview_submission.py",
            )
        ),
        "aipc_local_skill_contract_present": {
            "requirements.txt",
            "scripts/run.ps1",
            "scripts/install-env.ps1",
            "scripts/client.py",
            "scripts/server.py",
            "scripts/model_manager.py",
            "tests/test.ps1",
        }.issubset(names)
        and "scripts\\run.ps1" in skill
        and '"op": "request"' in read_archive_text(
            archive,
            "scripts/client.py",
        )
        and "run_aipc_pipe_server" in read_archive_text(
            archive,
            "scripts/server.py",
        )
        and ".partial" in read_archive_text(
            archive,
            "scripts/model_manager.py",
        ),
        "stability_reproduction_present": {
            "scripts/run_interview_service_stability.py",
            "scripts/run_qoder_bailian_stability.py",
            "scripts/run_trae_interview_stability.py",
        }.issubset(names),
        "openvino_interview_provider_present": {
            "requirements-openvino-whisper.txt",
            "scripts/download_openvino_whisper_model.py",
            "scripts/openvino_whisper_preflight.py",
            "scripts/transcribe_openvino_whisper.py",
            "vevc/interview_asr.py",
            "vevc/openvino_whisper_runtime.py",
        }.issubset(names),
        "qoder_bailian_launcher_present": {
            ".qoder/settings.local.json",
            "scripts/qoder_bailian.py",
        }.issubset(names)
        and "bailian/qwen3.8-max-pg" in qoder_settings
        and "${DASHSCOPE_API_KEY}" in qoder_settings
        and "sk-" not in qoder_settings,
        "model_provenance_complete": all(
            item["files_present"] and item["license_documented"]
            for item in model_checks
        ),
        "moonshine_license_documented": any(
            item["model_id"] == "moonshine-ai/base-zh-quantized"
            and item["license_documented"]
            for item in model_checks
        ),
    }
    return {
        "schema_version": "0.1.0",
        "profile": "interview",
        "status": "passed" if all(checks.values()) else "failed",
        "archive": {
            "path": str(archive),
            "size_bytes": archive.stat().st_size,
            "sha256": sha256(archive),
            "file_count": len(names),
        },
        "checks": checks,
        "forbidden_files": forbidden,
        "models": model_checks,
        "manual_external_actions_complete": False,
    }


def read_archive_text(archive: Path, name: str) -> str:
    with zipfile.ZipFile(archive) as package:
        return package.read(name).decode("utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
