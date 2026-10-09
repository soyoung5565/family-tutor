#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev-scan-all.py — jev 单票扫全库（并发 8，断点续传）

用户设计（2026-09-24）：
  ① jev 先扫全库拿态度（并发 8 实测 0.6s/题，全库 ~15 分钟）
  ② k3 + ds4.1 慢慢补（不着急）
  ③ 三票齐 → 2 票过则留

输出: _jev_scan_all.jsonl（每题一行，增量写；重跑自动跳过已处理的）
"""
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_jev_scan_all.jsonl'
NODE = r'D:\hermes-data\node\node.exe'
CLI_JS = r'D:\hermes-data\node\node_modules\command-code\dist\index.mjs'
WORKDIR = r'D:\hermes-data\node'


def load_questions():
    out = {}
    for subj in ['数学', '语文', '英语']:
        for f in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
            if not (f.parent.name.startswith(('u', 'sp', 'r')) and f.stem.count('.') == 1):
                continue
            try:
                for q in json.loads(f.read_text(encoding='utf-8')):
                    if q.get('qid'):
                        out[q['qid']] = q
            except Exception:
                pass
    return out


def load_kp_pools():
    pools = {}
    for subj in ['数学', '语文', '英语']:
        try:
            pools[subj] = json.loads(Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json')
                                     .read_text(encoding='utf-8'))
        except Exception:
            pools[subj] = {}
    return pools


def call_jev(state, questions, timeout=90, retries=3):
    """带限流退避重试"""
    prompt = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False)
    for attempt in range(retries):
        try:
            r = subprocess.run([NODE, CLI_JS, '-p', prompt, '-m', 'typesafe/jev',
                                '--output-format', 'json', '--skip-onboarding'],
                               capture_output=True, text=True, timeout=timeout, cwd=WORKDIR,
                               env={**os.environ, 'CI': '1'})
            out = (r.stdout or '') + (r.stderr or '')
            if 'Rate limit' in out:
                time.sleep(rotation_delay(attempt))     # 退避：1.5s, 3s, 6s
                continue
            if r.returncode != 0:
                return None, f'rc{r.returncode}'
            cand = [ln for ln in (r.stdout or '').strip().splitlines() if ln.startswith('{')]
            if not cand:
                return None, 'empty'
            return (json.loads(cand[-1]).get('answers') or None), None
        except Exception as e:
            time.sleep(rotation_delay(attempt))
            last = type(e).__name__
    return None, 'rate_limit'


def rotation_delay(attempt):
    import random
    return 1.5 * (2 ** attempt) + random.random()


def build_payload(q, kp_detail):
    stem = str(q.get('stem', ''))[:1200]
    opts = q.get('options') or []
    opt_txt = '\n'.join(f'{chr(65+i)}. {o}' for i, o in enumerate(opts[:6]))
    kp_name = kp_detail.get('name', '')
    kp_def = (kp_detail.get('definition') or '')[:300]
    state = {'subject': q.get('subject'), 'kp_id': q.get('kp_id'),
             'kp_name': kp_name, 'kp_definition': kp_def,
             'question': stem + (('\n' + opt_txt) if opt_txt else ''),
             'qtype': q.get('type', '')}
    questions = {
        'kp_match': {'type': 'noul', 'instructions': f'本题考点是否属于 KP「{kp_name}」？属则 yes。'},
        'out_of_scope': {'type': 'noul', 'instructions': '是否超纲（初中概念/超标词汇）？'},
        'stem_clear': {'type': 'noul', 'instructions': '题干是否清晰完整、无歧义？'},
        'age_ok': {'type': 'noul', 'instructions': '是否适合小学六年级？'},
        'difficulty': {'type': 'score', 'instructions': '难度', 'criteria': ['易', '中', '难']},
    }
    return state, questions


def jev_verdict(ans):
    if not ans:
        return None
    g = lambda k: (ans.get(k) or {})
    p_kp = g('kp_match').get('noul')
    p_scope = g('out_of_scope').get('noul')
    p_stem = g('stem_clear').get('noul')
    p_age = g('age_ok').get('noul')
    if None in (p_kp, p_scope, p_stem, p_age):
        return None
    passed = p_kp >= 0.5 and p_scope < 0.5 and p_stem >= 0.5 and p_age >= 0.5
    return {'passed': passed, 'kp_match': p_kp >= 0.5, 'out_of_scope': p_scope >= 0.5,
            'stem_clear': p_stem >= 0.5, 'age_appropriate': p_age >= 0.5,
            'difficulty_score': (g('difficulty') or {}).get('score'),
            'p': [round(p_kp, 3), round(p_scope, 3), round(p_stem, 3), round(p_age, 3)]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--limit', type=int)
    a = ap.parse_args()

    all_qs = load_questions()
    pools = load_kp_pools()
    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)['qid'])
                except Exception:
                    pass
    todo = [q for qid, q in all_qs.items() if qid not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(f"题库 {len(all_qs)} | 已完成 {len(done)} | 本次待扫 {len(todo)} | 并发 {a.workers}", flush=True)

    t0 = time.perf_counter()
    n_ok = n_fail = 0
    lock_lines = []

    def work(q):
        subj = q.get('subject', '语文')
        kp_detail = pools.get(subj, {}).get(q.get('kp_id', ''), {})
        state, questions = build_payload(q, kp_detail)
        ans, err = call_jev(state, questions)
        v = jev_verdict(ans)
        return q, v, err

    with open(OUT, 'a', encoding='utf-8') as fo:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = [ex.submit(work, q) for q in todo]
            for i, fut in enumerate(as_completed(futs), 1):
                q, v, err = fut.result()
                if v:
                    n_ok += 1
                    fo.write(json.dumps({'qid': q['qid'], 'subject': q.get('subject'),
                                         'kp_id': q.get('kp_id'), 'jev': v,
                                         'scanned_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
                                        ensure_ascii=False) + '\n')
                else:
                    n_fail += 1
                    fo.write(json.dumps({'qid': q['qid'], 'error': err or 'unknown'},
                                        ensure_ascii=False) + '\n')
                if i % 200 == 0:
                    fo.flush()
                    el = time.perf_counter() - t0
                    rate = i / el
                    eta = (len(todo) - i) / rate / 60 if rate else 0
                    print(f"  [{i}/{len(todo)}] ok={n_ok} fail={n_fail} | {rate:.1f} 题/s | ETA {eta:.1f} 分", flush=True)

    dt = time.perf_counter() - t0
    print(f"\n扫描完成: ok={n_ok} fail={n_fail} | {dt/60:.1f} 分钟 | {len(todo)/dt:.1f} 题/s")
    print(f"输出: {OUT}")


if __name__ == '__main__':
    main()
