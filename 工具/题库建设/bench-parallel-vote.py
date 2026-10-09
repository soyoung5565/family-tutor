#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bench-parallel-vote.py — 实测 3 LLM 并行 vs 串行（用真实调用方式）

M3   → api.minimaxi.com 直连（anthropic 格式）
其他 → new-api 网关（127.0.0.1:13000）
"""
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

NEWAPI_BASE = 'http://127.0.0.1:13000/v1'


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
PROMPT = '你是六年级数学教研组长。判断这道题是否合格（不超纲、题干清晰、符合六年级）。只回 JSON：{"passed":true,"kp_match":true,"out_of_scope":false,"stem_clear":true,"age_appropriate":true}\n题目：一个圆的直径是4厘米，它的周长是多少？'


def call_m3():
    t0 = time.perf_counter()
    try:
        r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
                          headers={'Authorization': f'Bearer {ENV.get("MINIMAX_CN_API_KEY","")}',
                                   'Content-Type': 'application/json',
                                   'anthropic-version': '2023-06-01'},
                          json={'model': 'MiniMax-M3', 'max_tokens': 800,
                                'messages': [{'role': 'user', 'content': PROMPT}]}, timeout=120)
        return 'MiniMax-M3', r.status_code, time.perf_counter() - t0
    except Exception as e:
        return 'MiniMax-M3', -1, time.perf_counter() - t0


def call_gw(model):
    t0 = time.perf_counter()
    try:
        r = requests.post(f'{NEWAPI_BASE}/chat/completions',
                          headers={'Authorization': f'Bearer {ENV.get("NEWAPI_CLIENT_TOKEN","")}',
                                   'Content-Type': 'application/json'},
                          json={'model': model, 'max_tokens': 800,
                                'messages': [{'role': 'user', 'content': PROMPT}]}, timeout=180)
        return model, r.status_code, time.perf_counter() - t0
    except Exception as e:
        return model, -1, time.perf_counter() - t0


print("═══ 并行：3 个同时发 ═══")
t0 = time.perf_counter()
with ThreadPoolExecutor(max_workers=3) as ex:
    futs = [ex.submit(call_m3)] + [ex.submit(call_gw, m) for m in ['kimi-k3', 'deepseek-flash']]
    res = [f.result() for f in futs]
par = time.perf_counter() - t0
for m, c, dt in res:
    print(f"   {m:<18} HTTP {c} ({dt:.1f}s)")
print(f"   并行总耗时: {par:.1f}s | 成功 {sum(1 for _,c,_ in res if c==200)}/3")

print("\n═══ 串行：逐个 + sleep 4s ═══")
t1 = time.perf_counter()
seq = [call_m3()] + [call_gw(m) for m in ['kimi-k3', 'deepseek-flash']]
for i, (m, c, dt) in enumerate(seq):
    print(f"   {m:<18} HTTP {c} ({dt:.1f}s)")
    if i < len(seq) - 1:
        time.sleep(4)
ser = time.perf_counter() - t1
print(f"   串行总耗时: {ser:.1f}s | 成功 {sum(1 for _,c,_ in seq if c==200)}/3")

print(f"\n═══ 对比 ═══")
print(f"  并行 {par:.1f}s vs 串行 {ser:.1f}s → 提速 {ser/par:.1f}x")
