#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""投票完成后处理 + 写报告（不关机版本）"""
import json, time, subprocess, sys
from pathlib import Path
from datetime import datetime

VOTE_RESULTS = Path(r'D:\家教\系统\scripts\_vote_results_v3.json')
REPORT = Path(r'D:\家教\系统\scripts\_final_report.md')

def wait_vote_done():
    print("等 vote-judge-v3 跑完...", flush=True)
    while True:
        r = subprocess.run(['powershell','-NoProfile','-Command',
            'Get-CimInstance Win32_Process -Filter "Name=\'python.exe\'" | Where-Object {$_.CommandLine -match "vote-judge-v3"} | Measure-Object | Select-Object -ExpandProperty Count'],
            capture_output=True, text=True, timeout=15)
        try:
            n = int(r.stdout.strip())
        except:
            n = 0
        if n == 0:
            print("vote 进程已退出", flush=True)
            break
        time.sleep(60)

def apply_results():
    results = json.loads(VOTE_RESULTS.read_text(encoding='utf-8'))
    print(f"应用 {len(results)} 条投票结果", flush=True)
    
    votes_by_qid = {r['qid']: r for r in results}
    n_marked_pass = 0
    n_marked_fail = 0
    
    for subj in ['数学','语文','英语']:
        base = Path(f'D:/家教/{subj}/测验')
        for p in sorted(base.rglob('*.json')):
            if p.parent.name.startswith(('u','sp','r')) and p.stem.count('.')==1:
                try:
                    qs = json.loads(p.read_text(encoding='utf-8'))
                    changed = False
                    for q in qs:
                        qid = q.get('qid')
                        if qid in votes_by_qid:
                            r = votes_by_qid[qid]
                            q['vote_review'] = {
                                'passed': r['passed'],
                                'n_pass': r['n_pass'],
                                'n_total': r['n_total'],
                                'difficulty_votes': [v['verdict'].get('difficulty') for v in r['votes']],
                                'reviewed_at': datetime.now().isoformat(),
                                'reviewer': 'vote-judge-v3',
                            }
                            if r['passed']: n_marked_pass += 1
                            else: n_marked_fail += 1
                            changed = True
                    if changed:
                        p.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
                except Exception as e:
                    print(f"err {p}: {e}", flush=True)
    
    return n_marked_pass, n_marked_fail

def gen_report(n_pass, n_fail):
    results = json.loads(VOTE_RESULTS.read_text(encoding='utf-8'))
    
    by_subj_unit = {}
    for r in results:
        key = (r['subject'], r['unit_id'])
        if key not in by_subj_unit:
            by_subj_unit[key] = {'pass': 0, 'fail': 0}
        if r['passed']: by_subj_unit[key]['pass'] += 1
        else: by_subj_unit[key]['fail'] += 1
    
    inv = {}
    grand_total = 0
    for subj in ['数学','语文','英语']:
        base = Path(f'D:/家教/{subj}/测验')
        all_qids = set()
        for p in sorted(base.rglob('*.json')):
            if p.parent.name.startswith(('u','sp','r')) and p.stem.count('.')==1:
                try:
                    qs = json.loads(p.read_text(encoding='utf-8'))
                    for q in qs:
                        if q.get('qid'): all_qids.add(q['qid'])
                except: pass
        inv[subj] = len(all_qids)
        grand_total += len(all_qids)
    
    md = f"""# 家庭教师题库投票筛选报告

**生成时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 📊 题库总量

| 科目 | 题数 |
|---|---|
| 数学 | {inv['数学']} |
| 语文 | {inv['语文']} |
| 英语 | {inv['英语']} |
| **总计** | **{grand_total}** |

## 🗳 投票结果

| 项 | 数 |
|---|---|
| 已投票 | {len(results)} |
| 通过 | {n_pass} |
| 否决 | {n_fail} |
| 通过率 | {100*n_pass/max(1,n_pass+n_fail):.1f}% |

## 按单元通过率

| 科目/单元 | 通过 | 否决 | 通过率 |
|---|---|---|---|
"""
    for (subj, u) in sorted(by_subj_unit.keys()):
        s = by_subj_unit[(subj, u)]
        total = s['pass'] + s['fail']
        rate = 100*s['pass']/total if total else 0
        md += f"| {subj}/{u} | {s['pass']} | {s['fail']} | {rate:.0f}% |\n"
    
    ai = [r for r in results if r.get('ai_generated')]
    ai_pass = sum(1 for r in ai if r['passed'])
    md += f"""
## AI 生成题通过率

- AI 生成：{len(ai)} 题
- 通过：{ai_pass} 题（{100*ai_pass/max(1,len(ai)):.0f}%）

## 投票规则

- 3 模型：MiniMax-M3 / kimi-k3 / deepseek-v4-pro
- 通过阈值：1票听1票，2票要2票，3票要2票多数
- 只看题目质量（KP 匹配 + 不超纲 + 题干清晰 + 适合六年级），不评答案解析
"""
    
    REPORT.write_text(md, encoding='utf-8')
    print(f"报告: {REPORT}", flush=True)

if __name__ == '__main__':
    wait_vote_done()
    print("\n开始应用投票结果...", flush=True)
    n_pass, n_fail = apply_results()
    print(f"标记: 通过 {n_pass}, 否决 {n_fail}", flush=True)
    print("\n生成报告...", flush=True)
    gen_report(n_pass, n_fail)
    print("\n完成（不关机）", flush=True)
