#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retry-jev-smart.py — jev 限流恢复后慢速重试 call_failed 条目"""
import json, time, importlib.util
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
V4F = BASE / '_vote_results_v4.json'

INITIAL_WAIT = 1200      # 先等 20 分钟让限流恢复
PER_ITEM_SLEEP = 8       # 每条间隔
FAIL_STREAK_LIMIT = 5    # 连续失败 N 次
FAIL_STREAK_WAIT = 420   # 则等待 7 分钟

print(f"等 {INITIAL_WAIT}s 让 jev 限流恢复...", flush=True)
time.sleep(INITIAL_WAIT)

spec = importlib.util.spec_from_file_location('vj4', str(BASE / 'vote-judge-v4.py'))
vj4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vj4)

v4 = json.loads(V4F.read_text(encoding='utf-8'))
all_qs = vj4.load_all_questions()
kp_pools = vj4.load_kp_pools()

todo = [r for r in v4 if r.get('jev_error') == 'call_failed']
print(f"待重试: {len(todo)}", flush=True)

ok = fail = 0
streak = 0
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
        ok += 1
        streak = 0
        print(f"  [{i}/{len(todo)}] {r['qid'][-38:]} jev={'OK' if passed else 'X'} ({dt:.1f}s)", flush=True)
    else:
        fail += 1
        streak += 1
        print(f"  [{i}/{len(todo)}] {r['qid'][-38:]} 失败 ({dt:.1f}s) 连续{streak}", flush=True)
        if streak >= FAIL_STREAK_LIMIT:
            print(f"    连续失败 {streak} 次 → 等 {FAIL_STREAK_WAIT}s", flush=True)
            time.sleep(FAIL_STREAK_WAIT)
            streak = 0
    if i % 10 == 0:
        V4F.write_text(json.dumps(v4, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"    ckpt {i} (ok={ok} fail={fail})", flush=True)
    time.sleep(PER_ITEM_SLEEP)

V4F.write_text(json.dumps(v4, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"\n完成: {ok} 成功 / {fail} 失败 | {(time.perf_counter()-t0)/60:.1f} 分钟", flush=True)
