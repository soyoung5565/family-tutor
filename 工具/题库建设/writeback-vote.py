#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writeback-vote.py — 把投票结果写回题库 vote_review（支持指定文件）
用法: python writeback-vote.py [结果文件]   默认 _vote_results_v4.json
"""
import json, sys
from pathlib import Path
from datetime import datetime

BASE = Path(r'D:\家教\系统\scripts')
fname = sys.argv[1] if len(sys.argv) > 1 else '_vote_results_v4.json'
VF = BASE / fname
if not VF.exists():
    print(f"找不到 {VF}")
    raise SystemExit(1)

results = json.loads(VF.read_text(encoding='utf-8'))
by_qid = {r['qid']: r for r in results}
print(f"读取 {len(results)} 条投票结果（{fname}）")

tag = 'v4' if 'v4' in fname else ('newbatch' if 'newbatch' in fname else 'vote')
n = 0
for subj in ['数学', '语文', '英语']:
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if not (p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1):
            continue
        try:
            qs = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        changed = False
        for q in qs:
            r = by_qid.get(q.get('qid'))
            if not r:
                continue
            q['vote_review'] = {
                'version': tag,
                'passed': r.get('passed'),
                'n_pass': r.get('n_pass'),
                'n_total': r.get('n_total'),
                'threshold': r.get('threshold'),
                'models': [v.get('model') for v in r.get('votes', [])],
                'difficulties': [(v.get('verdict') or {}).get('difficulty') for v in r.get('votes', [])],
                'reviewed_at': datetime.now().isoformat(),
            }
            changed = True
            n += 1
        if changed:
            p.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"写回 {n} 题")
