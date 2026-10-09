#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zxxk-merge-v4.py — 合并 zxxk v4 worker JSONL → 题库 + 索引 + 报告 + stats"""
import json, re
from pathlib import Path
from datetime import datetime

BASE = Path(r'D:/家教/系统/scripts')
STATS_F = BASE / '_zxxk_v4_merge_stats.json'
REPORT_F = BASE / '_zxxk_v4_report.md'


def main():
    records = []
    for f in sorted(BASE.glob('_zxxk_v4_ingest_w*.jsonl')):
        for line in f.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                pass
    by_id = {}
    for r in records:
        by_id[r['id']] = r
    records = list(by_id.values())
    print(f'读取 {len(records)} 页记录')

    by_subj = {}
    n_ok = n_noq = 0
    for r in records:
        if r.get('status') == 'ok':
            by_subj.setdefault(r['subject'], []).extend(r.get('questions', []))
            n_ok += 1
        else:
            n_noq += 1

    now = datetime.now().isoformat()
    total_inserted = 0
    per_kp = {}
    ins_by_subj = {}
    final_counts = {}
    for subj, qs in sorted(by_subj.items()):
        subj_dir = Path(f'D:/家教/{subj}')
        ins = 0
        for q in qs:
            kp_id = q['kp_id']
            unit_dir = subj_dir / '测验' / q['unit_id']
            unit_dir.mkdir(parents=True, exist_ok=True)
            kp_file = unit_dir / f'{kp_id}.json'
            existing = []
            if kp_file.exists():
                existing = json.loads(kp_file.read_text(encoding='utf-8'))
            if q['qid'] in {x.get('qid') for x in existing}:
                continue
            existing.append(q)
            kp_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
            ins += 1
            per_kp[kp_id] = per_kp.get(kp_id, 0) + 1
        total_inserted += ins
        ins_by_subj[subj] = ins

        index_file = subj_dir / '测验' / 'index.json'
        index = json.loads(index_file.read_text(encoding='utf-8')) if index_file.exists() else {}
        total = 0
        cov = {}
        for p in sorted((subj_dir / '测验').rglob('*.json')):
            if p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1:
                try:
                    qs_data = json.loads(p.read_text(encoding='utf-8'))
                    total += len(qs_data)
                    cov[p.stem] = {'total': len(qs_data)}
                except Exception:
                    pass
        index['total_questions'] = total
        index['kp_coverage'] = cov
        index['last_updated'] = now
        index.setdefault('source_distribution', {})
        index['source_distribution']['学科网'] = index['source_distribution'].get('学科网', 0) + ins
        index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        final_counts[subj] = total
        print(f'{subj}: 新入库 {ins}, 总题数 {total}')

    targets = json.loads((BASE / '_kp_targets.json').read_text(encoding='utf-8'))
    rows = []
    n_zero_before = n_zero_after = 0
    for subj, kps in targets.items():
        for kp in kps:
            kp_id = kp['kp_id']
            unit_id = kp_id.split('.')[0]
            f = Path(f'D:/家教/{subj}/测验/{unit_id}/{kp_id}.json')
            cur = 0
            if f.exists():
                try:
                    cur = len(json.loads(f.read_text(encoding='utf-8')))
                except Exception:
                    cur = 0
            old = kp.get('current', 0)
            new = per_kp.get(kp_id, 0)
            if old == 0:
                n_zero_before += 1
                if cur > 0:
                    n_zero_after += 1
            rows.append((subj, kp_id, kp.get('name', ''), old, new, cur))

    md = []
    md.append('# zxxk(学科网) v4 扩搜素材入库报告')
    md.append('')
    md.append(f'**生成时间**：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    md.append('')
    md.append('## 总览')
    md.append('')
    md.append('- 候选：**53** 份（116 筛后）| 抓到 SVG 文本 26 份')
    md.append(f'- 处理页数：{len(records)}（有题 {n_ok} 页 / 无题 {n_noq} 页）')
    md.append(f'- 新入库：**{total_inserted}** 题')
    for subj in sorted(final_counts):
        md.append(f'  - {subj}：本次 +{ins_by_subj.get(subj, 0)}，现总 {final_counts.get(subj, 0)} 题')
    md.append('')
    md.append('## 弱 KP 覆盖（目标 73 个）')
    md.append('')
    md.append('| 科目 | KP | 名称 | 原题数 | 本次新增 | 现题数 |')
    md.append('|---|---|---|---|---|---|')
    for subj, kp_id, name, old, new, cur in rows:
        flag = ' 🆕' if old == 0 and cur > 0 else ''
        md.append(f'| {subj} | {kp_id} | {name[:24]}{flag} | {old} | +{new} | {cur} |')
    md.append('')
    md.append(f'**原 0 题 KP：{n_zero_before} 个 → 现有题：{n_zero_after} 个（{n_zero_after} 个破零）**')
    md.append('')

    errs = []
    for f in sorted(BASE.glob('_zxxk_v4_errors_w*.json')):
        try:
            errs.extend(json.loads(f.read_text(encoding='utf-8')))
        except Exception:
            pass
    if errs:
        md.append('## 失败页面')
        md.append('')
        for e in errs[:40]:
            md.append(f"- {e.get('id')} {e.get('title', '')[:40]}")
        md.append('')

    stats = {'records': len(records), 'ok_pages': n_ok, 'noq_pages': n_noq,
             'inserted': total_inserted, 'ins_by_subj': ins_by_subj,
             'zero_before': n_zero_before, 'zero_after': n_zero_after,
             'errors': len(errs), 'generated_at': now}
    STATS_F.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    REPORT_F.write_text('\n'.join(md), encoding='utf-8')
    print('stats:', json.dumps(stats, ensure_ascii=False))
    print('报告:', REPORT_F)


if __name__ == '__main__':
    main()
