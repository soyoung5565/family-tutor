#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-fill.py — 正式补票（k3 + ds 双通道，令牌桶 15 请求/分）

依据 2026-09-24 22:00 实测速率曲线：
  6/10/15 请求每分 = 100% 成功；20 = 80%（实际更慢）；30 = 53%
  → 取 15 请求/分/通道 为"最稳最快"点

两通道：
  kimi-k3 走 127.0.0.1:13000（渠道 13/14/15，3 账户）
  deepseek-flash 走同网关（渠道 12/18，2 账户）

输出：_vote_new.jsonl（逐票，含 model/qid/passed/verdict）
      可断点续跑
"""
import json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests

BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_vote_new.jsonl'
LOG = BASE / '_vote_fill.log'
STATE = BASE / '_vote_fill_state.json'
RATE = 15          # 请求/分/通道
CONC = 4
MODELS = ['kimi-k3', 'deepseek-flash']

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


class Bucket:
    def __init__(self, rate, burst=2):
        self.rate, self.burst, self.tokens, self.last = rate, burst, burst, time.perf_counter()

    def acquire(self):
        while True:
            now = time.perf_counter()
            self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate / 60.0)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return
            time.sleep(0.1)


PROMPT = ('你是小学教师，判断题目质量。只回 JSON，格式：{"kp_match":true,"out_of_scope":false,'
          '"stem_clear":true,"age_appropriate":true,"passed":true}\n题目：')


def call(model, q):
    try:
        r = requests.post('http://127.0.0.1:13000/v1/chat/completions',
                          headers={'Authorization': f'Bearer {TOKEN}'},
                          json={'model': model, 'max_tokens': 120,
                                'messages': [{'role': 'user', 'content': PROMPT + q[:800]}]}, timeout=120)
        if r.status_code != 200:
            return None, r.status_code
        txt = r.json()['choices'][0]['message']['content']
        import re
        m = re.search(r'\{[^{}]*\}', txt)
        if not m:
            return None, 'nojson'
        v = json.loads(m.group(0))
        return v, None
    except Exception as e:
        return None, type(e).__name__


def load_qs():
    out = {}
    for subj in ['数学', '语文', '英语']:
        for f in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
            if not (f.parent.name.startswith(('u', 'sp', 'r')) and f.stem.count('.') == 1):
                continue
            try:
                for q in json.loads(f.read_text(encoding='utf-8')):
                    if q.get('qid') and q.get('stem'):
                        out[q['qid']] = (q.get('subject', subj), str(q['stem']))
            except Exception:
                pass
    return out


def main():
    qs = load_qs()
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.strip():
                try:
                    d = json.loads(line)
                    done.add((d['qid'], d['model']))
                except Exception:
                    pass
    log(f"=== 补票启动 | 题库 {len(qs)} | 已有票 {len(done)} | 限速 {RATE}/分/通道 | 并发 {CONC} ===")

    buckets = {m: Bucket(RATE) for m in MODELS}
    ok_n = fail_n = 0
    t0 = time.perf_counter()

    # 双通道真并行：k3 与 ds 各一个线程池，各自独立令牌桶
    import threading
    lock = threading.Lock()

    def run_channel(model, fo):
        nonlocal ok_n, fail_n
        todo = [(qid, s) for qid, (subj, s) in qs.items() if (qid, model) not in done]
        log(f"── {model}: 待投票 {len(todo)} 题（并行通道）──")
        b = buckets[model]
        my_ok = my_fail = 0

        def work(item):
            qid, stem = item
            b.acquire()
            v, err = call(model, stem)
            return qid, v, err

        with ThreadPoolExecutor(max_workers=CONC) as ex:
            for i, (qid, v, err) in enumerate(ex.map(work, todo), 1):
                if v is not None:
                    my_ok += 1
                    with lock:
                        fo.write(json.dumps({'qid': qid, 'model': model, 'verdict': v,
                                             'passed': bool(v.get('passed')),
                                             'ts': time.strftime('%Y-%m-%dT%H:%M:%S')},
                                            ensure_ascii=False) + '\n')
                else:
                    my_fail += 1
                if i % 100 == 0:
                    with lock:
                        fo.flush()
                        ok_n += 0  # 仅统计推进
                    el = time.perf_counter() - t0
                    log(f"  {model} [{i}/{len(todo)}] ok={my_ok} fail={my_fail} | {my_ok/(el/60):.1f} 票/分")
        with lock:
            ok_n += my_ok
            fail_n += my_fail
        log(f"── {model} 通道结束: ok={my_ok} fail={my_fail} ──")

    with open(OUT, 'a', encoding='utf-8') as fo:
        ths = [threading.Thread(target=run_channel, args=(m, fo), daemon=False) for m in MODELS]
        for th in ths:
            th.start()
        while any(th.is_alive() for th in ths):
            time.sleep(30)
            el = time.perf_counter() - t0
            STATE.write_text(json.dumps({'ok': ok_n, 'fail': fail_n,
                                         'elapsed_min': round(el/60, 1),
                                         'rate': round(ok_n/(el/60), 1) if el else 0,
                                         'updated': time.strftime('%Y-%m-%dT%H:%M:%S')},
                                        ensure_ascii=False, indent=1), encoding='utf-8')
    log(f"=== 补票完成: ok={ok_n} fail={fail_n} | {(time.perf_counter()-t0)/60:.1f} 分钟 ===")


if __name__ == '__main__':
    main()
