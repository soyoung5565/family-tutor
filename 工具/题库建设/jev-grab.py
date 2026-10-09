#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev-grab.py — 抢占 jev 免费额度（探活成功就调现成脚本批量打票+写回）

修复记录：
- 不再 import vote-judge-v4（其顶层 ENV = load_env() 会在 import 时崩溃）
- 探活间隔 20 分钟（避免自己刷新限流窗口）
"""
import json, os, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
NODE = r'D:\hermes-data\node\node.exe'
CLI_JS = r'D:\hermes-data\node\node_modules\command-code\dist\index.mjs'
NODE_WORKDIR = r'D:\hermes-data\node'
PY = r'D:\Python312\python.exe'
LOG = BASE / '_jev_grab.log'
PROBE_GAP = 1200      # 20 分钟
MAX_HOURS = 30        # 最长守候 30 小时（覆盖免费期最后一天）


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def jev_alive():
    prompt = json.dumps({"state": "测试题干是否清晰：选出没有错别字的一项",
                         "questions": {"ok": {"type": "noul", "instructions": "题干清晰吗？"}}}, ensure_ascii=False)
    try:
        r = subprocess.run([NODE, CLI_JS, '-p', prompt, '-m', 'typesafe/jev',
                            '--output-format', 'json', '--skip-onboarding'],
                           capture_output=True, text=True, timeout=120, cwd=NODE_WORKDIR,
                           env={**os.environ, 'CI': '1'})
        out = (r.stdout or '') + (r.stderr or '')
        if 'Rate limit' in out:
            return False
        return r.returncode == 0 and '"answers"' in (r.stdout or '')
    except Exception as e:
        log(f"探活异常: {type(e).__name__}")
        return False


def run(cmd, tag, timeout=7200):
    log(f"→ 跑 {tag}")
    try:
        r = subprocess.run(cmd, cwd=str(BASE), timeout=timeout, capture_output=True, text=True,
                           errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'CI': '1'})
        log(f"   {tag} rc={r.returncode}")
        if r.returncode != 0:
            log(f"   stderr: {(r.stderr or '')[-300:]}")
        return r.returncode == 0
    except subprocess.TimeoutExpired:
        log(f"   {tag} 超时")
        return False


log("=== jev 抢占启动（间隔 20 分钟，最长 30 小时）===")
deadline = time.time() + MAX_HOURS * 3600
rounds = 0

while time.time() < deadline:
    rounds += 1
    if jev_alive():
        log("★ jev 恢复可用！开始批量打票")
        ok1 = run([PY, 'vote-judge-v4.py', '--jev-only'], 'v4 补票')
        if ok1:
            run([PY, 'writeback-vote-v4.py'], '写回 v4')
        ok2 = run([PY, 'vote-newbatch.py'], '新批次补票')
        if ok2:
            run([PY, 'writeback-vote.py', '_vote_results_newbatch.json'], '写回新批次')
        log("本轮打票+写回完成")
        # 继续守着，万一还有剩余额度
        time.sleep(PROBE_GAP)
    else:
        if rounds % 5 == 1:
            log(f"jev 仍限流（第 {rounds} 次探活），继续等")
        time.sleep(PROBE_GAP)

log("=== jev 抢占结束（到期或完成）===")
