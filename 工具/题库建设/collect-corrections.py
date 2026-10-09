#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect-corrections.py — 第二阶段：对比学生订正，找出仍错的题

流程位置：
  第一次  wrong-list.py  → 订正清单（无答案）
  学生订正（拍照/文字）
  本脚本  → 对比 → 输出【仍错题】+【订正对比】（micro-publish.py 的决策依据）

用法:
  python collect-corrections.py --mistakes mistakes.json --corrections corr.json --subject 数学
  python collect-corrections.py --demo

corrections 格式（两种都支持）:
  {"q1": "9人", "q2": "50.24平方米"}          # id → 新答案
  [{"id": "q1", "corrected_answer": "9人"}]    # 列表形式

输出（out-dir 默认 D:/家教/系统）:
  仍错题_{date}.json          仍错的小题（给 micro-lesson.py / micro-publish.py）
  订正对比_{date}.json        按大题分组的订正结果（micro-publish.py 决策依据）
  订正报告_{date}.md          给学生看的订正报告

分组逻辑复用同目录的 micro-lesson.py，保证与微课堂粒度（一道大题 = 一个微课堂）一致。
"""
import argparse
import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path


def _load_micro_lesson():
    """加载同目录的 micro-lesson.py（文件名带连字符，不能直接 import）。"""
    p = Path(__file__).resolve().parent / "micro-lesson.py"
    spec = importlib.util.spec_from_file_location("micro_lesson", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_micro_lesson = _load_micro_lesson()
major_key = _micro_lesson.major_key
group_label = _micro_lesson.group_label
group_mistakes = _micro_lesson.group_mistakes


DEMO_MISTAKES = [
    {"id": "q5_1", "group": "q5", "question": "圆形花坛半径 3 米，周长是多少米？", "student_answer": "18.84 平方米", "correct_answer": "18.84 米",
     "knowledge_points": ["u2.k6"]},
    {"id": "q5_2", "group": "q5", "question": "同一个花坛，面积是多少平方米？", "student_answer": "18.84 平方米", "correct_answer": "28.26 平方米",
     "knowledge_points": ["u2.k7"]},
    {"id": "q5_3", "group": "q5", "question": "花坛外 1 米宽小路的面积？", "student_answer": "3.14 平方米", "correct_answer": "21.98 平方米",
     "knowledge_points": ["u2.k7", "u2.k8"]},
    {"id": "q2", "question": "绳子长 5 米，剪去 2/5，还剩多少米？", "student_answer": "2 米", "correct_answer": "3 米",
     "knowledge_points": ["u1.k1"]},
]
DEMO_CORR = {"q5_1": "18.84 米", "q5_2": "28.26 平方米", "q5_3": "3.14 平方米", "q2": "2 米"}
# 订正结果：q5_1 对、q5_2 对、q5_3 仍错、q2 仍错


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


def build_comparison(mistakes, fixed, still_wrong, missing, subject,
                     mistakes_file=None, corrections_file=None):
    """生成订正对比结构（按大题分组），供 micro-publish.py 决策。"""
    verdicts = {}
    for m in fixed:
        verdicts[str(m.get("id"))] = {"verdict": "fixed", "given": m.get("corrected_answer")}
    for m in still_wrong:
        verdicts[str(m.get("id"))] = {"verdict": "still_wrong", "given": m.get("corrected_answer")}
    for m in missing:
        verdicts[str(m.get("id"))] = {"verdict": "missing", "given": None}

    groups_out = {}
    for key, gitems in group_mistakes(mistakes).items():
        ids = [str(m.get("id")) for m in gitems]
        fx = [i for i in ids if verdicts.get(i, {}).get("verdict") == "fixed"]
        sw = [i for i in ids if verdicts.get(i, {}).get("verdict") == "still_wrong"]
        ms = [i for i in ids if verdicts.get(i, {}).get("verdict") == "missing"]
        groups_out[key] = {
            "group_key": key,
            "label": group_label(key),
            "mistake_ids": ids,
            "fixed": fx,
            "still_wrong": sw,
            "missing": ms,
            "unfixed": sw + ms,          # 未订正对的小题（= 重生成时要覆盖的小题）
            "all_correct": len(sw) == 0 and len(ms) == 0,
        }

    per_q = {}
    for m in mistakes:
        qid = str(m.get("id"))
        v = verdicts.get(qid, {"verdict": "missing", "given": None})
        per_q[qid] = {
            "verdict": v["verdict"],
            "given": v["given"],
            "expected": m.get("correct_answer", ""),
        }

    return {
        "subject": subject,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "mistakes_file": mistakes_file,
        "corrections_file": corrections_file,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "per_question": per_q,
        "groups": groups_out,
    }


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
    subject_cn = _micro_lesson.resolve_subject(a.subject)

    # 仍错的题 → 交给 micro-lesson.py / micro-publish.py
    wf = out_dir / f'仍错题_{subject_cn}_{date_str}.json'
    wf.write_text(json.dumps(still_wrong, ensure_ascii=False, indent=2), encoding='utf-8')

    # 订正对比（按大题分组）→ micro-publish.py 的决策依据
    comparison = build_comparison(mistakes, fixed, still_wrong, missing, a.subject,
                                  mistakes_file=str(a.mistakes) if a.mistakes else None,
                                  corrections_file=str(a.corrections) if a.corrections else None)
    cf = out_dir / f'订正对比_{subject_cn}_{date_str}.json'
    cf.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding='utf-8')

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
    rf = out_dir / f'订正报告_{subject_cn}_{date_str}.md'
    rf.write_text("\n".join(lines), encoding='utf-8')

    print(f"✓ 订正正确 {len(fixed)} | 仍错 {len(still_wrong)} | 未提交 {len(missing)}")
    print(f"✓ 仍错题（给 micro-lesson.py）: {wf}")
    print(f"✓ 订正对比（给 micro-publish.py）: {cf}")
    print(f"✓ 订正报告（给学生）: {rf}")


if __name__ == '__main__':
    main()
