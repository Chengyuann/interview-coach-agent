# AI 面试陪练官文章上传顺序

文章正文使用 `docs/interview-coach-article-publish.md`。该文件由下面的命令生成，
会合并源稿中仅用于本地阅读的手工换行，避免 ModelScope 编辑器把正文限制在左侧：

```bash
python3 scripts/build_interview_article_publish.py
```

## 图片

按正文出现顺序上传以下 11 张图片：

1. `docs/submission-assets/article/01-start.png`
   - 标题：选择岗位与面试题
2. `docs/submission-assets/article/02-first-answer.png`
   - 标题：第一次回答原文
3. `docs/submission-assets/article/02-product-workflow-drawio.png`
   - 标题：面试练习工作流
4. `docs/submission-assets/article/03-feedback.png`
   - 标题：首答六方面反馈与优先修改点
5. `docs/submission-assets/article/04-second-answer.png`
   - 标题：补齐事实和指标后的第二次回答
6. `docs/submission-assets/article/05-improved.png`
   - 标题：二答提升对比
7. `docs/submission-assets/article/08-report-download.png`
   - 标题：二答完成后的练习报告下载入口
8. `docs/submission-assets/article/png/07-intel-openvino-benchmark.png`
   - 标题：Intel CPU OpenVINO Whisper 单样本实测
9. `docs/submission-assets/article/06-role-switch.png`
   - 标题：四岗位复用
10. `docs/submission-assets/article/07-mobile-start.png`
   - 标题：移动端布局
11. `docs/submission-assets/article/interview-coach-demo-contact-sheet.jpg`
    - 标题：演示视频关键帧联系表

## 视频

上传或嵌入：

```text
output/interview-coach-redesign/interview-coach-demo-v2.mp4
```

视频已经过完整解码、黑帧和长静音检查；时长 38.60 秒，1920x1080，
H.264 + AAC。内容包含 4.2 → 6.7 对比、真实报告下载和报告内容展示。

## Qoder 证据

文章中的 Qoder 结果必须与以下原始证据一致：

```text
docs/evidence/qoder-interview-coach/
  qoder-bailian-skill-invocation-v1.1.30.txt
  qoder-bailian-skill-invocation-v1.1.30.status.json
```

关键结果：

```text
First answer total: 4.2
Second answer total: 6.7
Total delta: +2.5
Verdict: improved
```

## 发布检查

- 专题标签：`Intel AI PC`
- Skill 链接已加入正文
- 源码链接可匿名访问
- 11 张图片全部显示
- 视频可以播放
- 没有写入本地绝对路径或 API Key
