---
name: family-tutor
description: 家庭教师系统 - 学习规划、AI课堂、测验分析、查漏补缺闭环
tags: [education, tutor, learning, openmaic, quiz, open-design]
---

---

# 家庭教师系统

## ⚡ 触发即生效的硬性规则

任何题库搜索、3 模型投票、跨版本判定、AI 自审、批改/出卷/交付相关任务，进入时**先按下面各条执行**，再去读对应 references：

1. **搜题必须用 `multi-search-engine` skill**（百度千帆 + Tavily 双 API，content 字段含题面预览）。Hermes 自带 `web_search` 命中率 < 20%，不要用。详见 §「2026-09-12 系统升级」§0 题库建设硬性门。
2. **课后习题不入题库**。学生课堂已做，再做无练习价值。只可入 `_meta/reference_pool/` 做 AI 参考素材，不参与出卷。
3. **3 模型投票必须串行**（MiniMax-M3 / muse-spark-1.3-contributor / deepseek-v4-pro），不可并发；DS-Pro 是 reasoning 模型 `max_tokens ≥ 3000`；Muse 必须 `/v1/responses` + 不带 `-free` 后缀。详见 §0.2。
4. **错题本提醒 + 历史错题「必做」（always-on，2026-09-27）**：① 每日批改交付必附「错题本提醒」；② 周末交付（计划/试卷/消息）必附「错题本复盘」；③ 小试卷含历史错题回灌且学生再次做错 → 必须标「必做」。固定话术与机制见 §0.5，脚本已内置（day1-pipeline / generate-exam）。
5. **语文/英语批改必须查错字/拼写（2026-09-29 用户明确要求）**：批改语文、英语作业**不能只判对错**——必须逐字辨认：① 语文：有没有**错别字**、字本身是否**写错**（偏旁部首写错、缺笔、多笔，如「衬」衤写成礻、「挺」壬少一横）；② 英语：单词有没有**拼错**。注意：常规「转录式」读法下模型会把错字“脑补”成对的（2026-09-29 实测：三模型全漏报「挺」；「衬」仅 2/3 家报中，且同一模型同图两次跑可翻转）——错字/拼写检查必须走「**放大裁切＋逐字查错指令＋人工兜底**」的专项流程（参见下方「识别复核工作流」条目），检查结果**单独列出**，不混在对错批改里。

---

# 家庭教师系统

## 🧭 工作风格与反思坑（always-on）

1. **不擅自删除任何已建文件/脚本/数据**。删之前必须先确认，旧数据先移到 `_backup/` 或 `_meta/archived/` 而不是 `rm`。任何"是不是该删"的判断都不要替用户做。
2. **调研阶段"急没有用"**。题库建设、AI 自审规则、跨版本判定这类定方向的活，必须慢而扎实把机制吃透再动手。**不要为了推进度赶着试错**——试错成本比慢想成本高。
3. **不主动关闭用户已启用的服务**（clash、new-api、hermes-agent 等）。要操作前先 `tasklist` 看进程，问用户是否能关。
4. **用户给的"参考资料"先扫一眼再开始干**。比如今天用户贴了 4 个 URL，期望是"立刻去爬"，不是"先讨论可行性"。
5. **"敷衍选项"信号**：当用户用"我真是无语了"/"鬼扯"/"算了"/"先停"等词时，意味着你之前给的方案没尽力、没穷尽可能。立刻停止当前方向，列出所有可走的路径（包括依赖用户/付费/第三方），让用户选，而不是替用户拍板。
6. **解释流程时少铺垫多结果**。当用户问"准备就绪了吗"/"行不行"时，直接回答 + 给当下能立刻做的事，不要再问一轮细节。

## 📦 2026-09-08 系统升级：微课堂 + 图片批改 + 知识库结构重组

**本次新增三件事**（开发机验证完成，用户真实电脑按文档约定部署即可，**不需要物理迁移现有文件**）：

### 1. 文档结构（用户真实电脑按此组织）

```
D:/家教/
├── {语文|数学|英语}/              # 按科目分大目录
│   ├── 课本/                      # 教材 PDF
│   ├── 课件/                      # OpenMAIC 生成的课堂 JSON
│   ├── 知识点及掌握情况/           # 结构化 JSON（每个 KP 一个文件）+ 总览 MD
│   ├── 错题集/                    # 批改后的错题记录
│   └── 测验/                      # quiz-data 题库
└── 系统/
    ├── README.md                  # 完整说明文档
    ├── scripts/
    │   ├── grade-mistake.py       # 图片批改（独立 vision + 独立解题）
    │   ├── micro-lesson.py        # 微课堂生成（拼 requirement + 调 OpenMAIC）
    │   └── extract-knowledge-points.py  # 整本书知识点提取
    ├── 学习规划.md                # 整体学习计划
    └── 学习状态.json              # 全局学习状态
```

**与旧路径映射**：
- `materials/{subject}/` → `{subject}/课本/`
- `knowledge-points/{subject}_day{N}.md` → `{subject}/知识点及掌握情况/{subject}_day{N}_kp{M}.json`（每个 KP 一个文件）
- `quiz-data/` → `{subject}/测验/`
- `quiz-results/` → `{subject}/错题集/`
- `data/classrooms/`（OpenMAIC） → `{subject}/课件/`

**重要**：开发机 `D:/projects/family-tutor/` 是开发环境，用户真实电脑按上述结构组织即可，不需要物理迁移。

### 2. 图片批改流程（**两阶段：先订正、再讲解** ← 2026-09-24 用户流程调整）

**⚠️ 流程变更（用户明确要求，取代旧单阶段流程）**

旧流程：批改 → 直接给正确答案 + 微课堂。
**新流程（两阶段）**：
```
【第一次】批改 → 只告诉学生“哪几题错了”（不给答案/解法/错因）
              ↓  学生自己订正（拍照/文字回传）
【第二次】对比订正 → 订正对的表扬，仍错的才给正确答案 + 微课堂
```

**为什么**：让学生先自己订正，保留思考机会；直接给答案等于剥夺练习。

**实现（两个新脚本，均已实测）**

| 阶段 | 脚本 | 作用 |
|---|---|---|
| 第一次反馈 | `系统/scripts/wrong-list.py` | 从批改结果生成**订正清单**，**硬剔除** `correct_answer/correct_solution/common_mistakes`（内置泄漏检查） |
| 订正对比 | `系统/scripts/collect-corrections.py` | 对比学生订正 vs 标准答案（数字/单位宽松归一化），输出**仍错题.json** + **订正报告.md** |
| 第二次反馈 | `系统/scripts/micro-lesson.py`（现有） | 用 `仍错题.json` 生成答案 + 微课堂 |

```bash
# 第一次：批改后生成订正清单（无答案）
python 系统/scripts/wrong-list.py --mistakes mistakes.json --subject 数学
#   → 错题清单_YYYY-MM-DD.md / .html（学生版，无答案）

# 第二次：学生订正后对比
python 系统/scripts/collect-corrections.py --mistakes mistakes.json \
       --corrections corr.json --subject 数学
#   → 仍错题_YYYY-MM-DD.json（喂给 micro-lesson.py）
#   → 订正报告_YYYY-MM-DD.md（学生版：哪些订正对了）

# 第三次：对仍错的题生成答案 + 微课堂
python 系统/scripts/micro-lesson.py --subject math --mistakes 仍错题_YYYY-MM-DD.json
```

**纠正录入**：`corr.json` 支持 `{"q1": "9人"}` 或 `[{"id":"q1","corrected_answer":"9人"}]`；学生拍图时先 vision 提取答案再转 json。

**第一次反馈 = 纯文字（不是 HTML！2026-09-24 用户纠正）**

发给学生的**只能是纯文字**，直接粘到微信/对话框：
```
这次批改有 N 道题做错了，请你重新做一遍。

1. <原题干>
   （你上次写的：<学生答案>）

做完后把新的解答拍照发我，我再给你正确答案和讲解。
```
禁止把 HTML/网页/文件当成“发给学生”的形式（HTML 只当内部草稿）。生成：`python 系统/scripts/wrong-list.py --mistakes mistakes.json --subject 数学 --text-only`。

**第二次输入 = 学生重新发图（2026-09-24 用户明确）**

学生订正后**会重新发一张图片**（不是文字回填）。处理方式：
1. Agent 用 **vision 读图**（按题号逐题提取学生新答案，标 confidence；字迹不清就标低置信并回问）
2. 转成 `corr.json`（`{"q1":"9人"}` 或 `[{"id":"q1","corrected_answer":"9人"}]`）
3. `python 系统/scripts/collect-corrections.py --mistakes mistakes.json --corrections corr.json --subject 数学`
4. 输出：`仍错题_日期.json`（→ micro-lesson）+ `订正报告_日期.md`（纯文字发学生）

**称呼铁律**：面向学生/家长的所有文案用「你」，禁止直呼学生姓名。

**❗ 中英目录映射坑（已修，2026-09-24）**：`micro-lesson.py` 等脚本的参数习惯用 `--subject math/chinese/english`，但**用户真实目录是中文**（`D:/家教/数学/知识点及掌握情况/`）。不映射就会 `subj_dir` 找不到、`auto-loaded 0 knowledge points` → 微课堂失去 knowledgeScope 约束（可能讲超纲）。现已内置 `SUBJECT_ALIAS` + `resolve_subject()`（math↔数学 / chinese↔语文 / english↔英语），**新写脚本一律复用**。验收标准：跑 `micro-lesson.py --subject math --mistakes <真实错题> --no-submit` 必须输出 `auto-loaded N knowledge points`（N>0）。

---

### 2b. 图片批改内部流水线（两阶段共用的前段）

**关键设计：不信赖学生字迹**（字丑 → vision 误识别 → 错误归因）

```
学生拍照 → 发到 Hermes 对话框
       ↓
[Step 1] vision 只看题目文字（独立，不看学生答案）
       ↓
[Step 2] LLM 独立解题（不看学生答案） → 标准答案 + 解法
       ↓
[Step 3] vision 提取学生答案（标 confidence）
       ↓
[Step 4] 比对：答案错 → 记录错题
       ↓
[Step 5] LLM 列候选知识点
       ↓
[Step 6] 比对 {subject}/知识点及掌握情况/ 数据库，匹配到具体小节
       ↓
[Step 7] 写入 {subject}/错题集/mistake_{date}_{qid}.json
```

**由 Hermes 直接执行，不需要新接口。** 脚本 `grade-mistake.py` 提供 prompt 模板和 KP 匹配函数。

### 3. 微课堂生成（基于 OpenMAIC，**不修改源码**）

**核心理念**：不修改 OpenMAIC 任何代码。脚本精心构造 requirement 文本，让默认流程产出符合要求的短课。

**每道错题的硬性结构**（脚本里硬约束，不靠 LLM 自觉）：
- 场景 1：错题还原 + 圈出错处（不给答案）
- 场景 2 ~ N+1：每个知识点一页讲解（N = 涉及知识点数）
- 场景 N+2：回归错题，演示正确解法
- 禁止开场白、总结页、错题间过渡页
- 禁止任何 widget（simulation/diagram/game/3d/code/quiz）
- 只能引用 knowledgeScope 里的概念（防超纲物理边界）

**调用**：
```bash
# 真实批改流程
python D:/家教/系统/scripts/micro-lesson.py --subject math --mistakes mistakes.json --scope scope.json

# 仅打印 requirement（OpenMAIC 没启动时调试用）
python D:/家教/系统/scripts/micro-lesson.py --demo --no-submit

# 内置示例
python D:/家教/系统/scripts/micro-lesson.py --demo
```

**前置**：OpenMAIC 必须在 `localhost:3000` 运行。

### 4. 整本书知识点提取（新学期第一次处理教材时）

```bash
# 只渲染 + 打印 prompt（无 LLM 调用）
python D:/家教/系统/scripts/extract-knowledge-points.py --pdf textbook.pdf --subject math --grade "六年级上册" --dry-run

# 完整流程（需先 wire 好 vision 调用）
python D:/家教/系统/scripts/extract-knowledge-points.py --pdf textbook.pdf --subject math --grade "六年级上册"
```

输出 `{subject}/知识点及掌握情况/overview.md` 让家长扫一眼，确认无章节遗漏。

### 5. 不做的（用户明确要求）

- ❌ 不建任何 cron（手动触发即可）
- ❌ 不修改 OpenMAIC 源码（基于 requirement 注入约束）
- ❌ 不物理迁移开发机文件（用户真实电脑按文档组织）

---

### 6. OpenMAIC outline prompt 真实位置（2026-09-08 实证）

**当你想找"OpenMAIC 如何生成课堂大纲"的 prompt 模板时，看这里**：

- ✅ **真正在用的**：`packages/@openmaic/generation/templates/requirements-to-outlines/system.md`
  - 通过 `PROMPT_IDS.REQUIREMENTS_TO_OUTLINES` 引用
  - 由 `packages/@openmaic/generation/src/outline-generator.ts` 的 `buildOutlinePrompt()` 加载
  - 这是 OpenMAIC 默认流程的实际 prompt
- ❌ **已过时/未使用**：`lib/prompts/templates/interactive-outlines/system.md`
  - 它存在，但 grep 整个代码库没有任何 `INTERACTIVE_OUTLINES` / `interactive-outlines` 引用
  - 不要在这里写新 prompt——它不会被加载

**想加新 outline 模式（如微课堂）时，正确做法有两种**：
1. **不修改源码**（推荐）：在 requirement 文本里硬约束场景数/类型/widget 禁止/knowledgeScope 边界，让默认 `requirements-to-outlines` prompt 按你的意图产出。脚本 `D:/家教/系统/scripts/micro-lesson.py` 就是这个思路。
2. **改源码**：要在 `packages/@openmaic/generation/src/prompts/{index.ts, types.ts}` 加新的 PROMPT_ID，然后在 `outline-generator.ts:buildOutlinePrompt()` 加分支。改动链路长（5 处源码 + 重新 build），仅在大课堂 / 微课堂是两套截然不同的指令时再做。

---

## 🚨 迁移必读 — 给任何加载此 skill 的 Agent（含跨机器/打包迁移后的新实例）

本系统面向小学生，**孩子无法准确描述故障**，所以有一条铁律：

> **每收到用户的任意一条消息，第一件事是做服务健康检查，确认通过后才回答或执行任何操作。**

**首次加载本 skill 时，你必须立刻把下面这句写入你自己的持久 memory（不是只在本次会话记住）：**

> 家庭教师模式：每收到一条消息，先检查 OpenMAIC(端口3000) 和 quiz-server.py(端口8765) 是否存活（curl 探活），挂了先重启再回复。

具体检查命令和重启方法见下方「服务健康检查（每次回复前必做）」小节和故障排查决策树。这一规则的历史原因：孩子只会说"打不开""没反应"，不会说哪个服务挂了；等问清楚再去查，体验已经坏掉。

## ⚠️ 环境迁移记录（2026-08-18 换主板重装后验证）

系统重装（旧用户名 24378 → 新用户名 MR），Hermes 数据迁至 `D:\hermes-data`。以下为本项目相关的路径变更：

| 旧路径（已失效） | 新路径（有效） |
|---|---|
| `C:/Users/24378/.hermes/tools/mimo-multimodal.cjs` | `D:/mimo-multimodal/image_understand.py`（参数兼容，直接替换路径即可） |
| `C:/Users/24378/edge-debug-profile` | `D:/edge_debug_profile`（已在 D 盘） |
| `C:/Users/24378/AppData/Local/nvm/v24.18.0/...`（Open Design 用） | ⚠️ 未装 Node 24/nvm，**需要时先安装 Node 24**（OpenMAIC 用 hermes-data 的 Node 22 即可） |
| `C:/Users/24378/.mmx/config.json`（minimax OAuth） | ⚠️ 需重新执行 `mmx auth login --region cn` 生成（`C:/Users/MR/.mmx/config.json`），并同步 `.env.local` |

**答题模式确认（2026-08-18 验证，用户确认无需二次开发）：**

## 🔑 Key 与接入方式（2026-08-22 盘点实测）

| 服务 | Key/位置 | 状态 | 接入方式 |
|---|---|---|---|
| **MIMO (LLM+TTS)** | `sk-cvo0...slbvh`（用户 2026-08-22 提供） | ✅ **域名变更！** 旧 `token-plan-cn.xiaomimimo.com` 已废(404)，**新域名 `https://api.xiaomimimo.com`**；✅ TTS 可用；⚠️ LLM 402 余额不足 | **header 用 `api-key:` 不是 `Authorization`**；TTS=chat/completions + 顶层 `audio:{format,voice}`，user=音色描述、assistant=朗读文本；音色列表: [mimo_default, 冰糖, 茉莉, 苏打, 白桦, Mia, Chloe, Milo, Dean] |
| **MiniMax** | .env.local oat-7PF1... | ❌ 2026-08 已过期 | 已注释停用（TTS/Image/LLM 全停） |
| **百度千帆搜索** | `bce-v3/ALTAK-Ju2G4...bcec8`（.env.local + api-keys.json 同款） | ✅ 2026-08-22 实测 5 条 | `POST /v2/ai_search/web_search` + body `{"messages":[{"content":"kw","role":"user"}],"search_source":"baidu_search_v2","resource_type_filter":[{"type":"web","top_k":5}]}` + 头 `X-Appbuilder-From: openmaic`；**`.env.local` 里不能用旧端点 `/v2/chat/completions`（401 invalid_iam_token）** |
| **Tavily** | tvly-dev-3D...RQ0k | ✅ 实测 | 正常 |
| **百炼 DashScope ASR** | `sk-933...c29d`（课堂翻译 App `SettingsRepository.kt` 默认值） | ✅ 2026-08-22 实测 241 模型 | DashScope 兼容模式 `https://dashscope.aliyuncs.com/compatible-mode/v1`；⚠️ 翻译 key `sk-HtV...` 已 401 失效 |
| **OpenMAIC 默认 LLM** | `XIAOMI_*`→api.xiaomimimo.com + sk-cvo0...；DEFAULT_MODEL=xiaomi:mimo-v2.5-pro | ⚠️ 402 余额不足，**充值前课件生成会失败**；备选 opencode GO 中继（Hermes 主 key，见下） | - |
| **AI 批改（quiz-server）** | 读 `D:\hermes-data\.env` `OPENCODE_GO_API_KEY` → `https://opencode.ai/zen/go/v1` | ✅ 2026-08-22 实测 | ox-alpha-free + max_tokens≥2000 + Mozilla UA 头（详见本文件顶部 quiz-server 双通道说明） |
最新版答题模式 = **两阶段异步批改**，文件齐全：
1. 孩子用 `quiz-pending.html` 作答 → 提交 → POST `http://localhost:8765/api/quiz-results`（带 `pendingGrading: true`）→ 服务端**只保存不批改**
2. 孩子说"我答完了" → Hermes 读 `quiz-results/latest.json` → 逐题批改（选择题自判 + 简答题调 AI）→ 生成报告 → 更新 `learning-state.json`
- `quiz-ai.html` 是旧版（前端同步调 `/api/grade-essay` 批改），**已不用**；`quiz-server.py` 的 `/api/grade-essay` 端点为旧版保留
- 项目全部文件在 `D:\projects\family-tutor\`（脚本/页面/数据/备份齐全，9 个脚本语法验证通过）
- `quiz-server.py` 里硬编码的 minimax OAuth token 已过期（48h 有效期）。**2026-08-22 已改造为双通道批改：主通道 = opencode GO 中继（ox-alpha-free，读 `D:\hermes-data\.env` 的 OPENCODE_GO_API_KEY，英文提示词 + max_tokens≥2000 + Mozilla UA），备选 = minimax**；免费中继偶发响应 >2.5 分钟属正常现象，客户端超时别设太短
- 学习进度：语文 Day1/Day2 已完成，数学 4 天 + 英语 1 天待生成课件
- **2026-08-22 迁移后全链路复测通过**（真实浏览器端到端）：①load-quiz.html 跳转目标已从旧版 quiz.html 改为 quiz-pending.html；②quiz-pending.html 已兼容 question/text 字段名、字符串/索引答案、essay 题型收集；③analyze-weak-points.py 已兼容新旧批改报告格式（details/results），简答 <80 分计入薄弱；④generate-remedial.py 路径统一到 quiz-data/ 并自动注入 load-quiz-remedial.html 模板（含薄弱点展示），答案分布强制均衡（修复"全是A"复发）；⑤Python 解释器用 D:/Python312/python.exe（bash 无 python 命令）；⑥curl 在 git-bash 下对 localhost 解析 IPv6 会假失败，健康检查用 python urllib 打 127.0.0.1

## 📚 课本提取参考 (OCR / Vision LLM / ABBYY)

**见 `references/textbook-ocr-ai-extraction.md`** — 三大方案对比、智慧教育平台抓全本方法、Vision LLM 完整内容提取 prompt、用户对"对比图"和"前N张=全部N张"的强偏好。

**快速决策**:
- 给 AI 用 (KP 库/出题/讲解) → Vision LLM + "完整页面报告" prompt, 不需要版式
- 给孩子看 PDF → ABBYY 16 手动跑 30 张/批, 保留版式
- 不要用 PaddleOCR/ABBYY 处理数学公式 (30% 准确率)

**关键 Pitfall**: 智慧教育平台 `preview` 字段只返回 49 张, 实际全 130+ 张在 `transcode/image/N.jpg` 公开端点。

---

## 知识要点文档

### 文档结构
每个课程都有独立的知识要点文档，路径：`D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`

### 文档内容
1. **学习目标**：本课程要掌握的核心内容
2. **主要概念**：需要理解的核心概念
3. **核心公式**：需要记忆的公式（数学）
4. **例题解析**：典型例题的解题步骤
5. **练习题**：巩固练习
6. **易错点**：常见的错误和注意事项
7. **拓展知识**：相关的拓展内容

### 文档用途
1. **推进学习计划**：直接参考知识要点文档，不需要重新提取
2. **查漏补缺**：根据薄弱知识点，从知识要点文档中提取相关题目
3. **生成补强练习**：从知识要点文档中随机选择题目，每次不同

### 文档示例
```markdown
# 数学 Day 1 - 分数的应用（一）

