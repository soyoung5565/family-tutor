#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench-direct-vs-gateway.py — 直连 sensenova vs 走 new-api 网关

直连: https://token.sensenova.cn/v1/chat/completions + 5 把 key 轮换
网关: http://127.0.0.1:13000/v1/chat/completions + NEWAPI_CLIENT_TOKEN

目的: 判断网关是否额外限流（今天的"并发 2 就崩"有多少是网关造成的）
"""
import json, sqlite3, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

BASE = 'https://token.sensenova.cn'
PROMPT = '只回 JSON：{"ok":true}'


def load_keys():
    conn = sqlite3.connect(r'D:\new-api\one-api.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, name, key FROM channels WHERE id IN (12,13,14,15,18) ORDER BY id")
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


def load_token():
    for line in Path(r'D:\hermes-data\.env').read_text(encoding='utf-8', errors='replace').splitlines():
        if line.startswith('NEWAPI_CLIENT_TOKEN'):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    return ''


KEYS = load_keys()
TOKEN = load_token()


def call_direct(model, idx=0):
    key = KEYS[idx % len(KEYS)]['key']
    t0 = time.perf_counter()
    try:
        r = requests.post(f'{BASE}/v1/chat/completions',
                          headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
                          json={'model': model, 'max_tokens': 20,
                                'messages': [{'role': 'user', 'content': PROMPT}]}, timeout=90)
        return r.status_code, time.perf_counter() - t0
    except Exception as e:
        return type(e).__name__, time.perf_counter() - t0


def call_gw(model):
    t0 = time.perf_counter()
    try:
        r = requests.post('http://127.0.0.1:13000/v1/chat/completions',
                          headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
                          json={'model': model, 'max_tokens': 20,
                                'messages': [{'role': 'user', 'content': PROMPT}]}, timeout=90)
        return r.status_code, time.perf_counter() - t0
    except Exception as e:
        return type(e).__name__, time.perf_counter() - t0


def run(label, fn, conc, n=None):
    n = n or conc
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=conc) as ex:
        res = list(ex.map(lambda i: fn(i), range(n)))
    dt = time.perf_counter() - t0
    c = Counter(str(code) for code, _ in res)
    print(f"   {label} 并发{conc:>2}: 成功 {c.get('200',0)}/{n} | 总 {dt:.1f}s | {dict(c)}", flush=True)
    return c.get('200', 0)


print("═══ 直连 sensenova（5 把 key 轮换）═══", flush=True)
for model in ['kimi-k3', 'deepseek-flash']:
    print(f"\n── {model}（直连）──", flush=True)
    for conc in [1, 2, 4, 8]:
        run('直连', lambda i, m=model: call_direct(m, i), conc)
        time.sleep(6)

print("\n\n═══ 走 new-api 网关（对照）═══", flush=True)
for model in ['kimi-k3']:
    print(f"\n── {model}（网关）──", flush=True)
    for conc in [1, 2, 4]:
        run('网关', lambda i, m=model: call_gw(m), conc)
        time.sleep(6)
