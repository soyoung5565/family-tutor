# Day-1 三件套流水线（2026-09-26 建成）

## 0. 一句话
拿到孩子当天的错题 → 一条链完成：批改 → **错题文字清单（学生版·无答案）+ 自动生成错题讲解课堂**（流程默认步骤！不是等家长愿意看才做）/KP 漏洞分析/进度判定/错题入库/周计划刷新。

## 1. 命令（实测全绿）
```
# 拍照 → 结构化错题（火山 vision+LLM；逐小题判卷；正确题标 is_correct=true）
D:/Python312/python.exe D:/家教/系统/scripts/grade-mistake.py --image 作业照.jpg --subject 数学 --out 结果.json

# 三件套（自动跳过 is_correct=true 的题）
D:/Python312/python.exe D:/家教/系统/scripts/day1-pipeline.py --mistakes 结果.json            # 正式
D:/Python312/python.exe D:/家教/系统/scripts/day1-pipeline.py --mistakes 结果.json --dry-run   # 试跑
```
- day1 一步到位：①KP 漏洞分析+写 学习状态.json ②学校进度判定（调 classify-homework --no-write --kps，关键词立即切、密度信号需≥2次确认、复习→预习 7 天冷却）③错题入 `{科目}/错题集/错题集_YYYY-MM.json`（去重）→ ④自动跑 generate-weekly-plan.py。
- 测试记录（2026-09-26 凌晨，合成作业图 homework_test1.png）：3 小题逐题判卷（对/错/错）→ 跳对 → +2 入库 → 状态/周计划更新 ✓。

## 2. 周计划（generate-weekly-plan.py，2026-09-26 新建）
- 读 学习状态.json + 错题集 → 更新 `系统/学习规划.md`（本周块 upsert + 横幅）+ 写 `系统/周计划状态.json`（hook 用）。
- **不用 cron**：time-inject-hook.py 已扩展——跨周未更新时注入提醒；开发期静默（marker 不存在就不提醒）。

## 3. 学情闭环缺件审计（2026-09-25 → 09-26 修复情况）
| 构件 | 状态 |
|---|---|
| grade-mistake.py | ✅ 已接线（火山）；逐小题；is_correct 标记 |
| classify-homework.py | ✅ 可用（+--no-write/--kps 参数；密度判定可用了） |
| generate-weekly-plan.py | ✅ 新建（含 dry-run） |
| day1-pipeline.py | ✅ 新建（三件套编排） |
| 错题集 | ✅ 数学已建；语文/英语目录在首次入库时自动创建 |
| 周计划触发 | ✅ hook 注入（非 cron） |
| 维护责任条款 | ✅ SKILL.md 0.3（建立 init 脚本；每次作业后三处更新） |

## 4. 状态文件小知识
- 学习状态.json 的 `global.signal_log`（day1 写入）用于防抖；`weak_kps_global` 汇总三科薄弱。
- 周计划“学生最近表现/回灌清单”数据源：`mistakes_recent` + 错题集近7天。

## 5. 流程补正（2026-09-26 用户两次纠正，必须遵守）
1. **批改完 = 立即两条动作**：①错题用文字直接打出来（学生版清单，无答案）发给家长/孩子；②自动生成错题讲解课堂（day1-pipeline 默认已拉起，`--no-microlesson` 仅例外）。不再有“家长愿意看才做视频”的表述——那是误读。
2. **“家长未必看视频”的正解**：警戒句——不要因为家长/孩子没看视频，就把“记录学校学习进度 + 记录学生知识点漏洞”也忘了。这两项是铁律，与是否观看无关；三件套（分析/进度/入库）在任何情况下都必须照做。
3. **备份与家教无关**：用户提“像 Hermes 周一备份那样”只是**借用 hook 注入机制**做触发器；**家长端不需要备份 Hermes**，家教部署里不包含备份逻辑。
