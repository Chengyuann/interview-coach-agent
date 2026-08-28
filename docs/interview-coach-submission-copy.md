# AI 面试陪练官提交文案

## 作品名

AI 面试陪练官 / `interview-coach-agent`

## 一句话介绍

本地运行的语音面试练习 Skill：回答一道题后，立即获得六项反馈、追问、不编经历的参考表达、
二答提升对比和可归档的练习报告。

## 建议标签

- Skills 中心自定义标签：`AI PC`
- 研习社专题标签：`Intel AI PC`
- 内容关键词：本地语音、面试练习、Agent Skill、OpenVINO、Hybrid AI

## 使用场景

候选人练习行为面试、产品经理/算法工程师/销售/运营岗位题，想知道回答是否有 STAR 结构、是否有数字、本人贡献是否清楚，以及第二次回答是否真的变好。

## 核心亮点

- 支持文本和浏览器麦克风输入。
- 按 AIPC local skill authoring 参考补齐 `run.ps1` 固定入口、named pipe
  常驻服务、`.partial` 模型准备和 `--continue` 续跑。
- Moonshine 中文模型在 localhost 本地转写。
- OpenVINO Whisper 已接入同一 CLI 和 localhost 服务，可作为显式可选 ASR provider。
- 四岗位题库和岗位关键词。
- 六项反馈：STAR 结构、具体程度、数据量化、岗位匹配、表达清晰、真实可信。
- 参考表达只整理候选人已经讲过的内容；缺少数字或本人贡献时，明确提示继续补充。
- 二答和首答按总分及维度差值对比。
- 二答完成后可导出 Markdown 练习报告，供候选人归档、导师复盘或企业培训使用。
- TRAE CLI 与 Qoder CLI 均已真实调用本地 Skill。两个工具各进行 3 次全新启动实测，
  每轮执行 `roles → coach → report`，返回首答 4.2、二答 6.7、提升 +2.5，
  并生成 Markdown 报告。
- GPT-5.5 模拟了三种候选人回答风格，阅读反馈后二答平均提升 1.467 分；这只是 AI 模拟测试，不冒充真人试用。

## 复现命令

```bash
python3 -m pytest
python3 scripts/evaluate_interview_coach.py
python3 scripts/generate_interview_audio.py
.venv-moonshine/bin/python scripts/run_interview_audio_smoke.py
python3 scripts/qoder_bailian.py --smoke
python3 scripts/build_package.py --output dist/interview-coach-agent-0.1.0.zip
python3 scripts/build_interview_submission_bundle.py
```

## 证据摘要

- 8 组预设面试题测试：8/8 passed，覆盖四岗位，平均提升 2.76 分。
- 真实本地语音：16.336 秒音频，Moonshine 推理 0.651056 秒，RTF 0.039854，评分 6.0 / 7；参考文本覆盖率和转写精确率均为 100%，CLI 与 localhost 两条路径均通过 90% ASR 质量门。
- VoxCPM2 语音闭环：首答 3.0、二答 6.3，提升 +3.3；Moonshine RTF 0.031928 / 0.043800。
- OpenVINO 当前产品路径：CLI 与 localhost 服务均通过，17.60 秒音频 RTF 分别为 0.010778 / 0.015237；该组为 Apple Silicon 功能 smoke，不作为 Intel 性能证据。
- Intel OpenVINO 独立实测：Core i7-12650H、Whisper Base INT8、27.055 秒音频推理 1.409 秒、RTF 0.0521；中文准确率不足，因此不替换默认 Moonshine。
- GPT-5.5 AI 模拟候选人：3/3 二答提升，平均 +1.467；不是真人用户研究。
- 全量测试：194 passed。
- AIPC local Skill 合同：`run.ps1`、`install-env.ps1`、`client.py/server.py`
  named pipe、模型 `.partial` 原子准备、`--continue` 和 `tests/test.ps1`
  均已纳入发布审计。
- 发布包：`dist/interview-coach-agent-0.1.0.zip`，2,217,522 bytes、63 个文件，
  低于 5 MB，release audit passed；SHA-256 为
  `42a6be653667f03621155ecd08f9813e6bccc7b66d8be851f583d6e14de6b1b5`。
- 演示视频：`output/interview-coach-redesign/interview-coach-demo-v2.mp4`，
  38.60 秒，1920x1080，MCY 音色旁白，展示 4.2 → 6.7、真实报告下载和报告内容；
  H.264 + AAC，无内嵌字幕，视频 QA passed。
- Localhost 服务稳定性：`/v1/interview/coach` 连续 40 次请求全部通过，覆盖 8 个问题场景，错误数 0，中位延迟 0.001739 秒。
- 工具调用验证：Qoder CLI 1.1.30 与 TRAE CLI 0.120.47 各进行 3 次全新启动实测，
  共 6/6 完成 `roles → coach → report`。六份报告均为 3,193 bytes，SHA-256
  均为 `47062de9c07f2f37e8d3dec1158527f9e509522a66693be5133f6a727b7eee64`；
  六轮源码树执行前后指纹一致。证据位于
  `docs/evidence/agent-report-evidence/summary.json`。

## 技术架构

Windows Host → `scripts\run.ps1` → `install-env.ps1` → 短生命周期
`client.py` → named pipe 常驻 `server.py` → Moonshine 中文 ASR（默认）/
OpenVINO Whisper（可选）→ 六项稳定反馈 → 追问、不编经历的参考表达和二答对比。
浏览器工作台、Qoder 和 TRAE 都调用同一套本地逻辑，因此看到的反馈保持一致。

## 使用说明

这些反馈只用于练习，不用于自动招聘决策。参考表达只整理候选人已经说出的内容，不补造雇主、项目、职责、证书或结果数字。

API Key、模型权重和虚拟环境不进入 Skill ZIP。Qoder 百炼凭据从仓库外部 CSV
读取，只注入子进程环境；提交包中仅包含 `${DASHSCOPE_API_KEY}` 占位符。

## 公开链接待填

- ModelScope Skill：https://www.modelscope.cn/skills/ayuannn/interview-coach-agent
- 魔搭研习社文章：https://www.modelscope.cn/learn/436039
- Demo 视频：https://github.com/Chengyuann/interview-coach-agent/blob/main/demo/interview-coach-demo-v2.mp4
- 公开源码：https://github.com/Chengyuann/interview-coach-agent
- 小红书：
