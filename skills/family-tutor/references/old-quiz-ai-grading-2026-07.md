# 旧 quiz 系统：AI 批改与动态题型（2026-07-10 实证；自 SKILL.md 迁出 2026-09-29）

### AI 批改与动态题型（2026-07-10 实证）

60a. **AI 批改实现细节**（2026-07-10 实证） — 简答题不要用关键词匹配，要用 AI 语义理解批改。**实现方式**：
- 后端 `D:\projects\family-tutor\scripts\quiz-server.py` 增加 `/api/grade-essay` 端点，调用 MIMO API
- 前端 `D:\projects\family-tutor\quiz-ai.html` 提交简答题时 POST 到后端，等待 AI 返回结果
- AI 返回：`is_correct`、`error_reason`、`reference_answer`、`process_issues`（理科）、`suggestions`
- **用户明确要求**：简答题必须给出错误原因 + 参考答案 + 改进建议；理科要指出过程问题
- **不要用关键词匹配**（用户原话："不要用关键词审查哦，就是要让ai来看正确与否"）
- **MIMO API 提示词必须用英文**（中文提示词返回空内容，pitfall 66）
- **MIMO API max_tokens 必须 ≥500**（pitfall 67）
- **MIMO API JSON 解析**：结果可能被包裹在 markdown 代码块中，用正则提取 `\`\`\`(?:json)?\s*\n?(.*?)\n?\`\`\``

61. **动态补强练习题型**（2026-07-10 实证） — 补强练习的题型应根据错题类型动态调整：
- 运行 `python D:\projects\family-tutor\scripts\generate-remedial.py` 分析薄弱知识点
- **只错选择题 → 全是选择题**
- **错了简答题 → 才包含简答题**
- 脚本自动从原题中找同类型题目生成补强练习
- **用户明确要求**："你的体型应该不是固定的吧，加入我没有错情感差异分析这一步，则应该全是选择题才对吧？"
- **每次生成的题都不同**（AI 根据薄弱知识点生成新题），但考点一致
    **agentMode 必须是 `'default'`**（用户原话：\"那应该就是default就可以。不要快速模式\"）。
31c. **当前模型不支持视觉时的处理（2026-07-10 实证）** — 切换到 mimo-v2.5-pro 后 `vision_analyze` 和 `browser_vision` 都报 404（模型不支持图片输入）。**替代方案**：
    - 用 pymupdf 提取目标页为 PNG → `cmd.exe /c "start page_N.png"` 让用户自行查看
    - 或切回支持视觉的模型（如 minimax M3）做视觉分析
    - **不要在不支持视觉的模型上反复尝试 vision_analyze**——会浪费时间
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
