#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench-gw-concurrency2.py — 重测网关并发（k3/ds 已按 3:2 分账户）

修正上一版缺陷：k3 与 ds 原先共享 5 把 key 的同一池额度，串行测时互相污染。
现在已拆开（k3→渠道13/14/15；ds→渠道12/18），可分别测出真实并发极限。
"""
import json
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

NEWAPI = 'http://127.0.0.1:13000/v1'
ENV = {}
for line in Path(r'D:\hermes-data\.env').read_text(encoding='utf-8', errors='replace').splitlines():
    if '=' in line and not line.strip().startswith('#'):
        k, v = line.split('=', 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")
TOKEN = ENV.get('NEWAPI_CLIENT_TOKEN', '')
PROMPT = '只回 JSON：{"ok":true}'


def call(model):
    t0 = time.perf_counter()
    try:
        r = requests.post(f'{NEWAPI}/chat/completions',
                          headers={'Authorization': f'Bearer {TOKEN}'},
                          json={'model': model, 'max_tokens': 50,
                                'messages': [{'role': 'user', 'content': PROMPT}]}, timeout=120)
        return r.status_code, time.perf_counter() - t0
    except Exception as e:
        return type(e).__name__, time.perf_counter() - t0


def test(model, conc, n=None):
    n = n or conc
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        res = list(ex.map(lambda _: call(model), range(n)))
    dt = time.perf_counter() - t0
    c = Counter(str(code) for code, _ in res)
    ok = c.get('200', 0)
    print(f"   并发 {conc:>2}: 成功 {ok}/{n} | 总 {dt:.1f}s | 单请求均 {dt/n:.1f}s | {dict(c)}", flush=True)
    return ok, n


print("═══ 网关并发极限（3:2 分账户后）═══", flush=True)
for model, levels in [('kimi-k3', [1, 2, 3, 6, 9]), ('deepseek-flash', [1, 2, 4, 6])]:
    print(f"\n── {model} ──", flush=True)
    for conc in levels:
        test(model, conc)
        time.sleep(8)
