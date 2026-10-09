#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-zxxk-v4.py — 针对 <30 题 KP 搜学科网新卷（Tavily site:zxxk.com/soft）"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_zxxk_search_v4.json'

XI_ZUO = ['习作', '作文', '变形记', '多彩的活动', '让生活更美好', '传承好家风', '插上科学', '围绕中心意思']
targets = []
for subj in ['语文', '数学', '英语']:
    pool = json.loads(Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json').read_text(encoding='utf-8'))
    for kp_id, info in pool.items():
        name = info.get('name', '')
        if any(k in name for k in XI_ZUO):
            continue
        f = Path(f"D:/家教/{subj}/测验/{kp_id.split('.')[0]}/{kp_id}.json")
        cur = len(json.loads(f.read_text(encoding='utf-8'))) if f.exists() else 0
        if cur < 30:
            targets.append({'subj': subj, 'kp_id': kp_id, 'name': name, 'cur': cur})
print(f"目标 KP: {len(targets)}", flush=True)

# 已抓过的 soft_id（避免重复）
fetched = set()
v3 = BASE / '_zxxk_v3'
v4 = BASE / '_zxxk_v4'
for d in (v3, v4):
    if d.exists():
        fetched |= {p.name for p in d.iterdir() if p.is_dir()}

def core(name):
    n = re.sub(r'^(课文|例文|古诗|单元导语[：:]?|口语交际[：:·]?|梳理与交流[·：:]?)', '', name)
    n = re.sub(r'[《》]', '', n)
    n = re.sub(r'（[^）]*）', '', n)
    return n.strip() or name[:20]

EXCLUDE = ['下册', '下学期', '五年级', '四年级', '三年级', '二年级', '一年级',
           '七年级', '八年级', '九年级', '初一', '初二', '初三', '中考', '高考', '高中',
           '教案', '课件', 'ppt', '教学设计', '教学计划', '学案', '导学案', '说课']

queries = []
for t in targets:
    c = core(t['name'])
    for sfx in ['六年级 测试卷', '六年级 单元检测']:
        queries.append({**t, 'query': f'{c} {sfx}'})
print(f"计划 {len(queries)} 次查询（已抓过 {len(fetched)} 份）", flush=True)

results = []
if OUT.exists():
    try:
        results = json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        results = []
done = {r['query'] for r in results}

for i, item in enumerate(queries, 1):
    if item['query'] in done:
        continue
    urls = []
    try:
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f"site:zxxk.com/soft {item['query']}", 'max_results': 12},
            timeout=40)
        for x in r.json().get('results', []):
            u, ttl = x.get('url', ''), x.get('title', '')
            m = re.search(r'zxxk\.com/soft/(\d+)', u)
            if not m:
                continue
            sid = m.group(1)
            if sid in fetched:
                continue
            if not re.search(r'六年级|6年级|小学', ttl):
                continue
            if any(k in ttl for k in EXCLUDE):
                continue
            urls.append({'soft_id': sid, 'url': u, 'title': ttl[:90]})
        if urls:
            print(f"  [{i}/{len(queries)}] {item['kp_id']} -> {len(urls)}", flush=True)
    except Exception as e:
        print(f"  [{i}] err {str(e)[:60]}", flush=True)
    results.append({**item, 'zxxk_urls': urls})
    time.sleep(0.9)
    if i % 25 == 0:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [ckpt {i}]", flush=True)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
uniq = {}
for r in results:
    for u in r['zxxk_urls']:
        uniq.setdefault(u['soft_id'], u)
print(f"\n新 soft_id: {len(uniq)}", flush=True)
(BASE / '_zxxk_candidates_v4.json').write_text(
    json.dumps(list(uniq.values()), ensure_ascii=False, indent=2), encoding='utf-8')
