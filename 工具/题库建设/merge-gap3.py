#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge-gap3.py — 把专项补搜结果合并进两站输入文件"""
import json
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
d = json.loads((BASE / '_gap3_search.json').read_text(encoding='utf-8'))

# 21cnjy
uf = BASE / '_21cnjy_urls.json'
urls = json.loads(uf.read_text(encoding='utf-8'))
added_cn = 0
for r in d:
    if '21cnjy' not in r['site']:
        continue
    for u in r['urls']:
        if u['url'] not in urls:
            urls[u['url']] = {'title': u['title'],
                              'kps': [{'kp_id': r['kp_id'], 'subject': r['subject'], 'kp_name': r.get('kp_name', '')}]}
            added_cn += 1
uf.write_text(json.dumps(urls, ensure_ascii=False, indent=2), encoding='utf-8')

# 教习网
sf = BASE / '_51jiaoxi_search.json'
s = json.loads(sf.read_text(encoding='utf-8'))
have = set()
for rec in s:
    for u in rec.get('urls', []):
        have.add(u['doc_id'])
by_kp = {}
for r in d:
    if '51jiaoxi' not in r['site']:
        continue
    for u in r['urls']:
        did = u.get('id', '')
        if not did.isdigit() or did in have:
            continue
        by_kp.setdefault((r['kp_id'], r['subject'], r.get('kp_name', '')), []).append(
            {'url': u['url'], 'title': u['title'], 'doc_id': did})
added_jx = 0
for (kid, subj, kname), us in by_kp.items():
    s.append({'kp_id': kid, 'name': kname, 'unit_id': kid.split('.')[0], 'current': 0,
              'subject': subj, 'query': f'gap3 {kid}', 'urls': us})
    added_jx += len(us)
sf.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"合并完成: 21cnjy +{added_cn} 条 / 教习网 +{added_jx} doc")
