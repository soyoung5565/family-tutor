# MIMO TTS/ASR 配置参考

## 当前状态（2026-07-10）
- **TTS**: MIMO TTS 代理是**默认 TTS**（`openai-tts` provider，端口 8787）
- **ASR**: 浏览器原生（MIMO 没有 ASR）
- **minimax TTS**: 备选（`minimax-tts` provider，需要 OAuth `oat-` token）
- **MIMO LLM**: mimo-v2.5-pro 是默认 LLM（`xiaomi` provider）

## MIMO TTS 代理

文件：`D:\projects\family-tutor\mimo-tts-proxy.py`

代理服务器在 `http://127.0.0.1:8787/v1` 运行：
1. 接收 OpenAI 格式的 `POST /v1/audio/speech` 请求
2. 转换为 MIMO 格式的 `POST /v1/chat/completions` + `modalities` 请求
3. 从 MIMO 响应中提取 base64 音频，解码后返回 WAV 音频流

### 启动代理
```bash
python D:/projects/family-tutor/mimo-tts-proxy.py
# 输出: MIMO TTS Proxy running on http://127.0.0.1:8787
```

### .env.local 配置
```bash
TTS_OPENAI_API_KEY=YOUR_MIMO_API_KEY
TTS_OPENAI_BASE_URL=http://127.0.0.1:8787/v1
```

### MIMO API 信息
- Base URL: `https://token-plan-cn.xiaomimimo.com/v1`
- Key: `YOUR_MIMO_API_KEY`
- TTS 模型: `mimo-v2.5-tts`
- LLM 模型: `mimo-v2.5-pro`
- 限流: IP 级别非 key 级别，单线程 1.5s 稳定

### MIMO 可用音色
| OpenAI 音色 | MIMO 音色 |
|-----------|---------|
| alloy | 冰糖 |
| echo | 茉莉 |
| fable | 苏打 |
| onyx | 白桦 |
| nova | Mia |
| shimmer | Chloe |
| (默认) | Milo |
| (默认) | Dean |

### MIMO TTS API 格式（供参考）
```json
POST /v1/chat/completions
{
  "model": "mimo-v2.5-tts",
  "modalities": ["text", "audio"],
  "messages": [{"role": "assistant", "content": "要合成的文字"}],
  "audio": {"voice": "冰糖", "format": "wav"}
}
```
**注意：** 文字必须放在 `role: assistant` 的消息中，不能放在 `role: user` 中。

### ASR
MIMO ASR 格式也与 OpenAI 不同，目前暂无代理。用浏览器原生 ASR 作为替代。

## 测试
```bash
# 测试代理是否工作
curl -X POST http://127.0.0.1:8787/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"input":"你好","voice":"alloy"}' \
  -o test.wav && file test.wav
# 应输出: RIFF (little-endian) data, WAVE audio, Microsoft PCM, 16 bit, mono 24000 Hz
```

## Pitfalls
1. **模型名映射** — 代理支持 OpenAI 模型名（gpt-4o-mini-tts/tts-1/tts-1-hd）和 MIMO 模型名（mimo-v2.5-tts），会自动映射
2. **音色名必须用 OpenAI 格式** — alloy/echo/fable/onyx/nova/shimmer，代理会映射到 MIMO 音色
3. **返回 464 字节 HTML 错误** — 如果代理返回 HTML 而不是 WAV，说明模型名或音色名错误
4. **代理必须在 OpenMAIC 之前启动** — 否则 TTS 会报连接失败（HTTP 000）
