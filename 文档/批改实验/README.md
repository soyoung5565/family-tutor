# 周末模拟批改 · 测试与验证档案（2026-09-27 起）

> 本目录 = 周测批改全链路测试/验证遗留物。**所有结论已固化进 skill `family-tutor`**（模型对比、两遍批改、扫描版A/B）。
> 2026-09-29 清场：模拟输出已删、实验中间物已归档 `_archive/`。

## 结构

- **`_originals_20260929/`** —— 作业原件（保真勿动）
  - 5 张手机原照：`phone_20260927_19333`（语文p17·园地）、`19334`（语文p18·判断标点）、`19335`（语文·阅读页·全空）、`19350`（数学·圆面积）、`19351`（数学·推导+练一练）
  - `phone_20260929_204451_yingyu.jpg` —— 英语卷照（66/67 作文页）
  - `scan_yingyu_comp.jpg / scan_yuwen_p17.jpg / scan_yuwen_p18.jpg` —— 3 张"扫描版"

- **`_testset/`** —— 测试装置与数据
  - `truth_lock.json` —— ⭐ **真值表**（用户人工复核锁定：判断√√空空、标点3题、第5张词语/多选、错字项）
  - `scan_ab/` —— 扫描版 vs 照片版 A/B 全部原始读数（含英语精读 4 轮定稿 `bandA2_read.txt`、`bandB2_read_*.txt`）
  - `test_run.py` / `mode_run.py` / `typo_run.py` / `scan_ab.py` —— 对比测试装置
  - `score_and_report*.py` / `scores*.json` —— v1(19项)/v2(28项)/复赛 评分数据
  - `grade_test_yuwen19734.json` —— 两遍批改流水线首次实测输出（EXIT=0）
  - `check_biaodian.png` / `check_panduan.png` —— 复核用对照图

- **`_archive/`** —— 实验中间物（历史证据链，不占视线）
  - `test_in/ test_in2/ test_out/ test_out2/ typo_test/` —— 实验原料图与读数批次
  - `_zoom_test/ _ocr_redo/ _recheck/` —— 早期实验目录
  - `originals中间物/` —— 裁图/过程读数/旧版低清原件
  - `demo模拟-系统/` —— 模拟运行的 学习状态.json
  - ⚠️ 重跑评分脚本时，把需要的目录从 `_archive/` 移回 `_testset/` 即可

- **报告**（本目录根）
  - `批改模型对照实验_结论_20260929.md` —— 模型对比总结论（seed 最优）
  - `批改测试报告_20260927.md` / `详细批改对比报告_20260927.md`
  - `周末卷生成命令.md`

- `_build_demo.py` —— 搭建本模拟目录的脚本

## 关键结论索引（详见 skill family-tutor）

1. **模型**：doubao-seed-2.1pro 最准（23/28）> k3（21/28）> flash（11/28）
2. **两遍批改**：对错批改 + 错字/拼写专项（语文/英语），已进 `grade-mistake.py`（全 seed、并发）
3. **扫描版 A/B**：与照片版平手（21/25 vs 21/25）——不必特意扫描；**放大精读**才是细字（涂改/标点框/拼写）的杠杆
4. **错字检查边界**：AI 能抓"衬/挺/Sanyan/should't"级，但需人工兜底；全页读会脑补修正
