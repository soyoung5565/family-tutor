#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev-morning-retry.py — 定时任务用：重试 jev 票 + 写回题库 vote_review"""
import subprocess, json
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
PY = r'D:\Python312\python.exe'

def run(script_name, timeout=1800):
    r = subprocess.run([PY, str(BASE / script_name)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=str(BASE), timeout=timeout)
    return r.stdout or '', r.stderr or ''

out1, err1 = run('retry-jev-failed.py')
print("=== jev 重试 ===")
print(out1[-1800:])
if 'Rate limit' in out1 or '仍失败' in out1[-2000:]:
    print("[!] jev 仍限流——额度可能按日重置，稍后再试")
    raise SystemExit(0)

out2, err2 = run('writeback-vote-v4.py', timeout=900)
print("\n=== 写回题库 ===")
print(out2[-1500:])

# 汇报 v4 统计
try:
    v4 = json.loads((BASE / '_vote_results_v4.json').read_text(encoding='utf-8'))
    n_jev = sum(1 for r in v4 if any(v.get('model') == 'jev' for v in r.get('votes', [])))
    v4p = sum(1 for r in v4 if r.get('passed_v4', r.get('passed')))
    print(f"\n[结果] {len(v4)} 条中 {n_jev} 条有 jev 票 | v4 通过 {v4p} ({100*v4p/len(v4):.1f}%)")
except Exception as e:
    print("统计失败:", e)
