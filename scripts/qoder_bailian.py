#!/usr/bin/env python3
"""Launch Qoder with the Alibaba Cloud Model Studio key exported from CSV."""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS = (
    Path(os.environ["QODER_BAILIAN_CREDENTIALS"]).expanduser()
    if os.environ.get("QODER_BAILIAN_CREDENTIALS")
    else None
)
MODEL_KEY = "bailian/qwen3.8-max-pg"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS,
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=ROOT,
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
    )
    args, qoder_args = parser.parse_known_args()

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

    command = [qodercli, "--cwd", str(args.cwd.expanduser().resolve())]
    if args.list_models:
        command = [qodercli, "--list-models"]
    elif args.smoke:
        command.extend(
            [
                "-p",
                "--permission-mode",
                "bypass_permissions",
                "--no-session-persistence",
                "--max-output-tokens",
                "128",
                "-m",
                MODEL_KEY,
                "Reply exactly QODER_BAILIAN_OK and do not call tools.",
            ]
        )
    else:
        command.extend(["-m", MODEL_KEY, *qoder_args])

    os.execve(qodercli, command, environment)
    return 0


def read_credentials(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise SystemExit(f"credential CSV was not found: {path}")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.reader(handle))
    values: dict[str, str] = {}
    for row in rows:
        if not row:
            continue
        values[row[0].strip()] = row[1].strip() if len(row) > 1 else ""
    return values


if __name__ == "__main__":
    sys.exit(main())
