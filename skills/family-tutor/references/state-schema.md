# 学习规划 + 学习状态 Schema（2026-09-12 起执行）

## 0. 用途

| 文件 | 角色 | 写时机 |
|---|---|---|
| `D:/家教/系统/学习规划.md` | 整本书排期 + 每周计划 | 每周日 22:00 + 模式切换时 |
| `D:/家教/系统/学习状态.json` | 全局状态机（每个 KP 的掌握度、最近错题、当前模式） | 任何批改完成后立即更新 |

两个文件互为表里：
- `学习规划.md` 是人看的（家长/老师/学生）
- `学习状态.json` 是机器读的（所有脚本的输入）

---

## 1. 学习规划.md 结构

### 1.1 完整骨架

```markdown
# 学习规划（六年级上学期）

> ⚡ 当前模式：{模式}
> 📅 本周：{日期范围}
> 📊 薄弱 KP 数：{N}
> 🎯 本周目标：{一句话目标}
>
> 上次模式切换：{时间}（{触发信号}）

---

## 📖 学期总览

### 数学（北师大版）
- u1 分数除法（6 KP）— Week 1-3
- u2 百分数应用（10 KP）— Week 4-6
- u3 图形的运动（9 KP）— Week 7-9
- ...
- sp1/sp2 数学好玩（机动）
- r1 总复习（4 KP）— Week 18-20

### 语文（统编版）
- u1 自然（6 KP）— Week 1-2
- u2 革命岁月（8 KP）— Week 3-4
- ...
- 习作与综合性学习（机动）

### 英语（粤教沪外版）
- u1 Growing up（6 KP）— Week 1-3
- u2 ... — Week 4-6
- ...
- Project / Review — Week 16-20

> 学期关键节点（基于过往年份，仅作参考，最终看作业信号）：
> - 期中：约 Week 8-10
> - 期末：约 Week 18-20
> - 寒暑假：自主预习模式

---

## 📅 每周计划

### Week 1（{日期}）
**模式**：{模式名}
{完整周计划，参考 weekly-plan-engine.md §3 模板}

### Week 2（{日期}）
...

---

## 🎯 学期目标

- [ ] 三科所有 KP 掌握度 ≥ 80%
- [ ] 期中/期末各科 ≥ 85 分
- [ ] 错题回灌覆盖率 100%
- [ ] 薄弱 KP 数量 < 总 KP 数的 10%
```

### 1.2 关键字段

| 字段 | 说明 | 来源 |
|---|---|---|
| 当前模式 | 横幅显示 | weekly-plan-engine.md §6 |
| 上次模式切换 | 触发信号 | classify-homework.py |
| 本周目标 | 1 句话 | 自动总结 |
| 周计划详细内容 | 每日安排 | generate-weekly-plan.py |

### 1.3 初始化

第一次跑 `init-learning-state.py` 时生成骨架 + Week 1 的基础计划。

---

## 2. 学习状态.json 完整 Schema

### 2.1 顶层结构

```json
{
  "schema_version": "2026-09-12",
  "student": {
    "grade": "六年级",
    "semester": "2026 秋",
    "location": "深圳",
    "active_date": "2026-09-12"
  },
  "subjects": {
    "数学": { ... },
    "语文": { ... },
    "英语": { ... }
  },
  "global": {
    "current_mode": "预习周",
    "current_mode_detail": {
      "数学": "预习周",
      "语文": "预习周",
      "英语": "预习周"
    },
    "last_mode_change": {
      "at": "2026-09-12T01:30:00",
      "subject": "数学",
      "old_mode": "预习周",
      "new_mode": "单元复习周",
      "trigger_signal": "Unit 1 综合练习作业"
    },
    "weak_kps_global": ["数学/u1.k2", "语文/u2.k5"]
  },
  "weekly_history": [
    {
      "week": "Week 1",
      "date_range": "2026-09-01 ~ 2026-09-07",
      "mode": "预习周",
      "exams_generated": [],
      "completion_rate": 0.85
    }
  ],
  "next_actions": [
    "周日下午自动跑 generate-weekly-plan.py",
    "周三开始英语 u1.k2 单词听写"
  ]
}
```

### 2.2 每个科目的 Schema

