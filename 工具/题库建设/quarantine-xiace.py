#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""quarantine-xiace.py — 等核查完成 → 把「下册内容」题隔离到 _meta/quarantine_xiace/"""
import json, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
QUAR = Path(r'D:\家教\_meta\quarantine_xiace')
QUAR.mkdir(parents=True, exist_ok=True)
CHECK = BASE / '_xiace_check.json'
PID = 6852


def alive(p):
    r = subprocess.run(['tasklist', '/FI', f'PID eq {p}'], capture_output=True, text=True, errors='replace')
    return str(p) in (r.stdout or '')


print(f"等核查进程 {PID} 退出...", flush=True)
t0 = time.time()
while alive(PID) and time.time() - t0 < 3600:
    time.sleep(30)
print(f"核查进程结束（等了 {(time.time()-t0)/60:.1f} 分钟）", flush=True)
time.sleep(5)

if not CHECK.exists():
    print("核查文件不存在，退出", flush=True)
    raise SystemExit(0)

check = json.loads(CHECK.read_text(encoding='utf-8'))
bad_qids = {r['qid'] for r in check if r['ok'] is False}
n_checked = len(check)
print(f"核查 {n_checked} 条 | 判定错归属 {len(bad_qids)} 条（{100*len(bad_qids)/max(1,n_checked):.0f}%）", flush=True)

moved = 0
per_subj = {}
for subj in ['数学', '语文', '英语']:
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if not (p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1):
            continue
        try:
            qs = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        keep, quar = [], []
        for q in qs:
            if q.get('qid') in bad_qids:
                q['_quarantine'] = {'reason': '册次不符（六年级下册内容混入上册）',
                                    'checked_by': 'check-xiace-content.py'}
                quar.append(q)
            else:
                keep.append(q)
        if quar:
            qf = QUAR / f"{subj}_{p.parent.name}_{p.stem}.quarantined.json"
            qf.write_text(json.dumps(quar, ensure_ascii=False, indent=2), encoding='utf-8')
            p.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding='utf-8')
            moved += len(quar)
            per_subj[subj] = per_subj.get(subj, 0) + len(quar)

print(f"隔离 {moved} 题 -> {QUAR}", flush=True)
print(f"按科目: {per_subj}", flush=True)

# 隔离后题库统计
tot = {}
for subj in ['数学', '语文', '英语']:
    n = 0
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1:
            try: n += len(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass
    tot[subj] = n
print(f"题库现状: {tot} = {sum(tot.values())}", flush=True)
