"""Optional OpenVINO GenAI Whisper provider for Intel deployment."""

from __future__ import annotations

import hashlib
import json
import platform
import time
from pathlib import Path
from typing import Any

import numpy as np

from vevc.contracts import load_transcript, write_json, write_jsonl


class OpenVINOWhisperRuntime:
    def __init__(
        self,
        *,
        model_dir: Path,
        device: str = "CPU",
    ) -> None:
        self.model_dir = model_dir.expanduser().resolve()
        self.device = device
        self._pipeline = None
        self.load_seconds: float | None = None

    def preload(self) -> dict[str, Any]:
        self._get_pipeline()
        return self.metadata()

    def transcribe_file(
        self,
        *,
        audio_path: Path,
        language: str,
        output_path: Path,
        evidence_path: Path,
    ) -> dict[str, Any]:
        audio, sample_rate = load_audio_16k(audio_path)
        pipeline = self._get_pipeline()
        config = pipeline.get_generation_config()
        if language:
            config.language = f"<|{language}|>"
        config.task = "transcribe"
        config.return_timestamps = False
        started = time.perf_counter()
        result = pipeline.generate(audio, config)
        inference_seconds = time.perf_counter() - started
        text = result_text(result)
        if not text:
            raise ValueError("OpenVINO Whisper produced no text")
        duration_ms = max(1, round(audio.size / sample_rate * 1000))
        audio_hash = sha256(audio_path)
        rows = [
            {
                "schema_version": "0.1.0",
                "segment_id": "S0001",
                "start_ms": 0,
                "end_ms": duration_ms,
                "speaker_id": "unknown",
                "text": text,
                "language": language,
                "confidence": None,
                "source": {
                    "type": "asr",
                    "audio_sha256": audio_hash,
                    "model": self.model_dir.name,
                    "revision": model_revision(self.model_dir),
                    "device": self.device,
                },
            }
        ]
        write_jsonl(output_path, rows)
        load_transcript(output_path)
        evidence = {
            "schema_version": "0.1.0",
            "status": "passed",
            "provider": "openvino-genai-whisper",
            "model": self.metadata(),
            "host": {
                "system": platform.system(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
            "audio": {
                "path": str(audio_path.resolve()),
                "sha256": audio_hash,
                "duration_ms": duration_ms,
            },
            "text": text,
            "inference_seconds": round(inference_seconds, 6),
            "real_time_factor": round(
                inference_seconds / (duration_ms / 1000),
                6,
            ),
        }
        write_json(evidence_path, evidence)
        return evidence

    def metadata(self) -> dict[str, Any]:
        return {
            "id": self.model_dir.name,
            "revision": model_revision(self.model_dir),
            "runtime": "openvino-genai",
            "model_path": str(self.model_dir),
            "device": self.device,
            "load_seconds": self.load_seconds,
        }

    def _get_pipeline(self):
        if self._pipeline is not None:
            return self._pipeline
        try:
            import openvino_tokenizers  # noqa: F401
            import openvino_genai
        except ImportError as exc:
            raise RuntimeError(
                "OpenVINO GenAI is unavailable. Install "
                "requirements-openvino-whisper.txt in a separate environment."
            ) from exc
        if not self.model_dir.is_dir():
            raise RuntimeError(
                f"OpenVINO Whisper model directory is missing: {self.model_dir}"
            )
        started = time.perf_counter()
        pipeline_class = getattr(
            openvino_genai,
            "ASRPipeline",
            None,
        ) or getattr(openvino_genai, "WhisperPipeline", None)
        if pipeline_class is None:
            raise RuntimeError(
                "OpenVINO GenAI exposes neither ASRPipeline nor "
                "WhisperPipeline."
            )
        self._pipeline = pipeline_class(
            str(self.model_dir),
            self.device,
        )
        self.load_seconds = round(time.perf_counter() - started, 6)
        return self._pipeline


def result_text(result: Any) -> str:
    if isinstance(result, str):
        return result.strip()
    texts = getattr(result, "texts", None)
    if texts:
        return str(texts[0]).strip()
    return str(result).strip()


def load_audio_16k(path: Path) -> tuple[np.ndarray, int]:
    import wave

    resolved = path.expanduser().resolve()
    with wave.open(str(resolved), "rb") as handle:
        channels = handle.getnchannels()
        sample_width = handle.getsampwidth()
        sample_rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if sample_width != 2:
        raise ValueError("OpenVINO Whisper adapter requires 16-bit PCM WAV")
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    if sample_rate != 16000:
        size = max(1, round(audio.size * 16000 / sample_rate))
        audio = np.interp(
            np.linspace(0, audio.size - 1, size),
            np.arange(audio.size),
            audio,
        ).astype(np.float32)
        sample_rate = 16000
    return audio, sample_rate


def model_revision(model_dir: Path) -> str | None:
    metadata = model_dir / "vevc_model.json"
    if not metadata.is_file():
        return None
    return json.loads(metadata.read_text(encoding="utf-8")).get("revision")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
