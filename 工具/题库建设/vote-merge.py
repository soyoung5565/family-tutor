#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-merge.py — 三票合并判定（kimi-k3 + deepseek + jev，2 票过则留）

用户规则（2026-09-24）：
  - 三个独立裁判：kimi-k3 / deepseek-v4.1-flash / jev
  - M3 不再投票（其判断已由第一层 self_review 承担）
  - **>=2 票通过 → 保留**；<2 → 剔除（进候选清单）

票来源：
  ① 题库内已有 vote_review（历史，含 MiniMax-M3 票 → 本节忽略 M3）
  ② _jev_scan_batched.jsonl（jev 分批扫描）
  ③ _vote_results_target.json（定向投票结果）

输出：
  _vote_merged.json     每题三票明细 + 最终判定
  _vote_verdict_stats.md  统计摘要
"""
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
JUDGES = ['kimi-k3', 'deepseek-flash', 'jev']      # M3 已排除


def load_questions():
    """题库全量"""
    out = {}
    for subj in ['数学', '语文', '英语']:
        for f in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
            if not (f.parent.name.startswith(('u', 'sp', 'r')) and f.stem.count('.') == 1):
                continue
            try:
                for q in json.loads(f.read_text(encoding='utf-8')):
                    if q.get('qid'):
                        out[q['qid']] = {'subject': subj, 'kp_id': q.get('kp_id'),
                                         'stem': str(q.get('stem', ''))[:80]}
            except Exception:
                pass
    return out


def norm_name(m):
    """归一化模型名"""
    m = (m or '').lower()
    if 'kimi' in m:
        return 'kimi-k3'
    if 'deepseek' in m:
        return 'deepseek-flash'
    if 'jev' in m:
        return 'jev'
    if 'minimax' in m or 'm3' in m:
        return 'MiniMax-M3'
    return m


def collect_votes():
    """收集全部票：{qid: {judge: passed_bool}} + legacy 历史票"""
    votes = defaultdict(dict)
    legacy = {}

    # ① 题库内 vote_review
    n_from_bank = 0
    for subj in ['数学', '语文', '英语']:
        for f in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
            if not (f.parent.name.startswith(('u', 'sp', 'r')) and f.stem.count('.') == 1):
                continue
            try:
                for q in json.loads(f.read_text(encoding='utf-8')):
                    qid = q.get('qid')
                    vr = q.get('vote_review')
                    if not qid or not vr:
                        continue
                    # 真实结构：passed/n_pass/n_total/models（无逐票明细）
                    models = [norm_name(m) for m in (vr.get('models') or [])]
                    judges_in = [m for m in models if m in JUDGES]
                    if not judges_in:
                        continue
                    # 可重建的只有"是否含 M3"与票数；M3 不参与新规则
                    # 记录为历史票（legacy），不强行拆成逐票
                    legacy[qid] = {'passed': bool(vr.get('passed')),
                                   'n_pass': vr.get('n_pass'), 'n_total': vr.get('n_total'),
                                   'models': models,
                                   'has_m3': any('minimax' in m.lower() or m == 'MiniMax-M3' for m in models),
                                   'judges': judges_in,
                                   'reviewed_at': vr.get('reviewed_at')}
                    n_from_bank += 1
            except Exception:
                pass

    # ② jev 分批扫描
    n_jev = 0
    jf = BASE / '_jev_scan_batched.jsonl'
    if jf.exists():
        for line in jf.read_text(encoding='utf-8', errors='replace').splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                if 'jev' in d:
                    votes[d['qid']]['jev'] = bool(d['jev'].get('passed'))
                    n_jev += 1
            except Exception:
                pass

    # ③ 定向投票结果
    n_target = 0
    for nm in ['_vote_results_target.json', '_vote_results_v4.json', '_vote_results_v3.json']:
        p = BASE / nm
        if not p.exists():
            continue
        try:
            data = json.loads(p.read_text(encoding='utf-8'))
            items = data if isinstance(data, list) else data.get('results', [])
            for r in items:
                qid = r.get('qid')
                if not qid:
                    continue
                for v in (r.get('votes') or []):
                    j = norm_name(v.get('model'))
                    if j in JUDGES and 'passed' in v:
                        votes[qid][j] = bool(v['passed'])
                        n_target += 1
        except Exception:
            pass

    return votes, legacy, n_from_bank, n_jev, n_target


def main():
    all_qs = load_questions()
    votes, legacy, n_bank, n_jev, n_target = collect_votes()

    print(f"题库 {len(all_qs)} 题")
    print(f"票来源: 题库内(legacy) {n_bank} | jev扫描 {n_jev} | 定向 {n_target}")
    has_m3 = sum(1 for d in legacy.values() if d['has_m3'])
    print(f"legacy 含 M3 的: {has_m3} / {n_bank}")
    print(f"有票的题: {len(votes)}")

    dist = Counter()
    verdicts = {}
    for qid in all_qs:
        v = votes.get(qid, {})
        n_pass = sum(1 for j in JUDGES if v.get(j) is True)
        n_vote = sum(1 for j in JUDGES if j in v)
        dist[f"{n_vote}票/{n_pass}过"] += 1
        if n_vote >= 2:
            verdicts[qid] = 'keep' if n_pass >= 2 else 'drop'
        elif n_vote == 1:
            verdicts[qid] = 'keep' if n_pass >= 1 else 'drop'    # 单票即终
        else:
            verdicts[qid] = 'pending'

    vdist = Counter(verdicts.values())
    print("\n═══ 票数分布 ═══")
    for k in sorted(dist, key=lambda x: (-int(x[0]), x)):
        print(f"   {k}: {dist[k]}")
    print("\n═══ 判定分布 ═══")
    for k in ['keep', 'drop', 'pending']:
        print(f"   {k}: {vdist.get(k, 0)}")

    # 输出
    out = {'rules': '三票(kimi-k3/deepseek-flash/jev) >=2 通过则留；M3 不投票',
           'judges': JUDGES,
           'verdicts': verdicts,
           'votes': {q: v for q, v in votes.items()},
           'legacy_vote_review': legacy}
    (BASE / '_vote_merged.json').write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f"\n输出: {BASE/'_vote_merged.json'}")

    # 摘要
    lines = ['# 投票合并判定摘要', '',
             f'- 规则: 三票({", ".join(JUDGES)}) ≥2 通过则留（M3 不投票）',
             f'- 题库: {len(all_qs)} 题', f'- 有票: {len(votes)} 题', '',
             '## 票数分布', '']
    for k in sorted(dist, key=lambda x: (-int(x[0]), x)):
        lines.append(f'- {k}: {dist[k]}')
    lines += ['', '## 判定分布', '']
    for k in ['keep', 'drop', 'pending']:
        lines.append(f'- {k}: {vdist.get(k, 0)}')
    (BASE / '_vote_verdict_stats.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f"输出: {BASE/'_vote_verdict_stats.md'}")


if __name__ == '__main__':
    main()
