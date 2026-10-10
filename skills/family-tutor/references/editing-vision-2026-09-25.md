# 课件生成：引入禁令加固 / 剪裁工具 / 视觉切换（2026-09-25 深夜）

## 1. 知识点页“预习引入式开场”→ 已加固
- 问题：知识点页被写成“新课引入”。全库扫描 14 份中 **9 份**有此类开场。
- 修复（`micro-lesson.py` 的 `build_group_requirement`，两轮）：约束2“必须直接精讲”；禁词黑名单（同学们好/大家好/欢迎/今天我们一起来认识·学习/我们一起来看/新朋友）+ 正向首句规则；multi-KP 行标注。实测 m3 两轮后 6/6 零引入 ✓。备份 `.bak-before-no-intro-20260925`。

## 2. 剪裁工具 `scripts/edit-micro-lesson.py`（新）
- `--list` / `--subs-preview N` / `--remove-scenes 4,5 [--keep-audio]` / `--restore-latest`。删场景→音频进 `audio/_removed/`→order 重排→JSON 备份。实测全绿。注意：还原页“错”标注不自动更新；删知识点页前确认无“沿用”。

## 3. Hermes 视觉切到火山方舟（用户指示，2026-09-25 晚）
- minimax-m3 额度用尽（周一重置）；`auxiliary.vision` 已改为 `custom:volcengine / glm-5-3-flash`（改 config 热生效；备份 `config.yaml.bak-before-volc-vision-20260925`）。切回=改回 `minimax-cn / minimax-m3`。火山 plan 端点只接受 plan 内模型（doubao-*-vision 不可用，glm-5-3-flash 可用）。

## 4. “场景1要题目分析”修复（2026-09-25 深夜，用户反馈）
- 反馈：新版第1页只是罗列学生错误答案（“同学写的是56:90，圈出来了…”），没有像旧版 w_oYFkn--W 那样带读题+逐选项分析。
- 修复：`build_group_requirement` 场景1 改为“错题还原 + 题目分析”：拆题（题目在问什么、已知条件、关键句/数量关系、每小题/选项该怎么读）+ 对照学生错误答案（点出错在哪环节），仍不给正确答案。备份 `.bak-before-scene1-analysis-20260925`。
- 实测：m3v3（`l-AVuwboSo`）场景1标题“原题还原与题目分析”，开头“一个字一个字地拆…先把题目读明白” ✓。

## 5. 【重要】语文/英语串科 bug 修复（2026-09-25 深夜重新发现）
- 症状：语文/英语生成的“知识点页”标题显示数学知识点（“整数除以分数”“用圆规画圆”）；课件/索引写进 `数学/` 目录。
- 根因：`micro-lesson.py --subject` 默认 `math`，**不读 mistakes 文件的 subject 字段** → 语文/英语任务（含 2026-09-25 前那批）全部按数学跑。
- 修复：`--subject` 缺省 None → 自动读 `mistakes["subject"]` → 兜底 math；日志会打 `[学科] 自动识读 mistakes 文件 subject = 语文`（务必看到这行）。备份 `.bak-before-subject-autodetect-20260925`。
- 影响：**2026-09-25 前生成的语文/英语课件（4pzXe2uY5d / gcbYojgZ_N / 41LTgoRwju / XAg0UsSinE 等）知识点全部串库，勿复用**；数学索引里错挂的 y*/e* 组已清理（备份 `微课索引…bak-before-subject-cleanup`）。
- 验证：语文 y3（`wizSHbzlo9`）→“知识点：《草原》老舍”；英语 e3（`RWYSrtlq9G`）→“Lesson 2 How to find lost things”。
