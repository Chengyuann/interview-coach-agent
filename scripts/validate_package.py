#!/usr/bin/env python3
"""Validate Agent Skills and ModelScope packaging constraints."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import yaml


NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FORBIDDEN_PARTS = {
    ".DS_Store",
    ".agent",
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".qoder",
    ".trae",
    ".agents",
    ".playwright-cli",
    "build",
    "dist",
    "models",
    "output",
    "outputs",
    "work",
}
FORBIDDEN_PREFIXES = (
    ("demo-web", "assets"),
    ("demo-web", "qa-enhanced"),
    ("docs", "evidence"),
    ("docs", "video-assets", "audio"),
)
RELEASE_EXCLUDED_FILES = {
    "docs/submission-assets/manifest.json",
    "final_submission.mp4",
    "qodercli-voice-evidence-demo.mp4",
    "requirements-demo.txt",
    "requirements-phase1.txt",
    "requirements-sensevoice.txt",
    "requirements-sherpa-experimental.txt",
    "docs/phase0-verification.md",
    "docs/phase1-backlog.md",
    "docs/phase1-verification.md",
    "docs/phase2-backlog.md",
    "docs/phase2-verification.md",
    "docs/phase3-verification.md",
    "docs/phase4-verification.md",
    "scripts/benchmark_qwen3_asr.py",
    "scripts/compare_asr_outputs.py",
    "scripts/export_qwen3_aligner.py",
    "scripts/export_qwen3_asr.py",
    "scripts/install_phase1_env.py",
    "scripts/install_sensevoice_env.py",
    "scripts/openvino_compile_probe.py",
    "scripts/phase1_import_smoke.py",
    "scripts/phase1_preflight.py",
    "scripts/prepare_sensevoice_models.py",
    "scripts/prepare_sherpa_zh.py",
    "scripts/qwen3_aligner_smoke.py",
    "scripts/qwen3_asr_smoke.py",
    "scripts/smart_turn_smoke.py",
    "scripts/transcribe_incident_fixture.py",
    "scripts/transcribe_incident_fixture_sensevoice.py",
    "scripts/transcribe_qwen3_asr.py",
    "scripts/transcribe_sensevoice.py",
    "scripts/transcribe_sherpa_zh.py",
    "scripts/run_ai_expert_eval.py",
    "scripts/score_ai_expert_eval.py",
    "demo-web/mobile-commands.png",
    "demo-web/mobile-overview.png",
    "demo-web/overview.png",
    "demo-web/test-audit.png",
    "demo-web/test-commands.png",
    "demo-web/test-decisions.png",
    "demo-web/test-evidence.png",
    "demo-web/test-overview.png",
    "demo-web/test-transcript.png",
}
SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|password)\s*[:=]\s*\S+"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)
INTERVIEW_RELEASE_FILES = {
    ".qoder/settings.local.json",
    "LICENSE",
    "README.md",
    "SKILL.md",
    "info.json",
    "meta.json",
    "pyproject.toml",
    "requirements.txt",
    "requirements-minimal.txt",
    "requirements-moonshine.txt",
    "requirements-openvino-whisper.txt",
    "demo-web/README.md",
    "demo-web/index.html",
    "demo-web/styles.css",
    "demo-web/app.js",
    "demo-web/vendor/lucide.min.js",
    "demo-web/assets/fonts/NotoSansSC-Bold-subset.ttf",
    "demo-web/assets/fonts/NotoSansSC-OFL.txt",
    "demo-web/assets/fonts/NotoSansSC-Regular-subset.ttf",
    "demo-web/assets/fonts/SmileySans-LICENSE.txt",
    "demo-web/assets/fonts/SmileySans-Oblique.ttf",
    "demo-web/assets/visuals/interview-coach-hero.jpg",
    "eval/interview_coach_cases.json",
    "examples/interview-coach/audio-script.json",
    "examples/interview-coach/pm-first-answer.json",
    "examples/interview-coach/pm-practice-report.md",
    "examples/interview-coach/pm-second-answer.json",
    "references/third-party-licenses.md",
    "references/aipc-local-skill-standard.md",
    "schemas/interview_coach_result.schema.json",
    "schemas/transcript.schema.json",
    "scripts/download_openvino_whisper_model.py",
    "scripts/evaluate_interview_coach.py",
    "scripts/generate_interview_audio.py",
    "scripts/install_moonshine_env.py",
    "scripts/interview.py",
    "scripts/interview_server.py",
    "scripts/client.py",
    "scripts/install-env.ps1",
    "scripts/model_manager.py",
    "scripts/openvino_whisper_preflight.py",
    "scripts/prepare_moonshine_models.py",
    "scripts/qoder_bailian.py",
    "scripts/run_interview_audio_smoke.py",
    "scripts/run_interview_http_audio_smoke.py",
    "scripts/run_interview_service_stability.py",
    "scripts/run.ps1",
    "scripts/run_qoder_bailian_stability.py",
    "scripts/server.py",
    "scripts/run_trae_interview_stability.py",
    "scripts/transcribe_openvino_whisper.py",
    "scripts/validate_package.py",
    "scripts/verify_interview_submission.py",
    "tests/release/test_interview_core.py",
    "tests/test.ps1",
    "vevc/__init__.py",
    "vevc/contracts.py",
    "vevc/interview_asr.py",
    "vevc/interview_coach.py",
    "vevc/interview_report.py",
    "vevc/moonshine_runtime.py",
    "vevc/openvino_whisper_runtime.py",
    "vevc/safety.py",
}
INTERVIEW_RELEASE_FORBIDDEN_SUBSTRINGS = (
    "incident-cache-regression",
    "Voice Evidence Compiler",
    "local-voice-evidence-compiler",
)


def validate_package(root: Path, profile: str = "interview") -> dict:
    root = root.expanduser().resolve()
    errors = []
    included_files = list(iter_release_files(root, profile=profile))
    if profile not in {"interview", "legacy-incident"}:
        errors.append(f"unknown release profile: {profile}")
    skill_files = [path for path in included_files if path.name == "SKILL.md"]
    root_skill = root / "SKILL.md"
    if skill_files != [root_skill]:
        errors.append(
            "package must contain exactly one included SKILL.md at the package root"
        )
    metadata = {}
    body = ""
    if root_skill.is_file():
        try:
            metadata, body = _parse_frontmatter(root_skill.read_text(encoding="utf-8"))
        except ValueError as exc:
            errors.append(str(exc))
    else:
        errors.append("missing root SKILL.md")

    name = metadata.get("name")
    description = metadata.get("description")
    version = metadata.get("version")
    if not isinstance(name, str) or not NAME_PATTERN.fullmatch(name):
        errors.append("frontmatter name must be lowercase kebab-case")
    else:
        project_name = _project_name(root)
        if project_name and project_name != name:
            errors.append("frontmatter name must match pyproject project.name")
    if not isinstance(description, str) or not (1 <= len(description) <= 1024):
        errors.append("description must contain 1-1024 characters")
    if not isinstance(version, str) or not version:
        errors.append("frontmatter version is required")
    if len(root_skill.read_text(encoding="utf-8").splitlines()) >= 500:
        errors.append("SKILL.md must be fewer than 500 lines")
    for reference in re.findall(r"`(references/[^`]+\.md)`", body):
        if not (root / reference).is_file():
            errors.append(f"missing referenced file: {reference}")

    source_bytes = 0
    for path in included_files:
        source_bytes += path.stat().st_size
        if path.suffix.lower() in {".md", ".py", ".json", ".txt", ".toml", ".ps1"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            for pattern in SECRET_PATTERNS:
                if pattern.search(text):
                    errors.append(f"possible secret or email in {path.relative_to(root)}")
    if profile == "interview":
        included_names = {path.relative_to(root).as_posix() for path in included_files}
        missing = INTERVIEW_RELEASE_FILES - included_names
        if missing:
            errors.append(
                "interview release file allowlist is missing expected files: "
                + ", ".join(sorted(missing))
            )
        unexpected = included_names - INTERVIEW_RELEASE_FILES
        if unexpected:
            errors.append(
                "interview release file allowlist contains unexpected files: "
                + ", ".join(sorted(unexpected))
            )
        errors.extend(validate_aipc_local_skill(root, included_names, metadata, body))
        for path in included_files:
            if path.suffix.lower() not in {".md", ".py", ".json", ".txt", ".toml"}:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            relative = path.relative_to(root).as_posix()
            if relative in {
                "references/third-party-licenses.md",
                "scripts/validate_package.py",
            }:
                continue
            for forbidden in INTERVIEW_RELEASE_FORBIDDEN_SUBSTRINGS:
                if forbidden in text:
                    errors.append(
                        f"interview release text references legacy product in {relative}: {forbidden}"
                    )

    return {
        "ok": not errors,
        "profile": profile,
        "name": name,
        "version": version,
        "description_chars": len(description) if isinstance(description, str) else 0,
        "skill_lines": len(root_skill.read_text(encoding="utf-8").splitlines())
        if root_skill.is_file()
        else 0,
        "included_file_count": len(included_files),
        "source_size_bytes": source_bytes,
        "under_5mb": source_bytes <= 5 * 1024 * 1024,
        "errors": errors,
    }


def validate_aipc_local_skill(
    root: Path,
    included_names: set[str],
    metadata: dict,
    skill_body: str,
) -> list[str]:
    errors: list[str] = []
    required = {
        "requirements.txt",
        "scripts/run.ps1",
        "scripts/install-env.ps1",
        "scripts/client.py",
        "scripts/server.py",
        "scripts/model_manager.py",
        "tests/test.ps1",
    }
    missing = required - included_names
    if missing:
        errors.append(
            "AIPC local Skill files are missing: " + ", ".join(sorted(missing))
        )

    description = str(metadata.get("description", "")).lower()
    for token in ("local", "offline", "aipc", "本地", "离线"):
        if token not in description:
            errors.append(f"SKILL.md description is missing AIPC routing token: {token}")

    run_path = root / "scripts" / "run.ps1"
    if run_path.is_file():
        run_text = run_path.read_text(encoding="utf-8")
        first_nonempty = next(
            (line.strip() for line in run_text.splitlines() if line.strip()),
            "",
        )
        if first_nonempty != "$ErrorActionPreference = 'Stop'":
            errors.append("scripts/run.ps1 must start with ErrorActionPreference Stop")
        for token in ("platform.exe", "install-env.ps1", "client.py"):
            if token not in run_text:
                errors.append(f"scripts/run.ps1 is missing required flow: {token}")

    client_text = read_if_file(root / "scripts" / "client.py")
    server_text = read_if_file(root / "scripts" / "server.py")
    model_text = read_if_file(root / "scripts" / "model_manager.py")
    install_text = read_if_file(root / "scripts" / "install-env.ps1")
    requirements = read_if_file(root / "requirements.txt")
    test_text = read_if_file(root / "tests" / "test.ps1")
    checks = {
        "named-pipe client": "multiprocessing.connection import Client" in client_text,
        "resume flag": "--continue" in client_text and "save_pending_request" in client_text,
        "standard pipe operations": all(
            token in server_text for token in ('"status"', '"request"', '"shutdown"')
        ),
        "server state machine": all(
            token in server_text
            for token in ('"starting"', '"downloading"', '"loading"', '"running"', '"error"')
        ),
        "atomic partial model directory": ".partial" in model_text and ".replace(" in model_text,
        "requirements hash cache": "Get-FileHash" in install_text,
        "OpenVINO dependency": "openvino-genai" in requirements,
        "model downloader dependency": "modelscope" in requirements,
        "PowerShell E2E test": "scripts\\run.ps1" in test_text,
        "SKILL only entry guidance": "scripts\\run.ps1" in skill_body,
        "no cloud fallback": "Do not fall back to a cloud service" in skill_body,
    }
    for label, passed in checks.items():
        if not passed:
            errors.append(f"AIPC local Skill check failed: {label}")
    return errors


def read_if_file(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML frontmatter")
    try:
        frontmatter, body = text[4:].split("\n---\n", 1)
    except ValueError as exc:
        raise ValueError("SKILL.md frontmatter is not closed") from exc
    metadata = yaml.safe_load(frontmatter)
    if not isinstance(metadata, dict):
        raise ValueError("SKILL.md frontmatter must be a mapping")
    return metadata, body


def _project_name(root: Path) -> str | None:
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    in_project = False
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_project = stripped == "[project]"
            continue
        if not in_project:
            continue
        match = re.fullmatch(r'name\s*=\s*"([^"]+)"', stripped)
        if match:
            return match.group(1)
    return None


def _excluded(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(
        part in FORBIDDEN_PARTS or part.startswith(".venv")
        for part in relative.parts
    ) or any(
        relative.parts[: len(prefix)] == prefix for prefix in FORBIDDEN_PREFIXES
    )


def iter_included_files(root: Path):
    root = root.resolve()
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        current_path = Path(current)
        if current_path == root / "tests":
            dirnames[:] = [
                dirname for dirname in dirnames if dirname == "release"
            ]
            filenames = []
        kept_dirs = []
        for dirname in dirnames:
            candidate = current_path / dirname
            if candidate.is_symlink() or _excluded(candidate, root):
                continue
            kept_dirs.append(dirname)
        dirnames[:] = kept_dirs
        for filename in filenames:
            path = current_path / filename
            if path.is_symlink() or _excluded(path, root):
                continue
            yield path


def iter_release_files(root: Path, profile: str = "interview"):
    if profile == "interview":
        for relative in sorted(INTERVIEW_RELEASE_FILES):
            path = root.resolve() / relative
            if path.is_file():
                yield path
        return
    for path in iter_included_files(root):
        if path.relative_to(root).as_posix() in RELEASE_EXCLUDED_FILES:
            continue
        yield path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument(
        "--profile",
        choices=["interview", "legacy-incident"],
        default="interview",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_package(args.root, profile=args.profile)
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if result["ok"] and result["under_5mb"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
