#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-newbatch.py — 对新增题目抽样跑 4 票制投票（3 LLM + jev，失败票自动跳过）"""
import json, time, importlib.util
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
SAMPLE_F = BASE / '_newbatch_sample.json'
OUT_F = BASE / '_vote_results_newbatch.json'

spec = importlib.util.spec_from_file_location('vj4', str(BASE / 'vote-judge-v4.py'))
vj4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vj4)

sample = json.loads(SAMPLE_F.read_text(encoding='utf-8'))
all_qs = vj4.load_all_questions()
kp_pools = vj4.load_kp_pools()

results = []
done = set()
if OUT_F.exists():
    try:
        results = json.loads(OUT_F.read_text(encoding='utf-8'))
        done = {r['qid'] for r in results}
    except Exception:
        results, done = [], set()

todo = [x for x in sample if x['qid'] not in done]
print(f"待审 {len(todo)} / 总 {len(sample)}（已完成 {len(done)}）", flush=True)

t0 = time.perf_counter()
for i, item in enumerate(todo, 1):
    qid = item['qid']
    q = all_qs.get(qid)
    if not q:
        continue
    subj = item['subject']
    kp_detail = kp_pools.get(subj, {}).get(q.get('kp_id', ''), {})
    votes = vj4.judge_one_llm(q, kp_detail, subj)
    vote_jev, dt = vj4.judge_jev(q, kp_detail, subj)
    if vote_jev:
        votes.append(vote_jev)
    n_total, n_pass, threshold, passed = vj4.apply_threshold(votes)
    results.append({'qid': qid, 'subject': subj, 'kp_id': q.get('kp_id'), 'unit_id': q.get('unit_id'),
                    'votes': votes, 'n_total': n_total, 'n_pass': n_pass,
                    'threshold': threshold, 'passed': passed,
                    'stem_preview': q.get('stem', '')[:60]})
    models = ','.join(v['model'] for v in votes)
    print(f"  [{i}/{len(todo)}] {qid[-38:]} {n_pass}/{n_total} {'PASS' if passed else 'x'} [{models}]", flush=True)
    if i % 10 == 0:
        OUT_F.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        npass = sum(1 for r in results if r['passed'])
        print(f"    ckpt {len(results)} | 通过 {npass} | {(time.perf_counter()-t0)/60:.1f}min", flush=True)

OUT_F.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
npass = sum(1 for r in results if r['passed'])
print(f"\n完成: {npass}/{len(results)} 通过 ({100*npass/max(1,len(results)):.1f}%) | {(time.perf_counter()-t0)/60:.1f} 分钟", flush=True)
