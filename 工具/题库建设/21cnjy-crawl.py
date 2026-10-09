#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""21cnjy-crawl.py — 抓 21cnjy 页面正文 → _21cnjy_pages/{id}.txt"""
import json, re, time, html as H
from pathlib import Path
import requests

BASE = Path(r'D:\家教\系统\scripts')
PAGES = BASE / '_21cnjy_pages'
PAGES.mkdir(exist_ok=True)
SEARCH_F = BASE / '_gap_search.json'
PROG_F = BASE / '_21cnjy_crawl_progress.json'
ERR_F = BASE / '_21cnjy_crawl_errors.json'

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}


def extract(html_text):
    body = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html_text, flags=re.DOTALL | re.I)
    text = re.sub(r'<[^>]+>', '\n', body)
    text = H.unescape(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    # 从"文档简介"/"资源简介"之后开始（去掉站头导航）
    start = 0
    for i, l in enumerate(lines):
        if len(l) < 14 and ('文档简介' in l or '资源简介' in l):
            start = i
            break
    out = lines[start:]
    # 去掉纯数字/单位噪声行
    cleaned = [l for l in out if not re.fullmatch(r'[\d.,]+\s*(KB|MB|B)?', l)]
    return '\n'.join(cleaned).strip()


search = json.loads(SEARCH_F.read_text(encoding='utf-8')) if SEARCH_F.exists() else []
urls = {}
for r in search:
    if '21cnjy' not in r.get('site', ''):
        continue
    for u in r.get('urls', []):
        uid = u.get('id')
        if uid and uid.isdigit():
            urls.setdefault(uid, u)

prog = set()
if PROG_F.exists():
    try: prog = set(json.loads(PROG_F.read_text(encoding='utf-8')))
    except Exception: prog = set()
errors = []
if ERR_F.exists():
    try: errors = json.loads(ERR_F.read_text(encoding='utf-8'))
    except Exception: errors = []

print(f"待抓 {len(urls)} | 已完成 {len(prog)}", flush=True)
for i, (uid, info) in enumerate(sorted(urls.items()), 1):
    if uid in prog:
        continue
    target = PAGES / f'{uid}.txt'
    if target.exists() and target.stat().st_size > 200:
        prog.add(uid)
        continue
    try:
        r = requests.get(info['url'], headers=UA, timeout=40)
        txt = extract(r.text)
        if len(txt) < 200:
            errors.append({'id': uid, 'url': info['url'], 'reason': f'short({len(txt)})'})
            print(f"  [{i}/{len(urls)}] {uid} 过短 {len(txt)}", flush=True)
        else:
            target.write_text(txt, encoding='utf-8')
            prog.add(uid)
            print(f"  [{i}/{len(urls)}] {uid} OK {len(txt)}字 | {info.get('title','')[:40]}", flush=True)
    except Exception as e:
        errors.append({'id': uid, 'url': info['url'], 'reason': str(e)[:80]})
        print(f"  [{i}/{len(urls)}] {uid} ERR {str(e)[:60]}", flush=True)
    time.sleep(1.5)
    if i % 10 == 0:
        PROG_F.write_text(json.dumps(sorted(prog), ensure_ascii=False), encoding='utf-8')
        ERR_F.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')

PROG_F.write_text(json.dumps(sorted(prog), ensure_ascii=False), encoding='utf-8')
ERR_F.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n抓取完成 {len(prog)}/{len(urls)} | 错误 {len(errors)}", flush=True)
