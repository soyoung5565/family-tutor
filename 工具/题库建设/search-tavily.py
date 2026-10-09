#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tavily + site:zxxk.com 大规模搜索"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'

plan = json.loads(Path(r'D:\家教\系统\scripts\_search_plan_v2.json').read_text(encoding='utf-8'))
print(f"开始 {len(plan)} 次搜索", flush=True)

# 已搜过的
done_queries = set()
for r in json.loads(Path(r'D:\家教\系统\scripts\_search_results_20260917.json').read_text(encoding='utf-8')):
    done_queries.add(r['query'])

# 断点续跑
OUT_FILE = Path(r'D:\家教\系统\scripts\_tavily_results.json')
existing = []
done_tavily_queries = set()
if OUT_FILE.exists():
    existing = json.loads(OUT_FILE.read_text(encoding='utf-8'))
    done_tavily_queries = {r['query'] for r in existing}
    print(f"已搜过 {len(done_tavily_queries)}，剩 {len(plan) - len(done_tavily_queries)}", flush=True)

new_results = []
for i, item in enumerate(plan, 1):
    q = item['query']
    if q in done_queries or q in done_tavily_queries:
        continue
    try:
        # site:zxxk.com 限定
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f'site:zxxk.com {q}', 'max_results': 10},
            timeout=30)
        results = r.json().get('results', [])
        zxxk_urls = []
        for x in results:
            url = x.get('url', '')
            # 支持 m.zxxk.com 和 www.zxxk.com
            m = re.search(r'zxxk\.com/soft/(\d+)', url)
            if m:
                zxxk_urls.append({'soft_id': m.group(1), 'url': url, 'title': x.get('title','')})
        new_results.append({**item, 'zxxk_urls': zxxk_urls, 'total_refs': len(results), 'source': 'tavily'})
        if zxxk_urls:
            print(f"  [{i}/{len(plan)}] {item['subject']}/{item['unit']} {q[:35]} -> {len(zxxk_urls)}", flush=True)
    except Exception as e:
        print(f"  [{i}] err: {e}", flush=True)
        new_results.append({**item, 'error': str(e), 'zxxk_urls': []})
    time.sleep(1)  # Tavily 宽容些
    
    if i % 20 == 0:
        all_r = existing + new_results
        OUT_FILE.write_text(json.dumps(all_r, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"  [checkpoint {i}] 累计 {len(all_r)}", flush=True)

# 最终保存
all_r = existing + new_results
OUT_FILE.write_text(json.dumps(all_r, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n完成 {len(new_results)} 次, 总 {len(all_r)}", flush=True)

# 统计 unique soft_id
all_sids = set()
for r in all_r:
    for u in r.get('zxxk_urls', []):
        all_sids.add(u['soft_id'])
print(f"unique soft_id: {len(all_sids)}", flush=True)
