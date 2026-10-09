#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-gap-kp.py — 针对未达标弱 KP 补搜（教习网 + 21cnjy），多关键词变体"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_gap_search.json'

# 未达标 KP（<10 题）
targets = json.loads((BASE / '_kp_targets.json').read_text(encoding='utf-8'))
gaps = []
for subj in ['语文', '数学', '英语']:
    for kp in targets[subj]:
        f = Path(f"D:/家教/{subj}/测验/{kp['unit_id']}/{kp['kp_id']}.json")
        cur = len(json.loads(f.read_text(encoding='utf-8'))) if f.exists() else 0
        if cur < 10:
            gaps.append({**kp, 'subject': subj, 'cur': cur})
print(f"未达标 KP: {len(gaps)}", flush=True)

EXCLUDE = ['下册', '下学期', '五年级', '四年级', '三年级', '二年级', '一年级',
           '七年级', '八年级', '九年级', '初一', '初二', '初三', '高中', '中考', '高考',
           '教案', '课件', 'ppt', 'PPT', '教学设计', '教学计划', '学案', '导学案', '说课']
INCLUDE = ['试卷', '测试', '练习', '检测', '真题', '单元', '期中', '期末', '达标', '训练', '题']


def clean_name(name):
    """从 KP 名提取搜索核心词"""
    n = re.sub(r'^(课文|例文|古诗|单元导语[：:]?|口语交际[：:·]?|梳理与交流[·：:]?)', '', name)
    n = re.sub(r'[《》]', '', n)
    n = re.sub(r'（[^）]*）', '', n)
    n = re.sub(r'[A-Za-z:：].*$', lambda m: m.group(0) if len(m.group(0)) < 20 else '', n)
    return n.strip() or name[:20]


queries = []
for g in gaps:
    core = clean_name(g['name'])
    subj = g['subject']
    variants = [f'{core} 六年级 {subj} 练习', f'{core} 六年级 {subj} 测试卷']
    for v in variants:
        for site in ['51jiaoxi.com', '21cnjy.com']:
            queries.append({'kp_id': g['kp_id'], 'kp_name': g['name'], 'subject': subj,
                            'cur': g['cur'], 'query': v, 'site': site})
print(f"计划 {len(queries)} 次搜索", flush=True)

results = []
if OUT.exists():
    try:
        results = json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        results = []
done = {(r['query'], r['site']) for r in results}

for i, item in enumerate(queries, 1):
    if (item['query'], item['site']) in done:
        continue
    urls = []
    try:
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f"site:{item['site']} {item['query']}", 'max_results': 12},
            timeout=40)
        for x in r.json().get('results', []):
            u, t = x.get('url', ''), x.get('title', '')
            if item['site'] not in u:
                continue
            if any(k.lower() in t.lower() for k in EXCLUDE):
                continue
            if not any(k in t for k in INCLUDE):
                continue
            m = re.search(r'51jiaoxi\.com/(?:doc-)?(\d+)\.html', u) if '51jiaoxi' in u else re.search(r'21cnjy\.com/(?:P/|p/)(\d+)', u)
            urls.append({'url': u, 'title': t[:90], 'id': m.group(1) if m else u[:40]})
        if urls:
            print(f"  [{i}/{len(queries)}] {item['kp_id']}@{item['site'][:9]} -> {len(urls)}", flush=True)
    except Exception as e:
        print(f"  [{i}] err {str(e)[:60]}", flush=True)
    results.append({**item, 'urls': urls})
    time.sleep(0.9)
    if i % 20 == 0:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [ckpt {i}]", flush=True)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
tot = sum(len(r['urls']) for r in results)
ji = sum(len(r['urls']) for r in results if '51jiaoxi' in r['site'])
cn = sum(len(r['urls']) for r in results if '21cnjy' in r['site'])
print(f"\n总命中 {tot}（教习网 {ji} / 21cnjy {cn}）", flush=True)
