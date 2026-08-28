# Reproduction Guide

## Requirements

- macOS or a compatible Python host
- Python 3.11+
- about 500 MB for the optional local speech runtime and model
- no cloud service is required for the core speech-to-coaching workflow

## Text Coaching

```bash
python3 -m venv .venv-minimal
.venv-minimal/bin/python -m pip install -r requirements-minimal.txt

.venv-minimal/bin/python scripts/interview.py roles
.venv-minimal/bin/python scripts/interview.py coach \
  --input examples/interview-coach/pm-second-answer.json \
  --output build/interview-coach-result.json \
  --overwrite
.venv-minimal/bin/python scripts/interview.py report \
  --input examples/interview-coach/pm-second-answer.json \
  --output build/interview-practice-report.md \
  --overwrite
.venv-minimal/bin/python scripts/interview.py evaluate
```

## Local Audio Runtime

```bash
python3 scripts/install_moonshine_env.py
.venv-moonshine/bin/python scripts/prepare_moonshine_models.py
.venv-moonshine/bin/python scripts/interview.py service --preload zh
```

In another terminal:

```bash
python3 scripts/generate_interview_audio.py
.venv-moonshine/bin/python scripts/run_interview_audio_smoke.py
```

The browser workbench is available at `http://127.0.0.1:8876`.

## AIPC Local Skill Entry

On Windows hosts, use the fixed entry required by the AIPC local skill
authoring pattern:

```powershell
scripts\run.ps1 roles
scripts\run.ps1 report `
  --input examples\interview-coach\pm-second-answer.json `
  --output build\interview-practice-report.md `
  --overwrite
```

The entry script creates or reuses the local venv, starts a resident named-pipe
server, validates local model files, and supports first-run resume with:

```powershell
scripts\run.ps1 --continue
```

The Windows end-to-end check is:

```powershell
tests\test.ps1
```

## Qoder Host Verification

This optional path verifies the Skill inside a production Agent host. It uses
Alibaba Cloud Model Studio only as the Qoder agent brain; interview audio,
transcription, scoring, and answer comparison remain local.

The launcher reads an external CSV credential and exports the key only to the
Qoder process:

```bash
python3 scripts/qoder_bailian.py --list-models
python3 scripts/qoder_bailian.py --smoke
python3 scripts/qoder_bailian.py
```

Provide the external credential without editing the project:

```bash
QODER_BAILIAN_CREDENTIALS=/secure/path/qoder-key.csv \
  python3 scripts/qoder_bailian.py --smoke
```

Expected smoke output:

```text
QODER_BAILIAN_OK
```

Full production-Agent report verification:

```bash
python3 scripts/run_qoder_bailian_stability.py
python3 scripts/run_trae_interview_stability.py
```

Each script performs three fresh-start checks through `roles`, `coach`, and
`report`, then independently verifies the generated Markdown and source-tree
fingerprints.

The verified model key is `bailian/qwen3.8-max-pg`. The credential CSV and
plain API key are not included in either release archive.

## Release Verification

One-command offline verification:

```bash
python3 scripts/verify_interview_submission.py
```

This verifies the role library, two-attempt coaching result, Markdown report,
localhost report API, Skill archive, and release audit without cloud access.

Full development checks:

```bash
python3 -m pytest
python3 scripts/validate_package.py .
python3 scripts/build_package.py \
  --output dist/interview-coach-agent-0.1.0.zip
python3 scripts/release_audit.py \
  --archive dist/interview-coach-agent-0.1.0.zip \
  --output build/interview-coach-release-audit.json
python3 scripts/build_interview_submission_bundle.py
```

The release archive includes a self-contained core test set:

```bash
python3 -m pip install "pytest>=8,<9"
python3 -m pytest tests/release -q
```

The builders also write `.sha256` sidecars next to the final ZIP files.
