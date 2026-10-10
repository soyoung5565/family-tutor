# 答题系统设计规则（2026-07-10 实证）

## 出题规则

### 题型选择
- **选择题**：所有客观题都用选择题，包括拼音、生字注音、作者朝代、诗句理解
- **简答题**：需要结合诗句分析的开放性问题
- **禁止填空题**：用户原话"语文的拼音这种题打字是打不了的"。拼音、生字注音等必须做成选择题

### 拼音题示例（正确）
{"type": "choice", "question": "「渚」的正确读音是？", "options": ["zhǔ", "zhù", "zǔ", "zù"], "answer": "zhǔ"}

### 生字注音题示例（正确）
{"type": "choice", "question": "下列生字注音完全正确的是？", "options": ["暮(mù)鹊(què)稻(dào)", "暮(mò)鹊(què)稻(dào)", "暮(mù)鹊(qüè)稻(dào)", "暮(mù)鹊(què)稻(diào)"], "answer": "暮(mù)鹊(què)稻(dào)"}

## 批改规则

### 选择题
精确匹配（选项包含答案或答案包含选项）

### 简答题（AI 批改）
- **不要用关键词匹配**（用户原话："不要用关键词审查哦，就是要让ai来看正确与否"）
- **用 AI 语义理解批改**：POST 到 `http://localhost:8765/api/grade-essay`，调用 MIMO API
- **AI 返回内容**：
  - `is_correct`：是否正确
  - `error_reason`：错误原因
  - `reference_answer`：参考答案
  - `process_issues`：解题过程问题（理科题目）
  - `suggestions`：改进建议
- **用户明确要求**：
  - 简答题必须给出错误原因 + 参考答案 + 改进建议
  - 理科题目要指出解题过程中的问题
  - 文理科都要给出参考答案和错误原因

## 结果同步

### 后端接收服务
- 文件：D:\projects\family-tutor\quiz-server.py
- 端口：8765
- API：POST /api/quiz-results（接收答题结果）
- API：GET /api/quiz-results/latest（获取最新结果）
- 存储：D:\projects\family-tutor\quiz-results\latest.json

### Hermes 读取结果
cat D:/projects/family-tutor/quiz-results/latest.json | python -c "import json,sys;d=json.load(sys.stdin);print(f'得分: {d[\"score\"]}%')"

## 页面文件
- **AI 批改答题页**：D:\projects\family-tutor\quiz-ai.html（推荐使用，支持语义理解批改）
- 旧版答题页：D:\projects\family-tutor\quiz.html（深色主题，Linear 风格，Open Design 生成）
- 加载页：D:\projects\family-tutor\load-quiz.html（点击按钮自动加载+跳转）
- 补强练习加载页：D:\projects\family-tutor\load-quiz-remedial.html（显示薄弱知识点列表）
- 补强练习脚本：D:\projects\family-tutor\generate-remedial.py（动态生成补强练习）
- 必须自动打开（用户原话："你直接给个浏览器链接或者直接打开文件，而不是让我来找"）
- 打开命令：cmd.exe /c "start D:\projects\family-tutor\quiz-ai.html"

## Open Design 生成的数据结构（2026-07-10）

Open Design 生成的 `quiz.html` 使用 `var QUESTIONS = [...]` 数组格式：

```javascript
var QUESTIONS = [
  {
    id: 'q1',
    type: 'choice',        // 'choice' 或 'text'
    multi: false,           // true = 多选
    topic: '古诗词常识',    // 知识点分类（用于薄弱点分析）
    text: '问题文本',
    options: ['A', 'B', 'C', 'D'],
    answer: 2,              // choice 题：正确选项索引（0-based）
  },
  {
    id: 'q9',
    type: 'text',
    topic: '诗词赏析',
    text: '简答题题目',
    answer: '参考答案文本',
    keywords: ['关键词1', '关键词2'],  // AI 批改用
  },
];
```

**更新题目时**：找到 `var QUESTIONS = [` 到 `];` 之间的内容，用新的题目数组替换。
**同步更新** `load-quiz.html` 中的 localStorage 数据。

## OpenTutor 已弃用
扫描版 PDF 无法解析（content_nodes 始终为空）、API 超时、维护成本高。
答题系统完全由 Hermes + MIMO 多模态 + quiz-ai.html + quiz-server.py 组成。

## 动态补强练习（2026-07-10 实证）

### 生成逻辑
1. 运行 `python analyze-weak-points.py` 分析薄弱知识点（不是错题）
2. 脚本读取 `quiz-results/latest.json` 提取薄弱知识点（如"渚的读音"、"见的读音"、"诗词情感对比"）
3. 运行 `python generate-remedial.py` 用 AI 生成新题
4. **核心逻辑**：根据薄弱知识点，用 AI 生成新题（不是重复原题）
5. **每次生成的题都不同**（AI 随机变换选项、问法），但考点一致
6. 输出到 `quiz-data-remedial.json`

### 用户明确要求
- "你的题型应该不是固定的吧，加入我没有错情感差异分析这一步，则应该全是选择题才对吧"
- **"你每次出的题都是一样的，这不叫查漏补缺，所以我是让你总结漏洞知识点而不是错题"**
- 补强练习的题型应根据错题类型动态调整，不能固定
- **补强练习必须生成新题，不能重复原题** — 用户明确说"这不叫查漏补缺"

### 文件命名
- `quiz-data-remedial.json` — 补强练习题数据
- `load-quiz-remedial.html` — 补强练习加载页（显示薄弱知识点列表）
- `analyze-weak-points.py` — 分析薄弱知识点脚本
- `generate-remedial.py` — 用 AI 生成新题脚本
