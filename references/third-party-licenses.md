# Third-Party Licenses

## Demo UI fonts

- Smiley Sans / 得意黑: SIL Open Font License 1.1. The bundled font file is
  `demo-web/assets/fonts/SmileySans-Oblique.ttf`.
- Noto Sans SC: SIL Open Font License 1.1. The demo bundles glyph-subset font
  files for the visible UI copy.

## Qwen3-ASR and Qwen3 Forced Aligner

- Models: `Qwen/Qwen3-ASR-0.6B-hf`,
  `Qwen/Qwen3-ForcedAligner-0.6B-hf`
- License: Apache-2.0
- Model weights are downloaded separately and are not included in the Skill
  archive.

## Moonshine Voice

- Runtime: `moonshine-voice==0.0.73`
- Runtime and bundled English model: MIT
- Chinese model: `moonshine-ai/base-zh-quantized`, Moonshine AI Community
  License
- The Chinese agreement includes revenue/registration conditions and
  attribution requirements, including `Powered by Moonshine AI`.

## sherpa-onnx Evaluation Candidate

- Runtime: `sherpa-onnx==1.13.4`, Apache-2.0
- Evaluated model:
  `sherpa-onnx-streaming-zipformer-small-ctc-zh-int8-2025-04-01`
- Model size: 26,342,340 bytes
- The model repository does not declare license metadata. It is not a release
  default until redistribution terms are confirmed.

## OpenVINO and Optimum Intel

- OpenVINO: Apache-2.0
- Optimum Intel: Apache-2.0
- Intel benchmark model: `OpenVINO/whisper-base-int8-ov`
- Current interview functional-smoke model:
  `OpenVINO/whisper-tiny-int8-ov`
- ModelScope model metadata license: Apache-2.0
- Model revision: `master`
- The experimental exporter is installed from pinned source revision
  `4ca1144eafc3ef7d3d805a99c7b92953441437e5`.

## SenseVoiceSmall and FSMN-VAD

- Models: `iic/SenseVoiceSmall`,
  `iic/speech_fsmn_vad_zh-cn-16k-common-pytorch`
- Used only as a separately downloaded baseline.
- Model files are excluded from the Skill archive.
- Users must review the model cards and applicable ModelScope terms before
  redistribution.

## Smart Turn v3.2

- Model: `pipecat-ai/smart-turn-v3`
- Revision: `f766f81d3cfdf7737ac64aad813d91bbfd56bf93`
- License: BSD-2-Clause
- Source repository revision:
  `4786657e242dfe77dd138699ac564ee074a2a543`
- `vevc/smart_turn_features.py` is adapted from Pipecat's
  `_whisper_features.py` at revision
  `31aa4ac65832fd2b24730fde1509e99c2923fe93` and retains the upstream
  copyright and SPDX notice.
- Model weights are downloaded separately and are not included in the Skill
  archive.
