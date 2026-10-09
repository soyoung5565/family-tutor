#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev-fill-missing.py — 只补 jev 票（不重跑 3 个 LLM）

场景：v4 文件里有些题已有 3 LLM 票但缺 jev（限流时期漏的）。
跑 vote-judge-v4 --targets 会重投 3 LLM（浪费 40 分钟）。
本脚本只调 jev，一题 ~4s。

用法:
  python jev-fill-missing.py                 # 补 _vote_results_v4.json 里所有缺 jev 的真实题
  python jev-fill-missing.py --dry-run       # 只统计
  python jev-fill-missing.py --writeback     # 补完自动写回题库
"""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
V4 = BASE / '_vote_results_v4.json'
NODE = r'D:\hermes-data\node\node.exe'
CLI_JS = r'D:\hermes-data\node\node_modules\command-code\dist\index.mjs'
NODE_WORKDIR = r'D:\hermes-data\node'


def call_jev(state, questions, timeout=90):
    prompt = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False)
    try:
        r = subprocess.run([NODE, CLI_JS, '-p', prompt, '-m', 'typesafe/jev',
                            '--output-format', 'json', '--skip-onboarding'],
                           capture_output=True, text=True, timeout=timeout, cwd=NODE_WORKDIR,
                           env={**os.environ, 'CI': '1'})
        if r.returncode != 0:
            return None
        cand = [ln for ln in (r.stdout or '').strip().splitlines() if ln.startswith('{')]
        if not cand:
            return None
        d = json.loads(cand[-1])
        return d.get('answers') or None
    except Exception:
        return None


def jev_verdict(ans):
    """答案 → 票（与 vote-judge-v4 同构）"""
    if not ans:
        return None
    q = ans.get('kp_match') or {}
    o = ans.get('out_of_scope') or {}
    s = ans.get('stem_clear') or {}
    a = ans.get('age_ok') or {}
    noul = lambda x: (x.get('noul') if isinstance(x, dict) else None)
    p_kp = noul(q); p_scope = noul(o); p_stem = noul(s); p_age = noul(a)
    if None in (p_kp, p_scope, p_stem, p_age):
        return None
    passed = p_kp >= 0.5 and p_scope < 0.5 and p_stem >= 0.5 and p_age >= 0.5
    return {'model': 'jev', 'model_label': 'jev', 'verdict': {
        'passed': passed, 'kp_match': p_kp >= 0.5, 'out_of_scope': p_scope >= 0.5,
        'stem_clear': p_stem >= 0.5, 'age_appropriate': p_age >= 0.5,
        'difficulty': (ans.get('difficulty') or {}).get('score'),
        'confidence': min(p_kp, p_stem, p_age) if passed else max(1 - p_kp, p_scope)}}


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


def apply_threshold(votes):
    n = len(votes)
    thr = n // 2 + 1
    npass = sum(1 for v in votes if (v.get('verdict') or {}).get('passed'))
    return n, npass, thr, npass >= thr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--limit', type=int)
    ap.add_argument('--writeback', action='store_true')
    a = ap.parse_args()

    d = json.loads(V4.read_text(encoding='utf-8'))
    todo = [r for r in d if not any(v.get('model') == 'jev' for v in (r.get('votes') or []))
            and 'ai_gen' not in str(r.get('qid'))]
    if a.limit:
        todo = todo[:a.limit]
    print(f"缺 jev 的真实题: {len(todo)} 条", flush=True)
    if a.dry_run or not todo:
        return

    all_qs = load_questions()
    pools = load_kp_pools()
    t0 = time.perf_counter()
    n_ok = 0
    for i, rec in enumerate(todo, 1):
        q = all_qs.get(rec['qid'])
        if not q:
            print(f"  [{i}] {rec['qid'][-40:]} 题不在库中，跳过")
            continue
        subj = q.get('subject', '语文')
        kp_detail = pools.get(subj, {}).get(q.get('kp_id', ''), {})
        state, questions = build_payload(q, kp_detail)
        ans = call_jev(state, questions)
        v = jev_verdict(ans)
        if not v:
            print(f"  [{i}] {rec['qid'][-40:]} jev 失败/空", flush=True)
            continue
        votes = [x for x in (rec.get('votes') or []) if x.get('model') != 'jev'] + [v]
        n_total, n_pass, thr, passed = apply_threshold(votes)
        rec['votes'] = votes
        rec['n_total'] = n_total
        rec['n_pass'] = n_pass
        rec['threshold'] = thr
        rec['passed_v4'] = passed
        n_ok += 1
        print(f"  [{i}/{len(todo)}] {rec['qid'][-42:]} jev={'OK' if v['verdict']['passed'] else 'X'} "
              f"→ {n_pass}/{n_total} {'PASS' if passed else 'x'}", flush=True)
        if i % 10 == 0:
            V4.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')

    V4.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    dt = time.perf_counter() - t0
    print(f"\n完成: {n_ok}/{len(todo)} 补上 jev 票 | {dt/60:.1f} 分钟")

    if a.writeback:
        for script in ['writeback-vote-v4.py']:
            print(f"→ 跑 {script}", flush=True)
            r = subprocess.run([r'D:/Python312/python.exe', script], cwd=str(BASE),
                               capture_output=True, text=True, errors='replace', timeout=900)
            print("  " + (r.stdout or '').strip()[-400:], flush=True)


if __name__ == '__main__':
    main()
