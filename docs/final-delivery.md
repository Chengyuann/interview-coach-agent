# Final Delivery

## Primary Assets

- Product: AI 面试陪练官 (`interview-coach-agent`)
- Published ModelScope Skill:
  `https://www.modelscope.cn/skills/ayuannn/interview-coach-agent`
- Skill archive: `dist/interview-coach-agent-0.1.0.zip`
- Skill archive size: 2,217,507 bytes
- Skill archive SHA-256:
  `7188cb1458c2dc82a60d77a37afd4d596b50b062b6dee982c0b8a4426b403962`
- Skill archive checksum:
  `dist/interview-coach-agent-0.1.0.zip.sha256`
- Submission bundle: `dist/interview-coach-agent-submission-bundle.zip`
- Submission guide: `docs/interview-coach-submission-guide.md`
- Demo video: `output/interview-coach-redesign/interview-coach-demo-v2.mp4`
- Demo video SHA-256:
  `1fa9adaceb4c7d35a4ff5eca4c4c252023bd2592b6d10c37ab3ab7c9efa2eea3`
- Compatible demo path: `build/interview-coach-demo.mp4`
- Demo video QA: `output/interview-coach-redesign/qa/render-report.json`
- Demo contact sheet: `output/interview-coach-redesign/qa/contact-sheet.jpg`
- Interactive workbench: `demo-web/index.html`
- AIPC fixed entry: `scripts/run.ps1`
- AIPC local skill mapping: `references/aipc-local-skill-standard.md`
- CLI entry point: `scripts/interview.py`
- Localhost service: `scripts/interview_server.py`
- Practice report sample: `examples/interview-coach/pm-practice-report.md`
- Practice report sample SHA-256:
  `a0d97e20dc4f06ae8777e4727e617c33bee9cb425c4e2950a958ec61b1c0fe7b`
- Practice report UI capture:
  `docs/submission-assets/article/08-report-download.png`
- Cross-role evaluation: `build/interview-coach-evaluation.json`
- Localhost coach stability: `docs/evidence/interview-service/stability-40.json`
- Real local audio smoke: `build/interview-audio-smoke/summary.json`
- HTTP audio smoke: `build/interview-http-audio-smoke.json`
- OpenVINO current-product CLI: `docs/evidence/interview-openvino-current-product-cli.json`
- OpenVINO current-product service: `docs/evidence/interview-openvino-current-product-service.json`
- GPT-5.5 simulated candidates: `docs/evidence/interview-simulated-users/gpt55-simulated-users.json`
- VoxCPM2 voice smoke: `docs/evidence/interview-simulated-users/tts-smoke/summary.json`
- TRAE tool invocation: `docs/evidence/trae-interview-coach/trae-cli-smoke.txt`
- TRAE tool stability:
  `docs/evidence/trae-interview-coach/trae-stability-v0.120.47.json`
- Agent-generated report summary:
  `docs/evidence/agent-report-evidence/summary.json`
- One-command offline verification:
  `build/interview-submission-verification.json`
- Qoder skill discovery: Qoder CLI 1.1.30 discovers
  `interview-coach-agent`; current evidence is in
  `docs/evidence/qoder-interview-coach/qoder-skill-discovery-v1.1.30.txt`.
- Qoder Alibaba Cloud invocation: Qoder CLI 1.1.30 uses
  `bailian/qwen3.8-max-pg` with an external CSV credential, invokes
  `interview-coach-agent`, runs `roles`, `coach`, and `report`, and reports
  4.2 to 6.7 (+2.5, `improved`).

## Local Audio Verification

- Fixture audio: `build/interview-audio-fixture/answer.wav`
- Duration: 16.336 seconds
- Moonshine local inference: 0.651056 seconds
- RTF: 0.039854
- Score after ASR normalization: 6.0 / 7
- Reference transcript recall: 1.0
- Transcript precision: 1.0
- Quality gate: passed; threshold remains 0.90

## New Evidence

- OpenVINO 2026.3 is integrated into the current interview CLI and localhost
  service as an explicit optional provider.
- AIPC local skill entry now uses `scripts\run.ps1`, `install-env.ps1`,
  short-lived `client.py`, resident named-pipe `server.py`, `.partial` model
  preparation, pending-request resume, and `tests\test.ps1`.
