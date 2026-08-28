# AI 面试陪练官

AI 面试陪练官是一个本地运行的语音面试练习 Agent。用户回答一道真实面试题后，系统立即返回：

- STAR 结构、具体程度、数据量化、岗位匹配、表达清晰、真实可信六项反馈；
- 最优先需要修改的问题；
- 面试官可能继续追问的问题；
- 不编经历的参考表达；
- 第二次回答相对首答的总分和各维度变化；
- 可供候选人、导师或企业培训复盘的本地 Markdown 练习报告。

当前支持产品经理、算法工程师、销售和运营岗位。

## 公开入口

- ModelScope Skill：https://www.modelscope.cn/skills/ayuannn/interview-coach-agent
- 技术文章：https://www.modelscope.cn/learn/436039
- 演示视频：[demo/interview-coach-demo-v2.mp4](demo/interview-coach-demo-v2.mp4)

## 已验证结果

- 8 组预设面试题测试：8 / 8 通过，覆盖四岗位，二答平均提升 2.76 分。
- 本地语音 smoke：16.336 秒音频，Moonshine RTF 0.039854；参考文本
  覆盖率和转写精确率均为 100%，评分 6.0 / 7。
- Qoder CLI 1.1.30：通过阿里云百炼
  `bailian/qwen3.8-max-pg` 真实调用本地 Skill，3 次从空白状态启动
  3 / 3 完成 `roles → coach → report`，复现 4.2 → 6.7（+2.5）。
- TRAE CLI 0.120.47：3 次全新启动实测，3 / 3 完成同一三步工作流。
- 两个工具共生成 6 份 Markdown 报告，SHA-256 均为
  `47062de9c07f2f37e8d3dec1158527f9e509522a66693be5133f6a727b7eee64`；
  每轮源码树指纹保持不变。
- Localhost `/v1/interview/coach` 稳定性：40 / 40 连续请求通过，错误数 0。
- 自动测试：194 passed。

## AIPC Local Skill 入口

正式发布包同时补齐了 AIPC local skill authoring 参考结构：

- `scripts\run.ps1` 是 Windows Host 固定入口；
- `scripts\install-env.ps1` 读取 `info.json`，按 `requirements.txt` 创建本地 venv；
- `scripts\client.py` 是短生命周期客户端，通过 named pipe 调用常驻 `scripts\server.py`；
- 模型使用 `.partial` 目录准备，校验 `required_files` 后原子落盘；
- 首次准备超时会保存 pending request，并要求 `scripts\run.ps1 --continue` 续跑；
- OpenVINO provider 自动优先 Intel GPU、回退 CPU；`auto` 模式下 OpenVINO 运行时不可用时回退本地 Moonshine，不使用云端。

标准映射见 `references/aipc-local-skill-standard.md`。

## 直接体验

首次启用本地语音：

```bash
python3 scripts/install_moonshine_env.py
.venv-moonshine/bin/python scripts/prepare_moonshine_models.py
```

启动包含本地中文语音模型的服务：

```bash
.venv-moonshine/bin/python scripts/interview.py service --preload zh
```

然后打开：

```text
http://127.0.0.1:8876
```

工作台支持键盘输入和浏览器麦克风。录音仅发送到本机 localhost，由 Moonshine 在本地转写。

### 可选 OpenVINO ASR

Moonshine 保持默认中文路径。需要验证 OpenVINO 当前产品路径时，使用独立环境：

```bash
python3.12 -m venv .venv-openvino-whisper
.venv-openvino-whisper/bin/python -m pip install \
  -r requirements-openvino-whisper.txt
.venv-openvino-whisper/bin/python \
  scripts/download_openvino_whisper_model.py \
  --model-id OpenVINO/whisper-tiny-int8-ov \
  --output models/openvino/whisper-tiny-int8-ov
```

OpenVINO CLI 转写：

```bash
.venv-openvino-whisper/bin/python scripts/interview.py transcribe \
  --audio answer.wav \
  --language zh \
  --output build/openvino-answer.jsonl \
  --evidence build/openvino-answer-evidence.json \
  --asr-provider openvino \
  --openvino-model-dir models/openvino/whisper-tiny-int8-ov \
  --openvino-device CPU
```

OpenVINO localhost 服务：

```bash
.venv-openvino-whisper/bin/python scripts/interview.py service \
  --asr-provider openvino \
  --openvino-model-dir models/openvino/whisper-tiny-int8-ov \
  --openvino-device CPU
```

模型权重和虚拟环境不进入 Skill ZIP。OpenVINO tiny INT8 是可选部署路径；当前中文准确率不如默认 Moonshine，因此不自动替换默认 provider。

## CLI

查看岗位和题目：

```bash
python3 scripts/interview.py roles
```

分析一次回答：

```bash
python3 scripts/interview.py coach \
  --role product-manager \
  --question-id pm-impact \
  --answer "我做过一个增长项目，后来效果明显变好。"
```

比较首答和二答：

```bash
python3 scripts/interview.py coach \
  --input examples/interview-coach/pm-second-answer.json \
  --output build/interview-coach-result.json \
  --overwrite
```

导出一份可直接归档或交给导师复盘的练习报告：

```bash
python3 scripts/interview.py report \
  --input examples/interview-coach/pm-second-answer.json \
  --output build/interview-practice-report.md \
  --overwrite
```

## 在 Qoder 和 TRAE 中实测

Qoder 使用仓库外部的阿里云百炼 CSV 凭据。通过
`QODER_BAILIAN_CREDENTIALS` 指定凭据文件路径。API Key 只在启动 Qoder
进程时注入，不写入仓库、Skill ZIP 或提交包。

```bash
# 检查 Qoder 可见模型
python3 scripts/qoder_bailian.py --list-models

# 非交互真实推理
python3 scripts/qoder_bailian.py --smoke

# 使用百炼模型启动交互式 Qoder
python3 scripts/qoder_bailian.py

# 3 个无状态会话：roles -> coach -> report
python3 scripts/run_qoder_bailian_stability.py

# 3 次全新启动 TRAE 实测：roles -> coach -> report
python3 scripts/run_trae_interview_stability.py
```

成功的完整 Skill 调用日志和机器可读状态文件包含在外部评审包中。

## Localhost API

不需要语音时，可用系统 Python 启动文本版本：

```bash
python3 scripts/interview_server.py --port 8876
```

主要接口：

```text
GET  /v1/status
GET  /v1/interview/roles
POST /v1/interview/coach
POST /v1/interview/report
POST /v1/interview/transcribe
```

## 使用说明

- 评分用于练习反馈，不用于自动招聘决策。
- 参考表达只整理候选人已经提供的内容。
- 缺少的结果、数字或本人贡献会显示为明确占位符，不会自动补造。
- 当前规则引擎强调可解释和可复现，后续可接入更强的本地模型。

## 发布包自检

一条命令检查完整的离线交付流程：

```bash
python3 scripts/verify_interview_submission.py
```

该命令验证岗位、两轮评分、Markdown 报告、localhost 报告接口、Skill ZIP 和
发布审计，不调用云端服务。

完整测试：

```bash
python3 -m pip install "pytest>=8,<9"
python3 -m pytest tests/release -q
python3 scripts/evaluate_interview_coach.py
python3 scripts/validate_package.py .
```

## License

Apache-2.0
