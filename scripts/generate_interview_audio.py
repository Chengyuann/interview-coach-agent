#!/usr/bin/env python3
"""Generate a reproducible local interview-answer WAV fixture on macOS."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCRIPT = ROOT / "examples" / "interview-coach" / "audio-script.json"
DEFAULT_OUTPUT = ROOT / "build" / "interview-audio-fixture"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, default=DEFAULT_SCRIPT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    config = json.loads(args.script.read_text(encoding="utf-8"))
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    aiff_path = output_dir / "answer.aiff"
    wav_path = output_dir / "answer.wav"
    subprocess.run(
        [
            "/usr/bin/say",
            "-v",
            config["voice"],
            "-r",
            str(config["rate"]),
            "-o",
            str(aiff_path),
            config["text"],
        ],
        check=True,
    )
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(aiff_path),
            "-ar",
            "16000",
            "-ac",
            "1",
            "-sample_fmt",
            "s16",
            str(wav_path),
        ],
        check=True,
    )
    aiff_path.unlink()
    result = {
        "schema_version": "0.1.0",
        "status": "passed",
        "audio": wav_path.relative_to(ROOT).as_posix(),
        "sha256": sha256(wav_path),
        "duration_ms": wav_duration_ms(wav_path),
        "voice": config["voice"],
        "rate": config["rate"],
        "language": config["language"],
        "role": config["role"],
        "question_id": config["question_id"],
        "script_text": config["text"],
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        return max(1, round(handle.getnframes() / handle.getframerate() * 1000))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