## 学习目标
掌握"求一个数的几分之几是多少"的计算方法

## 知识要点

### 主要概念
1. **分数的应用**：求一个数的几分之几是多少
2. **单位"1"的量**：作为基准的量
3. **分率**：表示部分与整体关系的分数

### 核心公式
数量 = 单位"1"的量 × 分率

### 例题解析
**题目**：气象小组有12人，摄影小组的人数是气象小组的1/3，航模小组的人数是摄影小组的3/4，求航模小组的人数。

**解题步骤**：
1. 先求摄影小组的人数：12 × 1/3 = 4人
2. 再求航模小组的人数：4 × 3/4 = 3人

**答**：航模小组有3人。
```

## 学习规划文档

### 文档结构
学习规划文档路径：`D:\projects\family-tutor\learning-plan.md`

### 文档内容
1. **学习目标**：整体学习目标
2. **学习安排**：每天学什么，用什么 PDF
3. **学习流程**：每天的学习流程
4. **查漏补缺流程**：如何分析漏洞和补强
5. **知识要点文档**：每个课程的知识要点文档路径
6. **技术架构**：前端、后端、数据、工具
7. **下一步计划**：今天、明天、后天的计划
8. **注意事项**：技术要点、用户偏好、学习方法

### 文档用途
1. **整体规划**：了解整个暑假的学习安排
2. **进度跟踪**：查看每天的学习进度
3. **技术参考**：了解系统架构和工具使用
4. **学习指导**：按照学习流程进行学习
- `references/openmaic-topic-patch.md` — OpenMAIC ?topic=xxx 参数patch详情
- `references/open-design-setup.md` — Open Design安装配置步骤
- `references/open-design-integration.md` — **Open Design 集成指南**（启动、CLI、生成页面流程）
- `references/open-design-form-flow.md` — **Open Design 表单交互流程**（Prototype/响应式网页/一键跳过）
- `references/pdf-textbook-processing.md` — 教材PDF处理工作流（视觉定位→裁切→知识点提取）
- `references/openmaic-api.md` — OpenMAIC API参考（PDF解析、课堂生成、状态轮询、端到端脚本）
- `references/openmaic-internal-architecture.md` — **OpenMAIC 内部架构解析（2026-09-08 关键发现）**：4 阶段生成流程、outline 模板路径、场景展开、白板动作清单、微课堂模式实现路径
- `references/micro-lesson-prompt-template-draft.md` — **微课堂 outline prompt 草案（2026-09-08）**：新建 `micro-lesson-outlines/system.md` 的完整内容、调用示例、待确认事项、已知风险
- `references/openmaic-config.md` — **OpenMAIC 配置架构**（前端段 vs 后端段，provider 加载决策树）
- `references/provider-switching-mid-task.md` — **中途切换 LLM provider**（2026-07-10 实证，处理 MIMO 过期不重新生成）
- `references/mimo-tts-asr.md` — MIMO TTS/ASR代理配置（MIMO 是默认 TTS，见 Pitfall 37）
- `references/mimo-multimodal.md` — **MIMO 多模态视觉理解**（图片/音频/视频分析，替代 vision_analyze）
- `references/quiz-system-design.md` — **答题系统设计规则**（题型选择、AI批改规则、结果同步、页面文件）
- `references/quiz-sync-code-template.md` — **答题结果同步代码模板**（Open Design 生成页面后必须手动添加）
- `references/quiz-workflow-complete.md` — **完整测验工作流（端到端实证）**（从出题到查漏补缺的完整流程，含补强练习示例）
- `references/remedial-quiz-workflow.md` — **补强练习完整工作流**（分析薄弱知识点→生成新题→AI批改→检查结果→决策循环）
- `references/late-session-learnings-2026-07-10.md` — **2026-07-10 晚间会话学习记录**（用户偏好总结、参数配置、决策表、启动检查清单）
- `references/openmaic-prompt-templates.md` — OpenMAIC提示词模板修改（解决每页"同学们好"问题）
- `references/openmaic-debug-recipes.md` — **OpenMAIC 调试配方**（查课件JSON/TTS/provider/Minimax切配）
- `references/minimax-tts-models.md` — **Minimax TTS 6个模型对比 + 中文音色推荐**（2026-07-09）
- `references/minimax-key-formats.md` — **minimax key 类型与端点对应关系**（`sk-cp-` vs OAuth `oat-` token、1004 错误码诊断、OAuth 流程）
- `references/greeting-fix-journey.md` — **"同学们好"问题三次修复实战记录**（2026-07-09，从改 prompt 到 processActions post-processor 的最终方案）
- `references/mimo-api-json-parsing.md` — **MIMO API JSON 解析问题**（markdown 代码块处理，2026-07-10）
- `references/mimo-api-chinese-prompt-issue.md` — **MIMO API 中文提示词返回空内容问题**（需用英文提示词，2026-07-10）
- `references/answer-distribution-randomization.md` — **补强练习答案随机分布**（用户强烈纠正，2026-07-10）
- `references/muse-ai-sdk-responses-fix-2026-09-01.md` — **muse-spark 在 OpenMAIC 走 /v1/responses 的根因+修复+curl 模板**（2026-09-01 实证，配套 pitfall 75g/75h/75i/75j/75k）
- `references/multi-process-port-conflict.md` — **多进程端口冲突问题**（重启服务时的常见陷阱，2026-07-10）
- `references/openmaic-indexeddb-import.md` — **OpenMAIC IndexedDB vs 文件系统导入工作流**（2026-07-10 关键发现：API 生成的课件不会自动出现在主页，必须打包 ZIP 手动导入或修改源码让 listStages 从文件系统读取）
- `references/textbook-grade-context-verification.md` — **教材背景年级与重点必须明确**（2026-07-10 实证：裁切 PDF 后必须验证年级和内容，重心要对——背景是小学数学不是数据分析专业）
- `references/answer-content-verification.md` — **AI 生成内容必须对照知识要点文档核对**（2026-07-10 实证：minimax M3 会"自主发挥"生成偏离主题的内容）
- `references/quiz-system-2026-07-10.md` — **答题系统完整工作流**（AI 批改、动态题型、答案随机分布、补强练习生成新题，2026-07-10 实证）

## 触发条件

加载本 skill 的关键词：
- 教学场景："上课""学习""测验""家庭教师""学习计划""错题""查漏补缺""微课堂""微课"
- 文件操作："作业拍照""批改作业""图片批改""错题图片""科目文件夹""文件夹重构"
- 工具相关："OpenMAIC""outline 模板""微课堂模式""knowledge-points""quiz-server"

未匹配但内容跟 K12 学习辅导有关的，主动加载。

## 系统架构
- **Hermes = 全能教师**：规划学习进度、用 MIMO 多模态读课本、出测验题、批改答案、分析薄弱点、生成课件
- **OpenMAIC = 课堂**：自己读PDF→自己决定教学重点→生成课件→AI老师讲课（localhost:3000）
- **learning-state.json = 记忆**：学习计划、进度、薄弱点、测验结果
- **knowledge-points/*.md = 知识要点**：每个课程的详细知识点（主要概念、公式、例题、练习题、易错点）
- **learning-plan.md = 学习规划**：整体学习安排、学习流程、技术架构
- **MIMO 多模态 = 视觉理解**：读课本图片、提取知识点、生成测验题（`mimo-multimodal.cjs`）
- **答题系统 = quiz-ai.html + quiz-server.py**：AI 批改版答题页面，结果自动同步到后端
- **Open Design = 页面美化**：生成精美 HTML 页面（需 Node 24，daemon 端口 7456）

**注意：OpenTutor 已弃用**（扫描版PDF无法解析、API超时、维护成本高）。Hermes 直接用 MIMO 多模态完成所有教学环节。

## OpenMAIC 内部架构（2026-09-08 关键解析）

**目的**：理解 OpenMAIC 怎么生成课堂的，才能在不重新发明轮子的前提下做微课堂。

**整体流程（4 阶段）**：

```
用户输入 requirement + pdfContent
       ↓
【第 1 步：选择 outline 模板】
  OpenMAIC 启动时根据 PROMPT_IDS 加载若干模板（**不是按 requirement 内容自动选**）：
  - requirements-to-outlines/system.md → 默认所有普通课堂（用户级 prompt 模板库 + packages 包内都有）
  - task-engine-outlines/system.md     → 职业教育专用（强制 10-14 场景，强制混合结构）
  - PBL（项目式学习）                  → 另一种模式
  ⚠️ **真实路径是 `packages/@openmaic/generation/templates/`，不是 `lib/prompts/templates/`**。
     `lib/prompts/templates/interactive-outlines/` 和 `task-engine-outlines/` 是 dead code，
     不被任何代码引用（grep PROMPT_IDS 引用即可确认）。真实代码在 packages 包内。
       ↓
【第 2 步：调 LLM 生成 outline JSON】
  真实代码路径：D:\projects\OpenMAIC\packages\@openmaic\generation\src\outline-generator.ts
  PROMPT_IDS 定义在：D:\projects\OpenMAIC\packages\@openmaic\generation\src\prompts\index.ts
  PROMPT_IDS.REQUIREMENTS_TO_OUTLINES = 'requirements-to-outlines'
  输出格式（requirements-to-outlines 模板强制）：
  {
    "languageDirective": "教学语言指令",
    "courseTitle": "课程名（≤30字）",
    "outlines": [
      {"id":"scene_1","type":"slide","title":"...","keyPoints":[...],"order":1},
      {"id":"scene_2","type":"interactive","widgetType":"simulation",...},
      ...
    ]
  }
       ↓
【第 3 步：每场景调 LLM 展开成 actions（白板动作）】
  - slide 类型 → 走 slide-actions prompt → 输出 wb_draw_text / wb_draw_latex / wb_draw_table
  - interactive + widgetType=X → 走对应 X-content prompt
  模板路径：D:\projects\OpenMAIC\packages\@openmaic\generation\templates\slide-actions\
       ↓
【第 4 步：processActions 后处理 + TTS 生成 + 持久化】
  路径：D:\projects\OpenMAIC\lib\generation\scene-generator.ts
  关键：白板/手指/标注/强调高亮都是这一步的内建动作（wb_draw_* 系列），不需要在 prompt 里手写
```

**白板/手指/标注是 OpenMAIC 的内建能力，不是 prompt 写出来的。** 用户原话："白板写出来而不是用嘴说，这本身就是 OpenMAIC 已经调好的东西"。微课堂方案只换 outline 模板，slide-actions 不动，白板效果自动保留。

## 微课堂 — 已验证可工作的方案（2026-09-08 真实测试通过）

### 最终方案 = **拼 requirement 调 OpenMAIC，不改任何源码**

**真相（真实测试 2026-09-08 04:32 通过）**：微课堂**不需要改 OpenMAIC 源码**，纯靠精心构造的 requirement 文本就能产出符合要求的 slide-only 短课。已用 2 道数学错题（分数应用题）实测：
- 6 个场景（2 错题 × 3 场景）✅
- 100% slide（无 widget）✅
- 所有要求的概念都覆盖 ✅
- 防超纲（"比"是误报，实际是"比较"不是数学"比"）✅
- 37/37 speech 全部生成 TTS 音频 ✅
- 课程标题："分数应用题错题讲解" ✅

### 为什么不需要改源码

- OpenMAIC 默认 REQUIREMENTS_TO_OUTLINES prompt 对"按错题生成"没硬性约束
- 但**用户在 requirement 里**塞入"硬性约束"（每错题 N+2 场景、只 slide、禁止 widget、knowledgeScope 边界），LLM 会按约束执行
- 唯一需要做的：**写一个 Python 脚本，构造极详细的 requirement 字符串，调 OpenMAIC `/api/generate-classroom`**

### 脚本实现

文件：`D:\家教\系统\scripts\micro-lesson.py`

构造的 requirement 模板（**真实可工作版本**，精简版）：
```
# 微课堂：错题讲解

你是一位中国小学六年级的数学老师，正在给学生讲他做错的题。
学生已经学过本学期内容，但在某些知识点上有漏洞。

你的教学风格：
- 把抽象概念一步一步拆开，从学生已经会的内容开始往上搭
- 用视觉辅助（白板画图、写公式），让抽象概念变具体
- 用词要符合六年级水平，不能超过小学六年级的范围

## 硬性约束（必须严格遵守）
1. 每一道错题生成 (知识点数 + 2) 个场景：
   - 场景 1：错题还原。在白板写出原题，圈出错处。不给正确答案。
   - 场景 2 ~ N+1：每个知识点一页讲解。
   - 场景 N+2：回归错题。用刚讲的方法做对，写正确答案。
2. 禁止任何开场白、总结页、错题之间的过渡页。
3. 只能使用 slide 场景。禁止任何 widget（simulation / diagram / game / visualization3d / code / quiz）。
4. 一页只能讲一个知识点。
5. 只能使用下方 knowledgeScope 列出的概念和例子。严禁引入 knowledgeScope 之外的概念。

## 学科
math

## knowledgeScope（严格边界，只用这里列的概念）
[从 knowledge-points 抽出的 1-2 个相关小节]

## 错题 1（涉及 N 个知识点 → 必须生成 N+2 个场景）
原题：...
标准答案：...
标准解法：...
涉及的知识点：...
学生写的答案：...
学生常见错法：...

[可选：错题 2/3/...]

请按上述要求生成大纲 JSON。
```

### 验证脚本（已写）

`D:\家教\系统\scripts\verify-micro-lesson.py` — 检查生成的 requirement 是否包含 10 项硬约束 + demo 内容，自动跑 PASS/FAIL。

### 完整真实测试记录

见 `references/micro-lesson-real-test-2026-09-08.md` — 包含端到端命令、生成 JSON、概念覆盖验证、TTS 覆盖率。

### 之前尝试过但已回退的方案

之前文档（75l、架构章节等）提过"改 outline-generator.ts 加 outlineMode 路由 + 新建 micro-lesson-outlines 模板"。**这个方案在 2026-09-08 已撤销**：用户原话"回退到正确的方案"，明确指出上面的纯 requirement 注入方案才是正确做法。

原方案的坑：
- `lib/prompts/templates/` 是 dead code（不被 packages 包引用），新建在那里根本没用
- 真实 outline prompt 在 `packages/@openmaic/generation/templates/`
- 即使改对位置，还得改 `outline-generator.ts` 加 outlineMode 分支 + 改 lib + 改 app/api 路由 → 5 处源码改动
- 实测发现纯 requirement 注入就够用，根本不需要改源码

### 微课堂 vs 大课堂对比

| 维度 | 大课堂（每天新课） | 微课堂（错题讲解） |
|---|---|---|
| 走哪个模板 | requirements-to-outlines（默认） | requirements-to-outlines（**同一个模板**） |
| requirement 内容 | "学第 X 课" + pdfContent | 错题 + knowledgeScope + 硬性约束 |
| 场景数 | 5-13（LLM 自行规划） | (N+2)×错题数（**脚本硬约束**） |
| 类型 | slide + interactive 混合 | 只 slide（**脚本硬约束**） |
| 物理边界 | OpenMAIC 自己保证 | knowledgeScope 物理隔离不超纲 |
| 触发时机 | 每天新课 | 错题批改后 / 周报 / 家长手动 |
| **改动量** | 0 | 0（**无源码改动**） |

## 图片批改（2026-09-08 用户纠正）

**不需要搭单独的批改接口。** 学生/家长直接拍照发到 Hermes 对话框即可。

**正确流程**：
1. 微信收到作业图片
2. Hermes 走 vision_analyze / MIMO 多模态识别（用 D:/mimo-multimodal/image_understand.py）
3. 从 quiz-data/{科目}/{测验}/ 读标准答案
4. 调 LLM 批改（opencode-go 中继，ox-alpha-free，max_tokens≥2000）
5. 写回 quiz-results/{科目}/{错题集}/{时间戳}.json 和 learning-state.json
6. 自动触发薄弱点分析（如果错题数 ≥ 阈值）

**不需要做的事**：
- 不需要新建 /api/quiz-submit-image 接口（用户原话："直接把作业拍照发到 Hermes 对话框不就可以了吗"）
- 不需要改 quiz-server.py（HTTP 接口是答题网页用的，跟图片批改无关）
- 不需要新前端页面

**skill 里要做的事**：
- 加一段"收到作业图片 → 走批改流程"的工作流
- 复用现有 vision 工具和批改 prompt
- 在批改完后自动更新薄弱点表

## 项目路径

### ⚠️ 文件夹结构重构（2026-09-08 用户要求）

当前旧结构是按文件类型分文件夹（materials/、quiz-data/、knowledge-points/ 散在各处）。用户明确要求改为按主题分，所有学科资源集中在同一个文件夹里。

新结构（按主题分）：
```
D:\家教\
├── 语文\
│   ├── 课本/                  # 原 materials/chinese/ 整体迁移
│   ├── 课件/                  # 原 OpenMAIC data/classrooms/{subject}_*.json 归档
│   ├── 知识点及掌握情况/        # 原 knowledge-points/{subject}_day{N}.md + 学生掌握度
│   ├── 错题集/                # 原 quiz-results/{subject}_*.json 归档（按学科）
│   └── 测验/                  # 原 quiz-data/{subject}_*.json 归档（按学科）
├── 数学\                      # 同上 5 个子目录
├── 英语\                      # 同上 5 个子目录
└── 系统\
    ├── scripts/                # 跨学科通用脚本
    ├── 学习规划.md             # 原 learning-plan.md
    └── 学习状态.json           # 原 learning-state.json
```

迁移原则：
- 物理移动（不要软链接，干净）
- OpenMAIC 生成的 classroom JSON（D:\projects\OpenMAIC\data\classrooms\*.json）按学科归到 /d/家教/{科目}/课件/
- 迁移完后逐个路径 grep 替换（skill、所有脚本、.env.local 里的硬编码路径都要更新）
- 迁移前全量备份到 D:\家教备份-{日期}\
- 不要一次性 rm 旧目录——先迁移，验证 3 天无问题后再删

重构后所有引用路径的更新点：
- family-tutor/SKILL.md 各处
- quiz-server.py / generate-remedial.py / analyze-weak-points.py 等所有脚本
- 答题页面（quiz-ai.html / quiz-pending.html）的相对路径
- OpenMAIC 配置里读 PDF 的路径（如有）

### 主目录（重构前）
- 学习中心：`D:\\projects\\family-tutor\\`
- 记忆文件：`D:\\projects\\family-tutor\\learning-state.json`
- 学习规划：`D:\\projects\\family-tutor\\learning-plan.md`
- 知识要点：`D:\\projects\\family-tutor\\knowledge-points\\{subject}_day{N}.md`

### 课本材料（materials）
- 语文课本：`D:\\projects\\family-tutor\\materials\\chinese\\`
- 数学课本：`D:\\projects\\family-tutor\\materials\\math\\`
- 英语课本：`D:\\projects\\family-tutor\\materials\\english\\`

### 测验数据（quiz-data）
- 测验题数据：`D:\\projects\\family-tutor\\quiz-data\\quiz-data-day{N}.json`
- 补强练习数据：`D:\\projects\\family-tutor\\quiz-data\\quiz-data-remedial.json`
- 薄弱知识点分析：`D:\\projects\\family-tutor\\quiz-data\\weak-points-analysis.json`

### 答题结果（quiz-results）
- 答题结果：`D:\\projects\\family-tutor\\quiz-results\\latest.json`
- 历史结果：`D:\\projects\\family-tutor\\quiz-results\\quiz_{timestamp}.json`

### 脚本文件（scripts）
- 薄弱知识点分析：`D:\projects\family-tutor\scripts\analyze-weak-points.py`
- 补强练习生成：`D:\projects\family-tutor\scripts\generate-remedial.py`
- 答题结果接收：`D:\projects\family-tutor\scripts\quiz-server.py`
- 批量生成课件：`D:\projects\family-tutor\scripts\generate-all-courseware.py`（一次提交 5+ 课件）
- 轮询课件状态：`D:\projects\family-tutor\scripts\poll-courseware.py`（轮询到完成）
- 验证课件内容：`D:\projects\family-tutor\scripts\verify-courseware.py`（核对知识点是否在课件里）
- 切换 provider：`D:\projects\family-tutor\scripts\switch-provider.py`（中途切换 LLM）

### 页面文件
- 答题网页：`D:\projects\family-tutor\quiz-ai.html`（AI 批改版）
- 补强练习页面：`D:\projects\family-tutor\load-quiz-remedial.html`
- 测验加载页面：`D:\projects\family-tutor\load-quiz.html`（点击"开始测验"自动加载题目）
- 学习中心页面：`D:\projects\family-tutor\index.html`

### 标准化文件结构（2026-07-10 整理）

```
D:\projects\family-tutor\
├── materials/                  # 课本材料（按学科分文件夹）
│   ├── chinese/                # 语文课本
│   ├── math/                   # 数学课本
│   │   ├── math_day1.pdf       # 前3页（分数的应用一）
│   │   ├── math_day2.pdf       # 后5页（分数的应用二）
│   │   ├── math_day3.pdf       # 前5页（数据分析三）
│   │   └── math_day4.pdf       # 后5页（数据分段整理）
│   └── english/                # 英语课本
│       └── english_unit1.pdf   # 第4-10页（代词与可数名词）
├── knowledge-points/           # 知识要点文档（独立 .md）
├── quiz-data/                  # 测验数据
├── quiz-results/               # 答题结果
├── scripts/                    # 脚本
├── backup/                     # 备份
└── *.html                      # 页面文件
```

### 备份文件（backup）
- 课件备份：`D:\\projects\\family-tutor\\backup\\`

### OpenMAIC
- OpenMAIC源码：`D:\\projects\\OpenMAIC\\`
- 桌面快捷方式：`家庭教师.lnk` → `D:\\projects\\start-tutor.bat`
- OpenMAIC源码：`D:\\projects\\OpenMAIC\\`
- 桌面快捷方式：`家庭教师.lnk` → `D:\\projects\\start-tutor.bat`

## 桌面快捷方式与启动顺序
- `家庭教师启动.bat` → `D:\\projects\\start-tutor.bat`
- bat文件不能设图标，必须创建.lnk快捷方式
- 创建方式：PowerShell `New-Object -ComObject WScript.Shell` → `CreateShortcut()` → 设置 `IconLocation`

## 启动顺序（start-tutor.bat必须包含）
1. MIMO TTS 代理: `python D:\\projects\\family-tutor\\mimo-tts-proxy.py`（端口8787）
2. 答题结果接收服务: `python D:\\projects\\family-tutor\\scripts\\quiz-server.py`（端口8765）
3. OpenMAIC: `pnpm dev`（需 Node 22, 不是 24）
4. Edge: 用户自己打开 localhost:3000

**注意：TTS代理和答题服务必须在OpenMAIC之前启动。**

## 服务健康检查（每次回复前必做）

**这是面向小孩子的系统，孩子不一定能准确描述问题。所以我每次收到信息时，必须先检查以下服务是否正常运行：**

```bash
# 1. 检查 OpenMAIC（端口 3000）
curl -s --max-time 5 http://localhost:3000/api/server-providers | python -c "import json,sys;d=json.load(sys.stdin);print('OpenMAIC:', list(d.get('providers',{}).keys()))"

