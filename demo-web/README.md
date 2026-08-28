# 面试陪练 Demo

The lightweight frontend is served by `scripts/server.py` and uses the real
local interview endpoints:

- `GET /v1/status`
- `GET /v1/interview/roles`
- `POST /v1/interview/coach`
- `POST /v1/interview/report`
- `POST /v1/interview/transcribe`

The primary flow is intentionally short:

1. Choose a role and question.
2. Answer by text or import a local WAV file.
3. Review the three highest-priority coaching points.
4. Answer again and compare the score.
5. Download a portable Markdown practice report.

The browser page does not invent candidate experience. Rewrites preserve the
facts in the supplied answer and mark missing evidence for the user to add.
