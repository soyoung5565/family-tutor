#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retry-jev-failed.py — 重试 v4 里 jev call_failed 的条目（原地更新，不追加）"""
import json, time, importlib.util
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
V4F = BASE / '_vote_results_v4.json'

spec = importlib.util.spec_from_file_location('vj4', str(BASE / 'vote-judge-v4.py'))
vj4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vj4)

v4 = json.loads(V4F.read_text(encoding='utf-8'))
all_qs = vj4.load_all_questions()
kp_pools = vj4.load_kp_pools()

todo = [r for r in v4 if r.get('jev_error') == 'call_failed']
print(f"待重试: {len(todo)}", flush=True)

ok = fail = 0
lat = []
t0 = time.perf_counter()
for i, r in enumerate(todo, 1):
    q = all_qs.get(r['qid'])
    if not q:
        r['jev_error'] = 'question_not_found'
        continue
    subj = r.get('subject', '语文')
    kp_detail = kp_pools.get(subj, {}).get(q.get('kp_id', ''), {})
    vote, dt = vj4.judge_jev(q, kp_detail, subj)
    if vote:
        votes = [v for v in r.get('votes', []) if v.get('model') != 'jev']
        votes.append(vote)
        n_total, n_pass, threshold, passed = vj4.apply_threshold(votes)
        r['votes'] = votes
        r['n_total'] = n_total
        r['n_pass'] = n_pass
        r['threshold'] = threshold
        r['passed_v4'] = passed
        r.pop('jev_error', None)
        lat.append(dt)
        ok += 1
        print(f"  [{i}/{len(todo)}] {r['qid'][-40:]} jev={'OK' if passed else 'X'} ({dt:.1f}s)", flush=True)
    else:
        fail += 1
        print(f"  [{i}/{len(todo)}] {r['qid'][-40:]} 仍失败 ({dt:.1f}s)", flush=True)
    if i % 10 == 0:
        V4F.write_text(json.dumps(v4, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"    ckpt {i}", flush=True)
    time.sleep(1)

V4F.write_text(json.dumps(v4, ensure_ascii=False, indent=2), encoding='utf-8')
import statistics
print(f"\n重试完成: {ok} 成功 / {fail} 失败 | {time.perf_counter()-t0:.0f}s", flush=True)
if lat:
    print(f"p50={statistics.median(lat):.1f}s", flush=True)
