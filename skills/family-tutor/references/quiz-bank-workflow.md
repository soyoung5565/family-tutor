# 题库建设端到端 SOP（2026-09-12 起执行）

## 0. 适用范围

**用户原话**：「构建题库这一步一定要慢慢来，质量优先。」「找免费网站，我可以帮你登录。」「搜索来源一定要广，质量优先。」「AI 需要对筛选出的题目自己读一遍看看有没有满足我上面说的，虽然不是同一个教材但题目要仔细看是不是可以通用的。深圳本地真题优先。整个过程也要可复用。」

**本文档**就是这套 SOP，每一步都可独立执行、可断点续做、可被真实用户在不同城市/不同教材复用。

---

## 1. 全流程 5 步（从 0 到可用题库）

```
Step 1: 来源清单与访问授权
Step 2: 按 KP 搜索候选题（每个 KP 至少搜 10 道）
Step 3: AI 自审 5 项（每题入库前必跑）
Step 4: 入库 + 索引同步
Step 5: 抽样人工核（每 10 道抽 2 道）
```

**每一步可独立断点续做**——做完哪个 KP 就入库哪个 KP，下次接着做下一个 KP。

---

## 2. Step 1：来源清单与访问授权

### 2.1 输出：`{科目}/测验/_meta/source-sites.json`

```json
{
  "深圳本地": [
    {"name": "深圳教育云", "url": "https://...", "access": "需登录", "vip": false, "owner": "深圳市教育局"},
    {"name": "深圳外国语学校资源库", "url": "https://...", "access": "公开", "vip": false, "owner": "深外"}
  ],
  "广东省": [
    {"name": "广东省教育研究院", "url": "https://...", "access": "公开", "vip": false},
    {"name": "广东教育出版社", "url": "https://...", "access": "公开", "vip": false}
  ],
  "其他版本真题": [
    {"name": "人教社官网", "url": "https://...", "access": "公开"},
    {"name": "苏教社官网", "url": "https://..."}
  ],
  "教辅资源": [
    {"name": "21 世纪教育网", "url": "https://...", "vip": true, "vip_owner": "用户"},
    {"name": "学科网", "url": "https://...", "vip": true, "vip_owner": "用户"},
    {"name": "教习网", "url": "https://...", "vip": false}
  ],
  "名校公开": [
    {"name": "深圳中学官网", "url": "..."},
    {"name": "深圳实验学校", "url": "..."}
  ],
  "LLM 兜底": {
    "model": "MiniMax-M3",
    "via": "new-api 网关",
    "fallback_when": "某 KP 搜不到 ≥ 6 道真题"
  }
}
```

### 2.2 执行

```bash
python D:/家教/系统/scripts/quiz-bank-search.py   --subject 语文 --mode init-sources   --output D:/家教/语文/测验/_meta/source-sites.json
```

**用户协助**：登录有 VIP 权限的网站，把账号填到 `.env` 或 `source-sites.json` 的 `credentials_ref` 字段（**不要明文密码**，引用 keychain 或环境变量）。

### 2.3 真实用户复用方法

换城市/换教材时，**只需要更新 source-sites.json**：
- 把"深圳本地"改成"广州本地"
- 把"北师大版"换成"人教版"
- 加新的可访问网站
- 其余流程不变

---

## 3. Step 2：按 KP 搜索候选题

### 3.1 输入与输出

**输入**：KP 列表（来自 index.json） + source-sites.json
**输出**：`{科目}/测验/_meta/candidates/{kp_id}_candidates.json`（每 KP 一文件，待审）

```json
{
  "kp_id": "yuwen_u1.k1",
  "searched_at": "2026-09-15T10:30:00",
  "candidates": [
    {
      "candidate_id": "cand_001",
      "stem": "「渚」的正确读音是？",
      "options": ["zhǔ", "zhù", "zǔ", "zù"],
      "answer": "zhǔ",
      "source_url": "https://...",
      "source_site": "深圳教育云",
      "source_title": "深圳外国语 2023 秋季六年级语文第一单元测试",
      "fetched_raw": "（原始 HTML/文本摘录）"
    },
    {
      "candidate_id": "cand_002",
      "stem": "「澹澹」的「澹」与下列哪个字的读音相同？",
      ...
    }
  ]
}
```

