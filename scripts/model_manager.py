#!/usr/bin/env python3
"""Model validation and first-run resume helpers for the AIPC Skill path."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "interview-coach-agent"
PENDING_NAME = f"{SKILL_NAME}-pending-request.json"
RUNTIME_FILES = (
    "scripts/server.py",
    "scripts/model_manager.py",
    "vevc/interview_asr.py",
    "vevc/interview_coach.py",
    "vevc/interview_report.py",
    "vevc/moonshine_runtime.py",
    "vevc/openvino_whisper_runtime.py",
    "vevc/safety.py",
)


def configure_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def skill_home() -> Path:
    configured = os.environ.get("LOCAL_SKILL_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        return Path.home() / ".openvino"
    return ROOT / "build" / ".local-skill"


def load_info() -> dict[str, Any]:
    return json.loads((ROOT / "info.json").read_text(encoding="utf-8"))


def runtime_hash() -> str:
    digest = hashlib.sha256()
    for relative in RUNTIME_FILES:
        path = ROOT / relative
        digest.update(relative.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def model_roots() -> list[Path]:
    home = skill_home()
    return [home / "models", ROOT / "models"]


def required_files_present(root: Path, required: list[str]) -> bool:
    if not root.exists():
        return False
    return all((root / item).is_file() for item in required)


def model_status() -> dict[str, Any]:
    models = []
    for item in load_info().get("models", []):
        required = list(item.get("required_files", []))
        ready_path = next(
            (
                path
                for root in model_roots()
                for path in model_candidates(root, item["dir_name"])
                if required_files_present(path, required)
            ),
            None,
        )
        models.append(
            {
                "model_id": item["model_id"],
                "dir_name": item["dir_name"],
                "required_files": required,
                "ready": ready_path is not None,
                "path": str(ready_path) if ready_path else None,
            }
        )
    return {
        "ok": all(item["ready"] for item in models),
        "models": models,
        "skill_home": str(skill_home()),
    }


def model_candidates(root: Path, dir_name: str) -> list[Path]:
    exact = root / dir_name
    candidates = [exact]
    if root.exists():
        candidates.extend(
            path
            for path in root.rglob(Path(dir_name).name)
            if path.is_dir() and path != exact
        )
    return candidates


def ensure_models() -> dict[str, Any]:
    status = model_status()
    if status["ok"]:
        return {"status": "ready", **status}

    prepared = []
    for item in load_info().get("models", []):
        target = skill_home() / "models" / item["dir_name"]
        required = list(item.get("required_files", []))
        if required_files_present(target, required):
            continue
        partial = target.with_name(target.name + ".partial")
        partial.parent.mkdir(parents=True, exist_ok=True)
        partial.mkdir(parents=True, exist_ok=True)
        if item["model_id"] == "moonshine-ai/base-zh-quantized":
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "prepare_moonshine_models.py"),
                    "--cache-dir",
                    str(partial),
                ],
                cwd=ROOT,
                check=True,
            )
        else:
            raise RuntimeError(
                f"No downloader is configured for model {item['model_id']}"
            )
        found = next(
            (
                path
                for path in [partial, *partial.rglob("*")]
                if path.is_dir() and required_files_present(path, required)
            ),
            None,
        )
        if found is None:
            raise RuntimeError(
                f"Downloaded model is missing required files: {required}"
            )
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        found.replace(target)
        shutil.rmtree(partial, ignore_errors=True)
        prepared.append(str(target))
    return {"status": "ready", "prepared": prepared, **model_status()}


def pending_request_path() -> Path:
    return skill_home() / PENDING_NAME


def save_pending_request(payload: dict[str, Any]) -> Path:
    path = pending_request_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def load_pending_request() -> dict[str, Any]:
    path = pending_request_path()
    if not path.is_file():
        raise FileNotFoundError(f"No pending request found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def clear_pending_request() -> None:
    path = pending_request_path()
    if path.exists():
        path.unlink()


def main() -> int:
    configure_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--ensure", action="store_true")
    parser.add_argument("--pending-path", action="store_true")
    args = parser.parse_args()
    if args.pending_path:
        print(pending_request_path())
        return 0
    if args.ensure:
        print(json.dumps(ensure_models(), ensure_ascii=False, indent=2))
        return 0
    print(json.dumps(model_status(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
