#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""writeback-vote-v4.py — 把 _vote_results_v4.json 写回题库每题 vote_review 字段 + 出对比报告"""
import json
from pathlib import Path
from datetime import datetime
from collections import Counter

BASE = Path(r'D:\家教\系统\scripts')
V4F = BASE / '_vote_results_v4.json'
V3F = BASE / '_vote_results_v3.json'
REP = BASE / '_vote_v4_report.md'

v4 = json.loads(V4F.read_text(encoding='utf-8'))
v3 = json.loads(V3F.read_text(encoding='utf-8'))
by_qid = {r['qid']: r for r in v4}

# ---- 1) 写回题库 ----
n_written = 0
for subj in ['数学', '语文', '英语']:
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if not (p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1):
            continue
        try:
            qs = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        changed = False
        for q in qs:
            r = by_qid.get(q.get('qid'))
            if not r:
                continue
            q['vote_review'] = {
                'version': 'v4',
                'passed': r.get('passed_v4', r.get('passed')),
                'v3_passed': r.get('passed_v3_orig'),
                'n_pass': r.get('n_pass'),
                'n_total': r.get('n_total'),
                'threshold': r.get('threshold'),
                'models': [v.get('model') for v in r.get('votes', [])],
                'difficulties': [(v.get('verdict') or {}).get('difficulty') for v in r.get('votes', [])],
                'reviewed_at': datetime.now().isoformat(),
            }
            changed = True
            n_written += 1
        if changed:
            p.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"写回题库: {n_written} 题")

# ---- 2) 对比报告 ----
rows = []
for r in v4:
    vs = r.get('votes', [])
    jev = next((v for v in vs if v.get('model') == 'jev'), None)
    llm = [v for v in vs if v.get('model') != 'jev']
    llm_pass = sum(1 for v in llm if (v.get('verdict') or {}).get('passed'))
    rows.append({
        'qid': r['qid'], 'subject': r.get('subject', '?'),
        'n_llm': len(llm), 'llm_pass': llm_pass,
        'llm_pass_all': (len(llm) > 0 and llm_pass == len(llm)),
        'llm_pass_none': (llm_pass == 0),
        'jev_pass': bool(jev and (jev.get('verdict') or {}).get('passed')),
        'has_jev': jev is not None,
        'v3': r.get('passed_v3_orig'), 'v4': r.get('passed_v4', r.get('passed')),
        'n_total': r.get('n_total'), 'n_pass': r.get('n_pass'), 'threshold': r.get('threshold'),
    })

md = ['# v4 投票报告（3 LLM + jev 第 4 票）', '', f'生成: {datetime.now().strftime("%Y-%m-%d %H:%M")}', '']
md.append(f'- v3 条目: {len(v3)} | v4 条目: {len(v4)}')
with_jev = [x for x in rows if x['has_jev']]
md.append(f'- 成功补上 jev 票: {len(with_jev)} | 未补到: {len(rows)-len(with_jev)}')
md.append('')

for tag, sel in [('全部', rows), ('语文', [x for x in rows if x['subject'] == '语文']),
                 ('数学', [x for x in rows if x['subject'] == '数学']),
                 ('英语', [x for x in rows if x['subject'] == '英语'])]:
    if not sel:
        continue
    v3p = sum(1 for x in sel if x['v3'])
    v4p = sum(1 for x in sel if x['v4'])
    md.append(f'## {tag}（{len(sel)} 题）')
    md.append('')
    md.append(f'- v3 通过: **{v3p}** ({100*v3p/len(sel):.1f}%)')
    md.append(f'- v4 通过: **{v4p}** ({100*v4p/len(sel):.1f}%)')
    changed_in = sum(1 for x in sel if x['v3'] != x['v4'])
    md.append(f'- 判定翻转: {changed_in} 题（{sum(1 for x in sel if not x["v3"] and x["v4"])} 拒→过 / {sum(1 for x in sel if x["v3"] and not x["v4"])} 过→拒）')
    md.append('')

# jev 与 LLM 共识的分歧
with_jev_l = [x for x in with_jev]
d1 = [x for x in with_jev_l if x['llm_pass_all'] and not x['jev_pass']]
d2 = [x for x in with_jev_l if x['llm_pass_none'] and x['jev_pass']]
d3 = [x for x in with_jev_l if x['llm_pass_all'] and x['jev_pass']]
d4 = [x for x in with_jev_l if x['llm_pass_none'] and not x['jev_pass']]
md.append('## jev 与 3 LLM 的一致性')
md.append('')
md.append(f'- LLM 全票通过 & jev 通过: **{len(d3)}**')
md.append(f'- LLM 全票通过 & jev 否决: **{len(d1)}** ← jev 拦下的')
md.append(f'- LLM 全票否决 & jev 通过: **{len(d2)}** ← jev 捞回的')
md.append(f'- LLM 全票否决 & jev 否决: **{len(d4)}**')
md.append('')
md.append('## 附：jev 与 3 LLM 票型分布')
pc = Counter((x['llm_pass'], x['jev_pass']) for x in with_jev_l)
for (a, b), c in sorted(pc.items()):
    md.append(f'- LLM {a}票过 / jev {"过" if b else "否"}: {c}')

REP.write_text('\n'.join(md), encoding='utf-8')
print("报告:", REP)
print('\n'.join(md[:40]))
