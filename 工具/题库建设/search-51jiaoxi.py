#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-51jiaoxi.py — Tavily 搜 51jiaoxi.com（教习网）按 73 个弱 KP 的候选试卷 URL"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_51jiaoxi_search.json'

targets = json.loads((BASE / '_kp_targets.json').read_text(encoding='utf-8'))

EXCLUDE = ['教案', '课件', 'ppt', 'PPT', '教学设计', '教学计划', '学案', '导学案',
           '说课', '教学反思', '进度表', '备课', '单元导读', '知识点汇总', '复习资料',
           '下册', '五年级', '四年级', '三年级', '二年级', '一年级',
           '初一', '初二', '初三', '七年级', '八年级', '九年级', '高中', '中考', '高考']
INCLUDE = ['试卷', '测试', '练习', '检测', '真题', '单元', '期中', '期末', '月考', '训练', '课时练']

queries = []
for subj, kps in targets.items():
    for kp in kps:
        name = kp['name']
        q = f"{name} 六年级 练习" if ('课文' in name or '《' in name) else f"{name} 六年级{subj} 练习"
        queries.append({**kp, 'subject': subj, 'query': q})

done = {}
if OUT.exists():
    try:
        prev = json.loads(OUT.read_text(encoding='utf-8'))
        done = {r['query']: r for r in prev}
    except Exception:
        done = {}
print(f"已完成 {len(done)} / {len(queries)}", flush=True)

results = list(done.values())
for i, item in enumerate(queries, 1):
    if item['query'] in done:
        continue
    try:
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f"site:51jiaoxi.com {item['query']}", 'max_results': 15},
            timeout=40)
        res = r.json().get('results', [])
        urls = []
        for x in res:
            u, t = x.get('url', ''), x.get('title', '')
            m = re.search(r'51jiaoxi\.com/(?:doc-)?(\d+)\.html', u)
            if not m:
                continue
            if any(k.lower() in t.lower() for k in EXCLUDE):
                continue
            if not any(k in t for k in INCLUDE):
                continue
            urls.append({'url': u, 'title': t[:90], 'doc_id': m.group(1)})
        results.append({**item, 'urls': urls})
        if urls:
            print(f"  [{i}/{len(queries)}] {item['kp_id']} -> {len(urls)}", flush=True)
    except Exception as e:
        print(f"  [{i}] err {str(e)[:80]}", flush=True)
    time.sleep(0.8)
    if i % 15 == 0:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [ckpt {i}]", flush=True)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
uniq, tot = set(), 0
for r in results:
    tot += len(r.get('urls', []))
    for u in r.get('urls', []):
        uniq.add(u['doc_id'])
print(f"\n总命中 {tot} 条 | unique doc_id {len(uniq)} | 覆盖 KP {sum(1 for r in results if r.get('urls'))}/{len(results)}", flush=True)
