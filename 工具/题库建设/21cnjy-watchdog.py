#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""21cnjy-watchdog.py - 独立兜底看门狗: 管线进程全部消失后, 校验 stats 并关机"""
import json, subprocess, time
from pathlib import Path
from datetime import datetime

BASE = Path(r'D:/家教/系统/scripts')
LOG = BASE / '_21cnjy_watchdog.log'


def log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')
        f.flush()


def pipeline_proc():
    try:
        import psutil
    except ImportError:
        return None
    try:
        for p in psutil.process_iter(['pid', 'cmdline']):
            try:
                cl = ' '.join(p.info.get('cmdline') or [])
            except Exception:
                continue
            if '21cnjy' in cl and ('run-21cnjy-pipeline' in cl or '21cnjy-ingest' in cl):
                return True
        return False
    except Exception:
        return None


def main():
    log('===== watchdog 启动 (独立兜底) =====')
    t0 = time.time()
    while time.time() - t0 < 8 * 3600:
        if pipeline_proc() is False:
            log('管线进程已全部消失')
            break
        time.sleep(60)
    log('等待 150s 让管线自己的关机先手...')
    time.sleep(150)
    try:
        stats = json.loads((BASE / '_21cnjy_merge_stats.json').read_text(encoding='utf-8'))
    except Exception:
        stats = {}
    ins = stats.get('inserted', 0) if isinstance(stats, dict) else 0
    rec = stats.get('records', 0) if isinstance(stats, dict) else 0
    log(f'stats: inserted={ins} records={rec}')
    if ins >= 150 and rec >= 150:
        log('校验通过 -> shutdown /s /t 120')
        try:
            r = subprocess.run(['shutdown', '/s', '/t', '120', '/c', '21cnjy done - auto shutdown'],
                               capture_output=True, text=True, encoding='gbk', errors='replace', timeout=30)
            log(f'shutdown rc={r.returncode} out={(r.stdout or "").strip()[:150]} err={(r.stderr or "").strip()[:200]}')
        except Exception as e:
            log(f'shutdown 异常: {e}')
    else:
        log('校验未通过 -> 不关机 (见 _21cnjy_ALERT.txt)')
    log('===== watchdog 结束 =====')


if __name__ == '__main__':
    main()
