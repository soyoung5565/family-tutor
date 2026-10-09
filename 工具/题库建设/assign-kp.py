#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""assign-kp.py — 对题库已有题目做真正的 KP 归属"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

CLASH = 'http://127.0.0.1:7897'


def load_env():
    env = {}
    for p in [r'D:\hermes-data\.env', r'/d/hermes-data/.env']:
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.split('#')[0].strip()
            return env
    raise FileNotFoundError('.env not found')


def call_muse(prompt, max_tokens=4000):
    r = requests.post('https://opencode.ai/zen/v1/responses',
        headers={'User-Agent':'opencode/0.20.5','X-Session-ID':str(uuid.uuid4()),
                 'HTTP-Referer':'https://opencode.ai/','X-Title':'opencode','Content-Type':'application/json'},
        json={'model':'muse-spark-1.3-contributor-free',
              'input':[{'role':'user','content':[{'type':'input_text','text':prompt}]}],
              'max_output_tokens':max_tokens,'reasoning':{'effort':'medium'}},
        proxies={'http':CLASH,'https':CLASH}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f'Muse HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    texts=[c['text'] for i in j.get('output',[]) if i.get('type')=='message' for c in i.get('content',[]) if c.get('type')=='output_text']
    return '\n'.join(texts)


def call_minimax(prompt, env, max_tokens=1500):
    r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
        headers={'Authorization': f'Bearer {env["MINIMAX_CN_API_KEY"]}', 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
        json={'model':'MiniMax-M3','max_tokens':max_tokens,'messages':[{'role':'user','content':prompt}]},
        timeout=240)
    if r.status_code != 200:
        raise RuntimeError(f'MiniMax HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    for b in j.get('content', []):
        if b.get('type') == 'text':
            return b['text']
    return ''


def build_prompt(q, kp_pool):
    lines = []
    for kp_id, info in kp_pool.items():
        lines.append(f"- {kp_id} [{info['unit_name']}] {info['name']}: {info['definition'][:80]}")
    kp_text = '\n'.join(lines)
    opts = q.get('options') or []
    opts_text = ' | '.join(opts) if opts else '(无选项)'
    head = '你是深圳六年级老师，判断下面这道题考查的核心知识点属于哪个 KP。\n\n'
    qpart = (f"【题目】\n题干：{q.get('stem','')}\n选项：{opts_text}\n答案：{q.get('answer')}\n解析：{q.get('explanation','')}\n\n"
             f"【候选 KP 列表】\n{kp_text}\n\n")
    tail = ('【任务】\n1. 选出最匹配的 1 个 KP 编号（严格来自列表）。\n2. 难度：易 / 中 / 难。\n'
            '3. 匹配理由（30 字内）。\n4. also_covers：最多 2 个其他 KP 编号（没有则空数组）。\n\n'
            '【输出】（严格 JSON）\n{"kp_id": "u2.k6", "difficulty": "中", "reason": "...", "also_covers": []}')
    return head + qpart + tail


def extract_json(text):
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            return None
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', required=True, choices=['数学','语文','英语'])
    ap.add_argument('--kp-file', help='只处理某个 KP（如 u1.k1）')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--model', default='muse', choices=['muse','minimax'])
    ap.add_argument('--base-dir', default=None)
    args = ap.parse_args()

    base_dir = Path(args.base_dir) if args.base_dir else None
    if not base_dir:
        for c in [Path('D:/家教'), Path('/d/家教')]:
            if c.exists():
                base_dir = c; break
    subj_dir = base_dir / args.subject
    kp_dir = subj_dir / '知识点及掌握情况'
    pool_file = kp_dir / '_kp_pool.json'

    if not pool_file.exists():
        kp_index = json.load(open(kp_dir/'index.json', encoding='utf-8'))
        pool = {}
        for u in kp_index['units']:
            for kp_id in u['kp_ids']:
                p = kp_dir / f'{kp_id}.json'
                if p.exists():
                    d = json.load(open(p, encoding='utf-8'))
                    pool[kp_id] = {'unit': u['id'],'unit_name': u.get('name',''),
                                   'name': d.get('name',''),'definition': d.get('definition','')}
        pool_file.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'构建 KP 池: {len(pool)} 个')
    kp_pool = json.load(open(pool_file, encoding='utf-8'))

    quiz_dir = subj_dir / '测验'
    if not quiz_dir.exists():
        print('题库不存在')
        return

    all_q = []
    for kp_file in quiz_dir.rglob('*.json'):
        if kp_file.name in ('index.json', '_meta.json') or kp_file.parent.name in ('by-type','_meta'):
            continue
        kp_id = kp_file.stem
        if args.kp_file and kp_id != args.kp_file:
            continue
        qs = json.loads(kp_file.read_text(encoding='utf-8'))
        for q in qs:
            all_q.append((kp_id, kp_file, q))

    print(f'共 {len(all_q)} 道题待归属（model={args.model}）')

    env = load_env() if args.model == 'minimax' else None
    caller = (lambda p: call_minimax(p, env)) if args.model == 'minimax' else call_muse

    moves = []
    for i, (old_kp, kp_file, q) in enumerate(all_q, 1):
        stem = q.get('stem','')[:40]
        print(f'[{i:3d}/{len(all_q)}] {old_kp} | {stem}...', end=' ', flush=True)
        try:
            prompt = build_prompt(q, kp_pool)
            text = caller(prompt)
            r = extract_json(text)
            if not r or 'kp_id' not in r:
                print('ERR 解析失败')
                continue
            new_kp = r['kp_id']
            if new_kp not in kp_pool:
                print(f'ERR 无效 KP: {new_kp}')
                continue
            changed = (new_kp != old_kp)
            mark = '->' if changed else '=='
            print(f'{mark} {new_kp} [{r.get("difficulty")}] {r.get("reason","")[:30]}')
            moves.append({'old_kp': old_kp, 'new_kp': new_kp,
                          'question': q, 'result': r, 'changed': changed})
        except Exception as e:
            print(f'ERR: {str(e)[:60]}')
        time.sleep(2)

    changed = [m for m in moves if m['changed']]
    print(f'\n=== 归属报告 ===')
    print(f'总题数: {len(all_q)}')
    print(f'判定成功: {len(moves)}')
    print(f'KP 变动: {len(changed)}')

    if args.dry_run:
        out = Path(f'D:/家教/{args.subject}/测验/_meta/assign-kp-dry-run.json')
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(moves, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'dry-run 已存 {out}')
        return

    if changed:
        by_old = {}
        for m in changed:
            by_old.setdefault(m['old_kp'], []).append(m)
        by_new = {}
        for m in changed:
            by_new.setdefault(m['new_kp'], []).append(m)

        for old_kp, ms in by_old.items():
            kp_file = quiz_dir / (old_kp.split('.')[0]) / f'{old_kp}.json'
            if not kp_file.exists():
                continue
            qs = json.loads(kp_file.read_text(encoding='utf-8'))
            move_qids = {m['question']['qid'] for m in ms}
            qs = [q for q in qs if q['qid'] not in move_qids]
            kp_file.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')

        for new_kp, ms in by_new.items():
            unit_id = new_kp.split('.')[0]
            unit_dir = quiz_dir / unit_id
            unit_dir.mkdir(parents=True, exist_ok=True)
            kp_file = unit_dir / f'{new_kp}.json'
            qs = []
            if kp_file.exists():
                qs = json.loads(kp_file.read_text(encoding='utf-8'))
            for m in ms:
                q = dict(m['question'])
                q['kp_id'] = new_kp
                q['unit_id'] = unit_id
                q['difficulty'] = m['result'].get('difficulty', q.get('difficulty','中'))
                if m['result'].get('also_covers'):
                    q.setdefault('cross_version', {})['also_covers'] = m['result']['also_covers']
                q.setdefault('self_review', {})['kp_match'] = True
                q['self_review']['kp_match_reason'] = m['result'].get('reason','')
                q['self_review']['reviewed_by'] = f'assign-kp.py ({args.model})'
                q['self_review']['reviewed_at'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
                if q['qid'] not in {x['qid'] for x in qs}:
                    qs.append(q)
            kp_file.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')

        print(f'已应用 {len(changed)} 个 KP 变动')

    report = Path(f'D:/家教/{args.subject}/测验/_meta/assign-kp-report.json')
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({
        'at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'model': args.model,
        'total': len(all_q),
        'judged': len(moves),
        'changed': len(changed),
        'moves': moves,
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'报告: {report}')


if __name__ == '__main__':
    main()
