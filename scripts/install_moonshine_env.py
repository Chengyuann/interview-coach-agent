#!/usr/bin/env python3
"""Create the lightweight Moonshine ASR environment."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--venv", type=Path, default=ROOT / ".venv-moonshine")
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()
    venv_python = args.venv / (
        "Scripts/python.exe" if sys.platform == "win32" else "bin/python"
    )
    commands = [
        [args.python, "-m", "venv", str(args.venv)],
        [str(venv_python), "-m", "pip", "install", "--upgrade", "pip"],
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "-r",
            str(ROOT / "requirements-moonshine.txt"),
        ],
    ]
    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    print(f"Moonshine environment ready: {args.venv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
