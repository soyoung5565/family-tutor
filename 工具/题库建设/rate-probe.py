#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""rate-probe.py — 令牌桶限速探测（找"最稳最快"的可持续速率）

用户要求：从 2 并行慢慢向上抬，找最稳最快的点。
实测发现：瓶颈是"请求速率配额"（窗口内 ~40 请求打满），不是并发。
所以改成：固定低并发 + 令牌桶控制速率，逐档抬速率，找可持续上限。
"""
import json, time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

BASE = Path(r'D:\家教\系统\scripts')
LOG = BASE / '_rate_probe.log'
STATE = BASE / '_rate_probe_state.json'

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


class TokenBucket:
    """每分钟 rate 个令牌；bust 允许短时突发"""
    def __init__(self, rate, burst=3):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last = time.perf_counter()

    def acquire(self):
        while True:
            now = time.perf_counter()
            self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate / 60.0)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            time.sleep(0.2)

    def set_rate(self, r):
        self.rate = r


def call():
    t0 = time.perf_counter()
    try:
        r = requests.post('http://127.0.0.1:13000/v1/chat/completions',
                          headers={'Authorization': f'Bearer {TOKEN}'},
                          json={'model': 'kimi-k3', 'max_tokens': 20,
                                'messages': [{'role': 'user', 'content': '回OK'}]}, timeout=60)
        return r.status_code, time.perf_counter() - t0
    except Exception as e:
        return type(e).__name__, time.perf_counter() - t0


def main():
    rates = [6, 10, 15, 20, 30, 45]
    results = {}
    log(f"=== 令牌桶速率探测启动 | 档位 {rates} 请求/分 | 每档 30 请求 ===")
    for rate in rates:
        bucket = TokenBucket(rate)
        ok = 0
        n = 30
        times = []
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = []
            for _ in range(n):
                bucket.acquire()
                futs.append(ex.submit(call))
            for f in futs:
                code, dt = f.result()
                if code == 200:
                    ok += 1
                times.append(dt)
        dt_total = time.perf_counter() - t0
        succ = ok / n
        results[rate] = {'ok': ok, 'n': n, 'succ': round(succ, 3),
                         'elapsed': round(dt_total, 1),
                         'actual_rate': round(ok / dt_total * 60, 1) if dt_total else 0}
        log(f"限速 {rate:>2}/分: {ok}/{n} ({succ:.0%}) | 实际用时 {dt_total:.1f}s | 实际速率 {results[rate]['actual_rate']} 请求/分")
        STATE.write_text(json.dumps({'results': results, 'updated': time.strftime('%Y-%m-%dT%H:%M:%S')},
                                    ensure_ascii=False, indent=1), encoding='utf-8')
        if succ < 0.7:
            log(f"  成功率 {succ:.0%} <70% → 这就是上限附近，停止抬升")
            break
        time.sleep(30)     # 档位间休息
    log("=== 探测结束 ===")
    log(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
