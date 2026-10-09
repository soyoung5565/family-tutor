#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gap3-pipeline.py — 专项补漏全流程：等搜索 → 合并 → 抓取 → 提取 → 入库"""
import json, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
PY = r'D:\Python312\python.exe'
SEARCH_PID = 30968


def run(script, timeout=2400):
    print(f"--- {script} ---", flush=True)
    r = subprocess.run([PY, str(BASE / script)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=str(BASE), timeout=timeout)
    print((r.stdout or '')[-1200:], flush=True)
    return r.stdout or ''


def alive(p):
    r = subprocess.run(['tasklist', '/FI', f'PID eq {p}'], capture_output=True, text=True, errors='replace')
    return str(p) in (r.stdout or '')


print(f"等搜索进程 {SEARCH_PID}...", flush=True)
t0 = time.time()
while alive(SEARCH_PID) and time.time() - t0 < 900:
    time.sleep(20)
print(f"搜索结束（{(time.time()-t0)/60:.1f} 分钟）", flush=True)

run('merge-gap3.py')
run('21cnjy-crawl.py')
run('51jiaoxi-crawl.py')

# 提取：4 个 21cnjy worker + 1 个教习网 worker
print("--- 启动提取 worker ---", flush=True)
procs = []
for w in range(4):
    lf = open(BASE / f'_21cnjy_w{w}.log', 'a', encoding='utf-8')
    lf.write(f"\n===== gap3 {time.strftime('%H:%M:%S')} =====\n"); lf.flush()
    procs.append(subprocess.Popen([PY, str(BASE / '21cnjy-ingest.py'), str(w), '4'],
                                  stdout=lf, stderr=subprocess.STDOUT, cwd=str(BASE)))
lf2 = open(BASE / '_51jiaoxi_w0.log', 'a', encoding='utf-8')
lf2.write(f"\n===== gap3 {time.strftime('%H:%M:%S')} =====\n"); lf2.flush()
procs.append(subprocess.Popen([PY, str(BASE / '51jiaoxi-ingest.py'), '0', '1'],
                              stdout=lf2, stderr=subprocess.STDOUT, cwd=str(BASE)))
print(f"worker pids: {[p.pid for p in procs]}", flush=True)
for p in procs:
    p.wait()
print("提取全部完成", flush=True)

run('51jiaoxi-merge.py')
run('21cnjy-merge.py')

tot = {}
for subj in ['数学', '语文', '英语']:
    n = 0
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1:
            try: n += len(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass
    tot[subj] = n
print(f"\n[结果] 题库: {tot} = {sum(tot.values())}", flush=True)
