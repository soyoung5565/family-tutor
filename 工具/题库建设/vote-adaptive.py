#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-adaptive.py — 自适应并发投票（渐进加压找最稳最快的并发）

用户要求（2026-09-24）：
  "从 2 并行慢慢向上抬"，找"怎么样并发最稳最快"

策略：
  - 起点并发 2（下限 1，上限 12）
  - 每 WINDOW 题评估一次成功率：
      ≥90% → 并发 +1（探更高）
      <70% → 并发 -1（退回去）
      70~90% → 保持
  - 每档位记录吞吐（题/分钟），供后续选型
  - 状态写 _vote_adaptive_state.json（供心跳读取）

目标：kimi-k3 三票里的第 1 票（走网关 127.0.0.1:13000）
"""
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

BASE = Path(r'D:\家教\系统\scripts')
STATE = BASE / '_vote_adaptive_state.json'
LOG = BASE / '_vote_adaptive.log'
OUT = BASE / '_vote_adaptive_results.jsonl'
MODEL = 'kimi-k3'
WINDOW = 20
MIN_C, MAX_C = 1, 12

ENV = {}
for line in Path(r'D:\hermes-data\.env').read_text(encoding='utf-8', errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")
TOKEN = ENV.get('NEWAPI_CLIENT_TOKEN', '')


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def save_state(d):
    STATE.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')


def call(model=MODEL):
    """单次调用，返回 (code, elapsed)"""
    t0 = time.perf_counter()
    try:
        r = requests.post('http://127.0.0.1:13000/v1/chat/completions',
                          headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
                          json={'model': model, 'max_tokens': 30,
                                'messages': [{'role': 'user', 'content': '只回 JSON：{"ok":true}'}]},
                          timeout=120)
        return r.status_code, time.perf_counter() - t0
    except Exception as e:
        return type(e).__name__, time.perf_counter() - t0


def main():
    conc = 2
    perf = {}          # {并发: [成功数, 总数, 总耗时]}
    total_ok = total_n = 0
    t_start = time.perf_counter()
    log(f"=== 自适应并发测试启动 | 起点并发 {conc} | 范围 {MIN_C}-{MAX_C} | 窗口 {WINDOW} ===")

    while True:
        # 跑一个窗口
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=conc) as ex:
            res = list(ex.map(lambda _: call(), range(WINDOW)))
        dt = time.perf_counter() - t0
        ok = sum(1 for c, _ in res if c == 200)
        rate = ok / dt * 60 if dt else 0

        perf.setdefault(conc, [0, 0, 0.0])
        perf[conc][0] += ok
        perf[conc][1] += WINDOW
        perf[conc][2] += dt
        total_ok += ok
        total_n += WINDOW
        succ = ok / WINDOW

        log(f"并发 {conc:>2}: {ok}/{WINDOW} ({succ:.0%}) | {dt:.1f}s | {rate:.1f} 题/分")

        # 自适应调整
        old = conc
        if succ >= 0.90 and conc < MAX_C:
            conc += 1
            log(f"  成功率 {succ:.0%} ≥90% → 并发 {old}→{conc} ↑")
        elif succ < 0.70 and conc > MIN_C:
            conc -= 1
            log(f"  成功率 {succ:.0%} <70% → 并发 {old}→{conc} ↓")
        else:
            log(f"  成功率 {succ:.0%} → 保持并发 {conc}")

        # 存状态（供心跳读）
        save_state({
            'conc': conc, 'window': WINDOW,
            'total_ok': total_ok, 'total_n': total_n,
            'elapsed_min': (time.perf_counter() - t_start) / 60,
            'overall_rate': total_ok / (time.perf_counter() - t_start) * 60,
            'perf': {str(k): {'ok': v[0], 'n': v[1], 'rate': round(v[0] / v[2] * 60, 1) if v[2] else 0}
                     for k, v in perf.items()},
            'updated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        })
        time.sleep(3)


if __name__ == '__main__':
    main()
