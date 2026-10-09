#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench-jev-concurrency.py — 测 jev 的并发极限（找触发 429 的并发度）

jev 调用 = Node CLI 子进程（~1-2s 冷启 + ~2s API）。
本测试逐级提升并发度，记录成功率与耗时，找出 429 出现的阈值。
"""
import json
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

NODE = r'D:\hermes-data\node\node.exe'
CLI_JS = r'D:\hermes-data\node\node_modules\command-code\dist\index.mjs'
WORKDIR = r'D:\hermes-data\node'


def one_call(idx):
    prompt = json.dumps({'state': f'测试第 {idx} 题：一个圆的直径是4厘米，求周长。',
                         'questions': {'ok': {'type': 'noul', 'instructions': '题干清晰吗？'}}},
                        ensure_ascii=False)
    t0 = time.perf_counter()
    try:
        r = subprocess.run([NODE, CLI_JS, '-p', prompt, '-m', 'typesafe/jev',
                            '--output-format', 'json', '--skip-onboarding'],
                           capture_output=True, text=True, timeout=120, cwd=WORKDIR,
                           env={**os.environ, 'CI': '1'})
        dt = time.perf_counter() - t0
        out = (r.stdout or '') + (r.stderr or '')
        if 'Rate limit' in out:
            return 'RATE_LIMIT', dt
        if r.returncode == 0 and '"answers"' in (r.stdout or ''):
            return 'OK', dt
        return f'ERR({r.returncode})', dt
    except subprocess.TimeoutExpired:
        return 'TIMEOUT', time.perf_counter() - t0
    except Exception as e:
        return f'EXC({type(e).__name__})', time.perf_counter() - t0


print("═══ jev 并发极限测试 ═══")
for conc in [1, 2, 4, 8]:
    n = conc * 2      # 每个并发度跑 2 轮
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        res = list(ex.map(one_call, range(n)))
    dt = time.perf_counter() - t0
    from collections import Counter
    c = Counter(r[0] for r in res)
    ok = c.get('OK', 0)
    per = dt / n
    print(f"  并发 {conc:>2}: {n} 请求 | 成功 {ok}/{n} | 总 {dt:.1f}s | 单请求均 {per:.1f}s | 分布 {dict(c)}")
    if c.get('RATE_LIMIT', 0) > 0:
        print(f"      ↑ 并发 {conc} 已触发限流")
    time.sleep(3)
