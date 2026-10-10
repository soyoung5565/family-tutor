# 完整测验工作流（端到端实证 2026-07-10）

## 概述
本文档记录从课件生成到测验到查漏补缺的完整流程，基于实际测试验证。

## 前置条件
- OpenMAIC 运行中（localhost:3000）
- MIMO TTS 代理运行中（localhost:8787）
- 答题结果接收服务运行中（localhost:8765）
- quiz-ai.html 已添加同步代码（见 quiz-sync-code-template.md）

## Step 1: 准备测验题

### 用 MIMO 多模态提取知识点
```bash
node "D:/mimo-multimodal/image_understand.py" \
  --type image \
  --input "D:/projects/family-tutor/materials/verify_pages/page_6.png" \
  --prompt "这是六年级上册语文课本的一页。请提取所有知识点：1）古诗标题和作者 2）生字（含拼音）3）注释 4）课后问题。用JSON格式输出。" \
  --json
```

### 生成测验题数据文件
写入 `D:\projects\family-tutor\quiz-data-day{N}.json`，格式见 quiz-system-design.md。

### 创建加载页面
写入 `D:\projects\family-tutor\load-quiz.html`（或 `load-quiz-remedial.html`）。
加载页面的 JavaScript 将题目写入 localStorage 并跳转到 quiz-ai.html。

### 打开加载页面
```bash
cmd.exe /c "start D:\projects\family-tutor\load-quiz.html"
```

## Step 2: 用户作答

用户在 quiz-ai.html 上作答，点击"提交答案"。
提交后自动：
1. 选择题立即批改（对比答案）
2. **简答题调用 AI 批改**（POST 到 http://localhost:8765/api/grade-essay）
3. AI 返回：是否正确、错误原因、参考答案、过程问题（理科）、改进建议
4. 显示结果和薄弱知识点
5. 保存到 localStorage
6. POST 到 http://localhost:8765/api/quiz-results

## Step 3: 读取结果

```bash
curl -s http://localhost:8765/api/quiz-results/latest | python -c "
import json, sys
d = json.load(sys.stdin)
print(f'得分: {d[\"score\"]}%')
print(f'答对: {d[\"correctCount\"]}/{d[\"totalQuestions\"]}')
print('薄弱知识点:')
for w in d.get('weakAreas', []):
    print(f'  - {w[\"topic\"]}: {w[\"rate\"]}%')
"
```

## Step 4: 分析漏洞 + 生成补强练习

### 分析漏洞知识点（不是错题！）
运行 `python analyze-weak-points.py` 提取薄弱知识点：
- **输出**：薄弱知识点列表（如"生字拼音"、"字词解释"、"诗词情感对比"）
- **关键**：薄弱点是"类别"（如生字拼音），不是"具体例子"（如渚、见）

### 生成补强练习题（每次不同！）
运行 `python generate-remedial.py` 生成补强练习：
- **核心逻辑**：从课本中提取多个同类知识点，随机选择出题
- **每次生成的题都不同**，但考点一致
- **只错选择题 → 全是选择题**
- **错了简答题 → 才包含简答题**
- **示例**：薄弱点是"生字拼音" → 测试多个不同生字（旷、暮、轼、稻...），不是只测渚和见
- **数学类比**：错了一道方程题，薄弱点是"整数解方程" → 应该多出几个不同的解方程题，而不是一直给出同一道题

写入 `D:\projects\family-tutor\quiz-data-remedial.json`

### 创建补强加载页面
写入 `D:\projects\family-tutor\load-quiz-remedial.html`（显示薄弱知识点列表）

### 打开补强练习
```bash
cmd.exe /c "start D:\projects\family-tutor\load-quiz-remedial.html"
```

## Step 5: 检查补强效果

用户作答后，再次读取结果。
- 如果薄弱知识点 rate >= 80% → 已掌握，进入下一课
- 如果仍有 rate < 80% → 继续补强

## 文件命名规范
- `quiz-data-day{N}.json` — 每天的测验题
- `quiz-data-remedial.json` — 补强练习题
- `load-quiz.html` — 主测验加载页
- `load-quiz-remedial.html` — 补强练习加载页
- `quiz-results/latest.json` — 最新答题结果
- `quiz-results/quiz_YYYYMMDD_HHMMSS.json` — 历史结果

## 常见问题

### 结果没有同步到后端
1. 检查 quiz-server.py 是否在运行：`cmd.exe /c "netstat -ano | findstr :8765 | findstr LISTENING"`
2. 检查 quiz-ai.html 是否有同步代码：`grep "localhost:8765" quiz-ai.html`
3. 如果没有同步代码，参考 quiz-sync-code-template.md 添加

### 浏览器无法读取 localStorage
browser_console 被安全限制拦截（pitfall 57）。必须通过后端 API 读取结果。

### 简答题批改不准确
当前使用 AI 语义批改（MIMO API）。如果批改不准确，可以：
1. 检查参考答案是否完整
2. 调整 AI 提示词
3. 增加关键词数量
