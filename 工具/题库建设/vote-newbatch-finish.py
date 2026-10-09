#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-newbatch-finish.py — 等新批次投票跑完 → 写回题库 vote_review"""
import json, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
PY = r'D:\Python312\python.exe'
PID = 32492

def alive(p):
    r = subprocess.run(['tasklist', '/FI', f'PID eq {p}'], capture_output=True, text=True, errors='replace')
    return str(p) in (r.stdout or '')

print(f"等待投票进程 {PID} 退出...", flush=True)
t0 = time.time()
while alive(PID) and time.time() - t0 < 10800:
    time.sleep(60)
print(f"投票进程已退出（等了 {(time.time()-t0)/60:.1f} 分钟）", flush=True)

r = subprocess.run([PY, str(BASE / 'writeback-vote.py'), '_vote_results_newbatch.json'],
                   capture_output=True, text=True, encoding='utf-8', errors='replace',
                   cwd=str(BASE), timeout=900)
print("=== 写回 ===", flush=True)
print(r.stdout or '', flush=True)

try:
    v = json.loads((BASE / '_vote_results_newbatch.json').read_text(encoding='utf-8'))
    npass = sum(1 for x in v if x['passed'])
    from collections import Counter
    print(f"\n[结果] 新批次 {len(v)} 题，通过 {npass} ({100*npass/max(1,len(v)):.1f}%)", flush=True)
    print("票型:", dict(Counter(x['n_total'] for x in v)), flush=True)
except Exception as e:
    print("统计失败:", e, flush=True)
