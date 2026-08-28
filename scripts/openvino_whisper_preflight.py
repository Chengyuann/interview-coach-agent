#!/usr/bin/env python3
"""Preflight optional OpenVINO Whisper environment and Intel hardware."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/evidence/openvino-whisper/preflight.json"),
    )
    args = parser.parse_args()
    result = preflight(args.model_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "ready" else 3


def preflight(model_dir: Path | None) -> dict:
    packages = {}
    for package in ("openvino", "openvino-genai", "openvino-tokenizers"):
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    system = platform.system()
    machine = platform.machine()
    processor = platform.processor()
    intel_host = "intel" in processor.lower() or machine.lower() in {
        "x86_64",
        "amd64",
    }
    model_ready = bool(
        model_dir
        and model_dir.expanduser().is_dir()
        and any(model_dir.expanduser().glob("*.xml"))
    )
    packages_ready = all(packages.values())
    available_devices = []
    device_error = None
    if packages["openvino"]:
        try:
            import openvino as ov

            available_devices = list(ov.Core().available_devices)
        except Exception as exc:
            device_error = f"{type(exc).__name__}: {exc}"
    ready = packages_ready and model_ready
    return {
        "schema_version": "0.1.0",
        "status": "ready" if ready else "pending",
        "host": {
            "system": system,
            "machine": machine,
            "processor": processor,
            "intel_compatible": intel_host,
        },
        "packages": packages,
        "model": {
            "path": str(model_dir.expanduser().resolve())
            if model_dir
            else None,
            "ready": model_ready,
        },
        "gates": {
            "packages_ready": packages_ready,
            "model_ready": model_ready,
            "intel_measurement_allowed": intel_host,
        },
        "openvino_devices": {
            "available": available_devices,
            "error": device_error,
            "cpu": any(
                device == "CPU" or device.startswith("CPU.")
                for device in available_devices
            ),
            "gpu": any(
                device == "GPU" or device.startswith("GPU.")
                for device in available_devices
            ),
            "npu": any(
                device == "NPU" or device.startswith("NPU.")
                for device in available_devices
            ),
        },
        "warning": (
            "Only results measured on an Intel host may be presented as "
            "Intel/OpenVINO hardware evidence."
        ),
    }


if __name__ == "__main__":
    raise SystemExit(main())
