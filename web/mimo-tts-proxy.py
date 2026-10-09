"""
MIMO TTS Proxy Server
将 OpenAI 标准 /v1/audio/speech 格式转换为 MIMO chat-completions TTS 格式

更新历史：
- 2026-07-09: 最初用 MIMO mimo-v2.5-tts (token-plan-cn.xiaomimimo.com, tp- key)
- 2026-07-31: MIMO key 过期，改用 minimax 原生 TTS
- 2026-08-22: MiniMax 过期，MIMO 官方域名改为 api.xiaomimimo.com（sk- key），
              官方 TTS 走 /v1/chat/completions + audio 字段（user=音色描述, assistant=朗读文本）
              音色列表: [mimo_default, 冰糖, 茉莉, 苏打, 白桦, Mia, Chloe, Milo, Dean]
"""

import http.server
import json
import urllib.request
import base64

# MIMO API 配置（2026-08-22 起用新域名 + sk- key）
MIMO_BASE = "https://api.xiaomimimo.com"
MIMO_KEY = "YOUR_MIMO_API_KEY"
MIMO_TTS_MODEL = "mimo-v2.5-tts"
PROXY_PORT = 8787

# OpenAI voice -> MIMO 音色
VOICE_MAP = {
    "alloy": "冰糖",       # 儿童友好女声（默认）
    "nova": "冰糖",
    "shimmer": "茉莉",
    "echo": "白桦",        # 中性/男声
    "onyx": "Dean",
    "fable": "Mia",
    "ash": "苏打",
    "coral": "Chloe",
    "sage": "Milo",
}
DEFAULT_VOICE = "冰糖"

# 音色描述（英文，MIMO TTS 对英文描述更稳定）
VOICE_DESC = {
    "冰糖": "Warm, crystal-clear female voice, gentle and patient, ideal for teaching elementary school children. Slow pace, friendly tone.",
    "茉莉": "Soft, sweet female voice, cheerful and lively, suitable for kids. Moderate pace, warm tone.",
    "苏打": "Fresh, bubbly female voice, energetic and playful, good for children stories.",
    "白桦": "Calm, natural male voice, steady and clear, suitable for narration.",
    "Mia": "Friendly young female voice, clear and approachable, good for teaching.",
    "Chloe": "Bright, cheerful female voice, expressive, good for storytelling.",
    "Milo": "Gentle young male voice, warm and reassuring.",
    "Dean": "Deep, steady male voice, clear and authoritative.",
}


class TTSHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默

    def do_POST(self):
        if self.path != "/v1/audio/speech":
            self.send_response(404)
            self.end_headers()
            return

        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = json.loads(self.rfile.read(content_length).decode('utf-8'))

            text = body.get('input', '')
            voice = VOICE_MAP.get(body.get('voice', 'alloy'), DEFAULT_VOICE)
            fmt = body.get('response_format', 'mp3')  # mp3/wav

            # MIMO TTS: chat/completions + audio 字段（user=音色描述, assistant=朗读文本）
            req_body = json.dumps({
                "model": MIMO_TTS_MODEL,
                "messages": [
                    {"role": "user", "content": VOICE_DESC.get(voice, VOICE_DESC[DEFAULT_VOICE])},
                    {"role": "assistant", "content": text}
                ],
                "audio": {"format": fmt, "voice": voice}
            }).encode('utf-8')

            req = urllib.request.Request(
                f"{MIMO_BASE}/v1/chat/completions",
                data=req_body,
                headers={
                    'Content-Type': 'application/json',
                    'api-key': MIMO_KEY,   # MIMO 用 api-key 头（不是 Authorization）
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Hermes/1.0'
                }
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))

            message = result.get('choices', [{}])[0].get('message', {})
            audio_data = message.get('audio', {}).get('data', '')
            if not audio_data:
                raise Exception(f"MIMO TTS 没有返回音频: {str(result)[:200]}")

            audio_bytes = base64.b64decode(audio_data)

            self.send_response(200)
            self.send_header('Content-Type', 'audio/mpeg' if fmt == 'mp3' else 'audio/wav')
            self.send_header('Content-Length', str(len(audio_bytes)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(audio_bytes)

        except Exception as e:
            error_msg = json.dumps({"error": str(e)}).encode('utf-8')
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(error_msg)))
            self.end_headers()
            self.wfile.write(error_msg)


if __name__ == '__main__':
    server = http.server.ThreadingHTTPServer(('127.0.0.1', PROXY_PORT), TTSHandler)
    print(f'MIMO TTS Proxy running on http://127.0.0.1:{PROXY_PORT} (voice={DEFAULT_VOICE})')
    server.serve_forever()
