#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""jev-scan-batched.py — jev 分批扫描（跨限流窗口自动调度）

背景（2026-09-24 实测）：
  jev 额度约 200~500 次/窗口，猛冲打满后要等几十分钟~几小时。
  所以本脚本：
    - 每批最多 BATCH 题（默认 150，低于实测打满阈值 200）
    - 一批跑完 → 探活；限流就等 COOLDOWN，恢复了继续
    - 断点续传（jsonl 增量），直到完成 TARGET 题或题库扫完
    - 全程无人值守（DETACH 启动不被会话回收）

用法:
  python jev-scan-batched.py --target 1000            # 抽样 1000 题
  python jev-scan-batched.py --target 0               # 全库（会跑很多天）
"""
import argparse
import json
import os
import random
import subprocess
import time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_jev_scan_batched.jsonl'
LOG = BASE / '_jev_scan_batched.log'
NODE = r'D:\hermes-data\node\node.exe'
CLI_JS = r'D:\hermes-data\node\node_modules\command-code\dist\index.mjs'
WORKDIR = r'D:\hermes-data\node'
BATCH = 150
COOLDOWN = 900          # 限流后等 15 分钟再探活


def log(m):
    line = f"[{time.strftime('%H:%M:%S')}] {m}"
    print(line, flush=True)
    with open(LOG, 'a', encoding='utf-8') as f:
        f.write(line + '\n')


def call_jev(state, questions, timeout=90):
    prompt = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False)
    try:
        r = subprocess.run([NODE, CLI_JS, '-p', prompt, '-m', 'typesafe/jev',
                            '--output-format', 'json', '--skip-onboarding'],
                           capture_output=True, text=True, timeout=timeout, cwd=WORKDIR,
                           env={**os.environ, 'CI': '1'})
        out = (r.stdout or '') + (r.stderr or '')
        if 'Rate limit' in out:
            return None, 'rate_limit'
        if r.returncode != 0:
            return None, f'rc{r.returncode}'
        cand = [ln for ln in (r.stdout or '').strip().splitlines() if ln.startswith('{')]
        if not cand:
            return None, 'empty'
        return (json.loads(cand[-1]).get('answers') or None), None
    except Exception as e:
        return None, type(e).__name__


def probe():
    """单次探活"""
    ans, err = call_jev('连通性测试：题干清晰吗？', {'ok': {'type': 'noul', 'instructions': '清晰吗？'}})
    return ans is not None


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
    ap.add_argument('--target', type=int, default=1000, help='目标题数（0=全库）')
    ap.add_argument('--batch', type=int, default=BATCH)
    a = ap.parse_args()

    all_qs = load_questions()
    pools = load_kp_pools()

    done = set()
    if OUT.exists():
        for line in OUT.read_text(encoding='utf-8', errors='replace').splitlines():
            if line.strip():
                try:
                    d = json.loads(line)
                    if 'jev' in d:
                        done.add(d['qid'])
                except Exception:
                    pass

    target = a.target if a.target else len(all_qs)
    log(f"=== jev 分批扫描启动 | 题库 {len(all_qs)} | 已完成 {len(done)} | 目标 {target} | 批大小 {a.batch} ===")

    round_no = 0
    while len(done) < target:
        round_no += 1
        todo = [q for qid, q in all_qs.items() if qid not in done]
        # 抽样：优先不同科目/来源，简单用随机
        random.shuffle(todo)
        batch = todo[:min(a.batch, target - len(done))]
        if not batch:
            log("无待扫题，结束")
            break

        log(f"第 {round_no} 轮：本批 {len(batch)} 题（已完成 {len(done)}/{target}）")
        n_ok = 0
        with open(OUT, 'a', encoding='utf-8') as fo:
            for i, q in enumerate(batch, 1):
                subj = q.get('subject', '语文')
                kp_detail = pools.get(subj, {}).get(q.get('kp_id', ''), {})
                state, questions = build_payload(q, kp_detail)
                ans, err = call_jev(state, questions)
                v = jev_verdict(ans)
                if v:
                    n_ok += 1
                    done.add(q['qid'])
                    fo.write(json.dumps({'qid': q['qid'], 'subject': q.get('subject'),
                                         'kp_id': q.get('kp_id'), 'jev': v,
                                         'scanned_at': time.strftime('%Y-%m-%dT%H:%M:%S')},
                                        ensure_ascii=False) + '\n')
                    fo.flush()
                elif err == 'rate_limit':
                    log(f"  第 {i} 题遇限流 → 本批结束（成功 {n_ok}）")
                    break
                time.sleep(0.3)

        log(f"第 {round_no} 轮结束：成功 {n_ok} | 累计 {len(done)}/{target}")

        if n_ok == 0:
            log(f"本批 0 成功 → 等待 {COOLDOWN//60} 分钟冷却再探活")
            time.sleep(COOLDOWN)
            while not probe():
                log(f"仍限流，再等 {COOLDOWN//60} 分钟")
                time.sleep(COOLDOWN)
            log("★ jev 恢复，继续下一批")

    log(f"=== 完成：{len(done)}/{target} | 输出 {OUT} ===")


if __name__ == '__main__':
    main()
