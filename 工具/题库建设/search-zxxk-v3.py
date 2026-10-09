#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-zxxk-v3.py — Tavily 扩搜 zxxk 试卷（地区+真题模板 + 针对性补漏 KP）"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_zxxk_search_v3.json'

# 已抓过的 soft_id
fetched = set()
v3dir = BASE / '_zxxk_v3'
if v3dir.exists():
    fetched = {p.name for p in v3dir.iterdir() if p.is_dir()}

REGIONS = ['北京', '上海', '深圳', '广州', '江苏', '浙江', '山东', '四川', '广东']
SUBJECTS = ['语文', '数学', '英语']
TERMS = ['期末', '期中']
SPECIAL = ['花坛周长 六年级 数学 练习', '花坛周长问题 六年级数学',
           '六年级上册 语文 灯光 练习', '六年级上册 我的战友邱少云 练习']

queries = [f'{r} 六年级 {s} {t} 真题' for r in REGIONS for s in SUBJECTS for t in TERMS] + SPECIAL
print(f"计划 {len(queries)} 次查询（已抓 {len(fetched)} 份）", flush=True)

results = []
if OUT.exists():
    try:
        results = json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        results = []
done_q = {r['query'] for r in results}

for i, q in enumerate(queries, 1):
    if q in done_q:
        continue
    urls = []
    try:
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f'site:zxxk.com/soft {q}', 'max_results': 15},
            timeout=40)
        for x in r.json().get('results', []):
            u, t = x.get('url', ''), x.get('title', '')
            m = re.search(r'zxxk\.com/soft/(\d+)', u)
            if not m:
                continue
            if not re.search(r'六年级|6年级|小学', t):
                continue
            if re.search(r'七年级|八年级|九年级|初一|初二|初三|高中|中考|高二|高三|高一', t):
                continue
            urls.append({'soft_id': m.group(1), 'url': u, 'title': t[:90]})
    except Exception as e:
        print(f"  [{i}] err {str(e)[:70]}", flush=True)
    results.append({'query': q, 'zxxk_urls': urls})
    if urls:
        print(f"  [{i}/{len(queries)}] {q[:36]} -> {len(urls)}", flush=True)
    time.sleep(1.0)
    if i % 15 == 0:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [ckpt {i}]", flush=True)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

uniq = {}
for r in results:
    for u in r.get('zxxk_urls', []):
        uniq.setdefault(u['soft_id'], u)
new = {k: v for k, v in uniq.items() if k not in fetched}
print(f"\n命中 unique soft_id: {len(uniq)} | 其中未抓过: {len(new)}", flush=True)
(BASE / '_zxxk_candidates_v3.json').write_text(
    json.dumps(list(new.values()), ensure_ascii=False, indent=2), encoding='utf-8')
print("候选清单: _zxxk_candidates_v3.json", flush=True)