### 3.2 搜索策略（按 KP 类型）

**拼音字形类（语文）**
- 搜索词：`{生字} 读音 拼音 六年级 单元测试`
- 找 5–10 道同字不同题

**古诗默写类**
- 搜索词：`{诗名} 默写 六年级上 必背`
- 直接找原文段落（不需要"题"，material 字段存原文 + 挖空规则）

**计算题（数学）**
- 搜索词：`{知识点关键词} 计算题 六年级 北师大版`
- 例：`分数除以整数 计算题 六年级`

**应用题（数学）**
- 搜索词：`{题型} 应用题 六年级 数学 {章节}`
- 例：`分数除法应用题 六年级`

**句型转换（英语）**
- 搜索词：`{句型} 句型转换 六年级 {版本}`
- 例：`be able to 句型转换 六年级 粤教沪外`

**阅读理解**
- 搜索词：`{主题} 阅读理解 六年级`
- 例：`自然 阅读理解 六年级 现代文`

### 3.3 候选题最低数量

**每 KP 必须搜到 ≥ 10 道候选**（进入 Step 3 后通过率 ~50–70%，最终保留 ≥ 6 道）。
- 如果候选 < 5：扩大搜索范围（其他城市 + 其他版本 + 名校卷）
- 如果候选 5–10：照常走 AI 自审
- 如果候选 ≥ 10：取质量最高的 10 道

### 3.4 命令

```bash
python D:/家教/系统/scripts/quiz-bank-search.py   --subject 语文 --mode search-kp   --kp-id u1.k1   --max-candidates 15
```

---

## 4. Step 3：AI 自审 5 项

### 4.0 自审实现方式（必读）

AI 自审 5 项**统一走 `multi-model-vote-judge` skill**（3 模型并发投票，≥ 2/3 通过才算合格）。不要单独调一个模型做自审，单模型幻觉率太高。具体实现 / 可达模型清单 / Pitfalls 见该 skill 文档。

### 4.1 自审清单（与 quiz-bank-design.md §5 完全对齐）

每道候选题 AI 必须独立做：

1. **考点对照**：列 1–3 个核心考点 → 在 KP 索引查覆盖
2. **超纲判定**：是否引入七年级/初中概念/超前公式
3. **年级情境**：字数/段落/词汇/数字是否符合六年级
4. **答案正确性**：AI 独立重做一遍
5. **解析质量**：写思路而非只给答案

### 4.2 自审输出

```json
{
  "candidate_id": "cand_001",
  "self_review": {
    "passed": true,
    "out_of_scope": false,
    "introduces_advanced_concept": false,
    "age_appropriate": true,
    "answer_correct": true,
    "kp_match": ["u1.k1"],
    "kp_match_reason": "考点=渚字读音，落在 KP u1.k1 定义范围内",
    "cross_version": {
      "applicable": true,
      "reason": "考点通用，无版本特异性"
    },
    "difficulty": "易",
    "difficulty_basis": "记忆 + 选择题，单 KP"
  },
  "transformed_question": {
    "qid": "yuwen_u1_k1_easy_001",
    "subject": "语文",
    "kp_id": "u1.k1",
    "unit_id": "u1",
    "type": "字音字形",
    "stem": "「渚」的正确读音是？",
    "options": ["zhǔ", "zhù", "zǔ", "zù"],
    "answer": "zhǔ",
    "explanation": "渚：水中小块陆地。读 zhǔ。常见误读 zhù。",
    "source": {
      "url": "https://...",
      "site": "深圳教育云",
      "title": "...",
      "is_real_paper": true,
      "is_shenzhen_local": true,
      "original_version": "统编版"
    }
  },
  "rejection": null
}
```

### 4.3 自审失败的题

- `passed=false` 或任一项 ✗ → 标记 `rejection`，**不删**，保留在 candidates 文件里
- 写入 `_meta/extraction-log.md`，记录失败原因
- 后期可人工救回（修改后重审）