# 2. 检查答题服务（端口 8765）
curl -s --max-time 5 http://localhost:8765/api/quiz-results/latest 2>&1 | head -1

# 3. minimax TTS 不需要代理（直接调 https://api.minimaxi.com/v1/t2a_v2）
# 只需要 OpenMAIC 配置 TTS_MINIMAX_API_KEY + TTS_MINIMAX_BASE_URL 即可
curl -s --max-time 10 "https://api.minimaxi.com/v1/t2a_v2" -H "Authorization: Bearer $TTS_MINIMAX_API_KEY" -H "Content-Type: application/json" -d '{"model":"speech-01-hd","text":"test","stream":false,"voice_setting":{"voice_id":"Chinese (Mandarin)_Crisp_Girl","speed":1.0,"vol":1.0,"pitch":0},"audio_setting":{"sample_rate":32000,"bitrate":128000,"format":"mp3"}}' | head -c 100
```

**如果某个服务挂了：**
- **OpenMAIC 挂了**：重启 `pnpm dev`
- **答题服务挂了**：重启 `python scripts/quiz-server.py`
- **TTS 不需要代理**，调 minimax 原生 API；如有问题先检查 OAuth token (`mmx auth refresh`)

**完整启动脚本：** `D:\\projects\\start-tutor.bat`

**故障排查决策树：**
1. 用户说"打不开"/"没反应"/"点不动" → 检查所有 3 个服务
2. 用户说"AI 批改失败" → 检查答题服务 + minimax OAuth token
3. 用户说"课件没声音" → 直接测 minimax TTS（无需代理），确认 OpenMAIC 配置
4. 用户说"主页没有课件" → 检查 OpenMAIC + 跑 `import-classrooms.py`
5. 用户说"答完一句话就结束" → 检查 OpenMAIC LLM 配置 (401 = key 类型错)

**关键洞察 (2026-08-01 实战总结)：**
- **minimax 一套 OAuth token 通吃全部 API**（不用切换 sk-cp- 和 oat-）
  - LLM: `https://api.minimaxi.com/anthropic/v1` (X-Api-Key header)
  - TTS: `https://api.minimaxi.com/v1/t2a_v2` (Authorization Bearer header)
  - Image: `https://api.minimaxi.com/v1/image_generation`
- **TTS 模型名是 `speech-01-hd` 不是 `speech-01`**（API 会返回 2013 错误）
- **OpenMAIC 不需要任何 TTS 代理**（minimax 原生 API 直接调）
- **TTS 代理 8787 端口永久关闭**，之前用是因为 MIMO key 过期
- **不要告诉孩子链接让他自己打开**，直接用 `cmd.exe /c "start <URL>"` 打开

**孩子无法准确表达问题，所以每次回复前主动检查！**

**quiz-server.py 关键配置（2026-07-10 实证）：**
- 使用 **minimax API**（不是 MIMO），`MINIMAX_API_KEY` 必须用 **OAuth `oat-` token**（不是 `sk-cp-`）
- **OAuth token 续期**：`mmx auth refresh`（不能用 `mmx auth login`，非交互模式需要 `--api-key`）
- 提示词必须用**英文**（中文提示词返回空内容）
- `max_tokens` 必须 ≥ 500（否则模型把 token 都用在推理上，没留 token 给回复）
- **API 调用失败** 返回 `{is_correct: false, error_reason: 'AI 批改失败: ...'}`，不能返回空白

**可用页面：**
- 学习中心: `D:\\projects\\family-tutor\\index.html`
- 答题网页: `D:\\projects\\family-tutor\\quiz-ai.html`
- AI课堂: `http://localhost:3000`
- 答题结果API: `http://localhost:8765/api/quiz-results/latest`
# 检查答题服务
cmd.exe /c "netstat -ano | findstr :8765 | findstr LISTENING"

# 测试 MIMO 代理
curl -s -X POST "http://127.0.0.1:8787/v1/audio/speech" \
  -H "Content-Type: application/json" \
  -d '{"input":"测试","voice":"alloy"}' \
  -o /tmp/test.wav -w "HTTP %{http_code}, size=%{size_download} bytes\n"

# 测试答题服务
curl -s http://localhost:8765/api/quiz-results/latest | head -5
```

**可用页面：**
- 学习中心: `D:\\projects\\family-tutor\\index.html`
- 答题网页: `D:\\projects\\family-tutor\\quiz.html`
- AI课堂: `http://localhost:3000`
- 答题结果API: `http://localhost:8765/api/quiz-results/latest`

**答题结果同步：**
- 答题网页会自动将结果 POST 到 `http://localhost:8765/api/quiz-results`
- 结果保存到 `D:\projects\family-tutor\quiz-results\` 目录
- Hermes 可以读取 `latest.json` 获取最新答题结果
- 结果包含：得分、薄弱知识点、每题详情（用户答案、AI批改结果）

### 验证 provider 真的加载成功（必做！）
光看 `.env.local` 写了 key 不算数，OpenMAIC 启动时会按 `LLM_ENV_MAP` 把 `MINIMAX_API_KEY`/`MINIMAX_BASE_URL`/`MINIMAX_MODELS` 转成 minimax provider。验证步骤：
```bash
# 1. 重启 OpenMAIC 后看启动日志：
#    [ServerProviderConfig] Loaded (server-providers.yml): N LLM, ...
#    N >= 1 且包含 minimax 才行

# 2. 查 API：
curl http://localhost:3000/api/server-providers | python -m json.tool
# 应该看到：
#   "providers": {
#     "minimax": {"models": ["MiniMax-M3", ...]}
#   }

# 3. 端到端冒烟测试（fast 模式 ~3 分钟）：
curl -X POST http://localhost:3000/api/generate-classroom \
  -H "Content-Type: application/json" \
  -d '{"requirement":"六年级上册语文第一单元第1课《古诗词三首》",
       "agentMode":"fast","enableWebSearch":false,"enableTTS":true}'
# 轮询直到 succeeded
```

**Common mistake**：直接信 `.env.local` 配好就开跑课堂生成。如果 env 变量没被加载（比如 .env.local 在 cwd 之外、或变量名拼错），课堂生成会挂得很慢看不出来。

## 🎯 课件生成默认参数（2026-08-22 用户明确要求，写死在 skill）

| 项目 | 值 | 说明 |
|---|---|---|
| 图片生成 | `enableImageGeneration: false` | 关闭（minimax 图质量差，Pitfall 31） |
| 视频生成 | `enableVideoGeneration: false` | 关闭（无视频 provider，Video: []，OpenMAIC 不产视频） |
| **深度交互** | **requirement 必须追加**：「本课件只使用 slide 讲解场景，**不要生成 quiz 或 interactive 场景**」 | ⚠️ **OpenMAIC 无公开开关**，场景类型由 LLM 决定（模板默认"每 3-5 页插 quiz"、"1-2 个 interactive"）——用户 08-22 反馈中场提问出过问题，必须显式禁止。⚠️⚠️ **提交前必检**：generate-classroom 的 requirement 里没有这句话就别发（2026-08-22 实证：漏了这句→LLM 自作主张生成"动词连连看"交互游戏场景→游戏 HTML 太大→免费中继连续 6 次 500/503 整个 job 失败） |
| 联网搜索 | `enableWebSearch: true` + `webSearchProviderId: "baidu"`（备选 `"tavily"`） | 两个 provider 都已配置（.env.local 有 BAIDU_API_KEY + TAVILY_API_KEY） |
| TTS | MIMO（`openai-tts` → 8787 代理 → api.xiaomimimo.com） | 默认 voice alloy→冰糖 |
| ASR | **百炼**（`qwen-asr`，`ASR_QWEN_API_KEY=sk-933...c29d`=课堂翻译 App 的 asr 默认 key，DashScope 原生 API qwen3-asr-flash） | ⚠️ 旧记录"ASR 走浏览器原生"**已作废**（用户 08-22 改要求） |
| LLM | **白名单（用户 2026-09-01 明确指定）**：`openai:muse-spark-1.2-contributor`（主用，codex_responses）+ `openai:kimi-k3`（chat_completions）+ `minimax:MiniMax-M3`（Anthropic 兼容端点）。**NVIDIA NIM 的 `moonshotai/kimi-k3` 也是 kimi-k3 的合法入口**（catalog 里有但 2026-09-01 不可达，监控恢复） | ⚠️ **严禁切换到白名单之外的模型**（pitfall 75h / 75h-bis），即使端点正常也不允许引入"看起来能跑"的备选；遇白名单内某个模型 500 保持原模型重跑或修路由，不要换模型 |
| agentMode | `'default'` | 不用 fast/generate（Pitfall 75c） |

**验证（2026-08-22 实测）**：`/api/server-providers` → LLM: [openai, minimax, xiaomi] ✅；TTS: [openai-tts] ✅；ASR: [qwen-asr] ✅；webSearch: {tavily, baidu} ✅；Video: [] ✅。2026-08-22 发现旧 7 个课件全部含 quiz+interactive 场景（详情见 Key 表上方），新课件必须用上面的 requirement 约束生成。

## OpenMAIC配置（2026-08-22 provider 对齐 Hermes）

**课件生成 LLM 默认 = opencode GO 中继（与 Hermes 主 provider 一致，用户要求），模型前端可选：**
```bash
# LLM 主力: opencode GO 中继（Hermes 同 key）
OPENAI_API_KEY=<D:\hermes-data\.env 的 OPENCODE_GO_API_KEY>
OPENAI_BASE_URL=https://opencode.ai/zen/go/v1
OPENAI_MODELS=deepseek-v4-flash,deepseek-v4-pro,deepseek-v4-flash-vision-exp,minimax-m3,kimi-k3,glm-5.3,ox-alpha-free,gpt-5.6-luna
DEFAULT_MODEL=openai:deepseek-v4-flash
```
- 2026-08-22 实测：Node 默认 fetch 直通 GO 中继（无 UA 问题），deepseek-v4-flash 返回 200
- LLM_ENV_MAP 支持前缀：OPENAI/ANTHROPIC/DEEPSEEK/XIAOMI/MIMO/MINIMAX 等（`lib/server/provider-config.ts`）
- 用户改模型：改 `DEFAULT_MODEL` 或前端设置页选；XIAOMI（MIMO，402 需充值）/MINIMAX（过期）保留为备选

### .env.local 配置项（双 LLM + MIMO TTS）
```bash
# LLM 主力: MIMO (xiaomi)
XIAOMI_API_KEY=YOUR_MIMO_API_KEY
XIAOMI_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
XIAOMI_MODELS=mimo-v2.5-pro,mimo-v2-pro,mimo-v2.5,mimo-v2-omni,mimo-v2-flash
DEFAULT_MODEL=xiaomi:mimo-v2.5-pro

# LLM 备选: minimax (保留不删)
MINIMAX_API_KEY=sk-cp-...T_4g
MINIMAX_BASE_URL=https://api.minimaxi.com/anthropic/v1
MINIMAX_MODELS=MiniMax-M3,MiniMax-M2.7-highspeed,MiniMax-M2.7

# 联网搜索 - 百度（优先，国内稳定）
BAIDU_API_KEY=bce-v3/ALTAK-.../<secret>
BAIDU_BASE_URL=https://qianfan.baidubce.com

# 联网搜索 - Tavily（备用）
TAVILY_API_KEY=tvly-dev-...

# TTS - MIMO 代理（默认，端口 8787）
TTS_OPENAI_API_KEY=YOUR_MIMO_API_KEY
TTS_OPENAI_BASE_URL=http://127.0.0.1:8787/v1

# TTS 备选 - minimax 原生（用 OAuth oat- access_token，见 Pitfall 38）
# TTS_MINIMAX_API_KEY=<oat-xxx from mmx auth login>
# TTS_MINIMAX_BASE_URL=https://api.minimaxi.com

# Image - 默认关闭（Pitfall 31），如需开启用 OAuth oat- token
# IMAGE_MINIMAX_API_KEY=<oat-xxx>
# IMAGE_MINIMAX_BASE_URL=https://api.minimaxi.com
```

**切换 LLM 只改 `DEFAULT_MODEL`**（`xiaomi:mimo-v2.5-pro` 或 `minimax:MiniMax-M3`），两个 provider 的 key/base_url 都保留。
**配置后必须重启OpenMAIC才生效。**

### OpenMAIC API（重要！）

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/parse-pdf` | POST | 解析PDF，返回 `{text, images[]}`（扫描版无文字层但有图片） |
| `/api/generate-classroom` | POST | 生成课堂（`requirement` + `pdfContent`=parse-pdf返回值） |
| `/api/generate-classroom/{jobId}` | GET | 轮询课堂生成状态 |
| `/api/server-providers` | GET | 列出服务端配置的 providers（minimax/xiaomi/tts 等） |
| `/api/generate/tts` | POST | 试听TTS（字段 `ttsProviderId`/`ttsVoice`/`audioId`/`text`） |

**正确流程（API 上传PDF → 生成课堂，2026-07-09 验证）：**
```bash
# 1. 解析PDF（得到 images[]，扫描版也能用）
curl -X POST http://localhost:3000/api/parse-pdf \
  -F "pdf=@unit1_古诗词三首_草原_丁香结.pdf" \
  -F "providerId=unpdf" \
  > /tmp/parse.json

# 2. 提取 pdfContent（必须是 parse-pdf 的 data 字段）
PDF_DATA=$(python -c "import json;d=json.load(open('/tmp/parse.json'));print(json.dumps(d['data']))")

# 3. 生成课堂 — requirement 必须简洁！只写"今天学哪课"
#    ⚠️ 一定要 enableTTS:true（详见 Pitfall 28）
curl -X POST http://localhost:3000/api/generate-classroom \
  -H "Content-Type: application/json" \
  -d "{\"requirement\":\"六年级上册语文第一单元第1课《古诗词三首》\",
       \"pdfContent\": $PDF_DATA,
       \"enableWebSearch\": false,
       \"enableTTS\": true,
       \"agentMode\": \"fast\"}"

# 4. 轮询（5-10秒/次，约3-5分钟完成）
curl http://localhost:3000/api/generate-classroom/{jobId}
```

**关键**：requirement 文本是给模型的简短指令（"今天学第一课"），**真正的课本内容通过 pdfContent 字段传入**（parse-pdf 的返回 data），OpenMAIC 会用 vision 模型看 images。**不要在 requirement 里塞原文/注释/课后题/学习目标**——用户多次纠正这是"备课"行为，会污染 OpenMAIC 的自主发挥。详见 Pitfall 26/32。

### 课堂生成提示词优化（每页"同学们好"问题）
**问题：** AI老师每页PPT都加"同学们好"开场白，内容重复。
**真·根本原因（2026-07-09 三次修正总结）：** 改 system prompt / store.ts persona 都不够，最终方案是 **processActions 后处理 strip 问候语**。详见 `references/greeting-fix-journey.md`（含完整代码 + 执行顺序图 + 备份流程）。

### OpenMAIC 的"前线/后方" 配置架构（2026-07-09 重点教训）

**OpenMAIC 的 provider 配置是**两段式**架构，不是一段式。理解这一点能避免"用户报没声音但我以为配好了"的反复：**

| 段 | 存哪里 | 决定什么 | 谁改 |
|----|--------|---------|------|
| **前端段** | 浏览器 localStorage（`settings-storage`） | "用哪个 provider" + "是否启用" | 用户在配置页点开关 |
| **后端段** | 服务端 `.env.local` | provider 的 API key + base URL | Hermes 改文件 + 重启 OpenMAIC |

**关键事实**：
- 配置页 TTS 按钮能听到声音 **≠** 课件播放有声音
  - 前者：前端用 localStorage 里的 provider，直接调 provider API（**绕过服务端 key 解析**）
  - 后者：课件调服务端 `/api/generate/tts`，服务端从 `.env.local` 取 key，**找不到或错就 500**
- 用户在配置页选了 `minimax-tts` 但 `.env.local` 没配 `TTS_MINIMAX_API_KEY` → **静默失败**：配置页"看起来 OK"，但课件没声音

**诊断这种"前端看起来配齐但实际没声音"**：
```bash
# 后端有没有这个 provider（看 .env.local 有没有相应 KEY 触发它）
curl -s http://localhost:3000/api/server-providers | python -c "import json,sys;d=json.load(sys.stdin);print('TTS providers on server:', list(d.get('tts',{}).keys()))"
# 如果输出是 {}，说明 .env.local 没配 TTS provider（即使前端选了也没用）
# 期望：['minimax-tts'] 表示 TTS 配齐了
```

**绝对可靠的诊断信号**（比"用户在配置页看到了什么"更可靠）：
- **OpenMAIC 启动日志**：`[ServerProviderConfig] Loaded (server-providers.yml): N LLM, M TTS, K Image, ...`
  - M（tts）> 0 且 K（image）> 0 → 后端配齐
  - M=0 或 K=0 → 后端没配，**无论前端怎么说都是假的**

**正确的工作流**：
1. **改后端配置**（.env.local）→ 重启 OpenMAIC → 看启动日志确认 Loaded
2. **前端**只是给用户看 provider 列表的"启用开关"，**不能取代后端 .env.local**
3. **不要相信**用户在配置页说"我开了"——只相信 OpenMAIC 启动日志

### OpenMAIC provider 诊断决策树（"用户报 X 模态不工作"，2026-07-09 实战总结）

按以下顺序诊断，**不要乱跳**：

```
1. 服务端 provider 注册了吗？
   └─ curl /api/server-providers | jq '.tts | keys' / '.image | keys' / '.providers | keys'
   └─ 没有 → 改 .env.local + 重启 OpenMAIC

2. 服务端 key 的"类型"对吗？（不是问"有没有 key"，是问"对端点用对 key 了吗"）
   └─ curl -H "Authorization: Bearer <key>" https://api.minimaxi.com/v1/token_plan/remains
   └─ 1004 → key 类型错（minimax sk-cp- 只能走 anthropic 端点，TTS/Image 需要 OAuth oat- token）
   └─ 200 → key 有效，可以调原生 API

3. 端点路径对吗？
   └─ 参考 references/minimax-key-formats.md 的"minimax 官方 CLI 端点"表
   └─ 404 → 端点错（不是 key 错！不要去改 key）

4. 鉴权头格式对吗？
   └─ Authorization: Bearer <token>（必须 Bearer 前缀）
   └─ x-api-key: <token>（minimax 有些端点也支持）

5. 启动日志对吗？
   └─ 启动时 [ServerProviderConfig] Loaded 行的数字都 > 0
```

**常见误判**：
- "用户说配好了" 不等于 "服务端配好了" → 看启动日志
- "1004" 不等于 "key 错" → 先看 /v1/token_plan/remains 验证（1004 必然是 key 类型错）
- "404" 不等于 "key 错" → 端点路径错（minimax 官方文档示例与 CLI 真实端点不完全一致，参考 references/minimax-key-formats.md）

### 正确的上课流程（重要！）
**不要在输入框手动输入主题，要用API或"导入课堂"上传PDF！**

方式一（API，推荐）：
1. 裁切好的PDF → `/api/parse-pdf` 解析 → `/api/generate-classroom` 生成课堂
2. 轮询状态直到completed → 获取课堂URL

方式二（浏览器）：
1. 裁切好的PDF → 点OpenMAIC页面的"导入课堂"按钮 → 上传PDF
2. OpenMAIC自己读PDF → 生成课程大纲 → AI老师讲课

**不要在输入框打字生成topic链接——用户多次纠正。**

## 操控用户前台浏览器（用户多次强调！）

**当用户要求"操控浏览器""配置页面""打开页面让用户看到"时，必须用Edge CDP连接用户前台Edge浏览器，不能用`browser_navigate`（它是headless后台浏览器，用户看不到）。**

