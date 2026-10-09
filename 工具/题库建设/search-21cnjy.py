#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
targets = json.loads(Path(r'D:\家教\系统\scripts\_kp_targets.json').read_text(encoding='utf-8'))

queries = []
for subj, kps in targets.items():
    for kp in kps:
        name = kp['name']
        if '课文' in name or '《' in name:
            q = f'{name} 六年级 练习'
        else:
            q = f'{name} 六年级{subj} 练习'
        queries.append({
            'subject': subj, 'kp_id': kp['kp_id'], 'unit_id': kp['unit_id'],
            'kp_name': name, 'query': q,
        })

OUT = Path(r'D:\家教\系统\scripts\_21cnjy_search.json')
existing = []
done_qs = set()
if OUT.exists():
    existing = json.loads(OUT.read_text(encoding='utf-8'))
    done_qs = {r['query'] for r in existing}
print(f"已搜: {len(done_qs)}, 待搜: {len(queries) - len(done_qs)}", flush=True)

new_results = []
for i, item in enumerate(queries, 1):
    if item['query'] in done_qs: continue
    q = item['query']
    try:
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f'site:21cnjy.com {q}', 'max_results': 10},
            timeout=30)
        results = r.json().get('results', [])
        cn_urls = []
        for x in results:
            url = x.get('url', '')
            if re.search(r'(mip\.21cnjy\.com/P/\d+|zy\.21cnjy\.com/\d+)', url):
                cn_urls.append({'url': url, 'title': x.get('title','')})
        new_results.append({**item, 'cn_urls': cn_urls})
        if cn_urls:
            print(f"  [{i}] {item['kp_id']} -> {len(cn_urls)}", flush=True)
    except Exception as e:
        print(f"  err {i}: {e}", flush=True)
    time.sleep(1)
    
    if i % 15 == 0:
        all_r = existing + new_results
        OUT.write_text(json.dumps(all_r, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [ckpt {i}]", flush=True)

all_r = existing + new_results
OUT.write_text(json.dumps(all_r, ensure_ascii=False, indent=2), encoding='utf-8')

total_urls = sum(len(r['cn_urls']) for r in all_r)
print(f"\n总命中 21cnjy URL: {total_urls}", flush=True)
print(f"覆盖 KP: {sum(1 for r in all_r if r['cn_urls'])} / {len(all_r)}", flush=True)
