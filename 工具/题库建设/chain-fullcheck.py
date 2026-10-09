#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""chain-fullcheck.py — 等下册核查+隔离完成 → 启动全库册次核查"""
import subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
PY = r'D:\Python312\python.exe'
GUARD_PID = 12740   # quarantine-xiace.py

def alive(p):
    r = subprocess.run(['tasklist', '/FI', f'PID eq {p}'], capture_output=True, text=True, errors='replace')
    return str(p) in (r.stdout or '')

print(f"等隔离守护 {GUARD_PID} 完成...", flush=True)
t0 = time.time()
while alive(GUARD_PID) and time.time() - t0 < 3600:
    time.sleep(30)
print(f"隔离守护结束（{(time.time()-t0)/60:.1f} 分钟）", flush=True)
time.sleep(10)

print("启动全库册次核查...", flush=True)
lf = open(BASE / '_xiace_check_all.log', 'w', encoding='utf-8')
proc = subprocess.Popen([PY, str(BASE / 'check-xiace-content.py'), '--all'],
                        stdout=lf, stderr=subprocess.STDOUT, cwd=str(BASE),
                        creationflags=0x00000008 | 0x00000200)
print(f"全库核查 pid={proc.pid}", flush=True)
