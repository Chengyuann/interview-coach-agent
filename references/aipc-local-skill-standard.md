# AIPC Local Skill Standard Mapping

This package follows the reusable contract in
<https://github.com/openvino-dev-samples/local-ai-skill-authoring>, reviewed at commit
`0a6e3c2dc3a07009dfebda2b304741ddf3110ee7`.

## Implemented

- Fixed Windows host entry: `scripts/run.ps1`.
- Environment installer: `scripts/install-env.ps1`, driven by `info.json` and
  a requirements SHA-256 cache.
- Short-lived client and resident service: `scripts/client.py` and
  `scripts/server.py`.
- Windows named pipe `\\.\pipe\interview-coach-agent`; a short Unix socket is
  used only for development and CI.
- Standard pipe operations: `status`, `request`, and `shutdown`.
- Server states: `starting`, `downloading`, `loading`, `running`, and `error`.
- Model validation through `info.json.required_files`.
- `.partial` model preparation followed by an atomic directory move.
- Pending-request file and exit code `3` for `scripts\run.ps1 --continue`.
- UTF-8 stdout/stderr configuration, structured JSON responses, and local logs.
- Runtime file hashing; the client shuts down and restarts a stale resident
  service after a Skill update.
- OpenVINO provider selection prefers an available Intel GPU and falls back to
  CPU. In `auto` mode, an unavailable OpenVINO runtime falls back to the local
  Moonshine provider without using a cloud service.
- Windows end-to-end test: `tests/test.ps1`.

## Host-Specific Adaptations

- `platform.exe --is-aipc` is used when the host supplies it. The standalone
  package remains usable when that Marvis-specific binary is absent.
- Instead of Marvis `server-dog`, the short-lived client starts the resident
  service and the service enforces `server_alive_timeout` itself.
- The Skill name remains `interview-coach-agent` to preserve existing
  ModelScope, Qoder, and TRAE links rather than renaming it to `local-*`.

## Boundaries

- Model weights and virtual environments are excluded from the Skill ZIP.
- The default Chinese model is Moonshine. OpenVINO Whisper is an explicit local
  option and is not represented as higher-accuracy unless measured evidence
  supports that claim.
- No inference path falls back to a cloud API.
