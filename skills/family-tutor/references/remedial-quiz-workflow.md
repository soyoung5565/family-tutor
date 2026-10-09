# 补强练习完整工作流

## 概述
补强练习是查漏补缺的核心环节。当用户完成课后测验后，系统会分析薄弱知识点，动态生成新的练习题（不是重复原题），让用户巩固薄弱环节。

## 完整流程

### 1. 课后测验完成
用户在 `quiz-ai.html` 上作答并提交后：
- 结果自动 POST 到 `http://localhost:8765/api/quiz-results`
- 保存到 `D:\projects\family-tutor\quiz-results\latest.json`

### 2. 分析薄弱知识点
```bash
cd /d/projects/family-tutor && python analyze-weak-points.py
```

**输出**：`weak-points-analysis.json`
```json
{
  "weak_topics": ["生字拼音", "字词解释", "诗词对比"],
  "weak_points": [
    "渚的读音（zhǔ）",
    "见的读音（xiàn，表示出现）",
    "渚的意思（水中间的小块陆地）",
    "诗词情感对比分析（需要详细分析两首诗的情感差异）"
  ],
  "has_choice_errors": true,
  "has_essay_errors": true
}
```

**关键**：薄弱点是"类别"（如生字拼音），不是"具体例子"（如渚、见）。

### 3. 生成补强练习题
```bash
cd /d/projects/family-tutor && python generate-remedial.py
```

**核心逻辑**：
- 从课本知识点库（`KNOWLEDGE_BASE`）中随机选择相关题目
- **每次生成的题都不同**（随机变换选项、问法）
- **答案随机分布**（用 `shuffle_options()` 函数打乱选项顺序）
- **只错选择题 → 全是选择题**
- **错了简答题 → 才包含简答题**

**输出**：`quiz-data-remedial.json`

### 4. 创建加载页面
```bash
# 生成加载脚本
cat /d/projects/family-tutor/quiz-data-remedial.json | python -c "
import json, sys
d = json.load(sys.stdin)
print('const quizData = ' + json.dumps(d, ensure_ascii=False, indent=2) + ';')
print('localStorage.setItem(\"current-quiz\", JSON.stringify(quizData));')
" > /d/projects/family-tutor/load-remedial-data.js
```

**加载页面**：`load-quiz-remedial.html`
- 显示薄弱知识点列表
- 点击"开始补强练习"按钮
- 自动加载题目并跳转到 `quiz-ai.html`

### 5. 用户作答
- 打开 `load-quiz-remedial.html`
- 点击"开始补强练习"
- 在 `quiz-ai.html` 上作答
- 提交后 AI 批改（POST 到 `/api/grade-essay`）

### 6. 检查结果
```bash
curl -s http://localhost:8765/api/quiz-results/latest | python -c "
import json, sys
d = json.load(sys.stdin)
print('=== 补强练习结果 ===')
print(f'得分: {d[\"score\"]}%')
print(f'答对: {d[\"correctCount\"]}/{d[\"totalQuestions\"]}')
print()
print('薄弱知识点:')
for w in d.get('weakAreas', []):
    print(f'  - {w[\"topic\"]}: {w[\"rate\"]}%')
"
```

### 7. 决策
- **如果薄弱知识点 rate >= 80%** → 已掌握，进入下一课
- **如果薄弱知识点 rate < 80%** → 继续补强（回到步骤 2）

## 关键 Pitfalls

### 1. 不要重复原题
用户明确说："你每次出的题都是一样的，这不叫查漏补缺"。

**正确做法**：从课本知识点库中随机选择相关题目，每次生成的题都不同。

### 2. 答案必须随机分布
用户明确说："你自己说答案随机分布了，然后不管是你给的网页还是你第二遍给的答案都是aaaaa"。

**正确做法**：用 `shuffle_options()` 函数打乱选项顺序。

### 3. 题型要动态调整
用户明确说："你的题型应该不是固定的吧，加入我没有错情感差异分析这一步，则应该全是选择题才对吧"。

**正确做法**：
- 只错选择题 → 全是选择题
- 错了简答题 → 才包含简答题

### 4. AI 批改用英文提示词
MIMO API 对中文提示词返回空内容，必须用英文提示词。

### 5. AI 批改 max_tokens 需要 ≥500
`max_tokens=50` 时，模型用 49 token 做推理、1 token 回复（空）。

## 文件清单

| 文件 | 用途 |
|------|------|
| `analyze-weak-points.py` | 分析薄弱知识点（提取知识点，不是错题） |
| `generate-remedial.py` | 用 AI 生成新题（根据知识点生成新题，每次不同） |
| `quiz-data-remedial.json` | 补强练习题数据 |
| `load-quiz-remedial.html` | 补强练习加载页（显示薄弱知识点列表） |
| `weak-points-analysis.json` | 薄弱知识点分析结果 |
| `quiz-ai.html` | AI 批改版答题页面 |
| `quiz-server.py` | 结果接收服务 + AI 批改端点（端口 8765） |
