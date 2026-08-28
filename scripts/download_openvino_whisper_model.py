#!/usr/bin/env python3
"""Download an OpenVINO Whisper snapshot, preferring ModelScope."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-id",
        default="OpenVINO/whisper-tiny-int8-ov",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    errors: list[str] = []

    try:
        from modelscope.hub.snapshot_download import snapshot_download

        snapshot_download(
            model_id=args.model_id,
            local_dir=str(output),
        )
        provider = "modelscope"
    except Exception as exc:
        errors.append(f"ModelScope: {type(exc).__name__}: {exc}")
        try:
            from huggingface_hub import snapshot_download

            snapshot_download(
                repo_id=args.model_id,
                local_dir=str(output),
            )
            provider = "huggingface"
        except Exception as fallback:
            errors.append(
                f"Hugging Face: {type(fallback).__name__}: {fallback}"
            )
            print(
                json.dumps(
                    {
                        "status": "failed",
                        "model_id": args.model_id,
                        "output": str(output),
                        "errors": errors,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 2

    xml_files = sorted(path.name for path in output.glob("*.xml"))
    if not xml_files:
        print(
            json.dumps(
                {
                    "status": "failed",
                    "model_id": args.model_id,
                    "output": str(output),
                    "provider": provider,
                    "errors": [
                        "download completed but no OpenVINO XML files found"
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2
    print(
        json.dumps(
            {
                "status": "passed",
                "model_id": args.model_id,
                "output": str(output),
                "provider": provider,
                "xml_files": xml_files,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
