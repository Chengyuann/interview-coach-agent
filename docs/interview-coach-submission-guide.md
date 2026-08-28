# AI 面试陪练官参赛提交导航

官方活动：Production AI Skills 大赛。

当前官方详情 API 的报名截止时间为：

```text
2026-08-31 23:59 CST
```

## 1. 提交文件

| 用途 | 文件 |
|---|---|
| ModelScope Skill 上传 | `dist/interview-coach-agent-0.1.0.zip` |
| 外部评审完整包 | `dist/interview-coach-agent-submission-bundle.zip` |
| Skill ZIP 校验 | `dist/interview-coach-agent-0.1.0.zip.sha256` |
| 评审包校验 | `dist/interview-coach-agent-submission-bundle.zip.sha256` |
| 技术文章正文 | `docs/interview-coach-article-publish.md` |
| 表单提交文案 | `docs/interview-coach-submission-copy.md` |
| 文章图片顺序 | `docs/interview-coach-article-upload-order.md` |
| 练习报告样例 | `examples/interview-coach/pm-practice-report.md` |
| 小红书文案 | `docs/interview-coach-social-copy.md` |
| 公开链接回填 | `docs/publication-links.md` |
| 机器可读证据索引 | `docs/interview-coach-evidence-index.json` |

当前 Skill ZIP：

```text
Size:   2,217,507 bytes
Files:  63
SHA256: 7188cb1458c2dc82a60d77a37afd4d596b50b062b6dee982c0b8a4426b403962
```

## 2. 发布顺序

1. 上传 Skill ZIP 到 ModelScope Skills 中心。
2. 添加自定义标签 `AI PC`。
3. 发布技术文章，添加专题标签 `Intel AI PC`。
4. 按上传顺序加入真实工作台截图、Qoder/百炼证据和演示视频。
5. 将 Skill、文章、视频、源码链接回填到 `docs/publication-links.md`。
6. 发布小红书内容，核对两个账号和五个话题。
7. 使用未登录浏览器逐个验证公开链接。
8. 在 2026-08-31 23:59 CST 前提交比赛表单。

## 3. 核心主张

- 原始语音、转写、反馈和回答对比可在 localhost 完成。
- 输出不是泛化润色，而是六项具体反馈、追问、不编经历的参考表达、二答变化和
  Markdown 练习报告。
- 参考表达只整理候选人已经讲过的内容，不补造雇主、项目、职责、证书或结果数字。
- Qoder CLI 1.1.30 和 TRAE CLI 均真实调用过本地 Skill。
- Qoder 与 TRAE 各进行 3 次全新启动实测，执行 `roles → coach → report`，返回
  4.2 → 6.7（+2.5，`improved`），并生成 6 份统一 SHA 的 Markdown 报告。
- OpenVINO Whisper 已接入当前 CLI 与 localhost 服务，但仍是可选 ASR
  provider；默认中文路径保持 Moonshine。
- 二答完成后可导出本地 Markdown 报告，供候选人归档、导师复盘或企业培训使用。

## 4. 哪些话不能说过头

- GPT-5.5 模拟候选人和专家角色只是 AI 模拟测试，不是真人用户研究。
- Apple Silicon OpenVINO 数据不作为 Intel 性能证明。
- Intel Core i7 数据不外推到 GPU/NPU。
- 反馈不是招聘决策，也不代表真实面试官结论。
- 阿里云 API Key、模型权重和虚拟环境不包含在任何提交 ZIP 中。

## 5. 提交前自动检查

```bash
python3 -m pytest
python3 scripts/validate_package.py .
python3 scripts/build_package.py \
  --output dist/interview-coach-agent-0.1.0.zip
python3 scripts/release_audit.py \
  --archive dist/interview-coach-agent-0.1.0.zip \
  --output build/interview-coach-release-audit.json
python3 scripts/qoder_bailian.py --smoke
python3 scripts/build_interview_submission_bundle.py
```

预期：

- `194 passed`
- package validation passed
- release audit passed
- `QODER_BAILIAN_OK`
- 两个 ZIP 均可完整解压
- 源码、文档和配置中没有明文 API Key

## 6. 当前人工待办

- [x] 发布 ModelScope Skill 并添加 `AI PC`：
  `https://www.modelscope.cn/skills/ayuannn/interview-coach-agent`
- [x] 发布研习社文章并添加 `Intel AI PC`：
  `https://www.modelscope.cn/learn/436039`
- [x] 发布公开源码和演示视频：
  `https://github.com/Chengyuann/interview-coach-agent`
- 发布小红书并添加：
  `@OpenVINO中文社区`、`@魔搭ModelScope社区`、
  `#英特尔`、`#openvino`、`#魔搭`、`#agentic`、`#skills`。
- 回填其余公开链接，并使用未登录浏览器验证 Skill 公开访问。
- 截止前记录三平台累计阅读量。
