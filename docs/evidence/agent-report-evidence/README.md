# Agent 生成练习报告证据

验证日期：2026-08-26

## 验证目标

确认生产力 Agent 不只是读取评分 JSON，而是能够真实完成：

```text
roles -> coach -> report
```

并把最终 Markdown 练习报告写入允许的本地目录。

## 验证结果

| 工具 | 版本 | 启动次数 | 成功 | Bash / 轮 | 报告 |
|---|---|---:|---:|---:|---:|
| Qoder CLI | 1.1.30 | 3 | 3 | 3 | 3 |
| TRAE CLI | 0.120.47 | 3 | 3 | 3 | 3 |

六轮均返回：

```text
第一次回答：4.2
第二次回答：6.7
总分变化：+2.5
结论：improved
```

六份报告均为 3,193 bytes，SHA-256 均为：

```text
47062de9c07f2f37e8d3dec1158527f9e509522a66693be5133f6a727b7eee64
```

这些文件保留 2026-08-26 实测时的原始内容，不做事后改写。当前产品界面和新生成的
报告已改用更自然的展示词，例如“真实可信”“六方面表现”和“注意事项”；分数、
追问及 4.2 → 6.7（+2.5）的结果没有变化。

## 文件写入说明

- 允许写入：`build/agent-report-evidence/*.md`
- Qoder 进行了 3 次全新启动实测，并使用 `--no-session-persistence` 参数。
- TRAE 使用三个独立 session ID，并禁用 Edit、Write 和 Replace 工具。
- 外层验证脚本分别计算每轮执行前后的源码树 SHA-256。
- 六轮源码树指纹全部保持不变。

## 原始证据

- Qoder：
  `docs/evidence/qoder-interview-coach/qoder-bailian-stability-v1.1.30.json`
- TRAE：
  `docs/evidence/trae-interview-coach/trae-stability-v0.120.47.json`
- 汇总：
  `docs/evidence/agent-report-evidence/summary.json`
- 报告文件：
  `build/agent-report-evidence/`
