"""Lazy, reusable Moonshine runtime for the localhost service."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from vevc.contracts import (
    load_transcript,
    validate_document,
    write_json,
    write_jsonl,
)

MODEL_REVISION = "moonshine-voice-0.0.73"


class MoonshineRuntime:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self._models: dict[str, Any] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    @property
    def loaded_languages(self) -> list[str]:
        return sorted(self._models)

    def preload(self, language: str) -> dict[str, Any]:
        _, metadata = self._get(language)
        return metadata

    def transcribe_file(
        self,
        *,
        audio_path: Path,
        language: str,
        output_path: Path,
        evidence_path: Path,
    ) -> dict[str, Any]:
        load_wav_file = moonshine_imports()["load_wav_file"]
        resolved = audio_path.expanduser().resolve()
        audio, sample_rate = load_wav_file(resolved)
        transcriber, metadata = self._get(language)
        started = time.perf_counter()
        result = transcriber.transcribe_without_streaming(audio, sample_rate)
        inference_seconds = time.perf_counter() - started
        duration_ms = max(1, round(len(audio) / sample_rate * 1000))
        rows = transcript_rows(
            result=result,
            duration_ms=duration_ms,
            audio_hash=sha256(resolved),
            model_name=metadata["model_id"],
            language=language,
        )
        write_jsonl(output_path, rows)
        load_transcript(output_path)
        evidence = {
            "schema_version": "0.1.0",
            "status": "passed",
            "model": metadata,
            "model_reused": metadata["load_count"] > 1,
            "audio": {
                "path": str(resolved),
                "sha256": sha256(resolved),
                "duration_ms": duration_ms,
            },
            "segment_count": len(rows),
            "text": " ".join(item["text"] for item in rows),
            "inference_seconds": round(inference_seconds, 6),
            "real_time_factor": round(
                inference_seconds / (duration_ms / 1000),
                6,
            ),
        }
        write_json(evidence_path, evidence)
        return evidence

    def transcribe_manifest(
        self,
        *,
        manifest_path: Path,
        output_path: Path,
        evidence_path: Path,
    ) -> dict[str, Any]:
        load_wav_file = moonshine_imports()["load_wav_file"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        validate_document(manifest, "audio_manifest")
        transcriber, metadata = self._get("zh")
        segments = []
        results = []
        offset_ms = 0
        for record in manifest["segments"]:
            audio_path = (self.root / record["path"]).resolve()
            audio, sample_rate = load_wav_file(audio_path)
            started = time.perf_counter()
            result = transcriber.transcribe_without_streaming(audio, sample_rate)
            elapsed = time.perf_counter() - started
            text = " ".join(
                line.text.strip()
                for line in result.lines
                if line.text.strip()
            )
            if not text:
                raise ValueError(
                    f"{record['segment_id']}: Moonshine produced no text"
                )
            duration_ms = record["duration_ms"]
            segments.append(
                {
                    "schema_version": "0.1.0",
                    "segment_id": record["segment_id"],
                    "start_ms": offset_ms,
                    "end_ms": offset_ms + duration_ms,
                    "speaker_id": "unknown",
                    "text": text,
                    "language": "zh",
                    "confidence": None,
                    "source": {
                        "type": "asr",
                        "audio_sha256": record["sha256"],
                        "model": metadata["model_id"],
                        "revision": MODEL_REVISION,
                        "device": "cpu",
                    },
                }
            )
            results.append(
                {
                    "segment_id": record["segment_id"],
                    "text": text,
                    "inference_seconds": round(elapsed, 6),
                    "real_time_factor": round(
                        elapsed / (duration_ms / 1000),
                        6,
                    ),
                }
            )
            offset_ms += duration_ms
        write_jsonl(output_path, segments)
        load_transcript(output_path)
        evidence = {
            "schema_version": "0.1.0",
            "status": "passed",
            "model": metadata,
            "model_reused": metadata["load_count"] > 1,
            "manifest": str(manifest_path),
            "segment_count": len(segments),
            "total_audio_ms": offset_ms,
            "segments": results,
        }
        write_json(evidence_path, evidence)
        return evidence

    def close(self) -> None:
        for transcriber in self._models.values():
            transcriber.close()
        self._models.clear()

    def _get(self, language: str) -> tuple[Any, dict[str, Any]]:
        if language in self._models:
            metadata = self._metadata[language]
            metadata["load_count"] += 1
            return self._models[language], metadata
        imports = moonshine_imports()
        model_dir, arch, model_id = resolve_model(
            root=self.root,
            language=language,
            imports=imports,
        )
        started = time.perf_counter()
        transcriber = imports["Transcriber"](
            model_path=model_dir,
            model_arch=arch,
        )
        metadata = {
            "id": model_id,
            "model_id": model_id,
            "revision": MODEL_REVISION,
            "runtime": "moonshine-voice",
            "model_path": str(model_dir),
            "device": "cpu",
            "load_seconds": round(time.perf_counter() - started, 6),
            "load_count": 1,
        }
        self._models[language] = transcriber
        self._metadata[language] = metadata
        return transcriber, metadata


def moonshine_imports() -> dict[str, Any]:
    try:
        from moonshine_voice import (
            ModelArch,
            Transcriber,
            get_assets_path,
            load_wav_file,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Moonshine runtime is unavailable. Start the server with "
            ".venv-moonshine/bin/python."
        ) from exc
    return {
        "ModelArch": ModelArch,
        "Transcriber": Transcriber,
        "get_assets_path": get_assets_path,
        "load_wav_file": load_wav_file,
    }


def resolve_model(
    *,
    root: Path,
    language: str,
    imports: dict[str, Any],
) -> tuple[Path, Any, str]:
    if language == "en":
        return (
            Path(imports["get_assets_path"]()) / "tiny-en",
            imports["ModelArch"].TINY,
            "moonshine-ai/tiny-en-quantized",
        )
    search_roots = [root / "models" / "moonshine"]
    local_skill_home = os.environ.get("LOCAL_SKILL_HOME")
    if local_skill_home:
        search_roots.insert(
            0,
            Path(local_skill_home).expanduser().resolve() / "models" / "moonshine",
        )
    elif os.name == "nt":
        search_roots.insert(
            0,
            Path.home() / ".openvino" / "models" / "moonshine",
        )
    matches = [
        candidate
        for search_root in search_roots
        if search_root.exists()
        for candidate in search_root.rglob("base-zh")
        if all(
            (candidate / name).is_file()
            for name in (
                "encoder_model.ort",
                "decoder_model_merged.ort",
                "tokenizer.bin",
            )
        )
    ]
    if not matches:
        raise RuntimeError(
            "Moonshine Chinese model is missing. "
            "Run scripts/prepare_moonshine_models.py."
        )
    return (
        matches[0],
        imports["ModelArch"].BASE,
        "moonshine-ai/base-zh-quantized",
    )


def transcript_rows(
    *,
    result: Any,
    duration_ms: int,
    audio_hash: str,
    model_name: str,
    language: str,
) -> list[dict[str, Any]]:
    rows = []
    for index, line in enumerate(result.lines, 1):
        text = line.text.strip()
        if not text:
            continue
        start_ms = max(0, round(line.start_time * 1000))
        end_ms = min(
            duration_ms,
            max(
                start_ms + 1,
                round((line.start_time + line.duration) * 1000),
            ),
        )
        rows.append(
            {
                "schema_version": "0.1.0",
                "segment_id": f"S{index:04d}",
                "start_ms": start_ms,
                "end_ms": end_ms,
                "speaker_id": "unknown",
                "text": text,
                "language": language,
                "confidence": None,
                "source": {
                    "type": "asr",
                    "audio_sha256": audio_hash,
                    "model": model_name,
                    "revision": MODEL_REVISION,
                    "device": "cpu",
                },
            }
        )
    if not rows:
        raise ValueError("Moonshine produced no transcript lines")
    return rows


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
