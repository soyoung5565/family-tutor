#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-monitor.py — 三投票状态一览（供心跳每轮调用）

盯三个票：
  ① kimi-k3（网关 127.0.0.1:13000）
  ② deepseek-flash（网关）
  ③ jev（commandcode Node CLI）

输出简明状态，供心跳判断"是否在推进"。
"""
import json, sqlite3, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')


def procs(pat):
    r = subprocess.run(['powershell', '-NoProfile', '-Command',
        f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{pat}*' }} | ForEach-Object {{ $_.ProcessId }}"],
        capture_output=True, text=True, timeout=60)
    return [p.strip() for p in (r.stdout or '').split() if p.strip().isdigit()]


def tail(p, n=3):
    p = Path(p)
    if not p.exists():
        return []
    ls = [l for l in p.read_text(encoding='utf-8', errors='replace').strip().splitlines() if l.strip()]
    return ls[-n:]


out = {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'votes': {}}

# ① 速率探测（k3）
out['votes']['k3_rate_probe'] = {
    'running': bool(procs('rate-probe')),
    'log': tail(BASE/'_rate_probe.log', 4),
}
sf = BASE/'_rate_probe_state.json'
if sf.exists():
    try:
        out['votes']['k3_rate_probe']['results'] = json.loads(sf.read_text(encoding='utf-8')).get('results')
    except Exception:
        pass

# ② jev 扫描
out['votes']['jev_scan'] = {
    'running': bool(procs('jev-scan-batched')),
    'log': tail(BASE/'_jev_scan_batched.log', 3),
}
jf = BASE/'_jev_scan_batched.jsonl'
if jf.exists():
    lines = [l for l in jf.read_text(encoding='utf-8', errors='replace').splitlines() if l.strip()]
    out['votes']['jev_scan']['collected'] = sum(1 for l in lines if '"jev"' in l)

# ③ 网关渠道状态
try:
    conn = sqlite3.connect(r'D:\new-api\one-api.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, name, status FROM channels WHERE id IN (12,13,14,15,18)")
    out['votes']['channels'] = {f"{r['id']}:{r['name']}": r['status'] for r in cur.fetchall()}
    cur.execute("""SELECT channel_id, model_name, COUNT(*) c FROM logs
                   WHERE created_at >= strftime('%s','now') - 600
                   GROUP BY channel_id, model_name""")
    out['votes']['recent_10min'] = [f"ch{r['channel_id']} {r['model_name']} x{r['c']}" for r in cur.fetchall()]
    conn.close()
except Exception as e:
    out['votes']['channels'] = f'err {e}'

# ④ 票数统计
mf = BASE/'_vote_merged.json'
if mf.exists():
    try:
        d = json.loads(mf.read_text(encoding='utf-8'))
        v = d.get('verdicts', {})
        from collections import Counter
        out['votes']['verdicts'] = dict(Counter(v.values()))
    except Exception:
        pass

print(json.dumps(out, ensure_ascii=False, indent=1))