### 启动Edge调试模式
```bash
taskkill /F /IM msedge.exe  # 先杀所有Edge
"/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" \
  --remote-debugging-port=9222 \
  --user-data-dir="D:/edge_debug_profile" \
  --no-first-run http://localhost:3000
```

### 通过Playwright CDP连接
```python
from playwright.sync_api import sync_playwright
pw = sync_playwright().start()
browser = pw.chromium.connect_over_cdp('http://127.0.0.1:9222')
context = browser.contexts[0]
page = context.pages[0] if context.pages else context.new_page()
page.goto('http://localhost:3000')
pw.stop()
```

## 工作流中的角色分工（重要）

| 角色 | 负责什么 | 不负责什么 |
|------|---------|-----------|
| **Hermes** | 规划每天学什么 → 用MIMO多模态读课本 → 出测验题 → 批改答案 → 分析薄弱点 → 生成课件 | 不决定OpenMAIC的教学重点 |
| **OpenMAIC** | 自己读PDF理解内容 → 自己决定教学重点 → 生成课件 → AI老师讲课 | 不规划、不追踪、不出题 |
| **MIMO多模态** | 读课本图片 → 提取知识点 → 生成测验题 | 不讲课 |
| **learning-state.json** | 存储学习计划、进度、薄弱点、测验结果 | 不做决策 |

**Hermes的定位（全能教师）：**
- 规划每天学什么（"今天学第一单元《宿建德江》"）
- 用MIMO多模态读课本，提取知识点
- 根据知识点出测验题（选择题、填空题、简答题）
- 批改答案，分析薄弱点
- 跟踪测验结果，调整学习进度
- **不传知识点给OpenMAIC**——OpenMAIC自己读PDF
- **不决定教学重点**——OpenMAIC自己决定

## 📄 教材 PDF 裁切 — 视觉方案已切换（2026-08-22，用户要求）

**PDF 页面渲染 + 视觉识别全部走 Hermes 同供应商（opencode GO），不再用 MIMO 多模态：**

```bash
# 1. 渲染页面为 PNG（pypdfium2，D:\Python312 已装；pymupdf/fitz 重装后未装）
D:/Python312/python.exe -c "
import pypdfium2 as pdfium
pdf = pdfium.PdfDocument(r'D:\projects\family-tutor\materials\<课本>.pdf')
page = pdf[<索引>]                      # 0-indexed
bitmap = page.render(scale=1.4)         # ~100dpi
bitmap.to_pil().save(r'...page_N.png')"

# 2. 视觉识别（opencode GO + ox-alpha-free，2026-08-22 用户指定；ds4f-vision-exp 为备选）
#    ⚠️ max_tokens 必须 ≥2000（否则推理吃满返回空 content）；英文提示词更稳
#    2026-08-22 实测：ox-alpha-free 正确识别语文/英语课本页（含无页码页面的内容判断）
POST https://opencode.ai/zen/go/v1/chat/completions
Authorization: Bearer <OPENCODE_GO_API_KEY>
{"model": "ox-alpha-free",
 "messages": [{"role": "user", "content": [
   {"type": "text", "text": "Which textbook page is this? ..."},
   {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}]}],
 "max_tokens": 2000}
```

裁切流程不变（先视觉定位单元边界 → 确认"第X单元"字样 → pymupdf/pypdfium2 按页拆分 → 裁切后逐页视觉验证年级与内容）。**PDF 源文件标注的年级 > 视觉识别结果**。

## 📄 教材处理流程

**绝不能凭空生成课程内容，必须基于真实教材。** 详见 `references/pdf-textbook-processing.md`。

1. **视觉识别目录**：用 `vision_analyze` 读取PDF目录页，获取单元/课文/书页码
2. **视觉定位单元边界**：书页码≠PDF索引，必须逐页验证"第X单元"字样
3. **按单元裁切PDF**：用 pymupdf (`fitz`) 按视觉确认的索引拆分
4. **视觉精读每单元**：提取生字、课后问题、学习目标、语文园地内容
5. **创建知识要点文档**（独立 .md 文件）：
   - 路径：`D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`
   - 内容：主要概念、公式、例题、练习题、易错点、拓展知识
   - **用途**：推进学习计划和查漏补缺时直接参考，不需要重新提取
6. **告诉OpenMAIC今天学什么**：只说"学哪课"，不传知识点
7. **上传裁切PDF到OpenMAIC**：作为参考材料存储
### PDF 裁切通用流程（适用于所有学科）

**英语/数学/语文都用同样的 pymupdf 裁切流程：**

```python
import fitz

# 裁切英语 PDF（第4-10页）
doc = fitz.open(r'英语课本.pdf')
pdf = fitz.open()
pdf.insert_pdf(doc, from_page=3, to_page=9)  # 0-indexed: 第4-10页
pdf.save(r'D:\projects\family-tutor\materials\english_unit1.pdf')
pdf.close()

# 裁切数学 PDF（第53-60页）
doc = fitz.open(r'数学课本.pdf')
pdf = fitz.open()
pdf.insert_pdf(doc, from_page=52, to_page=59)  # 0-indexed: 第53-60页
pdf.save(r'D:\projects\family-tutor\materials\math_unit1.pdf')
pdf.close()
```

**验证裁切结果（用 MIMO 多模态）：**
```bash
# 提取第一页为图片
python -c "
import fitz
doc = fitz.open(r'D:\projects\family-tutor\materials\english_unit1.pdf')
page = doc[0]
pix = page.get_pixmap(dpi=150)
pix.save(r'D:\projects\family-tutor\materials\verify_english.png')
"

# 用 MIMO 多模态验证内容
node "D:/mimo-multimodal/image_understand.py" \
  --type image --input "verify_english.png" \
  --prompt "这是课本的哪一部分？有什么内容？" --json
```

**已验证的裁切结果（2026-07-10）：**
- 英语：`english_unit1.pdf`（第4-10页）→ 语法复习板块（代词 + 可数名词）
- 数学：`math_unit1.pdf`（第53-60页）→ 第四单元《分数的应用》
- 数学：`math_unit2.pdf`（第95-102页）→ 第九单元《数据的表示和分析（三）》

**注意**：裁切后必须用 MIMO 多模态验证内容，确保裁切正确。

## 用户说"我要上课" / "按照工作流来" / "今天上课" / "继续推进"

**这是用户在指示我引导孩子完成完整学习闭环。按下面的步骤一步一步来，每一步主动做，不要问确认。**

### 完整工作流

**第 1 步：检查服务状态 + 读取学习计划**
1. **必做**：先检查 3 个服务（OpenMAIC, 答题服务, TTS）
2. 读取 `D:\projects\family-tutor\learning-state.json` 看当前进度
3. 读取 `D:\projects\family-tutor\learning-plan.md` 看完整计划
4. **告诉孩子**："今天我们学习 [科目] 的 [课文]，准备好了吗？"