```json
"数学": {
  "subject_meta": {
    "publisher": "北京师范大学出版社（北师大版）",
    "version": "2026.7.1 版",
    "isbn": "978-7-303-31949-7",
    "total_kps": 61,
    "total_units": 12,
    "kp_index_path": "数学/知识点及掌握情况/index.json"
  },
  "current_unit": "u3",
  "current_kps_in_progress": ["u3.k1", "u3.k2"],
  "kps": {
    "u1.k1": {
      "name": "分数除以整数",
      "unit_id": "u1",
      "master": 75,
      "attempts": 4,
      "correct": 3,
      "last_seen": "2026-09-08",
      "last_correct": true,
      "mistake_types": ["分母漏乘"],
      "consecutive_correct": 2,
      "consecutive_wrong": 0,
      "enabled_in_pool": true
    },
    "u1.k2": {
      "name": "分数除以分数",
      "master": 40,
      "attempts": 5,
      "correct": 2,
      "last_seen": "2026-09-10",
      "last_correct": false,
      "mistake_types": ["除以分数未取倒数", "整数与分数处理混淆"],
      "consecutive_correct": 0,
      "consecutive_wrong": 2,
      "enabled_in_pool": true
    }
  },
  "mistakes_recent": [
    {
      "date": "2026-09-10",
      "kp_id": "u1.k2",
      "qid": "math_u1_k2_mid_003",
      "type": "分数除法",
      "stem_summary": "2/3 ÷ 4/5 = ? 学生答 8/15",
      "expected_answer": "10/12 = 5/6",
      "explanation": "除以分数应取倒数再相乘",
      "remediation_count": 0
    }
  ],
  "exams_history": [
    {
      "date": "2026-09-08",
      "type": "单元复习卷",
      "scope": "u1",
      "score": 80,
      "total": 100,
      "weak_kps_after": ["u1.k2"]
    }
  ],
  "quiz_pool_meta": {
    "total_questions": 200,
    "enabled_questions": 180,
    "last_index_update": "2026-09-12",
    "kp_coverage_pct": 85
  }
}
```

### 2.3 KP master 值计算规则

每 KP 维护 `master` (0–100)。更新规则（详见 weekly-plan-engine.md §5.1）：

```
初始化：master = 0（从未做过）/ 50（已学过但未做练习）/ 历史初始值（如果有）
每次答题后：
  if 答对：master_new = min(100, master_old + 10)
  if 答错：master_new = max(0, master_old - 5)
  if 连续 3 次答对：master_new = min(100, master_old + 15)
  if 连续 3 次答错：master_new = max(0, master_old - 10)

特殊规则：
  - 同 KP 在单元复习卷做对：master += 5（额外奖励）
  - 同 KP 错题回灌卷做对：master += 8（额外奖励）
  - 期中/期末考试加权：分值 × 1.5 计算
```

### 2.4 薄弱 KP 判定

`master < 60` → 自动加入 `global.weak_kps_global`

同时按学科存：
- `学科.weak_kps`：本学科所有 master < 60 的 KP

---

## 3. 初始化流程

### 3.1 触发场景
- 学生首次启用家教系统
- 学生升年级 / 换教材 / 转学

### 3.2 `init-learning-state.py` 做的事

```
[1] 读取三科 KP 索引：
    - 数学/知识点及掌握情况/index.json
    - 语文/知识点及掌握情况/index.json
    - 英语/知识点及掌握情况/index.json

[2] 为每个 KP 创建初始记录：
    - master = 0
    - attempts = 0
    - correct = 0
    - last_seen = null
    - mistake_types = []
    - consecutive_correct = 0
    - consecutive_wrong = 0
    - enabled_in_pool = true

[3] 生成 学习规划.md 骨架：
    - 顶部横幅（current_mode = "预习周"）
    - 学期总览（三科所有 KP 列表 + 预估周次）
    - Week 1 模板（"开学第一周" 通用内容）
    - 学期目标清单

[4] 写入 学习状态.json

[5] 输出汇总报告：
    - 总 KP 数：141
    - 总单元数：25
    - 初始化时间
    - 下次 cron：周日 22:00
```

### 3.3 初始化命令

