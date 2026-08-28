# AI 面试陪练官小红书文案

## 标题

我做了一个不替你编经历的本地 AI 面试陪练

## 正文

很多面试工具会直接生成一段“标准答案”，但真正面试时最容易被追问击穿的，
恰恰是它替你补出来的项目、数字和个人贡献。

这次做了一个本地运行的 AI 面试陪练 Skill：

- 对着电脑回答一道真实面试题
- 本地 Moonshine 转写语音
- 从 STAR、具体程度、数据量化、岗位匹配、表达清晰、真实可信六方面给反馈
- 给出面试官可能继续追问的问题
- 给一版不编经历的参考表达；缺数字、缺本人贡献，就直接提醒你补
- 第二次回答后，直接展示总分和六项维度变化
- 二答完成后可以下载 Markdown 练习报告，用于个人归档或导师复盘

8 组预设面试题测试全部通过，覆盖四个岗位，二答平均提升 2.76 分。

Qoder 和 TRAE 都真实调用过这个 Skill。两个工具各进行 3 次全新启动实测，执行
`roles → coach → report`，样例从 4.2 提升到 6.7，差值 +2.5，并真实生成
6 份内容一致的本地练习报告。

录音、转写、反馈和二答对比都可以在 localhost 完成；OpenVINO Whisper 也已
接入当前 CLI 和服务，作为可选部署路径。

它不是招聘决策工具，而是帮助候选人发现“哪里还没讲清、哪里缺数字、哪里没说清
本人贡献”的练习工具。

Skill 链接：`[发布后回填]`

技术文章：`[发布后回填]`

## 必需账号与话题

```text
@OpenVINO中文社区
@魔搭ModelScope社区
#英特尔
#openvino
#魔搭
#agentic
#skills
```

## 配图顺序

1. `captures/01-start.png`
2. `captures/03-feedback.png`
3. `captures/05-improved.png`
4. `docs/submission-assets/article/08-report-download.png`
5. `captures/06-role-switch.png`
6. `qa/contact-sheet.jpg`
