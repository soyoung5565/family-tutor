#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev-retry-all.py — 补所有缺 jev 票的条目（v4 + newbatch），并写回题库"""
import json, time, importlib.util
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')

spec = importlib.util.spec_from_file_location('vj4', str(BASE / 'vote-judge-v4.py'))
vj4 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vj4)

all_qs = vj4.load_all_questions()
kp_pools = vj4.load_kp_pools()


def has_jev(r):
    return any(v.get('model') == 'jev' for v in r.get('votes', []))


def process(fname, timeout_note=''):
    f = BASE / fname
    if not f.exists():
        print(f"[skip] {fname} 不存在")
        return 0
    data = json.loads(f.read_text(encoding='utf-8'))
    todo = [r for r in data if not has_jev(r) and r.get('jev_error') != 'question_not_found']
    # newbatch 的结果没有 jev_error 字段，直接看缺票
    todo = [r for r in todo if r['qid'] in all_qs]
    print(f"\n[{fname}] {len(data)} 条 | 缺 jev 票待补 {len(todo)}", flush=True)
    ok = fail = 0
    for i, r in enumerate(todo, 1):
        q = all_qs.get(r['qid'])
        if not q:
            continue
        subj = r.get('subject', '语文')
        kp_detail = kp_pools.get(subj, {}).get(q.get('kp_id', ''), {})
        vote, dt = vj4.judge_jev(q, kp_detail, subj)
        if vote:
            votes = [v for v in r.get('votes', []) if v.get('model') != 'jev']
            votes.append(vote)
            n_total, n_pass, threshold, passed = vj4.apply_threshold(votes)
            r['votes'] = votes
            r['n_total'] = n_total; r['n_pass'] = n_pass
            r['threshold'] = threshold
            if 'passed_v4' in r or 'passed_v3_orig' in r:
                r['passed_v4'] = passed
            else:
                r['passed'] = passed
            r.pop('jev_error', None)
            ok += 1
        else:
            fail += 1
            if fail >= 8 and ok == 0:
                print("    连续失败过多（jev 可能仍在限流）→ 中止本次", flush=True)
                break
        if i % 10 == 0:
            f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"    ckpt {i} (ok={ok} fail={fail})", flush=True)
        time.sleep(1.2)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[{fname}] 补票 {ok} 成功 / {fail} 失败", flush=True)
    return ok


total_ok = process('_vote_results_v4.json')
total_ok += process('_vote_results_newbatch.json')

if total_ok > 0:
    import subprocess
    for fn in ['_vote_results_v4.json', '_vote_results_newbatch.json']:
        subprocess.run([r'D:\Python312\python.exe', str(BASE / 'writeback-vote.py'), fn],
                       cwd=str(BASE), timeout=600)
    print(f"\n[完成] 共补 {total_ok} 条 jev 票，已写回题库", flush=True)
else:
    print("\n[完成] 未补到任何 jev 票（jeV 仍在限流），题库未改", flush=True)