**第 2 步：检查课件**
1. 检查 `D:\projects\OpenMAIC\data\classrooms\` 是否有今天的课件
2. 如果没有：
   - 从 `D:\projects\family-tutor\materials\[subject]\` 找今天的 PDF
   - 调用 `python scripts/generate-all-courseware.py` 生成
3. 如果有：**直接打开** `cmd.exe /c "start http://localhost:3000/classroom/{id}"` ——不要告诉孩子链接
4. **告诉孩子**："课件已经打开，开始上课吧！"

**第 3 步：等孩子上完课，生成测验**
1. 孩子上完课后说"上完了"/"开始测验" → 生成测验
2. 读取 `D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`
3. 根据知识点生成 5-10 道题（2 选 + 3 简答，至少 1 道简答）
4. 写入 `D:\projects\family-tutor\quiz-data\quiz-data-day{N}.json`
5. **告诉孩子**："测验已经准备好，请打开答题页面作答。"

**第 4 步：等孩子提交答案**
1. 孩子提交后，答案自动保存到 `quiz-results/latest.json`
2. 孩子说"我答完了" / "批改一下" → **我批改**
3. 选择题立即判断对错
4. 简答题调用 minimax AI（OAuth token）批改
5. 生成详细报告：
   - 每题得分（选择=100/0；简答=0-100）
   - 错误原因、参考答案、改进建议
6. **告诉孩子**：报告内容

**第 5 步：分析薄弱知识点 + 查漏补缺**
1. 根据答题结果识别薄弱点（不是错题，而是知识点类别）
2. 跑 `python scripts/analyze-weak-points.py` 分析
3. 跑 `python scripts/generate-remedial.py` 生成补强练习（从课本随机抽同类题）
4. 补强练习写入 `quiz-data-remedial.json`
5. **直接打开** `cmd.exe /c "start D:\projects\family-tutor\load-quiz-remedial.html"`——不要告诉孩子链接
6. **告诉孩子**："我看了你的答题，[薄弱点总结]。来试试这些补强练习。"

**⏱️ 次数限制（重要）**：
- **课后练习最多 4 次**（1 次正式测验 + 最多 3 次补强）
- **如果补强 3 次后仍有薄弱点**，不要再补强，标记为"已尽力"，进入下一天
- 不要一直补强同一知识点，否则孩子会厌烦
- 用 `learning-state.json` 跟踪补强次数：`day{N}_remedial_count`

**第 6 步：循环或进入下一课**
- **如果补强后仍薄弱**：继续生成同类练习
- **如果已掌握**：进入下一天的课件

**关键原则**：
- ✅ **每一步主动推进**，不要问"要不要继续？"
- ✅ **每次回复前检查服务**（孩子不能准确表达问题）
- ✅ **告诉孩子当前进度**："现在我们做完了第3题..."
- ✅ **完成后等孩子确认或继续**

### 1. 开始学习
用户上传课本PDF后说"开始学习"：
1. 用 MIMO 多模态视觉精读课本（目录→单元边界→每单元关键页）
2. **创建知识要点文档**（独立 .md 文件）：
   - 路径：`D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`
   - 内容：主要概念、公式、例题、练习题、易错点、拓展知识
   - **用途**：推进学习计划和查漏补缺时直接参考，不需要重新提取
3. **创建学习规划文档**（独立 .md 文件）：
   - 路径：`D:\projects\family-tutor\learning-plan.md`
   - 内容：学习目标、学习安排、学习流程、技术架构
4. 制定学习计划（每天学什么）
5. 告诉OpenMAIC第1天学什么（只说"学哪课"，不传知识点）

### 2. 每天上课
用户说"今天上课"：
1. 读取 `learning-state.json` 看当前进度+薄弱点
2. 有薄弱点→先生成补强小课的PDF片段
3. 用 OpenMAIC 生成当天课件（上传裁切PDF + enableTTS:true）
4. **课件生成后导入 OpenMAIC 主页**（"最近学习"）：
   - OpenMAIC 主页从 **IndexedDB** 读取课件列表，不是文件系统
   - 文件系统的 `/data/classrooms/*.json` 只是临时存储
   - **方案 1（手动）**：打包 ZIP → 手动导入
   - **方案 2（自动）**：修改 OpenMAIC 源码（`listStages()` 从文件系统读取）。详见 `references/openmaic-indexeddb-import.md`
5. OpenMAIC自己读PDF决定怎么教
6. **不要在输入框打字，不要生成topic链接，直接用API生成**

### 3. 课后测验（两阶段流程）
用户说"今天测验"或"按照工作流来"：
1. **读取知识要点文档**（`D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`）
2. 根据知识点生成测验题（选择题、填空题、简答题）
3. 将题目写入 `D:\projects\family-tutor\quiz-data\quiz-data-day{N}.json`
4. **自动打开答题页面**：`cmd.exe /c "start D:\projects\family-tutor\quiz-pending.html"`（新模式：等待批改版）
5. 用户在网页上作答，**点击"提交答案"**：
   - 答案保存到 `D:\projects\family-tutor\quiz-results\quiz_{timestamp}.json`
   - 标记 `pendingGrading: true`
   - **不立即批改**（关键：新模式！）
6. 用户说"**我答完了**"：
   - Hermes 读取最新的 `quiz-results/latest.json`
   - **逐题批改**（选择题立即判断对错，简答题调 AI）
   - 生成详细的批改报告（错误原因、参考答案、改进建议）
   - 保存到 `quiz-results/{timestamp}-graded.json`
7. Hermes 读取 `latest.json` 分析薄弱点 → 写入 `learning-state.json` 的 `weak_areas`

**AI 批改规则**（用户明确要求）：
- **不要用关键词匹配**，要用 AI 语义理解
- **简答题必须给出**：错误原因 + 参考答案 + 改进建议
- **理科题目要指出**：解题过程中的问题
- **拼音题必须用选择题**，不能用填空题（用户原话："语文的拼音这种题打字是打不了的"）

**答题系统文件**：
- `D:\projects\family-tutor\quiz.html` — Open Design 美化的深色主题答题页面
- `D:\projects\family-tutor\load-quiz.html` — 加载页面（点击"开始测验"自动加载题目并跳转）
- `D:\projects\family-tutor\quiz-server.py` — 结果接收服务（端口 8765）
- `D:\projects\family-tutor\quiz-results\` — 结果存储目录
- `D:\projects\family-tutor\quiz-data-day{N}.json` — 每天的测验题数据

### 4. 分析漏洞 + 查漏补缺
1. **读取知识要点文档**（`D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`）
2. **分析漏洞知识点**（不是错题）：
   - 运行 `python analyze-weak-points.py` 分析薄弱知识点
   - **输出**：薄弱知识点列表（如"生字拼音"、"字词解释"、"诗词情感对比"）
   - **关键**：薄弱点是"类别"（如生字拼音），不是"具体例子"（如渚、见）
3. **动态生成补强练习**（根据知识点出新题，每次不同）：
   - 运行 `python generate-remedial.py` 生成补强练习
   - **核心逻辑**：从知识要点文档中提取相关知识点，随机选择出题
   - **每次生成的题都不同**，但考点一致
   - **答案随机分布**，不会全是 A
   - **只错选择题 → 全是选择题**
   - **错了简答题 → 才包含简答题**
   - **示例**：薄弱点是"生字拼音" → 测试多个不同生字（旷、暮、轼、稻...），不是只测渚和见
4. 自动打开补强练习页面：`cmd.exe /c "start D:\\projects\\family-tutor\\load-quiz-remedial.html"`
5. 用户作答后 AI 批改（不是关键词匹配！）
6. 如果仍有漏洞→继续补强
7. 如果已掌握→进入下一课
**具体流程（2026-07-10 实证）：**
```bash
# 1. 读取薄弱知识点
curl -s http://localhost:8765/api/quiz-results/latest | python -c "
import json, sys
d = json.load(sys.stdin)
print('=== 薄弱知识点 ===')
for w in d.get('weakAreas', []):
    print(f'  🔴 {w[\"topic\"]}: {w[\"rate\"]}%')
"

# 2. 生成补强练习题 → quiz-data-remedial.json
# 3. 创建补强加载页 → load-quiz-remedial.html（显示薄弱知识点列表）
# 4. 自动打开：cmd.exe /c "start D:\projects\family-tutor\load-quiz-remedial.html"
# 5. 用户作答后再次读取结果，检查薄弱知识点 rate 是否 >= 80%
```

**补强练习文件命名：**
- `quiz-data-remedial.json` — 补强练习题数据
- `load-quiz-remedial.html` — 补强练习加载页（显示薄弱知识点列表）

详见 `references/quiz-workflow-complete.md`。

### 5. 次日循环
第二天说"今天上课"：
1. 读 weak_areas → 生成补强小课
2. 生成新课（继续进度）
3. 循环直到计划完成

## ~~OpenTutor API~~（已弃用，仅供参考）
**OpenTutor 已完全移除（2026-07-10）。** 以下 API 仅供参考，不要再尝试调用。
- `GET /api/bridge/progress-summary` — 学习概览
- `GET /api/bridge/review-topic` — 分析薄弱点生成强化主题
- `POST /api/courses/` — 创建课程（注意尾部斜杠，字段是 `name` 不是 `title`）
- `POST /api/content/upload/` — 上传文件（FormData: file + course_id）
- `GET /api/quiz/{course_id}/next?count=N` — 获取测验题
- `POST /api/quiz/{course_id}/submit` — 提交答卷
- **所有POST/GET必须带尾部斜杠**，否则307重定向丢body
- **启动目录必须是 `D:\\projects\\OpenTutor\\apps\\api\\`**，不是 `D:\\projects\\OpenTutor\\`（否则 `ModuleNotFoundError: No module named 'config'`）。正确启动命令：`cd /d/projects/OpenTutor/apps/api && D:/projects/OpenTutor/venv/Scripts/python.exe -m uvicorn main:app --port 8000 --host 0.0.0.0`

**替代方案**：Hermes 直接用 MIMO 多模态出题 + quiz.html 答题 + quiz-server.py 接收结果 + Hermes 批改分析。

## 学习中心页面
`D:\projects\family-tutor\index.html` — Open Design生成基础设计 + 手动接入后端
- 文件上传区（拖拽+点击，支持PDF/Word/PPT/Excel/ZIP/图片/TXT/Markdown）
- 统计面板（课程数/测验题/正确率/薄弱知识点）
- 查漏补缺Tab（一键强化课堂 + 综合测验 + 薄弱知识点列表）
- 空状态引导（无硬编码内容）

## Open Design 集成（页面美化）— 强制使用

**⚠️ 用户明确要求：所有页面美化必须用 Open Design，不要手写 CSS。** 用户原话："不要你自己优化，我指定了open design就不要用别的"。

### 完整流程（2026-07-10 实证）
1. **启动 Open Design**（需 Node 24）：
   ```bash
   cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev stop web
   cd /d/projects/open-design && C:/Users/MR/AppData/Local/nvm/v24.18.0/npx pnpm tools-dev start web
   ```
   端口看启动输出（如 `http://127.0.0.1:60463`），**每次重启端口可能变**。

2. **打开 Web UI**：`cmd.exe /c "start http://127.0.0.1:<port>"` 或用 `browser_navigate`

3. **输入设计需求**：在输入框输入中文描述 → 点"发送"

4. **回答表单问题**（Open Design 会弹出确认表单）：
   - "我们要做什么？" → 选 **Prototype**
   - "目标平台" → 选 **响应式网页**
   - "目标用户" → 填具体描述
   - "大概需要多少内容？" → 填具体数量
   - 点 **"一键跳过"** 可跳过所有问题直接生成

5. **等待生成**（1-3 分钟，取决于模型速度）

6. **复制生成文件**：
   ```bash
   cp "D:/projects/open-design/.od/projects/<project-id>/index.html" "D:/projects/family-tutor/quiz.html"
   ```
   生成文件路径在 Open Design 聊天界面会显示（"写入 D:\...\index.html · N 行"）

### 注意事项
- **不要尝试用 CLI 命令行生成** — `od artifacts create` 只能上传文件，不能触发设计生成
- **不要尝试用 API 直接调用** — Open Design 的 API 不支持直接生成设计
- **必须通过 Web UI 交互** — 输入提示词 → 回答表单 → 等待生成
- **生成后需要手动更新题目数据** — Open Design 生成的是示例题目，需要替换为实际测验题
- **如果生成的设计不满意**，可以重新输入不同的提示词再生成一次

详见 `references/open-design-integration.md`。

**⚠️ 关键：Open Design 生成的页面不包含后端同步代码。** 生成后必须手动添加 sync 代码（POST 结果到 `http://localhost:8765/api/quiz-results`）。详见 `references/quiz-system-design.md` 的"同步代码模板"小节。

## 📷 扫描版课本 → KP 库（2026-09-08 验证流程，国家智慧教育平台）

**适用场景**：当用户给一个**国家中小学智慧教育平台**的 contentId（如 `45fe27cf-8cb3-4670-8397-a482731412fc`），要**直接拿到扫描版图片**作为"课本"放进 `D:/家教/{subject}/课本/`，再精读提 KP 库。**不需要 PDF 也不需要登录**。

### 完整流程（已 49 张实测验证，2026-09-08）

**Step 1 — 拿课本元数据 + 扫描版 JPG 直链**

```python
# 国家智慧教育平台的 s-file 端点公开可读（不需要登录！）
import urllib.request, json
CONTENT_ID = "<uuid>"
meta_url = f"https://s-file-2.ykt.cbern.com.cn/zxx/ndrv2/resources/tch_material/details/{CONTENT_ID}.json"
data = json.loads(urllib.request.urlopen(meta_url, timeout=15).read())
# preview 字段：{"Slide1": "https://r1-ndr.ykt.cbern.com.cn/.../image/1.jpg", ...}
# 出版社在 tag_list 找 tag_name="北师大版"/"人教版" 等
# 标题在 global_title["zh-CN"]
# 49 张扫描版全部在 r1/r2/r3-ndr.ykt.cbern.com.cn
```

**Step 2 — 批量下 JPG（公开资源，不需要 auth）**

```python
# 并发 8 下载 49 张 (~3-5 秒搞定)
import os
from concurrent.futures import ThreadPoolExecutor
sd = f"D:/家教/数学/课本/{CONTENT_ID}"
os.makedirs(sd, exist_ok=True)
def dl(n, url):
    p = f"{sd}/slide_{n:03d}.jpg"
    if os.path.exists(p) and os.path.getsize(p) > 5000: return
    urllib.request.urlretrieve(url, p)
with ThreadPoolExecutor(max_workers=8) as ex:
    list(ex.map(dl, range(1, 50), [data["custom_properties"]["preview"][f"Slide{n}"] for n in range(1, 50)]))
```

**Step 3 — PaddleOCR 批量 OCR（CPU 即可，每张 2-3 秒）**

参考 `scripts/ocr-batch-pages.py` — 跑完一个目录所有 JPG，输出 `{y, x, conf, text}` 列表，y-sorted。

**Step 4 — KP 库建表（12 单元 × 5-8 KP = ~50-80 KP）**

PaddleOCR 跑完后，**逐页**用 vision_analyze 看图（10-30 张关键页足够）+ LLM 知识补全，建 3 层结构：
- `D:/家教/{subject}/知识点及掌握情况/{subject}_{grade}_volume{N}_kpdb.json` — 总表
- `D:/家教/{subject}/知识点及掌握情况/{kp_id}.json` — 每个 KP 一个文件（micro-lesson.py 按 kp_id 自动加载）
- `D:/家教/{subject}/知识点及掌握情况/{subject}_{grade}_volume{N}_overview.md` — 人读总览

**Step 5 — 手工补核心公式（OCR 弱项）**

PaddleOCR 对印刷体汉字 100% 准，对**分式/公式** 30%（被打散成多行）。需要**人工**给关键 KP 加 `key_formulas` + `common_mistakes` 字段。例：

```json
{
  "id": "u1.k3", "name": "分数除以分数",
  "rule": "分数÷分数 = 被除数 × 除数的倒数",
  "example": "5/6 ÷ 12/5 = 5/6 × 5/12 = 25/72",
  "key_formulas": ["5/6 ÷ 12/5 = 5/6 × 5/12 = 25/72", "1/6 的倒数是 6"],
  "common_mistakes": ["分母漏乘", "分子分母同时除"]
}
```

### OCR 工具选型（4 选 1，2026-09-08 验证）

| 工具 | 跑通 | 汉字 | 公式 | 推荐场景 |
|---|---|---|---|---|
| **PaddleOCR 2.7 (CPU)** | ✅ 装上 | 100% | 30% (弱) | **本机默认选择**，2.5s/张 |
| **UmiOCR v2.1.5 (开源)** | 需手动下（GitHub/夸克在您网络都不顺） | 100% | 弱 | 想要桌面 GUI 时 |
| **Unlimited-OCR (VLM)** | ❌ 8GB 显存+RAM 装不下 6.36GB 模型 | SOTA | SOTA | 32GB RAM + 16GB 显卡才跑得动 |
| **ABBYY FineReader PDF** | 商业，700MB+，需夸克手动下 | SOTA | SOTA | 已有许可证时 |

**结论**：本机用 PaddleOCR 就够。公式差用手工补。

### Pitfalls — OCR 课本流程
> （2026-09-29 瘦身迁出）详见 `references/ocr-textbook-workflow-pitfalls.md`。核心：OCR/库脚本一律用 `D:/Python312/python.exe` 经 terminal 跑（勿用 execute_code）；PaddleOCR 用 2.x 降级组合。


### 相关参考资料

- `references/scanned-textbook-kp-extraction.md` — 详细 OCR 选型 + KP 库结构
- `references/ocr-tool-comparison-2026-09-08.md` — 4 工具对比
- `references/micro-lesson-real-test-2026-09-08.md` — 微课堂端到端
- `scripts/ocr-batch-pages.py` — 可复用 PaddleOCR 批量脚本

---

## Pitfalls

> ⚠️ **Pitfalls 已拆分到 `references/pitfalls.md`**（原文约 40K 字符，2026-09-24 拆分以便 SKILL.md 保持可维护）。
> 需要排查具体坑时读该文件。

## 调用 OpenMAIC 的"红线"（用户多次明确纠正！）
27. **必须按学习规划来，不要"按自己想"** — 用户原话："我们不是按照学习规划来的吗？第一天的课件啊？"。每天上课前**先读 `D:\projects\family-tutor\learning-state.json` 看 day N 学什么**，按学习计划生成对应单元的PDF课堂
28. **`enableTTS: false` 会让课件**完全没有声音资产**，前端播放时一片死寂**（2026-07-09 实证）— 测试生成时用 `"enableTTS": false` 想加速，结果课件生成完成后**所有 speech action 只有 `{id, type:'speech', text}` 三个字段**，前端播放走实时 TTS 调用，如果服务端 key 没配就直接 500。**最稳的做法是默认 `enableTTS: true`**（代价是生成时间多 1-2 分钟）。如果用户报"没声音"，**第一件事**是 grep 课件 JSON：`grep '"type":"speech"' data/classrooms/<id>.json | head -1` 看有没有 audio 字段。**没有 audio 字段 = 生成时没开 TTS，必须重新生成带 `enableTTS: true`**
29. **Minimax TTS 模型对比** — 内置6个模型，按质量排序：speech-2.8-hd（默认，HD音质，最稳）> speech-2.8-turbo（HD快版）> speech-2.6-hd（上一代HD）> speech-2.6-turbo > speech-02-hd > speech-02-turbo（老旗舰不推荐）。**家庭教师推荐 speech-2.8-hd + Chinese (Mandarin)_Crisp_Girl 或 female-shaonv 少女音色**（孩子上课）
30. **Token 消耗控制（2026-07-10 实证）** — 完整 13 页课堂带 web search + image + TTS 的单次 job 约消耗 **475K 输入 tokens + 96K 输出 tokens**（占月配额 ~22%）。**省 token 的开关组合**：
    - **最快省 token**（课件文字内容质量不降）：`enableWebSearch: false` + `enableImageGeneration: false` + `enableTTS: true`（**只关 web search 和 image**）— 输入降到 30-50K（**省 90%** token），课件内容和 TTS 完整
    - **最快**（但课件可能没图）：`enableTTS: true` + 其他全 false — 2-3 分钟跑完
    - **完整功能**（用户已显式禁用）：`enableWebSearch: true` + `enableTTS: true` + `enableImageGeneration: true` — 5-7 分钟跑完
    - **绝对不要 `enableTTS: false`** —— 课件没声音（pitfall 28）
31. **图片生成默认关闭（2026-07-10 用户决定）** — minimax `image-01` 生成的图**质量很差**（不写实、跟小学语文课本内容匹配度低），**默认 `enableImageGeneration: false`**。用户没特别说要图就**永远不开**。要打开时必须先确认（避免再开）
31a. **默认 generate-classroom 参数（2026-07-10 实战）** — 用户明确要求的默认参数，不要自行更改：
    ```json
    {
      "enableTTS": true,
      "enableImageGeneration": false,
      "enableWebSearch": true,
      "webSearchProviderId": "baidu",
      "agentMode": "default"
    }
    ```
    **只改 requirement 和 pdfContent**，其他参数不要动。用户说"开启/关闭"某功能时才改对应字段。**用户原话**：\\\"那应该就是default就可以。不要快速模式\\\"。
    **agentMode 必须是 `'default'`**（用户原话："那应该就是default就可以。不要快速模式"）。`'generate'` 模式虽然快但 minimax M3 会"自主发挥"生成偏离主题的内容。**绝对不要用 `'fast'`**（OpenMAIC 不支持，会被忽略或报错）。
31b. **pdfContent 太大不能用 curl 命令行传（2026-07-10 实证）** — 扫描版 PDF 解析后 `pdfContent` 字段约 18-22MB（base64 图片），**超出 bash 命令行参数长度限制**（`Argument list too long`）。**必须用 Python urllib 发请求**。详见原 SKILL.md `31b` 段落。
31c. **当前模型不支持视觉时的处理（2026-07-10 实证）** — 切换到 mimo-v2.5-pro 后 `vision_analyze` 和 `browser_vision` 都报 404（模型不支持图片输入）。**替代方案**：
    - 用 pymupdf 提取目标页为 PNG → `cmd.exe /c "start page_N.png"` 让用户自行查看
    - 或切回支持视觉的模型（如 minimax M3）做视觉分析
    - **不要在不支持视觉的模型上反复尝试 vision_analyze**——会浪费时间
75. **教材背景年级与重点必须明确（2026-07-10 实证）** — 用户原话："你知道这是小学五年级的数学课本吗？请你在知道背景是小学五年级数学课本的情况下再确定一下？" / "这些全部都是六年级上册的内容。切割的原pdf不是写了吗？我的意思是，这个的背景是小学数学，而不是扫描数据分析师应当学习的内容，重心不要搞错了"。**症状**：提取的数学 Day 4 知识点把"身高分段统计"写成了五年级内容（实际 PDF 是四年级下册）；数学 Day 3 知识点包含了"数据收集"、"数据分析师"等专业表述。**正确做法**：
    - **裁切 PDF 后立即用 MIMO 多模态验证年级和内容**：
      ```bash
      node "D:/mimo-multimodal/image_understand.py" \
        --type image --input "verify_math_day1.png" \
        --prompt "这是小学数学课本。请问这是几年级的课本？主要讲什么内容？" --json
      ```
    - **第一句 prompt 必须问年级**——不同年级同一知识点深度不同
    - **知识要点文档必须标注年级**：`## 学习目标（小学六年级上册）`
    - **不要用专业术语**——小学生课本用简单语言（"用分数乘法解决生活中的问题"），不要用"数据分析师"、"数据建模"等专业表述
    - **重心要对**：背景是小学数学，不是数据分析专业或政治等人文科目
    - **用户原话**："重心不要搞错了"——背景是小学数学
    - **重要**：math day 4 PDF 实际是四年级下册（用户原文确认），但被 MIMO 错误识别为五年级。用户原话："这些全部都是六年级上册的内容。切割的原pdf不是写了吗？"——即 PDF 原始文件标注的年级才是 ground truth，不要轻信 MIMO 识别结果。**PDF 源文件年级 > 视觉识别年级**，如果冲突以 PDF 源文件标注为准。
75b. **AI 生成内容必须对照知识要点文档核对（2026-07-10 实证）** — 用户原话："你等会可以拿那些知识点大致的核对一下生成的课程对不对哈"。**症状**：需求是"数据的表示和分析（三）- 人口老龄化"，minimax M3 生成"统计图的选择与应用"。**核对方法**：课件生成完后，对照 `knowledge-points/{subject}_day{N}.md` 检查关键知识点是否出现。**正确做法**：
    - 读取课件 JSON，对照知识要点文档
    - 检查场景标题和内容是否包含关键概念
    - 发现内容错误立即重新生成（minimax M3 在 `'generate'` 模式下更容易偏离主题）
    - **用户原话**："我再次提醒，我们的背景是小学六年级数学，而不是政治等人文科目，它的课件是没问题的吧？"
    - **关键判断标准**：用户原话"我再次提醒" — 即使 AI 生成的课件涉及"人口老龄化"，只要内容核心是小学数学（如统计图），就是合格的。**不要因为引入了社会场景就认为内容错误**，关键是**核心数学知识点是否正确**。
75c. **minimax M3 在 'default' 模式下生成内容更准确（2026-07-10 用户偏好）** — 用户原话："agentmode默认切换到支持的最高质量挡位，当前是什么挡位？" / "那应该就是default就可以。不要快速模式"。**正确做法**：
    - **永远用 `'agentMode: 'default'`**（用户明确要求）
    - **永远不要用 `'agentMode: 'fast'`**（OpenMAIC 不支持，会被忽略或报错）
    - **`'generate'` 模式**：速度快但模型容易"自主发挥"生成偏离主题的内容
    - **`'default'` 模式**：质量最高，模型更稳定地按需求生成
    - 查看源码：`/d/projects/OpenMAIC/lib/server/classroom-generation.ts:50` 定义 `agentMode?: 'default' | 'generate'`
75d. **答案随机分布必须真随机（2026-07-10 用户强烈纠正）** — 用户原话："你每次出的题都是一样的，这不叫查漏补缺" / "你自己说答案随机分布了，然后不管是你给的网页还是你第二遍给的答案都是aaaaa 你在自己反驳自己吗？"。**正确做法**：
    - 使用 `shuffle_options()` 函数打乱选项顺序
    - 不能让正确答案总是在 A 位置
    - **用户原话**：\\\"先验证再改\\\"——做完补强练习后检查答案分布，不能全是 A
75e. **补强练习必须生成新题，不能重复原题（2026-07-10 用户强烈纠正）** — 用户原话："你每次出的题都是一样的，这不叫查漏补缺，所以我是让你总结漏洞知识点而不是错题"。**核心逻辑**：
    - **分析漏洞知识点**（不是错题）：从错题中提取薄弱知识点（如"渚的读音"、"见的读音"、"诗词情感对比"）
    - **用 AI 生成新题**：调用 MIMO API 根据知识点生成新题
    - **每次生成的题都不同**（AI 随机变换选项、问法），但考点一致
    - **不要重复原题**——用户明确说"这不叫查漏补缺"
    - **示例**：薄弱点是"生字拼音" → 测试多个不同生字（旷、暮、轼、稻...），不是只测渚和见
75f. **切分 PDF 必须按学科合理切分（2026-07-10 实证）** — 用户原话："这些全部都是六年级上册的内容。切割的原pdf不是写了吗？"。**正确做法**：
    - **数学**：大单元再分小节（如 unit1 前3页+后5页 → 2个 PDF，每天一课）
    - **英语**：按语法板块裁切（如 unit1 第4-10页 → 1个 PDF）
    - **语文**：按古诗三首裁切（如 第6-7页、94-95页）
    - **每个小节生成独立课件**（一天一课）
    - **裁切后用 MIMO 多模态验证内容**（pitfall 6）

### OpenMAIC IndexedDB vs 文件系统（2026-07-10 关键发现）

61b. **OpenMAIC 主页从 IndexedDB 读取课件列表（不是文件系统）**（2026-07-10 实证）— 用户多次报"课件生成完了但主页看不到"。**根因**：OpenMAIC 存储是双轨制——生成时写文件系统，展示时从 IndexedDB 读。IndexedDB 是浏览器端数据库，服务端 Node.js 无法直接读写。**症状**：
- 文件系统有 7 个课件 JSON
- 主页只显示 3 个（之前手动在浏览器生成的）
- **解决方案**：
  - **方案 1（推荐）**：打包 ZIP → 手动导入。脚本 `D:\projects\family-tutor\scripts\pack-classrooms.py` 输出到 `exported-zips\`。
  - **方案 2（自动化）**：修改 OpenMAIC 源码，让 `listStages()` 也从文件系统读取。新增 API `D:\projects\OpenMAIC\app\api\classroom\list-filesystem\route.ts` + 修改 `D:\projects\OpenMAIC\lib\utils\stage-storage.ts`。**限制**：只读，无法编辑。
  - **详见**：skill `openmaic-indexeddb-import` 或 `references\openmaic-indexeddb-import.md`
- **用户原话**："你说是自动的，但这里面没有啊" / "我从始至终都是想让你做自动导入"
- **不要假设**文件系统存储会自动同步到 IndexedDB

### AI 批改与动态题型（2026-07-10 实证）
> （2026-09-29 瘦身迁出）历史实现（旧 quiz 系统 / MIMO 时代）详见 `references/old-quiz-ai-grading-2026-07.md`；**在用的批改＝§0.4 流水线 + 下方「批改流水线两遍升级」条目**。


## 2026-07-10 晚间补充（中途切换 provider + 知识要点文档工作流）

### Knowledge-Points 文档工作流
每科每个学习单元生成一个独立的 Markdown 文档：`D:\projects\family-tutor\knowledge-points\{subject}_day{N}.md`。文档内容：学习目标、主要概念、核心公式、例题解析、练习题、易错点、拓展知识。**用途**：推进学习计划和查漏补缺时直接参考，不需要重新提取（用户原话："知识要点和学习规划安排是需要用独立world文档来记录的"）。

### 多学科 PDF 裁切规范
- **数学**：大单元再分小节（如 unit1 前3页+后5页 → 2个 PDF），每天一课
- **英语**：按语法板块裁切（如 unit1 第4-10页 → 1个 PDF）
- **语文**：按古诗三首裁切（如 第6-7页、94-95页）

### 切换 Provider 的实战工作流（2026-07-10）
用户原话："mimo 过期了，能不能剩下的部分用 minimax 生成，还是必须重新生成？"

**答案：理论上可以切换 provider 让 job 继续，但实际复杂。** 推荐做法：
1. 修改 `.env.local` 的 `DEFAULT_MODEL`（保留两个 provider 的 key）
2. 重启 OpenMAIC，正在运行的 job 会用新 provider 完成剩余步骤
3. 如果 `sk-cp-` key 已过期，把 `MINIMAX_API_KEY` 替换为 `oat-` OAuth token

**完整脚本**：`scripts/switch-provider.py`（修改 DEFAULT_MODEL）+ `references/provider-switching-mid-task.md`

### 课件内容正确性校验
生成后必须验证内容是否与需求匹配。用户原话："有一个不是已经生成完了吗还重新生成干嘛？" — **答**：跑完了但内容不对（如用户要"人口老龄化"，模型生成"统计图的选择"），必须重新生成。**校验方法**：
```bash
python -c "
import json
d = json.load(open('D:/projects/OpenMAIC/data/classrooms/<id>.json'))
name = d.get('stage', {}).get('name', '')
print(f'课程名: {name}')
"
```

### minimax LLM Key 过期处理（2026-07-10 实证）
症状：所有 minimax LLM 任务报 `AI_APICallError: login fail: Please carry the API secret key in the 'X-Api-Key' field` 或 `authentication_error`。**修法**：把 `MINIMAX_API_KEY` 从 `sk-cp-...` 替换为 OAuth `oat-...` token：
```python
import json, re, shutil
fp = r'D:\projects\OpenMAIC\.env.local'
shutil.copy(fp, fp + '.bak.skcp_backup')
d = json.load(open(r'C:\Users\MR\.mmx\config.json'))
at = d['oauth']['access_token']
content = open(fp, encoding='utf-8').read()
content = re.sub(r'MINIMAX_API_KEY=.*', f'MINIMAX_API_KEY={at}', content)
open(fp, 'w', encoding='utf-8').write(content)
```

### 多进程端口冲突（2026-07-10 实证）
重启服务后，`netstat -ano | findstr :端口` 可能显示多个 PID 监听同一端口。**必须杀掉所有旧进程再重启**，否则请求走旧代码。脚本：
```bash
for pid in $(cmd.exe /c "netstat -ano | findstr :8765 | findstr LISTENING" 2>&1 | awk '{print $NF}' | sort -u | tr -d '\r'); do
  cmd.exe /c "taskkill /F /PID $pid"
done
```

### 批量生成课件脚本（`scripts/generate-all-courseware.py`）
一次提交 5+ 个课件，Job IDs 保存到 `quiz-data/courseware-jobs.json`：
```python
import json, urllib.request

BASE = r'D:\projects\family-tutor\quiz-data'

def gen(parse_file, requirement, name):
    d = json.load(open(parse_file, encoding='utf-8'))
    body = json.dumps({
        'requirement': requirement,
        'pdfContent': d['data'],
        'enableWebSearch': True,
        'webSearchProviderId': 'baidu',
        'enableTTS': True,
        'enableImageGeneration': False,
        'agentMode': 'fast'
    }).encode('utf-8')
    req = urllib.request.Request('http://localhost:3000/api/generate-classroom', data=body, headers={'Content-Type': 'application/json'})
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print(f'{name}: jobId={resp["jobId"]}')
    return resp['jobId']

jobs = []
jobs.append(gen(f'{BASE}/parse_math_day1.json', '六年级上册数学《分数的应用（一）》', '数学Day1'))
# ... 添加其他 4 个
with open(f'{BASE}/courseware-jobs.json', 'w') as f:
    json.dump({'jobs': jobs}, f)
```

### 标准化文件结构（2026-07-10 整理）
```
D:\projects\family-tutor\
├── materials/                  # 课本材料（按学科分文件夹）
│   ├── chinese/                # 语文课本
│   ├── math/                   # 数学课本
│   │   ├── math_day1.pdf       # 前3页（分数的应用一）
│   │   ├── math_day2.pdf       # 后5页（分数的应用二）
│   │   ├── math_day3.pdf       # 前5页（数据分析三）
│   │   └── math_day4.pdf       # 后5页（数据分段整理）
│   └── english/                # 英语课本
│       └── english_unit1.pdf   # 第4-10页（代词与可数名词）
├── knowledge-points/           # 知识要点文档（独立 .md）
├── quiz-data/                  # 测验数据
├── quiz-results/               # 答题结果
├── scripts/                    # 脚本
│   ├── analyze-weak-points.py
│   ├── generate-remedial.py
│   ├── quiz-server.py
│   ├── generate-all-courseware.py
│   └── switch-provider.py
├── backup/                     # 备份
└── *.html                      # 页面文件
```

## 晚间补丁：用户明确要求题型根据错题动态调整（2026-07-10）
用户原话："你的体型应该不是固定的吧，加入我没有错情感差异分析这一步，则应该全是选择题才对吧？" → 补强练习的题型应动态调整：
- 只错选择题 → 全是选择题
- 错了简答题 → 才包含简答题
- 每次生成的题都不同（AI 根据薄弱知识点生成新题），但考点一致
- 答案必须随机分布，不能全是 A（用 shuffle_options 函数打乱）

### 工作流纪律（用户明确纠正过！）
30. **先 reload skill 再动手** — 用户原话：「你好好去看看记忆和skill，你完全没有按照已经设定好的工作流在执行」。当用户说『按学习规划来』『按之前的工作流』『按设定的流程』时，**第一步是 skill_view 当前 skill**，看 SKILL.md 的「完整工作流」小节和 Pitfall 列表是否被自己忽略
31. **PDF 已裁切就直接传，不要再备课** — 用户原话：「你把资料给他就行，然后让他根据资料讲解就行了，不要其他的提示词什么的误导他以及影响质量」。每个单元的PDF已存在于 `D:\projects\family-tutor\materials\unit*_*.pdf`，**调用 OpenMAIC 时只传 1-2 句简短 requirement**
32. **OpenMAIC `requirement` 字段传太短（不传 pdfContent）反而翻车**（2026-07-09 实证）— 完全没传 `pdfContent` 时，OpenMAIC 没东西可读，模型会凭记忆发挥，引入没学过的篇目（生成"马致远《天净沙》"做对比、自动加王安石《书湖阴先生壁》）。**正确做法**是用 `/api/parse-pdf` 解析裁切后的 PDF，把 data 字段作为 `pdfContent` 传入。**如果**只能传 requirement（不传 pdfContent），**必须**在 requirement 里**显式列出**"请只讲以下三首：宿建德江、六月二十七日望湖楼醉书、西江月"，**禁止**用马致远/王安石做对比
33. **Minimax 客服回复的解读陷阱（2026-07-09）** — 客服说"anthropic格式的请求接口：国内服务填 `https://api.minimaxi.com/anthropic`" **这是回答 LLM 端点的问题，**不是** TTS/Image 也能用 anthropic 路径**。我误以为 TTS 也能走 `/anthropic/v1/t2a_v2`，实际试了 404。**别把客服关于 LLM 的回复扩展到 TTS/Image**——TTS/Image 单独按 `references/minimax-key-formats.md` 处理
34. **"minimax 套餐一 key 通吃" 是用户常见误解（2026-07-09 minimax CLI 源码证实）** — 用户的 `sk-cp-` 静态 key **只对 Anthropic 兼容端点** `/anthropic/v1/messages` 有效，**不能**用于 minimax 原生 API（`/v1/t2a_v2` TTS、`/v1/image_generation` Image、`/v1/token_plan/remains` Quota 等）。minimax Token Plan 套餐"全模态覆盖"**确实是真的**，但接入方式是 **OAuth Device Authorization Grant**（`mmx auth login` → 浏览器授权 → 拿 `access_token` + `resource_url`），不是用 `sk-cp-` 这种静态 key。**诊断 key 类型错的最快方法**：`curl /v1/token_plan/remains -H "Authorization: Bearer <key>"`，同样 1004 = key 类型错，不要再去查端点路径。当用户说"minimax 一 key 通吃"时，**不要默认相信**——先 curl `/v1/token_plan/remains` 验证一次 key 是否真的能用原生端点
35. **OpenMAIC `Authorization` 头没加 `Bearer` 前缀（minimax TTS 调用细节，2026-07-09 观察）** — OpenMAIC 源码 `lib/audio/tts-providers.ts:714` 写的是 `Authorization: *** ${config.apiKey}`（**没有 Bearer 前缀**），而 minimax 官方文档示例用 `Authorization: Bearer ***`。**这本身不是 1004 的根因**（用户直接 curl 加 Bearer 也是 1004，问题是 key 类型），但 OpenMAIC 即使换成 native access_token 也得保证有 Bearer 前缀。**如果将来 minimax 拿到 OAuth access_token 但 TTS 还 1004**，第一时间检查 OpenMAIC 是否加了 Bearer 前缀
41. **用户问"TTS 为什么没声音"时，按这个诊断树走**（2026-07-09 实战总结）：
    1. `cat data/classrooms/<id>.json | grep '"type":"speech"' | head -1` — **没有 audio 字段？= 生成时没开 TTS（enableTTS:false），必须重生成**
    2. `cat ~/.mmx/config.json | python -c "import json,sys,datetime;d=json.load(sys.stdin);exp=d.get('oauth',{}).get('expires_at','');print('EXPIRED' if exp and datetime.datetime.fromisoformat(exp.replace('Z','+00:00'))<datetime.datetime.now(datetime.timezone.utc) else 'OK')"` — **EXPIRED？跑 `mmx auth login --region cn` 续期 → 同步到 .env.local → 重启 OpenMAIC**
    3. `curl /api/server-providers | python -m json.tool` — **tts: {}（空）？= TTS_MINIMAX_API_KEY 没在 .env.local 配上 / 配错了**
    4. `mmx speech generate --text "测试" --output-file /tmp/x.mp3` — **mmx 直接调都失败？= OAuth token 真失效，去 minimax 控制台看看登录态**
    5. 上面都过了还没声音？查 OpenMAIC 启动日志 `[ServerProviderConfig] Loaded: N LLM, M TTS, K Image, ...` —— M 必须 > 0
42. **mmx CLI 必须先设 `region=cn` 才能调 minimax 国内 API**（2026-07-09 踩坑）— 默认 fallback 到 `https://api.minimax.io`（global），所有原生 API 调不通。**首次安装 mmx 后第一步**：`mmx config set --key region --value cn && mmx config set --key base_url --value https://api.minimaxi.com`
44. **`Failed to parse scene outlines response` 错误 = LLM 输出格式问题，**直接重跑一次**就好**（2026-07-10 实证）— minimax M3 偶发输出非法 JSON（`generate-classroom-scene` 或 `scene-outlines-stream` 调用）。**症状**：job 状态从 `running 15%` 突然 `failed`，error 字段含 "Failed to parse scene outlines response"。**不是配额/不是 key/不是 prompt**——纯 LLM 偶发。**修法**：完全相同的 request body 重跑 1 次就过（session 间不会再次出现相同失败）。**避免误判**：看到此错误时不要去改 .env.local / 提示词 / provider 配置，**直接重跑**。诊断信号是 `step=failed` + error 含 "Failed to parse"
45. **用户"先看效果再采用"的工作流（2026-07-10 实证）** — 选 TTS voice / 改其他全局配置时，**用户先要求"先按这个生成一个课件看看"验证，确认 OK 后才接受**。**不要**在用户说"试试"时直接全局改默认（如 `DEFAULT_TTS_VOICES`）然后让用户盲信。**正确流程**：①生成 1-2 个 sample 让用户试听 → ②用户选 → ③改全局默认 + 重启。**这条跟 pitfall 25g"先验证再改"配合**——具体到 voice 选择的实操就是 10 个候选 + 试听 + 选定 + 改默认
46. **TTS 速率限制 1002 是**大课堂**（>50 speech）的常态，不是 bug**（2026-07-10 实证）— minimax 限流按 RPM（requests per minute），86 个串行请求每条 1.5s 在 1 分钟内跑完 → 触发限流窗口。**症状**：课件 JSON 里 ~30% 的 speech 没有 `audioUrl`（"86 个 speech 只有 57 个有 audioUrl"）。**修法**已经做：retry 3 次（3s/6s/12s 退避）。**生成后必查覆盖率**：`cat data/classrooms/<id>.json | python -c "import json,sys;d=json.load(sys.stdin);speech=[a for s in d['scenes'] for a in s['actions'] if a.get('type')=='speech'];audio=[a for a in speech if a.get('audioUrl')];print(f'{len(audio)}/{len(speech)} ({len(audio)*100//len(speech)}%)')"` 期望 ≥ 95%
47. **每天上课前的检查清单（2026-07-10 实战总结，MIMO TTS 版）** — 用户多次因为漏掉某步导致 5-10 分钟浪费。**按顺序**：
    1. **MIMO 代理确认**：`cmd.exe /c "netstat -ano | findstr :8787 | findstr LISTENING"` — 没有？启动 `python D:\projects\family-tutor\mimo-tts-proxy.py`
    2. **Provider 加载确认**：`curl http://localhost:3000/api/server-providers | python -c "import json,sys;d=json.load(sys.stdin);print('LLM:', list(d.get('providers',{}).keys()));print('TTS:', list(d.get('tts',{}).keys()))"` — 期望 LLM 含 `xiaomi`，TTS 含 `openai-tts`
    3. **检查 MIMO 配额**：MIMO Token Plan 也有用量限制（类似 minimax 2056）。如果生成失败报配额错误，让用户去 MIMO 控制台充值
    4. **如用 minimax TTS 备选**：先跑 Pitfall 40 的 OAuth token 同步脚本（确保 `TTS_MINIMAX_API_KEY` 没过期）

    **这 4 步应该在 30 秒内完成**。任何一步失败立刻停下问用户（不要继续生成）。
48. **MIMO 多模态视觉理解（2026-07-10 实证）** — 当 OpenMAIC 的 LLM 不支持 vision 时（如 mimo-v2.5-pro），用 MIMO 多模态脚本做图片分析：
    ```bash
    node "D:/mimo-multimodal/image_understand.py" \
      --type image \
      --input "D:/path/to/image.png" \
      --prompt "描述这张图片的内容" \
      --json
    ```
    **用途**：
    - 裁切 PDF 后验证页面内容（"这页是哪首古诗？"）
    - 扫描版课本视觉精读（提取生字、课后问题等）
    - 任何需要图片理解的场景
    **注意**：`--json` 输出含 `content`（回答）、`reasoning_content`（思考过程）、`usage`（token 用量）。**不要用 `vision_analyze`**（会 404，因为 mimo-v2.5-pro 不支持 OpenAI 兼容的 vision API）。**也不要用 `browser_vision`**（同样 404）。
    **支持类型**：`--type image`（图片）、`--type audio`（音频转录）、`--type video`（视频理解）。
49. **切换 LLM provider 的正确模式（2026-07-10 用户纠正）** — 用户在 MIMO 和 minimax 之间切换时，**不要问"要不要删旧配置"**。正确做法：
    - **两个 provider 的 key/base_url 都保留**（.env.local 里同时有 `XIAOMI_*` 和 `MINIMAX_*`）
    - **只改 `DEFAULT_MODEL`**（`xiaomi:mimo-v2.5-pro` 或 `minimax:MiniMax-M3`）
    - **重启 OpenMAIC** 让新默认生效
    - 用户说"切到 MIMO" → 改 `DEFAULT_MODEL=xiaomi:mimo-v2.5-pro` → 重启
    - 用户说"切到 minimax" → 改 `DEFAULT_MODEL=minimax:MiniMax-M3` → 重启
    - **不要删旧 provider 的配置**（用户原话："别把minimax删了，我们后续可能还要用"）

> （与上方《2026-07-10 晚间补充》完全重复，已合并删除——原文见上文。2026-09-26 清理）

## 📦 2026-09-12 系统升级：题库 + 模拟卷 + 周计划 + 学情闭环

**新增 5 块拼图，把家教系统从"批改 + 微课"扩成完整闭环**：

### 0. 题库建设的硬性门（每次搜题前必读）

**搜题必须用 `multi-search-engine` skill，不要用 Hermes 自带 `web_search`**。原因：
- `multi-search-engine` 走百度千帆 + Tavily 双 API，**一次返回 6+ 条带 content 预览**的题源
- Hermes `web_search` 只有标题无题面预览，**命中率不到 20%**（实测对比）

**搜题 SOP**（每个 KP 跑一次）：
```python
import json, requests
keys = json.load(open(r'D:\hermes-data\skills\multi-search-engine\api-keys.json', encoding='utf-8'))
baidu_key = keys['channels']['baidu_qianfan']['api_key']

def baidu(q, top_k=6):
    r = requests.post('https://qianfan.baidubce.com/v2/ai_search/web_search',
        headers={'Authorization': f'Bearer {baidu_key}', 'X-Appbuilder-From': 'openmaic', 'Content-Type': 'application/json'},
        json={'messages':[{'content':q,'role':'user'}], 'search_source':'baidu_search_v2',
              'resource_type_filter':[{'type':'web','top_k':top_k}]}, timeout=30)
    return r.json().get('references', []) if r.status_code == 200 else []

# 示例：搜深圳/北师大版六年级上数学
refs = baidu('北师大版 六年级数学上册 第一单元 圆 测试卷 真题')
# refs[i].keys() = title, url, content
```

**搜题关键词模板**（覆盖三科）：
- 数学：`{版本} 六年级数学上册 第{N}单元 {单元名} 测试卷 真题`
- 语文：`部编版 六年级语文上册 第{N}单元 {单元名} 测试卷`
- 英语：`粤教沪外版 六年级英语上册 Unit {N} {单元名} 测试卷`

**搜题原则**：
1. **广撒网**：每个 KP 至少搜 1 次（21 个 KP 全跑一遍），不要只搜 1 个 KP 就停
2. **不限于免费**：搜出来列表就行，是否需要登录是入库阶段的事
3. **content 字段是金**：百度千帆返回的 `content` 经常包含题目预览（如「蒙古包(méng√měng)」），比直接抓原网页更稳

### 0.1. 题库选题红线（用户硬性规则）

**课后习题不入题库**。原因：学生课堂上已经做过，再做一遍没练习价值。可用作：
- AI 参考素材（喂给 LLM 当出题风格样本）
- 课本官方标注的 `is_official=true`，免投票直接入**参考池**（`_meta/reference_pool/`，不参与出卷）

### 0.2. 3 模型投票 pipeline 的硬性约束（参考脚本 `系统/scripts/vote-judge.py`）

| 模型 | Provider | 调用规范 | 网络 |
|---|---|---|---|
| MiniMax-M3 | minimax-cn | `https://api.minimaxi.com/anthropic/v1/messages`，anthropic 协议 | 国内直连 |
| muse-spark-1.3-contributor | opencode zen GO | `https://opencode.ai/zen/go/v1/responses`，**Responses API**（不是 chat/completions！），model 不带 `-free` | Clash 7897 |
| deepseek-v4-pro | new-api | `http://127.0.0.1:13000/v1/chat/completions` | 国内直连 |

**踩坑记录**：
- Muse 走 `/chat/completions` 一律 HTTP 500（必须 `/v1/responses`，参考 skill `muse-model-call`）
- Muse 模型名带 `-free` 走 GO 中继一律 Model not supported（GO 只接受 `-contributor`）
- DS-Pro 是 reasoning 模型，`max_tokens` 必须 ≥ 3000，否则 reasoning_content 把 token 吃光导致 content 为空被判失败
- MiniMax `max_tokens` 设 2000、`timeout` 设 180s（长题会被 60s 默认截断）

**调用规则**：
- **3 模型必须串行**，不可并发（DS-Pro 和任何同 new-api provider 的模型并发必 429）
- 串行间隔 1.0s（防 429 触发）
- 任一票失败自动跳过，最终阈值 = 成功票数的过半数（2 票全过、3 票过 2）



### 0.3 状态文件维护责任（2026-09-26 用户明确）
- **建立**：首用/迁移时由 AI 跑 `init-learning-state.py`（或按 state-schema.md 手建）生成 `学习状态.json` + `学习规划.md`；开发期（尚未真正使用）允许不存在或停更。
- **维护（上线后）**：AI **必须**在每次处理作业/错题后随手更新三处——① `学习状态.json`（KP 的 attempts/correct/master、mistakes）；② 错题集（`D:/家教/{科目}/错题集/`）入库；③ `学习规划.md`（模式横幅 + 周安排；生成/更新规则见 weekly-plan-engine.md，触发=交互时由 time-inject-hook 提醒，**不用 cron**）。
- 任何会话发现状态文件落后于最新作业 → 先补更新再继续任务。

### 0.4 Day-1 三件套流水线（2026-09-26 起可用，已全链实测）
- 打包链：`grade-mistake.py --image 作业照 --subject X --out 结果.json`（火山 vision+LLM：题目/作答分离提取 → 逐小题判卷 → 候选KP→匹配KP库）→ `day1-pipeline.py --mistakes 结果.json`（①KP漏洞分析+状态写入 ②进度判定（信号/防抖/冷却）③错题入库 → 自动刷新周计划 → ⑤学生版错题文字清单（无答案）→ ⑥自动生成讲解课堂（默认！--no-microlesson 才跳过））。
- **用户铁律（2026-09-26）**：批改完＝立即文字清单+生成课堂；记录进度/漏洞不依赖家长是否看视频；“备份参考”仅为 hook 机制参考，**家长端不需要备份 Hermes**。
- grade-mistake 已“接活”（原来是桩）；正确题标 is_correct=true，day1 自动跳过。
- 实测（2026-09-26 凌晨，合成作业照）：3 小题逐题判卷 ✓ 跳对题 ✓ 入库+2 ✓ 学习状态/周计划更新 ✓。
- 触发免 cron：time-inject-hook 在跨周时读 `系统/周计划状态.json` 提醒；周计划本体=`generate-weekly-plan.py`。
- 全景图文档：`D:/家教/系统/流程结构.md`；细节：`references/day1-workflow-2026-09-25.md`。

### 0.5 错题本提醒 + 历史错题「必做」规则（2026-09-27 用户要求，always-on）

**三处提醒（固定话术，交付消息里原样带上，不得省略/删改）：**

1. **每日批改交付**（错题清单/发给家长孩子的消息结尾）：
   > 📒 错题本提醒：把今天做错的题整理进错题本——① 抄题目；② 写清自己错在哪（错因）；③ 写正确解法。订正时先自己重做一遍，再看讲解。
2. **周末交付**（周末卷/周计划/周末消息）：
   > 📒 周末错题本复盘：把本周全部错题过一遍（盖住答案重做），新错题全部整理进错题本。
3. **历史错题仍错（最高优先级）**：小试卷（周末卷/回灌卷）里的历史错题（错题集原题或同类题）如果再次做错，必须醒目提醒：
   > ⚠️ 必做：第 X、Y 题是之前错过的题，这次又错了——这几题是必做的！先看讲解，把错因写进错题本，再重做一遍。

**机制（已落在脚本里，2026-09-27）：**
- `day1-pipeline.py`：批改时自动比对「错题集 + 试卷标记」检测历史重复 → 清单顶部置顶「⚠️ 必做提醒（历史错题又错了！）」，清单结尾固定附「📒 错题本提醒」；stdout 同时打印必办提示。
- `generate-exam.py`：出卷自动嵌入错题回灌（原题优先，≥1 道），卷面标 **★必做**、卷首横幅；落 `{科目}/试卷/试卷标记_*.json`（批改匹配用，含每题答案，**不进卷面**）。
- **出卷规格（2026-09-27 用户要求）**：总题数 ≤10（默认 10 = 8 道常规 + 2 道错题回灌，即「9题＋本周错题」量级）；**卷面不放答案、不放错题本提醒**——卷尾改为「知识点分布」（如 `u2.k4（圆周率 π）：第 4、7、10 题`）；答案与解析只存 `试卷标记_*.json`，批改时使用。
- **错题本提醒 = Hermes 在聊天里直接打字**（2026-09-27 用户明确：不进文档）。每日批改、周末交付都在消息文本里带上固定话术（§0.5 三条）。
- **交付三保险（2026-09-27 实测教训）**：Hermes 桌面端点击 `.docx` 媒体卡可能报「Windows 找不到文件」（即使文件存在；客户端为旧构建，根因未完全定位）→ 交付试卷/文档必须：① MEDIA: 行用**英文文件名**（中文名支持不稳）；② 同时复制到**桌面文件夹**（如 `C:/Users/MR/Desktop/家教周末卷_日期/`）并在消息里给出路径（用户可直接双击、打印）；③ 原文件保留在 `{科目}/试卷/`。只发 MEDIA: 卡片不算交付完成。
- **桌面文件夹每日检查（2026-09-27 用户要求）**：桌面交付文件夹（`家教周末卷_*` 等）只保留当天；每天首次交互时检查上一天的文件夹是否还在，还在就在回复里提醒用户清理——不擅自删除（用户原话：「每天记得检查上一天的有没有删掉」）。
- **识别复核工作流（2026-09-29 用户要求；原话：「不要再把已经判断过的给我看了，只保留我没人工复核过的」）**：① 用户已复核/指认过的项 = 锁定，永不再回显、不再请求复核；给用户看的清单只列「尚未人工复核」的项。② 复核中发现的模型错读 → 记入「模型错读样本」评分集（不删、不辩）。③ 已锁定真值表：`_demo_周末模拟_20260927/_testset/truth_lock.json`；模型新读数与锁定值冲突时以锁定值为准，不得覆盖。④ 重灾区：空框/小标点——页级自由读会把「空」幻觉成符号（如空判断括号读成 ×），此类一律记错读样本。⑤ **复核与展示单位＝整页整图**（2026-09-29 用户明确：「人工复核不是复核方框，而是整图我来复核」，防模型漏读整块）——机器侧分块/裁切只用于提升识别，最终必须合成整页读数呈现；不得要求用户按方框逐步核对。
- **盲读对比测试 v1 结论（2026-09-29，3模型×5页×28项真值）**：整图单次模式下 **doubao-seed-2.1pro 23/28 > kimi-k3 21/28 > ds4.1-flash 11/28**（评分与真值：`_demo_周末模拟_20260927/_testset/{scores_v2.json,truth_lock.json}`，装置 `test_run.py`，报告 `comparison_20260929_v2.html`）。要点：① **读法影响大于模型**——flash 整图模式标点题全塌（1/15）、近读模式约 8/15；正式流水线建议「分段近读→合成整页读数→用户整图复核」。② 共性幻觉：填空/空白处会脑补（flash 图3 凭空读②①、seed 题2末位补句号）——盲读提示词必须含「没写标【空】、看不清标【不清】」。③ k3 最诚实但涂改处不给值；seed 综合最强。④ 学生更正痕迹（写错→划掉→重写）三家均未完整读出——待专项实验。
- **批改流水线两遍升级（2026-09-29 落地，已实测）**：`grade-mistake.py`＝【对错批改】＋【错字/拼写专项】两遍——专项仅语文/英语（`TYPO_CHECK_SUBJECTS`），与主流程**并发**（`--concurrency` 默认4（可用 --concurrency 上调）、`--no-typo-check` 关闭）；全流程模型统一 `doubao-seed-2.1-pro`（glm-5-3-flash 已弃：曾在语文用例输出非 JSON 直接崩）；逐题容错＋JSON 失败重试一次。结果 JSON 增 `typo_check`；`day1-pipeline.py` 清单自动生成「✏️ 错字/拼写检查」小节（在错题本提醒之前）。实测≈10 分钟/页、专项零误报（能正确判「本页无手写汉字→未发现错字」）；已知 bug：无（「阅读文段截断」已重新定性＝页面真实跨页截断，非 bug，输出已加「题干跨页/不完整」提示语）；提速已落地（2026-09-29 晚验证）：多页并行壳 `grade-batch.py`（实测 3 页 14.9 分钟＝1.9× 串行；单页 inner 默认 4）；仍候选：可疑细字区自动放大复核、两次提取合一。
- **长跑脚本纪律（2026-09-29 教训）**：长脚本必须真后台启动＋`PYTHONUNBUFFERED=1 python -X faulthandler -u … > log 2>&1`；**前台跑一半被「转后台」的瞬间进程会被误杀**（日志停在启动行、无退出码）。
- **阅读载体 A/B（2026-09-29，3 页同题同读法）**：**扫描版 vs 照片版＝平手**（21/25 vs 21/25：扫描空框更稳但丢多选 D；照片瞎补过标点）→ 不必要求扫描版，照片拍清晰即可；正确率真正杠杆＝**放大精读**（全页读漏的「talke」「shouldn't 的 n 写法」，放大两次独立读到）。英语拼写专项细字会分歧，**人工兜底保留**。原始读数：`_demo_周末模拟_20260927/_testset/scan_ab/`。
- **无题目作业（抄写/默写/听写）＝只记录不批改（2026-09-29 用户要求）**：不是每天都有可判分的题目。流程先跑 `homework-triage.py --image 页.jpg` 判页型——exercise→批改；copy/dictation→**不批改**（不进错题、不判对错），只记录：追加一行到 `系统/作业记录.log` ＋当日交付消息里注明「{科目}：抄写类作业（已收，无需批改）」；blank→跳过；other→人工。如家长要求在默写/听写上额外做「错字检查」，按需另跑专项。
- **法定节假日周期规则（2026-09-29 用户要求；数据=`系统/holidays.json`）**：3 天小长假=与正常周末一致=**1 个周期**；5 天/7 天（含春节 9 天）=**2 个周期＋向前预习 1 课时**；调休上班日按工作日。工具：`scripts/holiday-cycles.py`（`--date`/`--week`）；`generate-weekly-plan.py` 已自动在触达 ≥3 天假期的周块插入「🎉 假期安排」块。**2026 国庆 10/1–10/7：2 轮+预习**（2027 表待官方通知后填）。排周计划前先跑 holiday-cycles 确认。
- **中途进入的剩余安排（2026-10-10 用户要求，always-on）**：学生在**周末/≥3 天假期中途**才来（如周六才上传作业、长假第 N 天才交）→ **绝不能只处理当天、把剩下几天空着**。必须给出「今天 + 剩余每一天」的安排，并让学生**明天再来找 AI 完成当天任务**。机制：`scripts/day-schedule.py`（`--date`/`--json`；`FAMTUTOR_TODAY` 可覆盖“今天”，测试/补排用）——周末=周测卷→错题本复盘→预习下周新课；3 天=复习→错题卷→补漏；5/7/9 天=2 周期+预习；**进入晚则按剩余天数合并、富余标「机动」、最后一天全压缩到当天**。落点三处（缺一不可）：① `generate-weekly-plan.py` 刷新时自动写「📍 剩余安排」段进 学习规划.md 顶部；② `day1-pipeline.py` 把该段附进错题清单末尾（全对无错题时也会打印）；③ 交付消息必须带上该段 + 「明天记得再来找 AI」固定提示（最后一天→「明天起按周计划」）。
- **预习流程（按需＋节假日触发，接入题库；2026-09-29 用户要求）**：资产=各科课本全册页图（`{科目}/课本/<uuid>/slide_*.jpg`，语文六上 138 页）＋裁剪/教材 SOP（references/pdf-textbook-processing.md 等）＋题库（`{科目}/测验/`，index.json＋单元目录）＋`generate-exam.py`。流程：①定进度（学习状态＋作业信号→学到哪）②向后裁剪下一课时/单元课本页为材料 ③扔 OpenMAIC 上预习课（同暑假流程）④课后出预习小试卷（接题库选题）→学生做→记录漏洞点 ⑤出查漏补缺小试卷，**最多 2 轮**，结果记入漏洞点/KP。触发：家长/学生要求时；5/7 天小长假（含国庆）自动带一次。
- `generate-weekly-plan.py`：周末段固定含「错题本」行；刷新时在周末/假期自动写入「📍 剩余安排」段（day-schedule.py）。`time-inject-hook.py` 的周六/周日注入已在开发机移除（2026-09-27 按用户要求；规则保留，家长机部署时再定）。
- AI 纪律：文档内的「必做」标记不得删；「错题本提醒」由 Hermes 打字进交付消息（2026-09-27 起不再进文档）。

### 1. 架构闭环图

```
课本 PDF
   ↓
[extract-knowledge-points.py] → KP 索引（每科 26–61 KP）
   ↓
[init-learning-state.py] → 学习状态.json + 学习规划.md（骨架）
   ↓
   ┌──────────────────────────────────────────────┐
   │                                              │
   ↓                                              ↓
学生作业（图片/文字）                  [quiz-bank-search.py]
   ↓                                  search → self-review → insert
[classify-homework.py]                     ↓
识别：KP 归属 + 复习信号             题库（按 KP 二级索引）
   ↓                                  含 by-type 聚合 + 真题来源
[更新 学习状态.json：master + mode]            │
   ↓                                           ↓
[grade-mistake.py] 错题入"错题集"  [generate-exam.py]
   ↓                                  题目卷 / 默写卷 / 错题回灌卷
   ↓                                  听写包 / 背诵检查表
   ↓                                           │
   ↓                                           ↓
   ↓                                  PDF + Word 输出到 试卷/
   ↓                                           │
[周日 22:00 cron]                                │
   ↓                                           │
[generate-weekly-plan.py]                        │
按 current_mode + weak_kps 自动出下周计划       │
   ↓                                           │
   └──────────→ 学生 ←─────────────────────────┘
                ↓
        学习规划.md（横幅显示当前模式）
```

**用户原话**：「学习进度由学生的作业进行判断，这样就无需跟进学校进度。当学生的作业开始变为单元复习或期末，其中复习的时候，ai需要立刻察觉到并将本周末的学习计划由查漏补缺＋预习调整为查漏补缺＋单元/全方面复习。」

### 2. 5 个新 References（按重要顺序）

| Reference | 作用 | 何时读 |
|---|---|---|
| **quiz-bank-design.md** | 题库 schema / 难度标定 / AI 自审 5 项清单 / 跨版本判定 SOP | 建题库前必读 |
| **exam-formats.md** | 5 种试卷形式（题目卷/默写卷/错题回灌/听写包/背诵检查表）的出题规则和输出格式 | 出卷前必读 |
| **weekly-plan-engine.md** | 周模式识别 / 模式切换 / 错题回灌规则 / 周计划模板 | 模式判断时读 |
| **state-schema.md** | 学习规划.md + 学习状态.json 完整 schema + init 规则 | init/迁移时读 |
| **quiz-bank-sources-sop.md** | 实测可达免费题源 + multi-search-engine 搜题入口 + playwright fallback | 搜题前必读 |
| **quiz-bank-workflow.md** | 题库建设 5 步 SOP（搜 → 筛 → 自审 → 入库 → 抽样核） | 建库流程总览 |

### 3. 4 个新脚本（系统/scripts/）

| 脚本 | 职责 | 调用方式 |
|---|---|---|
| `init-learning-state.py` | 扫三科 KP 生成 学习规划.md + 学习状态.json 骨架 | `python init-learning-state.py --force` |
| `generate-exam.py` | 5 种试卷生成器（题目/默写/错题回灌/听写/背诵） | `python generate-exam.py --subject 语文 --format question --scope u1` |
| `classify-homework.py` | 学生作业识别（KP 归属 + 复习信号检测 → 模式切换） | `python classify-homework.py --subject 数学 --text "..."` |
| `quiz-bank-search.py` | 题库 5 步 SOP 自动化（init-sources / search-kp / self-review / insert / full-cycle） | `python quiz-bank-search.py --subject 语文 --mode full-cycle --kp-id u1.k1` |

### 4. 关键约定（避免和现有规则冲突）

- 题库入库 `options` 字段**不预洗牌**，由 generate-exam.py 出卷时洗（沿用 answer-distribution-randomization）
- 题库 schema 见 quiz-bank-design.md §2，AI 自审清单 §5（5 项不可省）
- 周模式 3 种：预习周 / 单元复习周 / 期中/期末周，识别规则见 weekly-plan-engine.md §2
- 错题回灌：每周模拟卷必含 ≥ 1 道，期中/期末 ≥ 2 道（详见 exam-formats.md §3）
- AI 批改沿用 quiz-system-design.md + remedial-quiz-workflow.md（不重写）
- 整套系统跨城市/跨教材复用方法：仅改 source-sites.json + KP 索引（详见 quiz-bank-workflow.md §8）

### 5. 当前完成度

```
✅ 已完成：
  - 5 个新 references（共 56 KB）
  - 4 个新脚本（实测 init/搜索/分类全跑通）
  - 学习规划.md + 学习状态.json 骨架生成（深圳/六年级/三科 141 KP）
  - 30 个真题候选网站清单（含深圳/广东省/全国/VIP 教辅/LLM 兜底）

❌ 待开始（阶段 B，等真实用户登录有 VIP 的网站）：
  - 题库真题建设（按 KP 逐个搜索 + 自审 + 入库）
  - 错题回灌机制接入 grade-mistake.py
  - 周日 cron 配置（generate-weekly-plan.py）
  - 真实学生作业的 vision 批改接入（classify-homework.py 调 mimo）
```

### 6. 一句话复用

**当学生换城市/换教材/升级年级时，只需要改 3 个文件**：
1. `source-sites.json`（改城市和教材版本）
2. KP 索引（重跑 extract-knowledge-points.py）
3. `学习状态.json`（跑 init-learning-state.py --force）

其余 5 references + 4 脚本全部沿用，闭环完整继承。

### 7. ⚠ 题源现实（题库建设的硬约束，2026-09-12 实证）

**不要再列"30 个免费教辅站"当题源——这条路走不通。**

实测结论（curl 直拉 + browser_exec 实操后）：

| 来源类型 | 真实情况 |
|---|---|
| 21cnjy / 学科网 / 组卷网 | 登录墙 + VIP 墙，**搜出来的列表都要登录**，主页是 JS 渲染（curl 拿到的是空壳 1.3 MB） |
| 道客巴巴 / 豆丁网 / 百度文库 | 标题免费，**内容必须积分下载**（付费或上传文档换积分） |
| 通通好课 / 类似 PDF 站 | 题面在 PDF 里，**没有网页展示**，拿不到题面文字 |
| 电子课本网 dzkbw | 免费公开课本原文（GBK），**只有课本不是题库** |
| 政府教研网（深圳/广东/广州） | 题量极小，**远不够 141 KP × 6 题起步** |

**agent 没有持久的浏览器登录态**——`browser_exec` 每次开新会话，不继承 cookie。所以"用户登录后 agent 自己爬"做不到。

**三条现实路径（任选 1–2 条并行）**：
- **路径 A — 用户贴题**：用户手头有真题卷（PDF/拍照），发 vision → 入库。质量 100%，速度最快。**30–60 分钟入库 1–2 套完整试卷**（约 60 道）。
- **路径 B — LLM 兜底**（按 quiz-bank-design.md §9）：数学可直接 LLM 主出（占比 ≥ 60%）；语文英语 LLM 出题弱，只能补缺口。每 10 道抽 2 道人工核。
- **路径 C — 课本课后习题提取**：OCR `D:/家教/{科目}/课本/` 下教材 PDF 的"课后练习"页 → 按 KP 自动归属 → 入库标 `source.is_official=true`。**题目已有、零成本、与教材对齐**，但只有基础题，无期中/期末综合性题目。

**默认推荐**：A + C 并行。C 由 agent 全自动跑（OCR + KP 归属 + 入库）；A 等用户发题后入库。

### 8. 🚦 阶段 B（题库建设）的标准启动话术

下次会话启动题库建设时，**直接告诉用户三选一**（不要再次列网站清单）：

> 题库建设三条路径：
> A. 你发深圳/广东真题卷（PDF/拍照）给我，我入库标 `is_shenzhen_local=true`
> B. 数学走 LLM 自动出题，你抽检
> C. 我自动提取你课本 PDF 里的课后习题入库
>
> 推荐 A + C 并行。你那边有真题卷吗？有几套？

不要重新罗列"30 个免费网站"——已证明不可行。

---

## ⚠️ Always-on 教训与 Pitfalls（2026-09-12 沉淀）

本节是 family-tutor 全流程必须遵守的硬规则，违反会立刻踩坑。每条都标注**踩坑机制**。

### P1. 真实客户不在开发机 —— skill 为可复用优先

**规则**：本电脑（D 盘家教目录）现阶段只用于 **写 skill + 流程跑通**，不在此电脑跑出完整题库、不在此电脑接真实学生作业。

**踩坑机制**：早期容易"一鼓作气把所有 KP 的题库都搜完入库"，但真实客户在深圳、真实作业来自他家，搜索结果只对真实客户的目标 KP 有价值。在开发机堆 141 KP 题库=做无用功。

**正确做法**：skill + 流程脚本先写完；题库建设**等真实客户接入时再启动**，按他/她当时的目标 KP 跑搜索入库。

### P2. 题库不是"日常答题"用的 —— 仅服务两个场景

**规则**：`D:/家教/{科目}/测验/` 里的题库 **不** 用于学生日常答题（日常答题=学生拍照→AI 即时讲，详见 quiz-system-design.md）。题库**只服务**：
1. **新预习课的课后习题**（AI 抽 1–3 道给学生练）
2. **模拟卷生成**（单元复习 / 期中 / 期末 / 错题回灌）

**踩坑机制**：早期曾把题库当成"独立 quiz-data 仓库"反复设计，错把它当作答题环节的来源。2026-09-12 用户明确：日常答题是学生自带的题，不需要预存库。

### P3. WSL / MSYS bash 的 Python 路径不可见 —— 脚本必须自动探测

**规则**：所有家教学员/脚本的 `--base-dir` 默认值**不要写死** `D:/家教` 或 `/mnt/d/家教`。必须自动探测 `[D:/家教, /d/家教, /mnt/d/家教]`。

**踩坑机制**：
- bash `cd /d/家教 && ls` ✅ 可用（bash builtin，drivfs 翻译）
- Python `Path('D:/家教').exists()` 在 WSL 下返回 `False`，但 `Path('/d/家教').exists()` 返回 `True`
- bash 的 `for s in 数学 语文 英语; do ls $s/...` 里中文变量展开后路径 untranslatable，ls 报"无法访问"（但 bash 里直接 ls 中文路径是 OK 的）

**正确做法**（代码模式）：
```python
def auto_detect_base_dir():
    for cand in [Path("D:/家教"), Path("/d/家教"), Path("/mnt/d/家教")]:
        if cand.exists():
            return cand
    raise FileNotFoundError("请用 --base-dir 显式指定")
```
所有新脚本第一行调用它；不要让真实用户每次跑都 `--base-dir`。

### P4. 多行 Python 文件不要走 `write_file` + `terminal` bash 路径

**规则**：写多行 Python（特别是带中文 + 单引号 + 三引号字符串的）**不要用** `write_file` 然后 `terminal` 跑。改用 `execute_code` 在 Python 解释器内 `open(..., 'w').write(content)`。

**踩坑机制**：
- bash 把 heredoc / 引号嵌套的中文 + 单引号字符串**提前掐断**，错误是 `unexpected EOF while looking for matching "'"`
- `patch` 工具的 `new_string` 参数也走 bash，同样会炸
- 错误信息指向 Python，但**真正的根因是 bash 转义层**

**正确做法**：写 ≥ 10 行的 Python / Markdown，**全部走 execute_code**。bash `terminal` 只用于跑 `python3 脚本.py` 这类短命令。

### P5. 试卷形式不止题目卷 —— 默认 5 种并存

**规则**：用户要求"试卷的形式不应该只被试卷所束缚"。默认提供 5 种形式，按场景自动选择：
1. **题目卷**（单元复习 / 期中 / 期末，PDF + Word）
2. **默写卷**（字词 / 单词 / 课文，挖空 + 错字回灌）
3. **错题回灌卷**（每周模拟卷必含 ≥ 1 道，期中/期末 ≥ 2 道）
4. **听写包**（英语单词 / 语文生字，TTS 音频 + 答案）
5. **背诵检查表**（不算"题"，仅 Word）

**踩坑机制**：早期只有"题目卷"单一形式，导致学生英语单词一直错只能反复出题，效率低。默写卷/听写包对**反复错同字/同词**的情况更精准。

### P6. AI 自审不可省 —— 每题入库前必跑 5 项清单

**规则**（quiz-bank-design.md §5）：入库前必须逐项自审：
1. 考点对照（vs KP definition + key_points）
2. 超纲判定（七年级概念 / 奥数 / 初中语法）
3. 年级情境（字数 / 词汇 / 数字合理）
4. 答案正确性（AI 独立重做一遍）
5. 解析质量（思路 + 引用 KP 原文，非"答案=X"）

**踩坑机制**：题目一旦入库就被当作权威，自审漏洞会被反复使用放大。**特别是跨版本题**——苏教版/北师大版/人教版/统编版，考点重合但方法可能不同，必须 case-by-case 标 `cross_version`。

**质量门**：每 10 道入库抽 2 道人工核（20%），抽到不合格全 KP 重审。

### P7. 题库建设慢活质量优先 —— 不为进度妥协

**规则**：每个 KP 至少搜 10 道候选 → AI 自审 → 入库 6 道起步（3 易 + 2 中 + 1 难）。找不到不强行凑，宁可留空后续补。

**踩坑机制**：LLM 兜底出题是占位，质量远不如真题。语数英三科里**数学可以 LLM 主出（≥ 60%）**，**语文英语必须真题主出（≥ 60%）**——抽象要素 LLM 容易写空话。

**搜索词模板**：见 quiz-bank-search.py 的 `SEARCH_TEMPLATES` 常量，按 KP 类型选模板，搜索词必须含「六年级 + {教材版本} + {题型/知识点}」。

### P8. 周模式识别被动跟随 —— 不预设学校进度

**规则**：学生当前处于预习 / 单元复习 / 期中期末，**靠作业信号判定**，不靠日历。识别规则（weekly-plan-engine.md §2）：
- 关键词命中（"期中复习"/"期末复习"/"单元复习"）即切换
- KP 覆盖密度：单次作业 ≥ 5 个同单元 KP = 单元复习；≥ 4 个不同单元 = 期中/期末
- 防抖：非明确关键词需要 ≥ 2 次独立确认；复习周切回预习周有 7 天冷却

**踩坑机制**：日历推算会跟学校实际进度错位（提前/滞后 1–2 周很常见）。用户原话："AI 需要立刻察觉到"。

### P9. 错题回灌是闭环关键 —— 每周模拟卷强制含

**规则**：每周模拟卷必含 ≥ 1 道错题回灌题，期中/期末模拟卷 ≥ 2 道。错字回灌到默写卷、错词回灌到听写包。

**踩坑机制**：错过的题不重新出现，学生会重复错同一个 KP。错题回灌是查漏补缺的物理保障，不是可选项。

### P10. AI 批改全闭环 —— 不预留"老师手动批改"环节

**规则**：批改 = AI（vision + LLM 解题 + 比对），不依赖家长/老师手动判分。简答题用 AI 语义批改（MIMO API / new-api 网关），不是关键词匹配。

**踩坑机制**：早期默认假设有家长批改，导致部分流程断在"等老师评分"。AI 批改准确率虽然不是 100%，但胜在即时 + 全自动 + 一致性。错题由 AI 标，AI 自审的元数据自动积累。

### P11. 跨设备同步走 Git 私有仓库 —— 不手动同步

**规则**：`学习状态.json` + 题库 JSON 走 Git 私有仓库（参考 memory：Git D 盘 repo）。**写入时不要改字段顺序**，保证 diff 稳定。

**踩坑机制**：JSON 字段顺序随机化会产生海量 noise diff，commit review 无法做。

---

## 🔁 Skill 复用一句话

**学生换城市 / 换教材 / 升级年级时只改 3 个文件**：
1. `source-sites.json`（改城市名 + 教材版本）
2. KP 索引（重跑 extract-knowledge-points.py）
3. `学习状态.json`（跑 init-learning-state.py --force，自动备份旧的）

其余 5 references + 4 脚本 + 11 条 pitfall 全部沿用，闭环完整继承。

---

## 📦 2026-09-12 深夜升级：3 模型投票流水线 + 真题入库闭环

**新增核心能力**：题库建设从"骨架+占位"变成"全自动端到端可用"。

### 1. 投票流水线（实测通过 2026-09-12 02:50）

**3 模型串行投票**（用户明确要求：不可并发，DS-Pro 和 Kimi 同 provider 必 429）：

| 模型 | Provider | 路由 | 状态 |
|---|---|---|---|
| vote_1: MiniMax-M3 | minimax-cn | api.minimaxi.com/anthropic 国内直连 | ✅ 已验证 |
| vote_2: deepseek-v4-pro | new-api | 127.0.0.1:13000 国内直连 | ✅ 已验证 |
| vote_3: muse-spark-1.3-contributor-free | opencode zen | 127.0.0.1:7897 clash 代理 | ⚠ HTTP 500 持续（用户称"测过能用"，但当前 500）|

**降级规则**：任一票失败自动跳过，阈值降为「成功票数过半数」。
**实测**：数学 u1.k1 第一道 smoke test → MiniMax ✓ + DS-Pro ✓ + Muse 500 → 综合 2/2 通过入库。

### 2. 新增脚本（实测可用）

| 脚本 | 职责 | 实测 |
|---|---|---|
| `系统/scripts/vote-judge.py` | 3 模型投票判定器（单题 + 批处理）| ✅ 21 秒出结果 |
| `系统/scripts/extract-real-exam.py` | 真题图片/PDF → MiniMax vision OCR → 投票 → 入库 | ✅ 语法通过 |
| `系统/scripts/extract-textbook-exercises.py` | 课本 PDF → MiniMax vision OCR → KP 自动归属（slide_range）→ 入库（官方题免投票）| ✅ 语法通过 |

`系统/scripts/quiz-bank-search.py` 的 `mode=self-review` 已升级为自动调 `vote-judge.py`（不再占位）。

### 3. 关键约束（写进脚本默认值）

- MiniMax-M3 + Muse 都要 clash → **串行调用，不可并发**（用户原话）
- DS-Pro 和 Kimi 同 provider（new-api）→ 并发必 429 → Kimi **不并入主投票**，只可作第 4 票独立跑
- MiniMax 走 minimax-cn 国内直连（不需要代理）
- Muse 走 opencode zen 美国区域，必须 clash:7897
- 题库入库规则：
  - 真题（人工喂图/爬取）：**必须 3 模型投票通过**（2 票过 2 或 3 票过 2）
  - 课本官方题（`extract-textbook-exercises.py`）：**免投票**，标 `bypass_vote=true` + `source.is_official=true`

### 4. 第一道题入库实证（2026-09-12 02:51）

```
题库现状：1 题 / 61 KP / 1 单元 / 数学 u1.k1
- qid：数学_u1.k1_001
- 题干：分数 4/5 除以整数 3 等于多少？
- 答案：4/15（选项 0）
- 难度：易（MiniMax + DS-Pro 一致）
- 投票：2/2 通过
- 位置：D:/家教/数学/测验/u1/u1.k1.json
```

### 5. Muse 500 问题（待用户协助排查）

用户原话："在最新的会话跑了个 test，确认了 1.3 是可用的"。
session_search 搜了 5 个相关会话，最新 test 会话只有一句"test"无实际测试记录。
**当前实测**（2026-09-12 02:48）：连续 3 次 HTTP 500 Internal server error。

**建议排查路径**（不阻塞流程）：
1. 重新测一下 opencode zen 的 zen_key 是否过期
2. 试 `muse-spark-1.3`（不带 contributor-free），看是否只是 free 套餐挂了
3. 试 opencode.go（10 美元/月套餐），看是否是套餐配额问题
4. 若 zen 持续挂，可改用其他免费模型（nemotron / ling 等）

### 6. 后续真用户使用流程

```bash
# 1. 准备真题（任选其一）
# a) 你手头有真题 PDF/图片 → 直接给我
# b) 你打开 21cnjy/学科网登录后告诉我页面 URL（我通过 vision 截图读）
# c) 我用课本提取脚本（extract-textbook-exercises.py）扫你的课本 PDF

# 2. 跑入库
python D:/家教/系统/scripts/extract-real-exam.py \
    --subject 数学 \
    --input shenzhen_real_exam.pdf \
    --source-site "深圳外国语学校" \
    --source-title "2023 秋季六年级数学第一单元测试" \
    --is-shenzhen-local

# 3. 或课本提取
python D:/家教/系统/scripts/extract-textbook-exercises.py \
    --subject 数学 \
    --input D:/家教/数学/课本/xxx.pdf \
    --page-range 7-15

# 4. 检查入库结果
cat D:/家教/数学/测验/_meta/extraction-log.md
```

### 7. 完成度（题库视角）

| 科目 | 总 KP | 当前入库题数 | 缺口 |
|---|---|---|---|
| 数学 | 61 | 1 | 60 KP × 6 道 = 360 道 |
| 语文 | 54 | 0 | 54 KP × 6 道 = 324 道 |
| 英语 | 26 | 0 | 26 KP × 6 道 = 156 道 |
| **合计** | **141** | **1** | **840 道** |

按质量门：每 KP 至少 3 易 + 2 中 + 1 难 = 6 道起步，关键 KP 8+ 道。

---

## 🔧 2026-09-12 03:15 紧急修复：vote-judge 长题超时

**触发**：后台进程 proc_fb00d73f31a6 完成输出显示 MiniMax 60s read timeout 失败，DS-Pro 因 reasoning 占满 token 可能没机会跑。

**已修**（vote-judge.py）：
- MiniMax timeout **60s → 180s**
- MiniMax max_tokens **1500 → 2000**
- Muse max_tokens **1500 → 2000**
- DS-Pro max_tokens **1500 → 3000**（reasoning_content 占大头，原 1500 不够）
- 串行调用间隔 **0.5s → 1.0s**（防 429 更稳）

**经验教训**：DS-Pro 是 reasoning 模型，max_tokens 必须 ≥ 3000，否则 reasoning_content 把 token 全吃光，content 为空被判为"返回空内容"失败。下次任何 reasoning 类模型投票都按这个标准预留 token。

---

## 🎯 2026-09-12 关键突破：KP 归属判定器真正工作（项目初衷达成）

**用户原话**：「题目对应的是哪些知识点，这才是我们的重点以及初衷，而不是只是堆一堆题目。AI 要仔细地读每道题及其对应的知识点或者说是否对应课本的知识点。」

### 1. 之前的错误（已纠正）

第一版入库用**关键词粗暴匹配**（题干含"圆"→u2、"分数"→u1），35 道题 KP 归属大面积错误：
- 利息计算题 → 错塞 u5.k1（数据处理）
- 反弹球百分数 → 错塞 u5.k1
- 线段图应用题 → 错塞 u5.k1
- 圆切拼三角形 → 错塞 u1.k1（分数除法！）

### 2. 正确做法（已验证）

**`系统/scripts/assign-kp.py`（新脚本）**：
- 构建 KP 池 `_kp_pool.json`（61 个 KP 的 definition + key_points 全文）
- 每道题调 **Muse 1.3**（或 MiniMax）：给题目 + 61 个 KP 定义 → 输出 `{kp_id, difficulty, reason, also_covers}`
- KP 判定不同的题**自动迁移**到正确 KP 文件
- 实测 70 道题全部判定成功，理由精确（如"利息=本金×年利率×存期直接应用"→ u7.k7）

**`系统/scripts/ingest-exam.py`（一键入库脚本）**：
```
详情页 URL → playwright 抓高清试卷图 → MiniMax-M3 vision 提取题目 → Muse 1.3 KP 归属 → 入库
```
实测深圳宝安区试卷：2 张图 16 题，KP 归属 100% 正确。

### 3. Muse 1.3 修复（关键前提）

之前 vote-judge 调 Muse 一直 500。修复会话 `20260912_030719_efa580`：
- **免费通道**：`https://opencode.ai/zen/v1/responses`（不是 chat/completions！不是 zen/go/v1！）
- **模型名**：`muse-spark-1.3-contributor-free`
- **匿名**（不带 Authorization）
- **OpenCode 客户端头**：`User-Agent: opencode/0.20.5` + `X-Session-ID: <uuid4>` + Referer/X-Title
- **必须 Clash**：127.0.0.1:7897
- 详见 skill `muse-model-call`

### 4. 判定质量实测（assign-kp 前 55 题）

| 题目 | 错误归属 → 正确归属 |
|---|---|
| 圆切拼三角形 | u1.k1(分数除法) → **u2.k6(圆面积推导)** |
| 海棠花相框 | u1.k1 → **u2.k5(圆周长)** |
| 除法/分数/比等式 | u1.k1 → **u5.k5(三者关系)** |
| 利息计算 | u5.k1(数据处理) → **u7.k7(利息)** |
| 反弹球百分数 | u5.k1 → **u7.k3(百分数)** |
| 可乐瓶容积 | u5.k1 → **u7.k4(求单位1)** |
| 除法分配律 | u5.k1 → **u1.k3(分数除以分数)** |
| 线段图 | u5.k1 → **u4.k1(求部分量)** |
| 遮挡观察 | u5.k1 → **u8.k1(观察物体)** |

### 5. 核心脚本清单（最终版）

| 脚本 | 职责 |
|---|---|
| `assign-kp.py` | 已有题库 KP 重新归属（修正历史错误） |
| `ingest-exam.py` | 一键：详情页 → 抓图 → vision → KP 归属 → 入库 |
| `vote-judge.py` | 3 模型质量投票（MiniMax/Muse/DS-Pro） |
| `extract-real-exam.py` | 真题图片 → vision → 投票 → 入库 |
| `init-learning-state.py` | 学习规划 + 学习状态初始化 |
| `generate-exam.py` | 5 种试卷生成器 |
| `classify-homework.py` | 作业识别（KP 归属 + 复习信号） |

### 6. 待办

- 宝安区试卷 ingest 跑完（16 题）
- assign-kp 全部 70 题归属完成
- 批量跑 `_exam_urls.json` 里 16 套试卷
- 语文/英语 KP 池构建 + 归属（题库还空）

---

## 🔁 2026-09-25 升级：微课堂粒度=「一题一课 + 订正后重生成」（端到端正式测试通过）

**新流程**：订正期间预生成（学生只看到"错题清单"、没有答案时）→ 学生订正 → 对比 → 按**大题**决策：覆盖不变→复用；变小→只对仍错小题重生成；全对→跳过。

### 脚本四件套（D:/家教/系统/scripts/，均已实测）

| 脚本 | 职责 |
|---|---|
| `micro-lesson.py` | 预生成。错题按**大题**分组（`major_key`：先读 group/group_id/parent_id/major_id 字段，否则从 id 提取数字前缀 → `g5`/`g2`），一组一课；场景数 = N(知识点)+M(小题)+1；写 `微课索引_*.json` |
| `collect-corrections.py` | 订正对比 → `订正对比_*.json`（含每大题 `unfixed`=仍错小题）+ `订正报告_*.md`（学生版）| ` |
| `micro-publish.py` | 订正后决策：`decide()`=全对 skip / 覆盖集不变 reuse / 变小 regenerate（只覆盖 unfixed）/ 无预生成 generate；内嵌 `importlib` 加载 micro-lesson 调 `generate_groups(..., tag="_v2")`；写 `微课发布_*.json/.md` + 回写索引 `post` |
| `verify-micro-lesson.py` | demo 校验器（`--demo --no-submit`） |

**组键一致性**：`collect-corrections.py` 里 `major_key = _micro_lesson.major_key`（直接复用），索引与对比的组键永远对齐（如 `q5`/`g2`）。改分组逻辑只能改 micro-lesson 一处。

### 命令（正式测试命令，2026-09-25 全绿 EXIT 0）

```bash
# 阶段A：订正期间预生成（两个大题 → 2 课）
D:/Python312/python.exe micro-lesson.py --mistakes test_mistakes.json --concurrency 1 --timeout 1800
# 阶段B：订正对比（可提前跑）
D:/Python312/python.exe collect-corrections.py --mistakes test_mistakes.json --corrections corr.json
# 阶段B：决策 + 重生成（先 --dry-run 看决定）
D:/Python312/python.exe micro-publish.py --subject 数学 --date 2026-09-25          # 加 --dry-run 只决策
```

### 必须记住的 6 个坑（全部踩过）

1. **jobId ≠ 产物文件名**！产物 id 在 job 记录的 **`result.classroomId`**（顶层没有 classroomId）。脚本曾读错字段 → 拿 jobId 拼路径 → `ClassroomNotFound`。轮询 API 也返回 `result`。
2. **API 对 failed job 也返回 `done: true`**。poll 必须先判 `status=="failed"` 抛 JobFailed，**再**判 success/done，否则失败被误当成功。
3. **EPERM 原子改名竞态**（Windows 特有）：OpenMAIC `lib/server/classroom-storage.ts` 的 `writeJsonFileAtomic` 的 `fs.rename` 会被文件监视器/杀软短暂锁住 → job 在 0% 秒死（error 含 EPERM）。已加 8 次退避重试（备份 `.bak-before-rename-retry`）。⚠️ 这是**唯一一处**对 OpenMAIC 源码的改动，纯存储可靠性、不碰生成逻辑。
4. **本机长任务必须 schtasks 真脱离**：hermes 宿主重启会连坐杀死同会话的后台子进程（2026-09-25 实测：脚本+OpenMAIC 双双被清、进程句柄注册表整体丢失）。已建计划任务：`FamTutorOpenMAIC` / `FamTutorStageA` / `FamTutorStageB`（ps1 在 `D:/hermes-data/tmp/`，日志 `*_stdout.log`）。`schtasks /Run /TN <任务>` 即用。
5. **测试期通道**：`.env.local` 已切 NewAPI —— `OPENAI_BASE_URL=http://127.0.0.1:13000/v1` + `DEFAULT_MODEL=openai:kimi-k3`（用户指示，其余套餐满）。k3 上游有 TPM 限流：会看到 429/重试、单课 5–15 分钟，能完成，别误判为失败。
6. **冷编译假失败**：`/classroom/{id}` 首次访问 Next dev 要编译，curl 30s 超时=000；重试即 200（实测 63KB）。判定前先重试一次。

### 场景顺序铁律（2026-09-25 用户纠正，已写进模板）

**大题多小题时，必须按小题逐个交错：还原 →（小题1 知识点页 → 回到小题1）→（小题2 知识点 → 回到小题2）→ …**
严禁“所有知识点集中讲完再统一回归”。`build_group_requirement` 会逐条枚举场景清单，重复知识点自动跳过（“沿用前面讲过的知识点”）。实测验证：第5题 3 小题 → 场景 = 还原→化简比→回到(1)→求比值→回到(2)→比的应用→回到(3) ✓。
旧版（集中式）已废弃；遇到旧产物按新模板重新生成即可。

### 题库驱动的正式测试配方（2026-09-25 实证，语数英全绿）

- 题库位置：`D:/家教/{科目}/测验/{unit}/{kp}.json`（数组格式，每题 qid/kp_id/stem/options/answer/explanation）；数学 5600+ / 语文 3700+ / 英语 2800+。
- 选“大题”判据：stem 含“（1）”；注意抽查 answer 字段是否可靠（脱式计算出过错误答案）、公式常被打散成空壳，**选前必须人工核验答案**。
- 英语大题很少：同一 source 的散题（如 xxxx_037/038/039）往往是同一对话/题组被拆散，可重组。
- 模拟测试数据（可直接复用）：`D:/hermes-data/tmp/banktest/`（paper/mistakes/corrections 三科 + _qcache.json）。
- 流程：mistakes → micro-lesson（预生成）→ corrections → collect-corrections → micro-publish（决策+重生成）。全链路 6 课实测 EXIT 0；决策覆盖 skip(3)/reuse(1)/regenerate(2)。
- **多科文件名（已修）**：collect-corrections 输出现为 `订正对比_{科目}_{日期}.json` / `仍错题_{科目}_{日期}.json` / `订正报告_{科目}_{日期}.md`；micro-publish 用 `--comparison` 显式指定；索引 `微课索引_{日期}.json` 共享一份（按 group key 合并）。
- 微课索引 post 字段：新预生成一轮会把该组 post 重置为 None（语义：新一轮预生成）。

### 产物落点

- 课件副本：`D:/家教/数学/课件/micro_{ts}_{组键}{tag}.json`（tag=`_v2` 为重生成版）
- 课堂本体：`D:/projects/OpenMAIC/data/classrooms/{classroomId}.json`
- 播放：`http://localhost:3000/classroom/{classroomId}`
- 索引：`D:/家教/数学/课件/微课索引_YYYY-MM-DD.json`（每组 status/job_id/classroom_id/lesson_file/verified/**post**）

### 🔊 无声音故障（2026-09-25 实证）——TTS 链路

**症状**：课件能播、有字幕/白板，但**全程无声**。

**根因链**（不是 429、与 LLM 无关）：
1. 生成管线 `lib/server/classroom-media-generation.ts:generateTTSForClassroom` 逐条 speech 调 TTS。
2. TTS 链路 = OpenMAIC `openai-tts` provider → `TTS_OPENAI_BASE_URL=http://127.0.0.1:8787/v1` → **`D:/projects/family-tutor/mimo-tts-proxy.py`**（MIMO 官方 chat/completions+audio 格式，`mimo-v2.5-tts`，voice alloy→冰糖）→ api.xiaomimimo.com。
3. **代理没在跑** → 每条 `fetch failed` → 日志刷 `[WARN] TTS generation failed ... fetch failed` 然后照样打印 `TTS generation complete`（**静默失败**，job 仍 succeeded）。

**排查 3 步**：① `netstat -ano | grep :8787`；② `grep -i "TTS generation failed" openmaic 日志`；③ 看课件 JSON speech 是否缺 `audioUrl`。

**修复**：
- 启动代理：`schtasks /Run /TN FamTutorTTS`（或 `D:/Python312/python.exe D:/projects/family-tutor/mimo-tts-proxy.py`）。**MIMO key 硬编码在代理文件里**（改 key 只改这里；`.env.local` 的 `TTS_OPENAI_API_KEY` 是给 OpenMAIC 看的、代理不校验）。
- 补录已有课件：用本 skill 的 `scripts/tts-backfill.py`（幂等）——逐条 POST 代理 → 落盘 `data/classrooms/{id}/audio/tts_s{场景序}_{actionId}.mp3` → 回写 `audioId`+`audioUrl`（`http://localhost:3000/api/classroom-media/{id}/audio/{fn}`）→ 重写课件 JSON。
- 播放端取数是 `GET /api/classroom?id={id}`（响应顶层是 `classroom` 字段），读的是文件，改完无需重启服务。
- 历史：miniMax TTS 从未在这台机启用（`TTS_MINIMAX_*` 一直是注释态）；用户 2026-09-25 明确「换 MIMO TTS，暂不用 minimax」。

## ⚡ 生成加速：ds-flash 关思考（2026-09-25 实测定版）

**默认模型切回设计主力**：OpenMAIC `.env.local` → `DEFAULT_MODEL=openai:deepseek-flash`、`OPENAI_MODELS=kimi-k3,deepseek-flash`（备份 `.env.local.bak_before_dsflash_20260925`；切回 k3 = 改回 `openai:kimi-k3` + 重启 OpenMAIC）。
**ds-flash 默认带思考**（响应含 `reasoning_content`，输出膨胀 4.7×：单场景调用 7~16.7k tok，实测 300 tok 预算全被思考吃光、正文 0 字）。已在 new-api 渠道 12/18 写 `param_override={"reasoning_effort":"none"}` 关闭（改完**重启 new-api** 才生效；`thinking:{"type":"disabled"}` 亦可；验证 = 响应无 reasoning_content、completion 数十级）。
**同题实测（每课 9 次调用）**：k3 6.5/5.0 min（Σ11k tok）→ ds 带思考 7.9/3.9 min（Σ51k）→ **ds 关思考 3.1/4.6 min（Σ8.4k）**；产物结构逐一核对一致（场景数/顺序/音频数 ✓）。
**剩余瓶颈**：TTS 串行（scene→action 逐条 await generateTTS；代理是单线程 HTTPServer），一节 24-26 条 ≈ 90-100s。想再快 = 并发化（未做，需同改代理与 `classroom-media-generation.ts`）。
**服务出入口**：`FamTutorOpenMAIC`（:3000）/ `FamTutorTTS`（:8787）为 schtasks 常驻任务（已 /SD 2099 防误触发；点火 = `schtasks /Run /TN`）。一次性测试任务**用完即删**（/ST 23:59 当晚真会再触发一次，2026-09-25 踩过）。

### TTS 并行（2026-09-25 晚落地，已实测）
- 代理 `mimo-tts-proxy.py` → `ThreadingHTTPServer`（备份 `.bak-before-threading-20260925`）；OpenMAIC `classroom-media-generation.ts` 的 `generateTTSForClassroom` → 4 路并发池（`TTS_CONCURRENCY` 环境变量可调；备份 `.bak-before-tts-parallel-20260925`）。**改这两个文件后必须重启对应服务**。
- 实测：6 并发冒烟全 200（总 3s）；整课 TTS 跨度 **94s → 21-25s**。

### 火山方舟 deepseek-v4-1-flash 对照（2026-09-25 晚，同题实测；思考开）
- 探针：**2.6-3.6s/调用、100-120 tok/s、无限流**；也自带思考（reasoning_content，短而快）。整课 **3.0 min**（外加 TTS 21s）——同题全场最快。
- 同题全配置对照：k3 298s(串行TTS) / ds思考 236-257s / ds无思考 184s / **火山思考 177s**；且 ds 跑的方差极大（184s~471s）全因上游限流抖动——与用户"上游不稳定"判断吻合。
- 切换方式：Hermes `config.yaml` 的 `custom:volcengine`（key=`VOLCENGINE_API_KEY` 在 D:/hermes-data/.env）；OpenMAIC 直连切换 = 改 `.env.local` 的 `OPENAI_BASE_URL/OPENAI_API_KEY/OPENAI_MODELS/DEFAULT_MODEL` 四行（备份 `.env.local.bak_before_volc_20260925`）。**2026-09-25 晚用户拍板：正式直连火山并保持**（`.env.local` 已切，备份 `.bak_before_volc_final_20260925` 可回退 ds；上方「默认 ds-flash」段落已被本条取代）。

### 2026-09-25 晚速记（详见 `references/editing-vision-2026-09-25.md`）：知识点页禁引入已加固（m3 6/6 干净）；新增剪裁工具 `edit-micro-lesson.py`；视觉已切火山 `glm-5-3-flash`。
- Day-1动作+缺件审计→`references/day1-workflow-2026-09-25.md`。
