#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect-corrections.py — 第二阶段：对比学生订正，找出仍错的题

流程位置：
  第一次  wrong-list.py  → 订正清单（无答案）
  学生订正（拍照/文字）
  本脚本  → 对比 → 输出【仍错的题】给 micro-lesson.py 生成答案+微课堂

用法:
  python collect-corrections.py --mistakes mistakes.json --corrections corr.json --subject 数学
  python collect-corrections.py --demo

corrections 格式（两种都支持）:
  {"q1": "9人", "q2": "50.24平方米"}          # id → 新答案
  [{"id": "q1", "corrected_answer": "9人"}]    # 列表形式
"""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path


DEMO_MISTAKES = [
    {"id": "q1", "question": "...", "student_answer": "27", "correct_answer": "9人",
     "knowledge_points": ["u1.k1"]},
    {"id": "q2", "question": "...", "student_answer": "25.12 平方米", "correct_answer": "50.24 平方米",
     "knowledge_points": ["u2.k6"]},
]
DEMO_CORR = {"q1": "9人", "q2": "25.12 平方米"}   # q1 订正对，q2 仍错


def norm(s):
    """数字/单位归一化，用于宽松比对"""
    s = str(s or '').strip().lower()
    s = s.replace('　', ' ')
    s = re.sub(r'\s+', '', s)
    s = s.replace('平方厘米', 'cm2').replace('平方分米', 'dm2').replace('平方米', 'm2')
    s = s.replace('厘米', 'cm').replace('分米', 'dm').replace('米', 'm')
    s = s.replace('千米', 'km').replace('毫米', 'mm')
    s = re.sub(r'[。，,．.；;：:、]', '', s)
    s = s.replace('＝', '=').replace('×', '*').replace('÷', '/')
    return s


def is_same(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return False
    if na == nb:
        return True
    # 数值等价（如 "9人" vs "9"）
    ma, mb = re.findall(r'-?\d+\.?\d*', na), re.findall(r'-?\d+\.?\d*', nb)
    if ma and mb and ma == mb and len(na) <= len(nb) + 2 and len(nb) <= len(na) + 2:
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mistakes', help='原 mistakes.json')
    ap.add_argument('--corrections', help='学生订正（json）')
    ap.add_argument('--subject', default='数学')
    ap.add_argument('--out-dir', default='D:/家教/系统')
    ap.add_argument('--demo', action='store_true')
    a = ap.parse_args()

    if a.demo:
        mistakes, corr = DEMO_MISTAKES, DEMO_CORR
    else:
        mistakes = json.loads(Path(a.mistakes).read_text(encoding='utf-8'))
        if isinstance(mistakes, dict):
            mistakes = mistakes.get('mistakes') or mistakes.get('items') or []
        corr = json.loads(Path(a.corrections).read_text(encoding='utf-8'))
        if isinstance(corr, list):
            corr = {str(c.get('id')): c.get('corrected_answer') for c in corr}

    fixed, still_wrong, missing = [], [], []
    for m in mistakes:
        qid = str(m.get('id'))
        if qid not in corr or not str(corr.get(qid) or '').strip():
            missing.append(m)
            continue
        given = corr[qid]
        if is_same(given, m.get('correct_answer')):
            fixed.append({**m, 'corrected_answer': given})
        else:
            still_wrong.append({**m, 'corrected_answer': given})

    out_dir = Path(a.out_dir)
    date_str = datetime.now().strftime('%Y-%m-%d')

    # 仍错的题 → 交给 micro-lesson.py（第二阶段：答案 + 微课堂）
    wf = out_dir / f'仍错题_{date_str}.json'
    wf.write_text(json.dumps(still_wrong, ensure_ascii=False, indent=2), encoding='utf-8')

    # 订正报告（给学生看）
    lines = [f"# {a.subject} 订正结果（{date_str}）", ""]
    lines.append(f"- 订正正确：**{len(fixed)} 道** ✅")
    lines.append(f"- 仍需讲解：**{len(still_wrong)} 道**")
    if missing:
        lines.append(f"- 未提交订正：{len(missing)} 道")
    lines.append("")
    if fixed:
        lines.append("## ✅ 订正正确（做得好！）")
        lines.append("")
        for m in fixed:
            lines.append(f"- **{m.get('id')}**：{str(m.get('question',''))[:60]}…")
            lines.append(f"  - 你的订正：`{m.get('corrected_answer')}` → **正确** 👍")
        lines.append("")
    if still_wrong:
        lines.append("## 📖 需要再看一遍")
        lines.append("")
        for m in still_wrong:
            lines.append(f"- **{m.get('id')}**：{str(m.get('question',''))[:60]}…")
            lines.append(f"  - 你的订正：`{m.get('corrected_answer')}`")
        lines.append("")
        lines.append("> 下面给你这几题的**正确答案和讲解（微课堂）**。")
    rf = out_dir / f'订正报告_{date_str}.md'
    rf.write_text("\n".join(lines), encoding='utf-8')

    print(f"✓ 订正正确 {len(fixed)} | 仍错 {len(still_wrong)} | 未提交 {len(missing)}")
    print(f"✓ 仍错题（给 micro-lesson.py）: {wf}")
    print(f"✓ 订正报告（给学生）: {rf}")


if __name__ == '__main__':
    main()
