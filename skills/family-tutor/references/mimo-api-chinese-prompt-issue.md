# MIMO API 中文提示词问题（2026-07-10 实证）

## 问题描述
`mimo-v2.5-pro` 模型在收到中文批改提示词时，`content` 字段返回空字符串（长度 0），但 `reasoning_content` 有内容。

## 根因
模型把所有 token 用在"推理"上，没留给实际回复。中文提示词触发了更多的"思考"过程。

## 解决方案
用英文提示词。测试证明英文提示词正常返回 JSON。

```python
# ❌ 中文提示词（返回空内容）
prompt = "批改答案，只返回JSON。\n题目：「泊」的正确读音是？\n学生答案：bó\n参考答案：bó\n\n返回格式：\n{\"is_correct\":true/false,\"score\":0-100}"

# ✅ 英文提示词（正常返回）
prompt = "Grade this answer. Return only JSON.\nQuestion: What is the pinyin of 泊?\nStudent answer: bó\nReference answer: bó\n\nReturn: {\"is_correct\":true/false,\"score\":0-100}"
```

## 测试结果
- 中文提示词：返回空内容（长度 0）
- 英文提示词：返回 `{"is_correct":true,"score":100}`（长度 31）

## 其他注意事项
1. **max_tokens 需要 ≥500** — `max_tokens=50` 时，模型用 49 token 做推理、1 token 回复（空）。`max_tokens=500` 时，推理用 100-200 token，剩余给回复。
2. **JSON 包裹在 markdown 代码块中** — 返回格式为 `` ```json\n{...}\n``` ``，需用正则提取：
   ```python
   import re
   match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
   if match:
       json_str = match.group(1).strip()
   ```
3. **批改场景推荐 `max_tokens: 500`** — 确保有足够 token 给回复。

## 相关 Pitfalls
- Pitfall 63: MIMO API 返回 JSON 包裹在 markdown 代码块中
- Pitfall 64: 补强练习答案必须随机分布
- Pitfall 65: AI 批改失败时的 fallback
