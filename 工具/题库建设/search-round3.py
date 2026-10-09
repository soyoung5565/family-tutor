#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-round3.py — 第三轮扩搜（<30题 KP，新关键词变体，21cnjy + 教习网）"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_round3_search.json'

# 目标 KP（<30 题，排除习作类）
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

# 新关键词后缀（与之前几轮不同）
SUFFIX = ['六年级 期末专项复习', '六年级 同步练习卷', '六年级 单元测试AB卷', '六年级 知识点专项训练', '六年级 名校真题卷']

def core(name):
    n = re.sub(r'^(课文|例文|古诗|单元导语[：:]?|口语交际[：:·]?|梳理与交流[·：:]?)', '', name)
    n = re.sub(r'[《》]', '', n)
    n = re.sub(r'（[^）]*）', '', n)
    return n.strip() or name[:20]

EXCLUDE = ['下册', '下学期', '五年级', '四年级', '三年级', '二年级', '一年级',
           '七年级', '八年级', '九年级', '初一', '初二', '初三', '中考', '高考', '高中',
           '教案', '课件', 'ppt', '教学设计', '教学计划', '学案', '导学案', '说课',
           '习作', '作文']
INCLUDE = ['试卷', '测试', '练习', '检测', '真题', '单元', '期中', '期末', '达标', '训练', '题']

queries = []
for t in targets:
    c = core(t['name'])
    for sfx in SUFFIX[:3]:
        for site in ['51jiaoxi.com', '21cnjy.com']:
            queries.append({**t, 'query': f'{c} {sfx}', 'site': site})
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
            u, ttl = x.get('url', ''), x.get('title', '')
            if item['site'] not in u:
                continue
            if any(k.lower() in ttl.lower() for k in EXCLUDE):
                continue
            if not any(k in ttl for k in INCLUDE):
                continue
            m = re.search(r'51jiaoxi\.com/(?:doc-)?(\d+)\.html', u) if '51jiaoxi' in u else re.search(r'21cnjy\.com/(?:P/|p/)(\d+)', u)
            urls.append({'url': u, 'title': ttl[:90], 'id': m.group(1) if m else u[:40]})
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
print(f"\n总命中 {tot} | 覆盖 KP {sum(1 for r in results if r['urls'])}/{len(results)}", flush=True)
