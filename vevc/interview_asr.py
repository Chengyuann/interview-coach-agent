"""ASR provider router for interview practice audio."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from vevc.moonshine_runtime import MoonshineRuntime


class InterviewAsrRuntime:
    def __init__(
        self,
        *,
        root: Path,
        provider: str = "moonshine",
        openvino_model_dir: Path | None = None,
        openvino_device: str = "CPU",
        moonshine_runtime: MoonshineRuntime | None = None,
    ) -> None:
        if provider not in {"moonshine", "openvino"}:
            raise ValueError(f"unsupported ASR provider: {provider}")
        self.root = root.resolve()
        self.provider = provider
        self.openvino_model_dir = (
            openvino_model_dir.expanduser().resolve()
            if openvino_model_dir
            else None
        )
        self.openvino_device = openvino_device
        self._moonshine = moonshine_runtime
        self._owns_moonshine = moonshine_runtime is None
        self._openvino: Any | None = None

    @property
    def loaded_languages(self) -> list[str]:
        if self.provider != "moonshine" or self._moonshine is None:
            return []
        return self._moonshine.loaded_languages

    def metadata(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "provider": self.provider,
            "loaded_languages": self.loaded_languages,
        }
        if self.provider == "openvino":
            result["model_dir"] = (
                str(self.openvino_model_dir)
                if self.openvino_model_dir
                else None
            )
            result["device"] = self.openvino_device
            result["loaded"] = self._openvino is not None
        return result

    def preload(self, language: str) -> dict[str, Any]:
        if self.provider == "moonshine":
            return self._get_moonshine().preload(language)
        return self._get_openvino().preload()

    def transcribe_file(
        self,
        *,
        audio_path: Path,
        language: str,
        output_path: Path,
        evidence_path: Path,
    ) -> dict[str, Any]:
        if self.provider == "moonshine":
            result = self._get_moonshine().transcribe_file(
                audio_path=audio_path,
                language=language,
                output_path=output_path,
                evidence_path=evidence_path,
            )
            result["provider"] = "moonshine"
            return result
        return self._get_openvino().transcribe_file(
            audio_path=audio_path,
            language=language,
            output_path=output_path,
            evidence_path=evidence_path,
        )

    def close(self) -> None:
        if self._moonshine is not None and self._owns_moonshine:
            self._moonshine.close()
        self._moonshine = None
        self._openvino = None

    def _get_moonshine(self) -> MoonshineRuntime:
        if self._moonshine is None:
            self._moonshine = MoonshineRuntime(self.root)
            self._owns_moonshine = True
        return self._moonshine

    def _get_openvino(self):
        if self._openvino is not None:
            return self._openvino
        if self.openvino_model_dir is None:
            raise RuntimeError(
                "OpenVINO ASR provider requires --openvino-model-dir."
            )
        from vevc.openvino_whisper_runtime import OpenVINOWhisperRuntime

        self._openvino = OpenVINOWhisperRuntime(
            model_dir=self.openvino_model_dir,
            device=self.openvino_device,
        )
        return self._openvino
