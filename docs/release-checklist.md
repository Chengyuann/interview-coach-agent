# Release Checklist

## Automated

- [x] All tests pass
- [x] Package validation passes
- [x] Release ZIP contains one root `SKILL.md`
- [x] Release ZIP is below 5 MB
- [x] AIPC fixed entry `scripts\run.ps1` and `tests\test.ps1` are packaged
- [x] Named-pipe client/server, `.partial` model preparation, and
      `--continue` resume are tested
- [x] Model weights and virtual environments are excluded
- [x] Legacy heavyweight backend scripts are excluded
- [x] Clean archive release smoke passes
- [x] Third-party licenses and model revisions are documented
- [x] Four-role interview evaluation passes
- [x] Local Moonshine speech-to-coaching smoke passes
- [x] Minimal localhost service smoke passes
- [x] TRAE CLI runs `roles`, `coach`, and `report` in 3 fresh-start checks
      and generates verified Markdown reports
- [x] Qoder CLI discovers and enables `interview-coach-agent`
- [x] Qoder CLI invokes `interview-coach-agent` through Alibaba Cloud Model
      Studio China Pay As You Go in 3 fresh-start runs and
      generates verified Markdown reports
- [x] One-command offline verifier checks roles, coaching, report, localhost
      API, Skill ZIP, and release audit
- [x] Final MCY-narrated video shows 4.2 to 6.7 and the real report download
- [x] Desktop and mobile workbench screenshots are current
- [x] Short looping GIF decodes fully and loops seamlessly

## Manual External Actions

- [ ] Publish the Skill archive to ModelScope Skills
- [ ] Add the `AI PC` custom tag to the Skill
- [ ] Publish the technical article with the `Intel AI PC` topic tag
- [ ] Upload all article images and embed the verified demo video
- [ ] Publish the Xiaohongshu material with both required mentions and topics
- [ ] Verify all public links after publication
- [ ] Submit the final form before 2026-08-31 23:59 CST
- [ ] Optional: collect 3-5 timed task results from interview candidates

External publication items require user accounts and are intentionally not
marked complete by automation.
