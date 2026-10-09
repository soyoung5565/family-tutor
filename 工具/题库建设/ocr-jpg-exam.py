#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""JPG 试卷 MiniMax-M3 vision OCR"""
import base64, json, os, re, ssl, sys, time, urllib.request
from pathlib import Path

ENV_FILE = r'D:\hermes-data\.env'
API_URL = 'https://api.minimaxi.com/anthropic/v1/messages'
MODEL = 'MiniMax-M3'

JPG_FILE = Path(r'D:\家教\系统\scripts\_jpg_urls.json')
OUT_BASE = Path(r'D:\家教\系统\scripts\_zxxk_v3')
PROGRESS = Path(r'D:\家教\系统\scripts\_jpg_progress.json')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def load_key():
    with open(ENV_FILE, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line.startswith('MINIMAX_CN_API_KEY='):
                v = line.split('=', 1)[1]
                return v.split('#')[0].strip()
    raise RuntimeError('no key')

def download_jpg(url, path):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    data = urllib.request.urlopen(req, timeout=30, context=ctx).read()
    path.write_bytes(data)
    return len(data)

def ocr_jpg(jpg_path, api_key):
    b64 = base64.b64encode(jpg_path.read_bytes()).decode('ascii')
    prompt = """这是一张小学试卷的扫描页。请把页面上的所有文字完整、准确地提取出来。

包括：题号、题干、选项(A/B/C/D)、填空、解答、应用题、拼音、汉字、英文、数字、算式。
忽略：页眉页脚的版权、页码、装订线、班级姓名栏。

要求：
1. 按阅读顺序从上到下、从左到右输出
2. 保留所有换行（每行一个题目/选项）
3. 数学公式用标准写法（分数 a/b，乘号×，除号÷）
4. 不要加任何解释或总结
5. 如果是双栏排版，先输出左栏（x<650），再输出右栏（x>=650）"""
    payload = {
        'model': MODEL,
        'max_tokens': 8192,
        'messages': [{
            'role': 'user',
            'content': [
                {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': b64}},
                {'type': 'text', 'text': prompt},
            ],
        }],
    }
    import httpx
    for attempt in range(3):
        try:
            r = httpx.post(API_URL,
                headers={'X-Api-Key': api_key, 'Content-Type': 'application/json'},
                json=payload, timeout=180)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f'    429 等 {wait}s', flush=True)
                time.sleep(wait)
                continue
            r.raise_for_status()
            j = r.json()
            content = j.get('content', [])
            for c in content:
                if c.get('type') == 'text':
                    return c.get('text', '')
            return ''
        except Exception as e:
            print(f'    attempt {attempt+1} err: {e}', flush=True)
            time.sleep(5)
    return ''

def main():
    api_key = load_key()
    jpg_urls = json.loads(JPG_FILE.read_text(encoding='utf-8'))
    progress = set()
    if PROGRESS.exists():
        progress = set(json.loads(PROGRESS.read_text(encoding='utf-8')))
    
    todo = [sid for sid in jpg_urls.keys() if sid not in progress]
    print(f'待 OCR: {len(todo)} 份', flush=True)
    
    for i, sid in enumerate(todo, 1):
        urls = jpg_urls[sid]
        print(f'\n[{i}/{len(todo)}] {sid}  {len(urls)} 页', flush=True)
        out_dir = OUT_BASE / sid
        out_dir.mkdir(parents=True, exist_ok=True)
        
        all_text = []
        for pi, url in enumerate(urls, 1):
            jpg_path = out_dir / f'page_{pi}.jpg'
            try:
                if not jpg_path.exists():
                    n = download_jpg(url, jpg_path)
                    print(f'  page {pi}: {n} bytes', flush=True)
                else:
                    print(f'  page {pi}: cached', flush=True)
                print(f'  page {pi} OCR...', flush=True)
                text = ocr_jpg(jpg_path, api_key)
                if text:
                    all_text.append(text)
                    print(f'    -> {len(text)} 字符', flush=True)
                else:
                    print(f'    x OCR 返回空', flush=True)
                time.sleep(3)
            except Exception as e:
                print(f'  page {pi} 失败: {e}', flush=True)
        
        full = '\n\n'.join(all_text)
        (out_dir / 'full.txt').write_text(full, encoding='utf-8')
        print(f'  总字符: {len(full)}', flush=True)
        
        progress.add(sid)
        PROGRESS.write_text(json.dumps(list(progress)), encoding='utf-8')
    
    print(f'\n完成 {len(progress)} 份', flush=True)

if __name__ == '__main__':
    main()
