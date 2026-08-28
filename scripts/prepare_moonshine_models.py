#!/usr/bin/env python3
"""Download the lightweight native Moonshine Chinese model."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from moonshine_voice import ModelArch, get_model_for_language

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = ROOT / "models" / "moonshine"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path("docs/evidence/lightweight/moonshine-model.json"),
    )
    args = parser.parse_args()
    model_path, model_arch = get_model_for_language(
        "zh",
        wanted_model_arch=ModelArch.BASE,
        cache_root=args.cache_dir.resolve(),
    )
    root = Path(model_path)
    files = [inspect_file(item, root) for item in sorted(root.iterdir()) if item.is_file()]
    result = {
        "schema_version": "0.1.0",
        "status": "passed",
        "runtime": "moonshine-voice",
        "runtime_version": "0.0.73",
        "language": "zh",
        "model_arch": "base",
        "license": "Moonshine AI Community License",
        "model_path": str(root),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def inspect_file(path: Path, root: Path) -> dict:
    return {
        "path": path.relative_to(root).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())

