#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, requests, time, re, sys
from pathlib import Path

keys = json.load(open('D:/hermes-data/skills/multi-search-engine/api-keys.json'))
key = keys['channels']['baidu_qianfan']['api_key']

plan = json.loads(Path(r'D:\家教\系统\scripts\_search_plan_v2.json').read_text(encoding='utf-8'))
print(f"开始 {len(plan)} 次搜索...", flush=True)

v3 = Path(r'D:\家教\系统\scripts\_zxxk_v3')
already_fetched = {p.name for p in v3.iterdir() if p.is_dir() and (p/'full.txt').exists()}
print(f"已抓过: {len(already_fetched)}", flush=True)

old_results = json.loads(Path(r'D:\家教\系统\scripts\_search_results_20260917.json').read_text(encoding='utf-8'))
old_queries = {r['query'] for r in old_results}

new_results = []
n_zxxk_total = 0
done = 0
for item in plan:
    q = item['query']
    done += 1
    if q in old_queries:
        continue
    try:
        r = requests.post('https://qianfan.baidubce.com/v2/ai_search/web_search',
            headers={'Authorization': f'Bearer {key}', 'X-Appbuilder-From': 'openmaic'},
            json={'messages':[{'content': q, 'role':'user'}],
                  'search_source':'baidu_search_v2',
                  'resource_type_filter':[{'type':'web','top_k':10}]}, timeout=30)
        refs = r.json().get('references', [])
        zxxk_urls = []
        for x in refs:
            url = x.get('url', '')
            if 'zxxk.com/soft/' in url:
                m = re.search(r'/soft/(\d+)', url)
                if m:
                    zxxk_urls.append({'soft_id': m.group(1), 'url': url, 'title': x.get('title','')})
        n_zxxk_total += len(zxxk_urls)
        new_results.append({**item, 'zxxk_urls': zxxk_urls, 'total_refs': len(refs)})
        if zxxk_urls:
            print(f"  [{done}/{len(plan)}] {item['subject']}/{item['unit']} {q[:35]} -> {len(zxxk_urls)}", flush=True)
    except Exception as e:
        new_results.append({**item, 'error': str(e), 'zxxk_urls': []})
    time.sleep(2)
    
    if done % 20 == 0:
        Path(r'D:\家教\系统\scripts\_search_results_v2.json').write_text(
            json.dumps(new_results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [checkpoint {done}] 已保存 {len(new_results)} 条", flush=True)

print(f"\n完成搜索 {len(new_results)} 次, zxxk URL 总数 {n_zxxk_total}", flush=True)
Path(r'D:\家教\系统\scripts\_search_results_v2.json').write_text(
    json.dumps(new_results, ensure_ascii=False, indent=2), encoding='utf-8')

all_results = old_results + new_results
all_soft_ids = {}
for r in all_results:
    for u in r.get('zxxk_urls', []):
        sid = u['soft_id']
        if sid not in all_soft_ids:
            all_soft_ids[sid] = {'soft_id': sid, 'title': u['title'], 'url': u['url'],
                                 'subjects_units': [(r['subject'], r['unit'])]}
        else:
            su = (r['subject'], r['unit'])
            if su not in all_soft_ids[sid]['subjects_units']:
                all_soft_ids[sid]['subjects_units'].append(su)

print(f"unique soft_id 总数: {len(all_soft_ids)}", flush=True)
new_sids = set(all_soft_ids.keys()) - already_fetched
print(f"新增待抓: {len(new_sids)}", flush=True)

Path(r'D:\家教\系统\scripts\_all_candidates_v2.json').write_text(
    json.dumps(list(all_soft_ids.values()), ensure_ascii=False, indent=2), encoding='utf-8')