```bash
python D:/家教/系统/scripts/init-learning-state.py --student "六年级学生" --grade 6 --location 深圳
```

### 3.4 二次初始化（换教材）

如果学生升年级，从 5 年级升 6 年级：
- **不删**旧 学习状态.json，移到 `_meta/archived/grade5_*.json`
- 创建新 学习状态.json 重新初始化
- 学习规划.md 整体替换

---

## 4. 维护规则

### 4.1 谁写
- **学习状态.json**：所有脚本（grade-mistake / classify-homework / generate-exam / weekly-plan）
- **学习规划.md**：仅 `generate-weekly-plan.py` 写完整周计划；其他脚本可追加备注

### 4.2 写入时机
- **学习状态.json**：
  - 每次 grade-mistake 完成 → 更新 `kps[id].master/attempts/correct/last_seen` + `mistakes_recent`
  - 每次 classify-homework 完成 → 检查是否需要更新 `global.current_mode`
  - 每周日 22:00 → 完整更新 + 写入 `weekly_history`
- **学习规划.md**：
  - 每周日 22:00 → 增量更新（追加 Week N+1）
  - 模式切换时 → 更新顶部横幅

### 4.3 备份
- 每周日 cron 备份 `学习状态.json` 到 `D:/家教/系统/_backup/`
- 保留最近 4 周（4 个文件）

### 4.4 跨设备同步
- 走 Git 私有仓库（参考 memory）
- 注意：JSON 文件格式需要稳定，**不要在写入时改字段顺序**（保持稳定的 diff）

---

## 5. 与现有系统集成

### 5.1 输入
- KP 索引（来自 `extract-knowledge-points.py`）
- 错题集（来自 `grade-mistake.py`）
- 学生作业分类（来自 `classify-homework.py`）

### 5.2 输出消费者
- `generate-exam.py`：读 `current_mode` + `weak_kps_global` 出卷
- `weekly-plan-engine.md`：读 master 计算薄弱 KP
- `generate-weekly-plan.py`：写 学习规划.md

### 5.3 与现有 reference 的关系

| 已有的 reference | 内容 | 本文档关系 |
|---|---|---|
| quiz-system-design.md | 答题页 / 批改规则 | 不涉及 |
| remedial-quiz-workflow.md | 补强流程 | 本文档的 weak_kps 是其上游 |

---

## 6. 边界情况

| 情况 | 处理 |
|---|---|
| 学生某 KP 错了 5 次后突然全对 | master 缓慢回升（每周 +10 上限） |
| 学生某 KP 一直满分 | master 保持高位，但每 2 周抽样测一次防退化 |
| 学生某 KP 完全跳过 | master = 0，attempts = 0；周计划自动排入预习 |
| 错题集清理 | 移到 `_meta/archived/mistakes/` 但 master 不重置（半年观察） |

---

## 7. 示例：初始化后的状态（节选）

```json
{
  "schema_version": "2026-09-12",
  "student": {
    "grade": "六年级",
    "semester": "2026 秋",
    "location": "深圳",
    "active_date": "2026-09-12"
  },
  "global": {
    "current_mode": "预习周",
    "current_mode_detail": {
      "数学": "预习周",
      "语文": "预习周",
      "英语": "预习周"
    },
    "last_mode_change": null,
    "weak_kps_global": []
  },
  "subjects": {
    "数学": {
      "subject_meta": {
        "publisher": "北京师范大学出版社（北师大版）",
        "total_kps": 61,
        "total_units": 12,
        "kp_index_path": "数学/知识点及掌握情况/index.json"
      },
      "current_unit": "u1",
      "kps": {
        "u1.k1": { "master": 0, "attempts": 0, "correct": 0, ... },
        "u1.k2": { "master": 0, "attempts": 0, "correct": 0, ... },
        ...
      },
      "mistakes_recent": [],
      "exams_history": []
    },
    "语文": { ... },
    "英语": { ... }
  }
}
```

---

## 8. 升级迁移

未来 schema 升级时（如加新字段）：
- 在 init-learning-state.py 加 `--migrate` 选项
- 读旧 schema → 转换 → 写新 schema
- 旧版本放 `_meta/schema-versions/v1.json` 保留
