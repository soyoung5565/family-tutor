#!/usr/bin/env python3
"""
家庭教师 - 答题结果接收服务 + AI 批改
接收答题网页的结果，保存到本地文件供 Hermes 分析
支持 AI 批改简答题（调用 minimax API）
"""

import json
import os
import re
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import urllib.request

# 配置
PORT = 8765
RESULTS_DIR = r'D:\projects\family-tutor\quiz-results'

# ---- AI 批改配置 ----
# 主通道: opencode GO 中继 (ox-alpha-free)。备选: minimax OAuth token（48h 有效期，过期自动跳过）
def _load_env_key(name):
    v = os.environ.get(name)
    if v:
        return v
    try:
        for line in open(r'D:\hermes-data\.env', encoding='utf-8', errors='replace'):
            if line.strip().startswith(name + '='):
                return line.strip().split('=', 1)[1].strip()
    except Exception:
        pass
    return ''

OPENCODE_API_KEY = _load_env_key('OPENCODE_GO_API_KEY')
OPENCODE_BASE_URL = _load_env_key('OPENCODE_GO_BASE_URL') or 'https://opencode.ai/zen/go/v1'
OPENCODE_MODEL = 'ox-alpha-free'

MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', 'oat-hfDGDKbaaTuQyDHXbgRpgd5QWi_d--Q2vhEKTH4ZnWg')
MINIMAX_BASE_URL = os.environ.get('MINIMAX_BASE_URL', 'https://api.minimaxi.com/v1')
MINIMAX_MODEL = os.environ.get('MINIMAX_MODEL', 'MiniMax-M3')

class QuizHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == '/api/quiz-results':
            # 保存答题结果
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            # 保存到文件
            os.makedirs(RESULTS_DIR, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'quiz_{timestamp}.json'
            filepath = os.path.join(RESULTS_DIR, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 同时保存为 latest.json
            latest_path = os.path.join(RESULTS_DIR, 'latest.json')
            with open(latest_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'ok', 'file': filename}).encode('utf-8'))

        elif self.path == '/api/grade-essay':
            # AI 批改简答题
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))

            question = data.get('question', '')
            user_answer = data.get('userAnswer', '')
            reference_answer = data.get('referenceAnswer', '')
            subject = data.get('subject', '语文')

            # 调用 minimax API 进行批改
            result = grade_with_ai(question, user_answer, reference_answer, subject)

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode('utf-8'))

        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == '/api/quiz-results/latest':
            latest_path = os.path.join(RESULTS_DIR, 'latest.json')
            if os.path.exists(latest_path):
                with open(latest_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

        elif self.path.startswith('/api/quiz-results/'):
            # 获取特定文件
            filename = self.path.split('/')[-1]
            filepath = os.path.join(RESULTS_DIR, filename)
            if os.path.exists(filepath):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
            else:
                self.send_response(404)
                self.end_headers()

        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def _parse_json_loose(ai_response):
    """从 AI 回复中宽松提取 JSON（兼容 markdown 代码块）"""
    m = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', ai_response, re.DOTALL)
    if m:
        json_str = m.group(1).strip()
    else:
        s = ai_response.find('{')
        e = ai_response.rfind('}')
        json_str = ai_response[s:e + 1] if s != -1 and e > s else None
    return json.loads(json_str) if json_str else None


def grade_with_ai(question, user_answer, reference_answer, subject):
    """LLM 语义批改：依次尝试 opencode GO -> minimax，全部失败才返回错误"""
    prompt = f"""Grade this answer. Return only JSON.

Question: {question}
Student answer: {user_answer}
Reference answer: {reference_answer}

Return: {{"is_correct":true/false,"score":0-100,"error_reason":"error reason","reference_answer":"reference answer","suggestions":"suggestions"}}"""

    providers = []
    if OPENCODE_API_KEY:
        providers.append((
            'opencode',
            f'{OPENCODE_BASE_URL}/chat/completions',
            {'Content-Type': 'application/json',
             'Authorization': f'Bearer {OPENCODE_API_KEY}',
             'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Hermes/1.0'},
            {'model': OPENCODE_MODEL,
             'messages': [{'role': 'user', 'content': prompt}],
             'temperature': 0.3, 'max_tokens': 2000},
        ))
    if MINIMAX_API_KEY:
        providers.append((
            'minimax',
            f'{MINIMAX_BASE_URL}/chat/completions',
            {'Content-Type': 'application/json',
             'Authorization': f'Bearer {MINIMAX_API_KEY}'},
            {'model': MINIMAX_MODEL,
             'messages': [{'role': 'user', 'content': prompt}],
             'temperature': 0.3, 'max_tokens': 500},
        ))

    errors = []
    for name, api_url, headers, payload in providers:
        try:
            req = urllib.request.Request(api_url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode('utf-8'))
            ai_response = result['choices'][0]['message'].get('content') or ''
            print(f"[DEBUG] [{name}] 响应长度: {len(ai_response)}")
            if not ai_response.strip():
                errors.append(f'{name}: 空回复(推理吃满token)')
                continue
            grading = _parse_json_loose(ai_response)
            if grading is None:
                errors.append(f'{name}: 未找到JSON')
                continue
            print(f"[DEBUG] [{name}] 批改成功")
            return {'status': 'ok', 'provider': name, 'grading': grading}
        except Exception as e:
            errors.append(f'{name}: {e}')

    return {
        'status': 'error',
        'error': '; '.join(errors),
        'grading': {
            'is_correct': False, 'score': 0,
            'error_reason': f'AI 批改失败: {"; ".join(errors)}',
            'reference_answer': reference_answer,
            'process_issues': '', 'suggestions': '请稍后重试'
        }
    }


def main():
    server = HTTPServer(('0.0.0.0', PORT), QuizHandler)
    print(f'📚 答题结果接收服务启动')
    print(f'   端口: {PORT}')
    print(f'   结果目录: {RESULTS_DIR}')
    print(f'   AI 批改: minimax API ({MINIMAX_MODEL})')
    print()
    print('按 Ctrl+C 停止服务')
    server.serve_forever()

if __name__ == '__main__':
    main()