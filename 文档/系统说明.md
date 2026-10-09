# 家庭教师系统 — 文件夹结构与脚本说明

本目录是用户实际部署的家教系统根目录（user 真实使用的电脑，不是开发机）。

## 文件夹结构

```
D:/家教/
├── 语文/
│   ├── 课本/                    # 教材 PDF（整本或分章节）
│   ├── 课件/                    # OpenMAIC 生成的课堂 JSON（每天新课 + 错题微课）
│   ├── 知识点及掌握情况/         # 该科目的全部知识点（结构化 .json + 总览 .md）
│   ├── 错题集/                  # 批改后的错题记录（按日期归档）
│   └── 测验/                    # quiz-data 题库
├── 数学/
│   └── （同上）
├── 英语/
│   └── （同上）
└── 系统/
    ├── README.md                # 本文件
    ├── scripts/                 # 批改/微课/提取脚本
    │   ├── grade-mistake.py
    │   ├── micro-lesson.py
    │   └── extract-knowledge-points.py
    ├── 学习规划.md              # 整体学习计划（哪天学什么）
    └── 学习状态.json            # 全局学习状态（当前进度、累计错题、薄弱点）
```

**注意**：本结构是文档约定，**不需要物理迁移现有文件**。用户在自己的真实电脑上按此结构组织即可。

## 脚本说明

### 1. `scripts/grade-mistake.py` — 错题批改

**何时用**：学生拍照发作业到 Hermes 对话框时调用。

**工作流（关键设计：不信赖学生字迹）**：
1. vision 只看题目文字（不看学生答案）
2. LLM 独立解题（不看学生答案）→ 标准答案 + 解法
3. vision 提取学生答案（标 confidence）
4. 比对：答案错 → 记录错题
5. LLM 列出候选知识点
6. 比对知识点库，匹配到具体小节
7. 写入 `D:/家教/{subject}/错题集/mistake_{date}_{qid}.json`

**调用**：
```bash
python grade-mistake.py --image homework.png --subject math --kp-db "D:/家教/数学/知识点及掌握情况"
```

### 2. `scripts/micro-lesson.py` — 微课堂生成

**何时用**：批改完错题后，针对每道错题生成讲解课。

**关键**：不修改 OpenMAIC 源码。脚本精心构造 requirement 文本，让默认流程产出 slide-only 短课。

**每个错题的硬性结构**：
- 场景 1：错题还原 + 圈出错处
- 场景 2 ~ N+1：每个知识点一页讲解
- 场景 N+2：回归错题，演示正确解法
- 禁止开场白、总结、过渡
- 禁止任何 widget（只 slide）
- 只能引用 knowledgeScope 里的概念

**调用**：
```bash
python micro-lesson.py --subject math --mistakes mistakes.json --scope scope.json
python micro-lesson.py --demo  # 跑内置示例
python micro-lesson.py --no-submit --demo  # 只打印 requirement，不调 OpenMAIC
```

**前置**：OpenMAIC 必须在 `http://localhost:3000` 运行。

### 3. `scripts/extract-knowledge-points.py` — 整本书知识点提取

**何时用**：新学期开始，第一次处理一本教材时。

**工作流**：
1. 把 PDF 渲染成图片（pypdfium2）
2. vision 定位章节边界（找"第X单元"字样）
3. 每个章节调 LLM 提取知识点（结构化 JSON）
4. 每个知识点写一个 `{subject}_day{N}_kp{M}.json`
5. 生成 `overview.md`（章节列表 + 知识点数）让家长扫一眼

**调用**：
```bash
python extract-knowledge-points.py --pdf textbook.pdf --subject math --grade "六年级上册" --dry-run
# dry-run 只渲染 + 打印 prompt，不调 LLM

python extract-knowledge-points.py --pdf textbook.pdf --subject math --grade "六年级上册"
# 完整流程（需先在脚本里 wire 好 LLM 调用）
```

## 与现有 family-tutor skill 的关系

本目录结构与 `family-tutor` skill 完全兼容：
- skill 里的 `materials/{subject}/` → 本目录的 `{subject}/课本/`
- skill 里的 `knowledge-points/{subject}_day{N}.md` → 本目录的 `{subject}/知识点及掌握情况/{subject}_day{N}_kp{M}.json`（从单文件改为每 KP 一个文件）
- skill 里的 `quiz-data/` → 本目录的 `{subject}/测验/`
- skill 里的 `quiz-results/` → 本目录的 `{subject}/错题集/`
- skill 里的 `data/classrooms/`（OpenMAIC 生成）→ 本目录的 `{subject}/课件/`

## 迁移指南（开发机 → 用户机）

1. 用户在自己的电脑上创建 `D:/家教/` 结构（按上面）
2. 把教材 PDF 复制到对应 `{subject}/课本/`
3. 在 Hermes 对话中触发 `extract-knowledge-points.py` 提取知识点
4. 用户扫一眼 `知识点及掌握情况/overview.md`，确认无遗漏
5. 之后正常进入日常学习循环（每天新课 → 课后测验 → 错题批改 → 微课讲解）
