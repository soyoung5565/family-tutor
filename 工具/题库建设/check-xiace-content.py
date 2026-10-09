#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check-xiace-content.py — 核查「下册来源」题的内容是否真属于上册范围（只出清单，不改题库）"""
import json, sys, time, requests
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_xiace_check.json'

env = {}
for line in open('D:/hermes-data/.env', encoding='utf-8'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k] = v.split('#')[0].strip()
KEY = env['MINIMAX_CN_API_KEY']


def ask(stem, kp_id, kp_name, title):
    prompt = f"""你是小学六年级教研员。判断这道题的内容是否**适合放在「六年级上册」的题库**里。

【题目】{stem[:300]}

【被归属到的知识点】{kp_id} {kp_name}

【出处标题（可能不可靠）】{title[:80]}

【判定规则】
1. **通用知识点**（字词、拼音、成语、计算、解方程、统计图、修辞手法、句型变换等）——无论在哪个册次出现，都算适合（ok=true）。
2. **课文内容题**：只有当题目考的是**六年级上册**的课文才适合。若考的是六年级下册课文（如《学弈》《两小儿辩日》《为人民服务》《匆匆》《腊八粥》《那个星期天》《表里的生物》□注：《表里的生物》是上册）或初中内容，判 ok=false。
3. 不确定时判 ok=true（宁可保留）。

只输出严格 JSON：{{"ok": true|false, "reason": "15字内"}}"""
    try:
        r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
            headers={'X-Api-Key': KEY, 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
            json={'model': 'MiniMax-M3', 'max_tokens': 600, 'temperature': 0.1,
                  'messages': [{'role': 'user', 'content': prompt}]}, timeout=120)
        if r.status_code != 200:
            return None
        txt = ''.join(b.get('text', '') for b in (r.json().get('content') or []) if isinstance(b, dict))
        import re as _re
        m = _re.search(r'\{.*\}', txt, _re.DOTALL)
        if not m:
            return None
        return json.loads(m.group(0))
    except Exception:
        return None


# 收集待核查题：默认只查「下册」来源（高风险）；--all 则查全库
ALL_MODE = '--all' in sys.argv
targets = []
for subj in ['语文', '数学', '英语']:
    for pth in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if not (pth.parent.name.startswith(('u', 'sp', 'r')) and pth.stem.count('.') == 1):
            continue
        try:
            qs = json.loads(pth.read_text(encoding='utf-8'))
        except Exception:
            continue
        for q in qs:
            s = q.get('source') or {}
            if ALL_MODE:
                targets.append({'subj': subj, 'qid': q['qid'], 'kp': q.get('kp_id'),
                                'stem': q.get('stem', ''), 'title': s.get('title', ''),
                                'file': str(pth)})
            elif s.get('suspect') and '下册' in (s.get('suspect_reason') or ''):
                targets.append({'subj': subj, 'qid': q['qid'], 'kp': q.get('kp_id'),
                                'stem': q.get('stem', ''), 'title': s.get('title', ''),
                                'file': str(pth)})
print(f"模式: {'全库' if ALL_MODE else '下册来源'} | 待核查 {len(targets)}", flush=True)

print(f"待核查「下册」来源题: {len(targets)}", flush=True)
results = []
if OUT.exists():
    try:
        results = json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        results = []
done = {r['qid'] for r in results}

bad = 0
for i, t in enumerate(targets, 1):
    if t['qid'] in done:
        continue
    a = ask(t['stem'], t['kp'], '', t['title'])
    rec = {**t, 'ok': (a or {}).get('ok', True), 'reason': (a or {}).get('reason', 'check_failed')}
    results.append(rec)
    if rec['ok'] is False:
        bad += 1
        print(f"  [{i}/{len(targets)}] ✗ {t['qid'][-34:]} {rec['reason']} | {t['stem'][:50]}", flush=True)
    if i % 20 == 0:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"    ckpt {i} | 疑似错归属 {bad}", flush=True)
    time.sleep(1.2)

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
n_bad = sum(1 for r in results if r['ok'] is False)
print(f"\n核查完成: {len(results)} 条 | 疑似错归属（下册内容混入上册）: {n_bad}", flush=True)
