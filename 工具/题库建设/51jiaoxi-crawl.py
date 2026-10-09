#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""51jiaoxi-crawl.py — 抓教习网文档正文 → _51jiaoxi_pages/{doc_id}.txt"""
import json, re, time, html as H
from pathlib import Path
import requests

BASE = Path(r'D:\家教\系统\scripts')
PAGES = BASE / '_51jiaoxi_pages'
PAGES.mkdir(exist_ok=True)
SEARCH_F = BASE / '_51jiaoxi_search.json'
PROG_F = BASE / '_51jiaoxi_crawl_progress.json'
ERR_F = BASE / '_51jiaoxi_crawl_errors.json'

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}


def extract(html_text):
    """从 intro-content-inner 取正文（含完整题目+选项+答案）"""
    m = re.search(r'<p class="intro-content-inner[^"]*">(.*?)</p>', html_text, re.DOTALL)
    if not m:
        return ''
    c = m.group(1)
    c = re.sub(r'<br\s*/?>', '\n', c, flags=re.I)
    c = re.sub(r'<[^>]+>', '', c)
    c = H.unescape(c)
    c = c.replace('\r\n', '\n').replace('\r', '\n')
    c = re.sub(r'\n{3,}', '\n\n', c)
    return c.strip()


search = json.loads(SEARCH_F.read_text(encoding='utf-8'))
urls = {}
for r in search:
    for u in r.get('urls', []):
        urls.setdefault(u['doc_id'], u)

prog = set()
if PROG_F.exists():
    try:
        prog = set(json.loads(PROG_F.read_text(encoding='utf-8')))
    except Exception:
        prog = set()
errors = []
if ERR_F.exists():
    try:
        errors = json.loads(ERR_F.read_text(encoding='utf-8'))
    except Exception:
        errors = []

print(f"待抓 {len(urls)} | 已完成 {len(prog)}", flush=True)

for i, (did, info) in enumerate(sorted(urls.items()), 1):
    if did in prog:
        continue
    target = PAGES / f'{did}.txt'
    if target.exists() and target.stat().st_size > 200:
        prog.add(did)
        continue
    try:
        r = requests.get(info['url'], headers=UA, timeout=40)
        txt = extract(r.text)
        if len(txt) < 300:
            errors.append({'doc_id': did, 'url': info['url'], 'title': info.get('title', '')[:60],
                           'reason': f'short({len(txt)})'})
            print(f"  [{i}/{len(urls)}] {did} 过短 {len(txt)}", flush=True)
        else:
            target.write_text(txt, encoding='utf-8')
            prog.add(did)
            print(f"  [{i}/{len(urls)}] {did} OK {len(txt)}字 | {info.get('title','')[:40]}", flush=True)
    except Exception as e:
        errors.append({'doc_id': did, 'url': info['url'], 'title': info.get('title', '')[:60],
                       'reason': str(e)[:100]})
        print(f"  [{i}/{len(urls)}] {did} ERR {str(e)[:70]}", flush=True)
    time.sleep(1.5)
    if i % 10 == 0:
        PROG_F.write_text(json.dumps(sorted(prog), ensure_ascii=False), encoding='utf-8')
        ERR_F.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')

PROG_F.write_text(json.dumps(sorted(prog), ensure_ascii=False), encoding='utf-8')
ERR_F.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n抓取完成 {len(prog)}/{len(urls)} | 错误 {len(errors)}", flush=True)
