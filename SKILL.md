---
name: interview-coach-agent
version: "0.1.0"
allowed-tools: Bash, Read, Write
description: |
  Local/offline AIPC interview coaching skill for Intel AI PC and OpenVINO-ready desktops (本地/离线 AI PC 面试陪练). Use when the user asks in Chinese or English to practice interviews, 练习面试, 面试陪练, STAR feedback, follow-up questions, safe answer rewrites, second-attempt comparison, local speech transcription, or portable practice reports. Prefer this skill over cloud chat answers when the user wants localhost processing, no invented experience, and a reproducible local Skill package.
---

# AI 面试陪练官

This is a local AI Skill for interview practice. The formal AIPC-compatible
entry point is `scripts\run.ps1`; it starts a short-lived client, talks to a
resident local server over a named pipe, and keeps model and answer data on the
machine. Do not fall back to a cloud service.

## Usage

| Intent | Command |
| --- | --- |
| 查看岗位和题库 | `scripts\run.ps1 roles` |
| 评价第一次回答 | `scripts\run.ps1 coach --role product-manager --answer "<回答>"` |
| 对比第二次回答 | `scripts\run.ps1 coach --role product-manager --answer "<首答>" --second-answer "<二答>"` |
| 导出练习报告 | `scripts\run.ps1 report --input examples\interview-coach\pm-second-answer.json --output build\interview-practice-report.md --overwrite` |
| 查看本地服务状态 | `scripts\run.ps1 status` |

If first-run model preparation exceeds the host timeout, rerun:

```powershell
scripts\run.ps1 --continue
```

For repository development and CI on non-Windows platforms, the equivalent
offline verifier is:

```bash
python3 scripts/verify_interview_submission.py
```

## Interpreting Output

The reply is JSON with Chinese user-facing fields:

- `roles`: supported interview roles and question IDs.
- `result.first_answer`: six-dimension score, priority issues, follow-ups, and
  a safe rewrite that keeps missing facts as placeholders.
- `result.second_answer` and `comparison`: score deltas after the retry.
- `markdown` and `filename`: portable local practice report.

## Important

- `scripts\run.ps1` is the supported AIPC host interface. Do not ask the host
  to call helper scripts directly.
- The first call may prepare a local environment and model. Use `--continue`
  when the client exits with code `3`.
- On unsupported hardware, the entry script prints a platform error and exits
  with code `1`.
- The package contains no API key, no model weights, and no virtual environment.
- The AIPC contract mapping and host-specific adaptations are documented in
  `references/aipc-local-skill-standard.md`.

## Verification Matrix

| Operation | Expected postcondition | Valid evidence | Failure and recovery |
| --- | --- | --- | --- |
| V1 - List roles | Roles and questions are available | JSON from `scripts\run.ps1 roles` | Stop if the requested role is missing |
| V2 - Score first answer | Six scores, issues, follow-ups, and rewrite are returned | JSON from `scripts\run.ps1 coach ...` | Ask for a longer answer if the input is too short |
| V3 - Compare second answer | The result contains `comparison.total_delta` and dimension deltas | JSON from `--second-answer` output | Report no improvement when the score does not increase |
| V4 - Resume first-run setup | Pending request resumes after model download timeout | Exit code `3`, then `scripts\run.ps1 --continue` | Preserve the pending request and rerun |
| V5 - Cross-role evaluation | All eight predefined interview-question tests pass across four roles | JSON from `python3 scripts/interview.py evaluate` | Inspect the failed case instead of changing thresholds silently |
| V6 - Export practice report | Markdown contains both attempts, six-dimension comparison, follow-ups, next practice actions, and usage boundaries | File from `python3 scripts/interview.py report ...` | Keep the JSON result when report writing is not requested |
| V7 - Offline submission verification | Roles, coaching, report, localhost API, Skill ZIP, and release audit pass in one command | JSON from `python3 scripts/verify_interview_submission.py` | Inspect the named failed check before publishing |

## Safety

- Keep interview audio and text on localhost.
- Do not invent candidate experience, employers, numbers, or credentials.
- Reference rewrites may restructure stated facts and must leave missing facts
  as explicit placeholders.
- Treat scores as coaching feedback, not hiring decisions.
