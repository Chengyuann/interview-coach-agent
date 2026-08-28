#!/usr/bin/env python3
"""Transcribe WAV with the optional OpenVINO GenAI Whisper provider."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from vevc.openvino_whisper_runtime import OpenVINOWhisperRuntime


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--device", default="CPU")
    parser.add_argument("--language", default="zh")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path(
            "docs/evidence/openvino-whisper/transcription.json"
        ),
    )
    args = parser.parse_args()
    runtime = OpenVINOWhisperRuntime(
        model_dir=args.model_dir,
        device=args.device,
    )
    result = runtime.transcribe_file(
        audio_path=args.audio,
        language=args.language,
        output_path=args.output,
        evidence_path=args.evidence,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.stdout.flush()
    sys.stderr.flush()
    if sys.platform == "win32":
        os._exit(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
