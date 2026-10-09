# MIMO 多模态视觉理解

## 概述
当 OpenMAIC 的 LLM 不支持 vision API 时（如 mimo-v2.5-pro），用 MIMO 多模态脚本做图片/音频/视频分析。

## 脚本位置
`D:\mimo-multimodal\image_understand.py`

## 用法
```bash
# 图片分析
node "D:/mimo-multimodal/image_understand.py" \
  --type image \
  --input "D:/path/to/image.png" \
  --prompt "描述这张图片的内容" \
  --json

# 音频转录
node "D:/mimo-multimodal/image_understand.py" \
  --type audio \
  --input "D:/path/to/audio.mp3" \
  --prompt "转录音频内容" \
  --json

# 视频理解
node "D:/mimo-multimodal/image_understand.py" \
  --type video \
  --input "D:/path/to/video.mp4" \
  --prompt "描述视频内容" \
  --json
```

## 参数说明
| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--type` | 媒体类型：image / audio / video | image |
| `--input` | 文件路径（本地）或公网 URL | 必填 |
| `--prompt` | 提示词 | 必填 |
| `--model` | 模型名 | mimo-v2.5 |
| `--api-key` | API Key | 从环境变量 MIMO_API_KEY 读取 |
| `--base-url` | API 地址 | https://token-plan-cn.xiaomimimo.com/v1 |
| `--max-tokens` | 最大输出 token | 4096 |
| `--json` | JSON 格式输出 | 否 |

## 输出格式（--json）
```json
{
  "content": "模型的回答",
  "reasoning_content": "模型的思考过程",
  "model": "mimo-v2.5",
  "usage": {
    "prompt_tokens": 2425,
    "completion_tokens": 548,
    "total_tokens": 2973,
    "image_tokens": 2145,
    "reasoning_tokens": 340
  }
}
```

## 典型用途
1. **裁切 PDF 后验证页面内容** — "这页是哪首古诗？"
2. **扫描版课本视觉精读** — 提取生字、课后问题等
3. **任何需要图片理解的场景**
4. **生成测验题**（2026-07-10 实证）— 扫描版 PDF 无法被 OpenTutor 解析时，用 MIMO 多模态直接生成测验题：
   ```bash
   node "D:/mimo-multimodal/image_understand.py" \
     --type image \
     --input "D:/path/to/page.png" \
     --prompt "你是小学六年级语文老师。根据这张课本页面，生成5道测验题（选择题和填空题）。用JSON格式输出，每题包含type、question、options(选择题)、answer。" \
     --json
   ```
   输出的 `content` 字段含 JSON 格式的测验题，直接解析给用户作答。

## 注意事项
- **不要用 `vision_analyze`**（会 404，因为 mimo-v2.5-pro 不支持 OpenAI 兼容的 vision API）
- **不要用 `browser_vision`**（同样 404）
- 脚本路径必须用 Windows 格式（`C:/Users/...`），不能用 MSYS 格式（`/c/Users/...`）
- 输出的 `content` 是模型的回答，`reasoning_content` 是思考过程

## MIMO API 信息
- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
- Key: `YOUR_MIMO_API_KEY`
- 支持模型: mimo-v2.5, mimo-v2.5-pro, mimo-v2-omni
