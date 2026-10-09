#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round3b-pipeline.py — 第三轮全流程：等抓取 → 提取 → merge → postclean"""
import json, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
PY = r'D:\Python312\python.exe'
CRAWL_PIDS = [21844, 32200]     # 21cnjy-crawl-b + 51jiaoxi-crawl


def run(script, timeout=2400):
    print(f"--- {script} ---", flush=True)
    r = subprocess.run([PY, str(BASE / script)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=str(BASE), timeout=timeout)
    print((r.stdout or '')[-1000:], flush=True)
    return r.stdout or ''


def alive(p):
    r = subprocess.run(['tasklist', '/FI', f'PID eq {p}'], capture_output=True, text=True, errors='replace')
    return str(p) in (r.stdout or '')


print(f"等抓取进程 {CRAWL_PIDS}...", flush=True)
t0 = time.time()
while time.time() - t0 < 1800:
    if not any(alive(p) for p in CRAWL_PIDS):
        break
    time.sleep(20)
print(f"抓取结束（{(time.time()-t0)/60:.1f} 分钟）", flush=True)

print("--- 启动提取 ---", flush=True)
procs = []
for w in range(4):
    lf = open(BASE / f'_21cnjy_w{w}.log', 'a', encoding='utf-8')
    lf.write(f"\n===== round3b {time.strftime('%H:%M:%S')} =====\n"); lf.flush()
    procs.append(subprocess.Popen([PY, str(BASE / '21cnjy-ingest.py'), str(w), '4'],
                                  stdout=lf, stderr=subprocess.STDOUT, cwd=str(BASE)))
lf2 = open(BASE / '_51jiaoxi_w0.log', 'a', encoding='utf-8')
lf2.write(f"\n===== round3b {time.strftime('%H:%M:%S')} =====\n"); lf2.flush()
procs.append(subprocess.Popen([PY, str(BASE / '51jiaoxi-ingest.py'), '0', '1'],
                              stdout=lf2, stderr=subprocess.STDOUT, cwd=str(BASE)))
print(f"worker pids: {[p.pid for p in procs]}", flush=True)
for p in procs:
    p.wait()
print("提取完成", flush=True)

run('51jiaoxi-merge.py')
run('21cnjy-merge.py')

print("--- postclean（隔离错年级，必须放 merge 之后）---", flush=True)
run('postclean.py')

tot = {}
for subj in ['数学', '语文', '英语']:
    n = 0
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1:
            try: n += len(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass
    tot[subj] = n
print(f"\n[结果] 题库: {tot} = {sum(tot.values())}", flush=True)
