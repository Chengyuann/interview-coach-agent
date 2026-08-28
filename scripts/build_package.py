#!/usr/bin/env python3
"""Build a ModelScope/TRAE-compatible Skill zip."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from validate_package import iter_release_files, validate_package


ZIP_TIMESTAMP = (2026, 1, 1, 0, 0, 0)
ZIP_FILE_MODE = 0o100644 << 16


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--profile",
        choices=["interview", "legacy-incident"],
        default="interview",
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    validation = validate_package(root, profile=args.profile)
    if not validation["ok"]:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        args.output.unlink()
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(iter_release_files(root, profile=args.profile)):
            relative = path.relative_to(root)
            write_stable_entry(archive, path, relative.as_posix())

    archive_sha256 = sha256(args.output)
    sha256_path = write_sha256_sidecar(args.output, archive_sha256)
    result = {
        "ok": True,
        "profile": args.profile,
        "output": str(args.output),
        "size_bytes": args.output.stat().st_size,
        "sha256": archive_sha256,
        "sha256_file": str(sha256_path),
        "under_5mb": args.output.stat().st_size <= 5 * 1024 * 1024,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["under_5mb"] else 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_sha256_sidecar(path: Path, digest: str) -> Path:
    sidecar = path.with_name(f"{path.name}.sha256")
    sidecar.write_text(f"{digest}  {path.name}\n", encoding="ascii")
    return sidecar


def write_stable_entry(
    archive: zipfile.ZipFile,
    path: Path,
    archive_name: str,
) -> None:
    info = zipfile.ZipInfo(archive_name, date_time=ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = ZIP_FILE_MODE
    archive.writestr(info, path.read_bytes())


if __name__ == "__main__":
    raise SystemExit(main())
