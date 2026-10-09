#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench-gw-concurrency.py — 测 new-api 网关（k3 / ds4.1）的并发极限

用户说"我们有五个 key，但上游本身不太稳定"——本测试逐级提升并发，
看网关在多少并发下开始大量 429/失败。
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

NEWAPI = 'http://127.0.0.1:13000/v1'


def load_env():
    env = {}
    p = Path(r'D:\hermes-data\.env')
    if p.exists():
        for line in p.read_text(encoding='utf-8', errors='replace').splitlines():
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return {**env, **os.environ}


ENV = load_env()
TOKEN = ENV.get('NEWAPI_CLIENT_TOKEN', '')
PROMPT = '你是六年级老师。只回 JSON：{"passed":true}\n题目：一个圆的直径是4厘米，求周长。'


def call(model):
    t0 = time.perf_counter()
    try:
        r = requests.post(f'{NEWAPI}/chat/completions',
                          headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
                          json={'model': model, 'max_tokens': 200,
                                'messages': [{'role': 'user', 'content': PROMPT}]}, timeout=120)
        return r.status_code, time.perf_counter() - t0
    except Exception:
        return -1, time.perf_counter() - t0


print("═══ new-api 网关并发极限（k3 / ds4.1）═══", flush=True)
for model in ['kimi-k3', 'deepseek-flash']:
    print(f"\n── {model} ──", flush=True)
    for conc in [2, 4, 8, 16]:
        n = conc
        t0 = time.perf_counter()
        with ThreadPoolExecutor(max_workers=conc) as ex:
            res = list(ex.map(lambda _: call(model), range(n)))
        dt = time.perf_counter() - t0
        from collections import Counter
        c = Counter(code for code, _ in res)
        ok = c.get(200, 0)
        avg = sum(d for _, d in res) / n
        print(f"  并发 {conc:>2}: 成功 {ok}/{n} | 总 {dt:.1f}s | 单请求均 {avg:.1f}s | 分布 {dict(c)}", flush=True)
        time.sleep(4)