- Current-product OpenVINO functional smoke: 17.60 seconds audio, CLI RTF
  0.010778, service RTF 0.015237. These Apple Silicon results are not claimed
  as Intel performance evidence.
- Existing Intel Core i7-12650H OpenVINO benchmark remains separate: 27.055
  seconds audio in 1.409 seconds, RTF 0.0521.
- GPT-5.5 AI simulated candidates: 3 / 3 improved after seeing actual coach
  feedback; average delta +1.467. This is not a human user study.
- VoxCPM2 generated voice path: first answer 3.0, second answer 6.3, delta
  +3.3 through local Moonshine transcription.
- Practice report delivery: CLI report generation writes
  `build/interview-practice-report.md`; localhost `/v1/interview/report`
  returns Markdown; browser download produced
  `.playwright-cli/interview-practice-product-manager-pm-impact.md`.

## Demo Video Verification

- Duration: 38.60 seconds
- Resolution: 1920x1080
- Frame rate: 30 fps
- Video: H.264
- Audio: AAC, 48 kHz mono, MCY voice
- Captions: no burned-in subtitles
- Capture boundary: browser page only; no desktop or unrelated window capture
- Full decode: passed
- Black-frame events: none
- Silence events over 2 seconds: none
- Content: current interview coach UI only
- Product flow: first answer 4.2, second answer 6.7, +2.5 delta, real report
  download, and downloaded Markdown report view

## Local Verification

- Full test suite: 194 passed
- Frozen scenario evaluation: 8 / 8 passed across 4 roles
- Average second-attempt improvement: 2.76 points
- Localhost `/v1/interview/coach` stability: 40 / 40 requests passed,
  success rate 1.0, error count 0, median latency 0.001739 seconds
- Skill archive: under 5 MB, release audit passed
- AIPC local Skill contract: packaged and release-audited
- Practice report endpoint: `/v1/interview/report` verified in browser and
  direct HTTP checks
- Desktop layout: 1600x900, no horizontal or vertical overflow
- Mobile layout: 390x844, no horizontal overflow
- TRAE tool invocation: passed with first score 4.2, second score 6.7,
  total delta +2.5
- TRAE stability: 3 / 3 fresh-start checks passed; each loaded the Skill,
  completed three Bash calls, reproduced +2.5, and generated one report under
  the allowed build directory without changing the source tree.
- Qoder tool invocation: passed. Qoder CLI 1.1.30 used Alibaba Cloud Model Studio China
  Pay As You Go `qwen3.8-max-pg`, invoked the local Skill, and verified the
  retry comparison at 4.2 to 6.7 (+2.5).
- Qoder stability: 3 / 3 fresh-start invocations passed with
  the same 4.2 to 6.7 (+2.5) result and one generated report per run.
- Agent report stability: 6 / 6 reports were created, each 3,193 bytes with
  SHA-256
  `47062de9c07f2f37e8d3dec1158527f9e509522a66693be5133f6a727b7eee64`;
  source-tree fingerprints were unchanged in all six runs.
- Secret boundary: the Alibaba Cloud credential CSV is external; the Skill ZIP
  and submission bundle contain only `${DASHSCOPE_API_KEY}` references.
- Submission integrity: both ZIP builders emit `.sha256` sidecars; the review
  bundle also includes `build/interview-coach-submission-manifest.json` with
  per-file hashes.

```bash
python3 scripts/verify_interview_submission.py
python3 -m pytest
python3 scripts/evaluate_interview_coach.py
python3 scripts/generate_interview_audio.py
.venv-moonshine/bin/python scripts/run_interview_audio_smoke.py
python3 scripts/validate_package.py .
python3 scripts/build_package.py \
  --output dist/interview-coach-agent-0.1.0.zip
python3 scripts/release_audit.py \
  --archive dist/interview-coach-agent-0.1.0.zip \
  --output build/interview-coach-release-audit.json

# Launch Qoder with the external Alibaba Cloud CSV credential.
python3 scripts/qoder_bailian.py

# Non-interactive provider smoke.
python3 scripts/qoder_bailian.py --smoke
```

## External Actions

The following require user accounts or human participants and are not claimed
as automated deliverables:

- Publish the Skill archive to ModelScope.
- Publish the technical article and social-media material.
- Verify public links after publication.
- Optional: collect timed task results from developers or SREs.