### 4.4 命令

```bash
python D:/家教/系统/scripts/quiz-bank-search.py   --subject 语文 --mode self-review   --kp-id u1.k1   --input D:/家教/语文/测验/_meta/candidates/u1.k1_candidates.json
```

---

## 5. Step 4：入库 + 索引同步

### 5.1 入库位置

```
D:/家教/语文/测验/u1/u1.k1.json      # 该 KP 的所有题目（数组）
D:/家教/语文/测验/index.json         # 全局索引（更新覆盖矩阵）
D:/家教/语文/测验/by-type/字音字形.json  # 题型聚合（追加）
```

### 5.2 入库逻辑

```python
def insert_to_bank(transformed_question):
    kp_id = transformed_question['kp_id']
    
    # 1. 写 KP 文件
    kp_file = f"D:/家教/{subject}/测验/{unit_id}/{kp_id}.json"
    questions = load(kp_file) or []
    if qid not in [q['qid'] for q in questions]:
        questions.append(transformed_question)
        save(kp_file, questions)
    
    # 2. 更新 by-type 聚合
    type_file = f"D:/家教/{subject}/测验/by-type/{type}.json"
    type_questions = load(type_file) or []
    if qid not in [q['qid'] for q in type_questions]:
        type_questions.append(transformed_question)
        save(type_file, type_questions)
    
    # 3. 更新 index.json
    update_index(subject, kp_id, transformed_question)
```

### 5.3 index.json 更新

每入库一道题，更新对应 KP 的计数：

```json
"kp_coverage": {
  "u1.k1": {"total": 6, "易": 3, "中": 2, "难": 1, "enabled": 6, "last_updated": "2026-09-15"}
}
```

并更新顶层统计：
- `total_questions`
- `difficulty_distribution`
- `source_distribution`
- `last_updated`

### 5.4 写入 extraction-log.md

每次入库记录：

```markdown
## 2026-09-15 语文 u1.k1 入库

**操作**：搜索 + 自审 + 入库
**候选人**：15 道
**通过**：6 道（3 易 + 2 中 + 1 难）
**拒绝**：9 道（5 道超纲 / 4 道答案有误）
**来源**：
- 深圳外国语学校资源库（3 道）
- 广东省教育研究院（2 道）
- 人教社官网（1 道，跨版本）

**备注**：渚、澹、莺 三字题充足；其他生字题少，需后续补
```

### 5.5 命令

```bash
python D:/家教/系统/scripts/quiz-bank-search.py   --subject 语文 --mode insert   --kp-id u1.k1   --input D:/家教/语文/测验/_meta/candidates/u1.k1_candidates.json
```

---

## 6. Step 5：抽样人工核（质量门）

### 6.1 抽样规则

- **每 10 道入库题 → 抽 2 道人工核**（20%）
- 抽样必须覆盖所有来源（深圳本地必抽、LLM 生成必抽、跨版本必抽）
- 抽样不通过 → 全 KP 重审

### 6.2 人工核清单

对抽到的每道题，验证：

- [ ] 答案确实是正确的（独立做一遍）
- [ ] 解析准确（不是从网上抄错的）
- [ ] 考点确实在 KP 定义里（不是 AI 自审瞎判）
- [ ] 没有引入超前概念
- [ ] 难度标记合理（与人工判断是否一致）

### 6.3 记录

```markdown
## 抽样核 2026-09-15

**抽样**：yuwen_u1_k1_easy_001, yuwen_u1_k1_mid_003, yuwen_u1_k1_hard_002
**核题人**：用户
**结果**：
- 001（深圳外国语）：✓ 通过
- 003（LLM 生成）：✓ 通过，但解析里"渚=水中小块陆地"改为更准确表述"渚=水中小块陆地或小岛"
- 002（跨版本人教版）：✗ 不通过 — 题目用了"澹澹"的"澹"字，但本教材六年级未教该字
**处置**：
- 001/003 入库保留
- 002 删除 + 标记 enabled=false + 记录到 log
```

---

## 7. 重复与覆盖检查

### 7.1 题目去重

