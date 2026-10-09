#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""21cnjy-crawl-r5.py — 抓 round3b 的 zy.21cnjy.com 页面 → _21cnjy_pages/{id}.txt
带标题预过滤：只要试卷/测试/练习类，排除教案/课件/PPT/计划。
"""
import json, re, time, html as H
from pathlib import Path
import requests

BASE = Path(r'D:\家教\系统\scripts')
PAGES = BASE / '_21cnjy_pages'
PAGES.mkdir(exist_ok=True)
SRC_F = BASE / '_round5_cn.json'
PROG_F = BASE / '_21cnjy_crawl_progress.json'
ERR_F = BASE / '_21cnjy_crawl_errors_r5.json'
LOG_F = BASE / '_21cnjy_crawl_r5.log'

UA = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'}

GOOD = ['试卷', '测试', '练习', '检测', '单元', '期中', '期末', '真题', '达标', '月考', '模拟', '训练', '题']
BAD = ['教案', '课件', 'ppt', '教学设计', '教学计划', '学案', '导学案', '说课', '知识清单',
       '复习提纲', '说课稿', '备课', '讲义', '计划', '素材', '视频', '音频', '朗读']


def log(m):
    print(m, flush=True)
    with open(LOG_F, 'a', encoding='utf-8') as f:
        f.write(m + '\n')


def extract(html_text):
    body = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', html_text, flags=re.DOTALL | re.I)
    text = re.sub(r'<[^>]+>', '\n', body)
    text = H.unescape(text)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    start = 0
    for i, l in enumerate(lines):
        if len(l) < 14 and ('文档简介' in l or '资源简介' in l):
            start = i
            break
    out = lines[start:]
    cleaned = [l for l in out if not re.fullmatch(r'[\d.,]+\s*(KB|MB|B)?', l)]
    return '\n'.join(cleaned).strip()


def title_of(html_text):
    m = re.search(r'<title>(.*?)</title>', html_text, re.S | re.I)
    return H.unescape(m.group(1)).strip() if m else ''


items = json.loads(SRC_F.read_text(encoding='utf-8'))
prog = set()
if PROG_F.exists():
    try: prog = set(json.loads(PROG_F.read_text(encoding='utf-8')))
    except Exception: prog = set()
errors = []

log(f"=== 21cnjy crawl-b 启动: 待抓 {len(items)} | 已完成 {len(prog)} ===")
ok = skip = 0
for i, it in enumerate(items, 1):
    uid = it['doc_id']
    if uid in prog:
        continue
    target = PAGES / f'{uid}.txt'
    if target.exists() and target.stat().st_size > 200:
        prog.add(uid)
        continue
    try:
        u = it['url']
        # 兼容新域名格式
        if re.match(r'https?://zy\.21cnjy\.com/\d+', u):
            page_url = u
        else:
            page_url = f'https://zy.21cnjy.com/{uid}'
        r = requests.get(page_url, headers=UA, timeout=40)
        ttl = title_of(r.text)
        tl = ttl.lower()
        GRADE_OK = any(g in ttl for g in ['六年级', '六上', '六下', '6年级', '小学六'])
        if not GRADE_OK:
            skip += 1
            log(f"  [{i}/{len(items)}] {uid} 跳过（非六年级）: {ttl[:45]}")
            prog.add(uid)
            continue
        if any(b in tl for b in BAD) and not any(g in tl for g in GOOD):
            skip += 1
            log(f"  [{i}/{len(items)}] {uid} 跳过（非试卷）: {ttl[:50]}")
            prog.add(uid)
            continue
        txt = extract(r.text)
        if len(txt) < 200:
            errors.append({'id': uid, 'url': page_url, 'reason': f'short({len(txt)})'})
            log(f"  [{i}/{len(items)}] {uid} 过短 {len(txt)}")
        else:
            target.write_text(txt, encoding='utf-8')
            prog.add(uid)
            ok += 1
            log(f"  [{i}/{len(items)}] {uid} OK {len(txt)}字 | {ttl[:45]}")
    except Exception as e:
        errors.append({'id': uid, 'url': it.get('url', ''), 'reason': str(e)[:80]})
        log(f"  [{i}/{len(items)}] {uid} ERR {str(e)[:60]}")
    time.sleep(1.5)
    if i % 10 == 0:
        PROG_F.write_text(json.dumps(sorted(prog), ensure_ascii=False), encoding='utf-8')

PROG_F.write_text(json.dumps(sorted(prog), ensure_ascii=False), encoding='utf-8')
ERR_F.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
log(f"=== 完成: 成功 {ok} | 跳过(非试卷) {skip} | 错误 {len(errors)} ===")
