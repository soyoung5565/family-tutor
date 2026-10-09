#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run-21cnjy-pipeline.py — 启动 3 worker → 等完 → merge → 校验 → 关机（看门狗）
日志: _21cnjy_pipeline.log
"""
import json, subprocess, time
from pathlib import Path
from datetime import datetime

BASE = Path(r'D:/家教/系统/scripts')
PY = r'D:/Python312/python.exe'
LOG = BASE / '_21cnjy_pipeline.log'
N_WORKERS = 4
MAX_ROUNDS = 3


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def start_worker(w):
    lf = open(BASE / f'_21cnjy_w{w}.log', 'a', encoding='utf-8')
    lf.write(f"\n===== round start {datetime.now().isoformat()} =====\n")
    lf.flush()
    return subprocess.Popen([PY, str(BASE / '21cnjy-ingest.py'), str(w), str(N_WORKERS)],
                            stdout=lf, stderr=subprocess.STDOUT, cwd=str(BASE))


def main():
    log(f'===== 21cnjy 入库管线启动 (workers={N_WORKERS}) =====')
    for rnd in range(1, MAX_ROUNDS + 1):
        procs = [start_worker(w) for w in range(N_WORKERS)]
        log(f'round {rnd}: workers pids={[p.pid for p in procs]}')
        rcs = [p.wait() for p in procs]
        log(f'round {rnd}: rcs={rcs}')
        r = subprocess.run([PY, str(BASE / '21cnjy-ingest.py'), '0', str(N_WORKERS), '--status'],
                           capture_output=True, text=True, cwd=str(BASE), timeout=180)
        log(f'status: {(r.stdout or "").strip()[-300:]}')
        if 'REMAIN=0' in (r.stdout or ''):
            break
        time.sleep(30)

    log('workers 结束，开始 merge...')
    r = subprocess.run([PY, str(BASE / '21cnjy-merge.py')], capture_output=True, text=True,
                       cwd=str(BASE), timeout=1800)
    log(f'merge rc={r.returncode}')
    log('merge out:\n' + (r.stdout or '')[-4000:])
    if r.stderr:
        log('merge stderr:\n' + r.stderr[-1500:])

    try:
        stats = json.loads((BASE / '_21cnjy_merge_stats.json').read_text(encoding='utf-8'))
    except Exception as e:
        stats = {'error': str(e)}
    log(f'stats: {json.dumps(stats, ensure_ascii=False)}')

    ok = stats.get('inserted', 0) >= 150 and stats.get('records', 0) >= 150
    if ok:
        log('校验通过 → 300 秒后关机')
        try:
            r2 = subprocess.run(['shutdown', '/s', '/t', '300', '/c', '21cnjy ingest done. Auto shutdown in 5 min. Run shutdown /a to cancel.'],
                                capture_output=True, text=True, timeout=20)
            log(f'shutdown rc={r2.returncode} err={r2.stderr[:200]}')
        except Exception as e:
            log(f'shutdown 调用异常: {e}')
    else:
        log('校验未通过 → 不关机！留下 _21cnjy_ALERT.txt')
        (BASE / '_21cnjy_ALERT.txt').write_text(
            f"21cnjy 管线完成但校验未通过（{datetime.now().isoformat()}）\n"
            f"stats: {json.dumps(stats, ensure_ascii=False, indent=2)}\n请人工检查。\n",
            encoding='utf-8')
    log('===== 管线结束 =====')


if __name__ == '__main__':
    main()
