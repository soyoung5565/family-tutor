#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""postclean.py — 入库后规则化核查：隔离错年级 + 标记听力/下册内容。
用法: python postclean.py [--quiet]
必须放在每次 merge 之后跑（否则 merge 会把隔离题重新加回来）。
"""
import json, re, sys, shutil
from pathlib import Path
from collections import Counter

BASE = Path(r'D:\家教\系统\scripts')
QUAR = Path(r'D:\家教\_meta\quarantine_more')
QUAR.mkdir(parents=True, exist_ok=True)
QUIET = '--quiet' in sys.argv

BAD_GRADE = ['一年级','二年级','三年级','四年级','五年级','七年级','八年级','九年级',
             '初一','初二','初三','中考','高考','高中']
LISTEN = re.compile(r'听录音|听力|听音|listen and|听到的|听句子|听对话|听短文')
XIA_WORKS = ['北京的春节','腊八粥','藏戏','匆匆','那个星期天','学弈','两小儿辩日',
             '真理诞生于一百个问号之后','十六年前的回忆','为人民服务','马诗','石灰吟',
             '竹石','鲁滨逊漂流记','骑鹅旅行记','汤姆·索亚历险记','董存瑞','采薇',
             '春夜喜雨','江畔独步寻花','早春呈水部张十八员外','依依惜别']

n_quar = n_listen = n_xia = 0
detail = Counter()
for subj in ['数学', '语文', '英语']:
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if not (p.parent.name.startswith(('u','sp','r')) and p.stem.count('.') == 1):
            continue
        try:
            qs = json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        keep, quar = [], []
        changed = False
        for q in qs:
            title = (q.get('source') or {}).get('title', '')
            stem = str(q.get('stem', ''))
            hard = [k for k in BAD_GRADE if k in title]
            if hard:
                q['_quarantine'] = {'reason': '错年级:' + ','.join(hard), 'title': title[:80]}
                quar.append(q); n_quar += 1; changed = True
                for k in hard: detail[k] += 1
                continue
            if LISTEN.search(stem):
                if not q.get('suspect_no_audio'):
                    q['suspect_no_audio'] = True; n_listen += 1; changed = True
            hits = [w for w in XIA_WORKS if w in stem]
            if hits and not q.get('suspect_xiace_content'):
                q['suspect_xiace_content'] = hits[:2]; n_xia += 1; changed = True
            keep.append(q)
        if changed:
            if quar:
                qf = QUAR / f"{subj}_{p.parent.name}_{p.stem}.quarantined.json"
                old = json.loads(qf.read_text(encoding='utf-8')) if qf.exists() else []
                qf.write_text(json.dumps(old + quar, ensure_ascii=False, indent=2), encoding='utf-8')
            p.write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding='utf-8')

tot = 0
for subj in ['数学', '语文', '英语']:
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if p.parent.name.startswith(('u','sp','r')) and p.stem.count('.') == 1:
            try: tot += len(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass

print(f"[postclean] 隔离错年级 {n_quar} | 标记听力 {n_listen} | 标记下册 {n_xia}")
print(f"[postclean] 隔离明细: {dict(detail)}")
print(f"[postclean] 题库: {tot}")