入库前比对同 KP 文件已有题目：
- stem 完全一致 → 跳过
- stem 高度相似（相似度 > 0.85）→ 人工判定（保留更好的）

### 7.2 题型聚合检查

`by-type/{type}.json` 必须覆盖该科目所有题型：
- 题型未聚合 → 触发 `by-type-rebuild.py`
- 题型题量过少 → 标记 `next_actions`

---

## 8. 真实用户复用清单

**当学生换城市/换教材/升级年级时，复用本文档只需要改：**

| 字段 | 改动 |
|---|---|
| `source-sites.json` 里的"本地"区域 | 改成新城市 |
| KP 索引文件 | 换新教材的 KP 提取 |
| `学习状态.json` 的 `subject_meta.publisher` | 换新版本 |
| 题库路径 | 重置或归档旧题库 |
| `cross_version-rules.json` | 加新版本的兼容规则 |

**其余 5 步流程不变**，脚本可以复用。

---

## 9. 自动化等级

| 步骤 | 自动化程度 | 需人工介入 |
|---|---|---|
| Step 1 来源清单 | 半自动（AI 给候选 + 用户确认访问权限） | ✅ 必需 |
| Step 2 搜索候选 | 全自动（脚本 + AI 搜索） | 偶尔（搜不到时调整关键词） |
| Step 3 AI 自审 | 全自动 | 无（除非 AI 自身不确定） |
| Step 4 入库 | 全自动 | 无 |
| Step 5 抽样人工核 | 人工 | ✅ 必需（质量门） |

---

## 10. 进度看板

在 `_meta/extraction-log.md` 顶部维护：

```markdown
# 题库建设进度

最后更新：2026-09-15

## 语文（54 KP）
- 已完成：12 KP（u1 全完成 + u2 全完成）
- 进行中：u3（4/6 KP 完成）
- 未开始：u4-u8

## 数学（61 KP）
- 已完成：0 KP
- 进行中：u1（LLM 生成阶段）
- 未开始：u2-r1

## 英语（26 KP）
- 已完成：0 KP
- 未开始：全部

## 总进度
- 已入库题数：87 道
- 完成 KP 数：12 / 141（8.5%）
- 覆盖率：6.6%
```

---

## 11. 关键 Pitfalls（来自规则推断 + 用户原话）

### 11.1 不要急于求成
**用户原话**：「构建题库这一步一定要慢慢来，质量优先。」
- 每个 KP 花 30–60 分钟（搜 + 自审 + 入库 + 抽样）
- 不要为了凑数强行入 LLM 生成题（如果 KP 抽象到搜不到，宁可留空）

### 11.2 不要跨过 AI 自审
每题入库前必须跑 §4 自审 5 项。**任何一项不过 → 不入库**。
不能因为"看上去对"就放过。

### 11.3 不要忘记跨版本标注
跨版本题标 `cross_version.applicable=true` + reason，让出题脚本能区分对待。

### 11.4 不要忽略错字回灌
入默写/听写题型时，**主动从错题集挑题**（哪怕搜索结果没显示），
写进 `stem` 字段或单列一个 `must_include` 列表。

### 11.5 题库与 KP 必须同步
KP 改了（如新增/删除/合并）→ 题库对应调整：
- KP 删除 → 该 KP 的题移到 `_meta/archived/`
- KP 合并 → 题标记 `merged_to=new_kp_id`
- 新 KP → 按新 KP 重新搜题

---

## 12. 关键文件索引

| 文件 | 作用 |
|---|---|
| `quiz-bank-design.md` | 题库 schema / 难度 / 自审规范 |
| `exam-formats.md` | 试卷/默写/听写等形式规范 |
| `weekly-plan-engine.md` | 周计划 + 错题回灌规则 |
| `state-schema.md` | 学习状态 + 学习规划 schema |
| `answer-distribution-randomization.md` | 选项洗牌规则（出卷时） |
| `quiz-system-design.md` | 答题/批改规则（消费题库） |
| `remedial-quiz-workflow.md` | 补强流程（消费题库） |

**关系**：本文档是建设上游；其他 6 个是消费下游。
