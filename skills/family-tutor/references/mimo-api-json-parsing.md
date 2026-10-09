# MIMO API JSON 解析问题

## 问题描述

MIMO API 返回的 JSON 被包裹在 markdown 代码块中，导致 JSON 解析失败。

**错误示例：**
```json
{
  "status": "ok",
  "grading": {
    "is_correct": false,
    "score": 0,
    "error_reason": "AI 返回格式错误",
    "reference_answer": "...",
    "process_issues": "",
    "suggestions": "请重新作答"
  }
}
```

**实际 MIMO API 返回：**
```
```json
{
  "is_correct": true,
  "score": 95,
  "error_reason": "",
  "reference_answer": "...",
  "process_issues": "",
  "suggestions": "学生的答案基本正确..."
}
```
```

## 解决方案

在 `quiz-server.py` 中用正则表达式先提取 JSON：

```python
import re

# 尝试解析 JSON
try:
    # 处理 markdown 代码块（MIMO API 可能返回 ```json ... ```）
    json_block_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
    if json_block_match:
        json_str = json_block_match.group(1).strip()
    else:
        # 如果没有代码块，直接从响应中提取 JSON
        json_start = ai_response.find('{')
        json_end = ai_response.rfind('}') + 1
        if json_start != -1 and json_end != -1:
            json_str = ai_response[json_start:json_end]
        else:
            json_str = None
    
    if json_str:
        grading_result = json.loads(json_str)
        return {
            'status': 'ok',
            'grading': grading_result
        }
    else:
        # 如果没有找到 JSON，返回默认结果
        return {
            'status': 'ok',
            'grading': {
                'is_correct': False,
                'score': 0,
                'error_reason': 'AI 返回格式错误',
                'reference_answer': reference_answer,
                'process_issues': '',
                'suggestions': '请重新作答'
            }
        }
except json.JSONDecodeError:
    # JSON 解析失败，返回默认结果
    return {
        'status': 'ok',
        'grading': {
            'is_correct': False,
            'score': 0,
            'error_reason': 'AI 返回格式错误',
            'reference_answer': reference_answer,
            'process_issues': '',
            'suggestions': '请重新作答'
        }
    }
```

## 测试验证

```bash
# 测试 AI 批改端点
curl -s -X POST http://localhost:8765/api/grade-essay \
  -H "Content-Type: application/json" \
  -d '{"question":"《宿建德江》和《西江月·夜行黄沙道中》在写作手法上有何异同？","userAnswer":"相同点都借景抒情，不同点宿建德江静态描写，西江月动静结合","referenceAnswer":"相同点：两首诗词都运用了借景抒情的手法。不同点：《宿建德江》主要运用静态描写，《西江月·夜行黄沙道中》则运用了动静结合的手法。","subject":"语文"}'

# 期望返回：
# {
#   "status": "ok",
#   "grading": {
#     "is_correct": true,
#     "score": 95,
#     "error_reason": "",
#     "reference_answer": "...",
#     "process_issues": "",
#     "suggestions": "学生的答案基本正确..."
#   }
# }
```

## 相关文件

- `D:\projects\family-tutor\quiz-server.py` — 答题结果接收服务 + AI 批改端点
- `D:\projects\family-tutor\quiz-ai.html` — AI 批改版答题页面
