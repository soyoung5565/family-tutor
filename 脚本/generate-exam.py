#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate-exam.py
================
试卷生成器（5 种形式）

参考：
- references/exam-formats.md（5 种形式规范）
- references/quiz-bank-design.md（题库 schema）
- references/state-schema.md（学情数据）

支持的形式：
  --format question     题目卷（PDF + Word）
  --format dictation    默写卷（PDF + Word）
  --format remediation  错题回灌卷（PDF + Word）
  --format listening    听写包（MP3 + Word 答案）
  --format recitation   背诵检查表（仅 Word）

执行示例：
  # 单元复习卷（数学 u1）
  python generate-exam.py \
      --subject 数学 \
      --format question \
      --scope u1 \
      --type unit-review \
      --output D:/家教/数学/试卷/

  # 期中模拟卷
  python generate-exam.py \
      --subject 语文 \
      --format question \
      --scope u1-u4 \
      --type midterm \
      --output D:/家教/语文/试卷/

  # 默写卷（英语 u1 单词）
  python generate-exam.py \
      --subject 英语 \
      --format dictation \
      --scope u1 \
      --output D:/家教/英语/试卷/

  # 错题回灌
  python generate-exam.py \
      --subject 数学 \
      --format remediation \
      --kp-ids u1.k2,u1.k5 \
      --output D:/家教/数学/试卷/

作者：Hermes 家庭教师系统
最后更新：2026-09-12
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# CST 时间
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def load_state(base_dir: Path) -> dict:
    """加载学习状态.json"""
    state_file = base_dir / "系统/学习状态.json"
    if not state_file.exists():
        raise FileNotFoundError(f"未找到 学习状态.json：{state_file}\n请先运行 init-learning-state.py")
    return json.loads(state_file.read_text(encoding="utf-8"))


def load_question_pool(subject: str, base_dir: Path) -> dict:
    """加载题库索引和 KP 题目"""
    pool_dir = base_dir / subject / "测验"
    if not pool_dir.exists():
        return {"index": None, "questions": {}}

    index_file = pool_dir / "index.json"
    index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else None

    questions = {}
    for unit_dir in pool_dir.iterdir():
        if not unit_dir.is_dir() or unit_dir.name in ("by-type", "_meta"):
            continue
        for kp_file in unit_dir.glob("*.json"):
            try:
                qs = json.loads(kp_file.read_text(encoding="utf-8"))
                for q in qs:
                    questions[q["qid"]] = q
            except json.JSONDecodeError as e:
                print(f"⚠ 题库文件损坏：{kp_file} → {e}")

    return {"index": index, "questions": questions}


def get_weak_kps(state: dict, subject: str) -> list:
    """从学习状态.json 取薄弱 KP（master < 60）"""
    kps = state["subjects"][subject]["kps"]
    return [kp_id for kp_id, kp in kps.items() if kp["master"] < 60]


def shuffle_options(question: dict) -> dict:
    """打乱选项（沿用 answer-distribution-randomization 规则）"""
    import random
    if not question.get("options"):
        return question

    correct_answer = question["answer"]
    options = list(question["options"])

    # 找出正确答案在 options 中的位置
    if isinstance(correct_answer, int):
        correct_value = options[correct_answer]
    elif isinstance(correct_answer, str) and correct_answer.isdigit():
        idx = int(correct_answer)
        correct_value = options[idx]
    else:
        correct_value = correct_answer

    # 打乱
    indices = list(range(len(options)))
    random.shuffle(indices)
    new_options = [options[i] for i in indices]

    # 找新的索引
    new_correct_idx = new_options.index(correct_value)

    q = dict(question)
    q["options"] = new_options
    q["answer"] = str(new_correct_idx) if isinstance(correct_answer, str) and correct_answer.isdigit() else new_correct_idx
    return q


def generate_question_exam(args, state, pool) -> dict:
    """生成题目卷（PDF + Word 骨架）"""
    subject = args.subject
    scope = args.scope
    exam_type = args.type

    # 难度分布
    diff_dist = {
        "unit-review": {"易": 0.50, "中": 0.35, "难": 0.15},
        "midterm":     {"易": 0.30, "中": 0.50, "难": 0.20},
        "final":       {"易": 0.25, "中": 0.50, "难": 0.25},
    }.get(exam_type, {"易": 0.50, "中": 0.35, "难": 0.15})

    target_count = {
        "unit-review": 20,
        "midterm": 35,
        "final": 40,
    }.get(exam_type, 20)

    # 解析 scope
    if "-" in scope:
        unit_ids = [f"u{i}" for i in range(int(scope.split("-")[0][1:]), int(scope.split("-")[1][1:]) + 1)]
    elif "," in scope:
        unit_ids = [s.strip() for s in scope.split(",")]
    else:
        unit_ids = [scope]

    # 筛题（按 KP 覆盖 + 难度分布 + 错题回灌）
    available = []
    for qid, q in pool["questions"].items():
        if not q.get("enabled"):
            continue
        if q["unit_id"] not in unit_ids:
            continue
        available.append(q)

    weak_kps = get_weak_kps(state, subject)
    # 错题回灌：优先抽薄弱 KP 的题
    weak_questions = [q for q in available if q["kp_id"] in weak_kps]
    other_questions = [q for q in available if q["kp_id"] not in weak_kps]

    selected = []
    # 先保证薄弱 KP 至少 1 道（如果是 unit-review）或 2 道（midterm/final）
    min_weak = 2 if exam_type in ("midterm", "final") else 1
    for q in weak_questions:
        if len([x for x in selected if x in weak_questions]) >= min_weak:
            break
        selected.append(q)

    # 按 KP 覆盖补足
    covered_kps = set(q["kp_id"] for q in selected)
    target_kps = set()
    for uid in unit_ids:
        subject_data = state["subjects"].get(subject, {})
        for kp_id, kp in subject_data.get("kps", {}).items():
            if kp.get("unit_id") == uid:
                target_kps.add(kp_id)

    for q in sorted(other_questions, key=lambda x: (x["kp_id"], x["difficulty"])):
        if len(selected) >= target_count:
            break
        if q["kp_id"] not in covered_kps and q["kp_id"] in target_kps:
            selected.append(q)
            covered_kps.add(q["kp_id"])

    # 补足到 target_count（不强制 KP 覆盖）
    if len(selected) < target_count:
        for q in other_questions:
            if len(selected) >= target_count:
                break
            if q not in selected:
                selected.append(q)

    # 洗牌选项
    selected = [shuffle_options(q) for q in selected]

    # 估算时长
    minutes_per_q = {"易": 1, "中": 2, "难": 3}
    est_minutes = sum(minutes_per_q.get(q["difficulty"], 2) for q in selected)

    return {
        "format": "question",
        "subject": subject,
        "scope": scope,
        "type": exam_type,
        "title": f"六年级{subject} {exam_type.replace('-review', '复习').replace('midterm', '期中模拟').replace('final', '期末模拟')}卷",
        "questions": selected,
        "estimated_minutes": est_minutes,
        "difficulty_distribution": {
            d: sum(1 for q in selected if q["difficulty"] == d)
            for d in ["易", "中", "难"]
        },
        "weak_kps_covered": [q["kp_id"] for q in selected if q["kp_id"] in weak_kps],
    }


def generate_dictation(args, state, pool) -> dict:
    """生成默写卷骨架"""
    subject = args.subject
    scope = args.scope

    # 从 by-type 聚合筛题（字音字形 / 单词拼写）
    pool_dir = Path(f"D:/家教/{subject}/测验")
    by_type_file = pool_dir / "by-type"

    type_name = "字音字形" if subject == "语文" else "单词拼写" if subject == "英语" else None
    if type_name and (by_type_file / f"{type_name}.json").exists():
        candidates = json.loads((by_type_file / f"{type_name}.json").read_text(encoding="utf-8"))
    else:
        candidates = []

    # 限定 scope
    if "-" in scope:
        unit_ids = [f"u{i}" for i in range(int(scope.split("-")[0][1:]), int(scope.split("-")[1][1:]) + 1)]
    else:
        unit_ids = [scope]
    scoped = [q for q in candidates if q["unit_id"] in unit_ids and q.get("enabled")]

    # 取 20 个
    selected = scoped[:20]

    return {
        "format": "dictation",
        "subject": subject,
        "scope": scope,
        "type_name": type_name,
        "title": f"六年级{subject} {scope} 默写卷",
        "questions": selected,
        "estimated_minutes": 15,
    }


def generate_remediation(args, state, pool) -> dict:
    """生成错题回灌卷"""
    subject = args.subject
    kp_ids = [s.strip() for s in args.kp_ids.split(",")] if args.kp_ids else []

    # 从错题集找最近的错题
    mistakes_dir = Path(f"D:/家教/{subject}/错题集")
    recent_mistakes = []
    if mistakes_dir.exists():
        for mf in sorted(mistakes_dir.glob("*.json"), reverse=True)[:10]:
            try:
                m = json.loads(mf.read_text(encoding="utf-8"))
                recent_mistakes.append(m)
            except json.JSONDecodeError:
                continue

    # 筛选指定 KP 的错题
    target_mistakes = [m for m in recent_mistakes if m.get("kp_id") in kp_ids] if kp_ids else recent_mistakes[:3]

    # 从题库找同类题（首选），找不到则 LLM 改写（占位）
    selected = []
    for m in target_mistakes:
        kp_id = m.get("kp_id")
        if not kp_id:
            continue
        same_kp_questions = [
            q for q in pool["questions"].values()
            if q["kp_id"] == kp_id and q.get("enabled") and q["qid"] != m.get("qid")
        ]
        if same_kp_questions:
            selected.append(same_kp_questions[0])

    return {
        "format": "remediation",
        "subject": subject,
        "kp_ids": kp_ids,
        "title": f"错题回灌 - {'/'.join(kp_ids)}",
        "questions": selected,
        "source_mistakes": target_mistakes,
        "estimated_minutes": 10,
    }


def generate_listening(args, state, pool) -> dict:
    """生成听写包（MP3 + Word 答案）"""
    subject = args.subject
    scope = args.scope

    # 英语：从 by-type/单词拼写.json 取词
    # 语文：从 by-type/字音字形.json 取字
    pool_dir = Path(f"D:/家教/{subject}/测验")
    by_type_file = pool_dir / "by-type"

    type_name = "单词拼写" if subject == "英语" else "字音字形"
    candidates = []
    if (by_type_file / f"{type_name}.json").exists():
        candidates = json.loads((by_type_file / f"{type_name}.json").read_text(encoding="utf-8"))

    # 错词回灌：加最近错过的词
    mistakes_dir = Path(f"D:/家教/{subject}/错题集")
    mistake_words = []
    if mistakes_dir.exists():
        for mf in sorted(mistakes_dir.glob("*.json"), reverse=True)[:5]:
            try:
                m = json.loads(mf.read_text(encoding="utf-8"))
                if m.get("stem"):
                    mistake_words.append(m["stem"])
            except json.JSONDecodeError:
                continue

    return {
        "format": "listening",
        "subject": subject,
        "scope": scope,
        "title": f"六年级{subject} {scope} 听写包",
        "candidates": candidates[:30],
        "must_include_mistakes": mistake_words,
        "estimated_minutes": 15,
    }


def generate_recitation(args, state, pool) -> dict:
    """生成背诵检查表"""
    subject = args.subject
    scope = args.scope

    # 从 KP 列表找 type=课文背诵 的项
    kp_index_path = Path(f"D:/家教/{subject}/知识点及掌握情况/index.json")
    kp_index = json.loads(kp_index_path.read_text(encoding="utf-8"))

    recite_items = []
    if "-" in scope:
        unit_ids = [f"u{i}" for i in range(int(scope.split("-")[0][1:]), int(scope.split("-")[1][1:]) + 1)]
    else:
        unit_ids = [scope]

    for unit in kp_index["units"]:
        if unit["id"] not in unit_ids:
            continue
        for kp_id in unit.get("kp_ids", []):
            kp_file = Path(f"D:/家教/{subject}/知识点及掌握情况/{kp_id}.json")
            if kp_file.exists():
                kp = json.loads(kp_file.read_text(encoding="utf-8"))
                if "背诵" in kp.get("type", "") or "背诵" in kp.get("name", ""):
                    recite_items.append({"kp_id": kp_id, "name": kp.get("name", ""), "type": kp.get("type", "")})

    return {
        "format": "recitation",
        "subject": subject,
        "scope": scope,
        "title": f"六年级{subject} {scope} 背诵检查表",
        "items": recite_items,
    }


GENERATORS = {
    "question": generate_question_exam,
    "dictation": generate_dictation,
    "remediation": generate_remediation,
    "listening": generate_listening,
    "recitation": generate_recitation,
}


def write_markdown(exam_data: dict, output_dir: Path) -> Path:
    """写 Markdown 版（最通用）"""
    fmt = exam_data["format"]
    ts = now_str()
    md_file = output_dir / f"{exam_data['title']}_{ts}.md"
    output_dir.mkdir(parents=True, exist_ok=True)

    lines = []
    lines.append(f"# {exam_data['title']}")
    lines.append("")
    lines.append(f"**生成时间**：{ts}")
    lines.append(f"**科目**：{exam_data['subject']}")
    lines.append(f"**建议用时**：{exam_data.get('estimated_minutes', '?')} 分钟")
    if exam_data.get("weak_kps_covered"):
        lines.append(f"**错题回灌 KP**：{', '.join(exam_data['weak_kps_covered'])}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if fmt == "question":
        lines.append(f"## 题目（{len(exam_data['questions'])} 道）")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"### {i}. [{q['difficulty']}] {q.get('type', '')}（{q['kp_id']}）")
            lines.append("")
            lines.append(q["stem"])
            if q.get("options"):
                for j, opt in enumerate(q["options"]):
                    marker = chr(65 + j)
                    lines.append(f"- {marker}. {opt}")
            if q.get("material"):
                lines.append("")
                lines.append(f"> 材料：{q['material']}")
            lines.append("")

        # 答案页
        lines.append("---")
        lines.append("")
        lines.append("## 参考答案")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            ans = q["answer"]
            if isinstance(ans, int) and q.get("options"):
                ans_letter = chr(65 + ans)
                ans_text = q["options"][ans]
                lines.append(f"{i}. **{ans_letter}** {ans_text}")
            else:
                lines.append(f"{i}. {ans}")
        lines.append("")

        lines.append("## 解析")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"{i}. {q.get('explanation', '')}")
        lines.append("")

    elif fmt == "dictation":
        lines.append(f"## 默写（{len(exam_data['questions'])} 题）")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"{i}. {q.get('material', q['stem'])} → ＿＿＿")
        lines.append("")
        lines.append("## 答案")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"{i}. {q.get('answer', '')}")
        lines.append("")

    elif fmt == "remediation":
        lines.append(f"## 错题回灌（{len(exam_data['questions'])} 道）")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"### {i}. [{q['difficulty']}]（{q['kp_id']}）")
            lines.append(f"> 上次错在：{exam_data.get('source_mistakes', [{}])[i-1].get('stem_summary', '')}")
            lines.append("")
            lines.append(q["stem"])
            if q.get("options"):
                for j, opt in enumerate(q["options"]):
                    lines.append(f"- {chr(65 + j)}. {opt}")
            lines.append("")
        lines.append("## 答案与解析")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"{i}. **{q['answer']}** → {q.get('explanation', '')}")
        lines.append("")

    elif fmt == "listening":
        lines.append(f"## 听写词表（{len(exam_data['candidates'])} 个）")
        lines.append("")
        lines.append("### MP3 音频生成说明")
        lines.append("")
        lines.append("用 TTS 工具生成：每个词读 2 遍 + 间隔 5 秒")
        lines.append("")
        lines.append("### 词表")
        lines.append("")
        for i, q in enumerate(exam_data["candidates"], 1):
            lines.append(f"{i}. {q.get('stem', '')}  →  答案：{q.get('answer', '')}")
        lines.append("")
        if exam_data.get("must_include_mistakes"):
            lines.append("### 错词回灌（必须含）")
            lines.append("")
            for w in exam_data["must_include_mistakes"]:
                lines.append(f"- {w}")
            lines.append("")

    elif fmt == "recitation":
        lines.append(f"## 背诵检查（{len(exam_data['items'])} 项）")
        lines.append("")
        lines.append("日期：＿＿＿   家长签字：＿＿＿")
        lines.append("")
        for item in exam_data["items"]:
            lines.append(f"- □ {item['name']}（{item['type']}）")
        lines.append("")
        lines.append("### 备注（卡壳段落、需要多背几遍）")
        lines.append("")
        lines.append("＿")
        lines.append("")

    md_file.write_text("\n".join(lines), encoding="utf-8")
    return md_file


def main():
    parser = argparse.ArgumentParser(description="生成试卷/默写/听写包/背诵检查表")
    parser.add_argument("--subject", required=True, choices=["数学", "语文", "英语"])
    parser.add_argument("--format", required=True, choices=list(GENERATORS.keys()))
    parser.add_argument("--scope", help="覆盖范围，如 u1 / u1-u4")
    parser.add_argument("--type", choices=["unit-review", "midterm", "final"], default="unit-review",
                        help="题目卷类型（仅 question 形式用）")
    parser.add_argument("--kp-ids", help="错题回灌 KP 列表（仅 remediation 形式用），逗号分隔")
    parser.add_argument("--base-dir", default=None, help="自动探测 D:/家教 或 /d/家教")
    parser.add_argument("--output", help="输出目录（默认 D:/家教/{科目}/试卷/）")
    args = parser.parse_args()

    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        # 自动探测（Windows / WSL）
        for cand in [Path("D:/家教"), Path("/d/家教"), Path("D:\\\\家教")]:
            if cand.exists():
                base_dir = cand
                break
        else:
            print("❌ 未找到家教根目录，请用 --base-dir 显式指定")
            sys.exit(1)

    subject_dir = base_dir / args.subject

    if not subject_dir.exists():
        print(f"❌ 未找到科目目录：{subject_dir}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else (base_dir / args.subject / "试卷")

    # 加载状态 + 题库
    state = load_state(base_dir)
    pool = load_question_pool(args.subject, base_dir)

    # 生成
    generator = GENERATORS[args.format]
    exam_data = generator(args, state, pool)

    # 写出（Markdown 版，PDF/Word 由后续脚本转）
    md_file = write_markdown(exam_data, output_dir)
    print(f"✓ 已生成 {md_file}")
    print(f"  - 形式：{args.format}")
    print(f"  - 范围：{args.scope or args.kp_ids}")
    if exam_data.get("estimated_minutes"):
        print(f"  - 建议用时：{exam_data['estimated_minutes']} 分钟")
    if exam_data.get("questions"):
        print(f"  - 题目数：{len(exam_data['questions'])}")
    if exam_data.get("difficulty_distribution"):
        d = exam_data["difficulty_distribution"]
        print(f"  - 难度分布：易 {d.get('易', 0)} / 中 {d.get('中', 0)} / 难 {d.get('难', 0)}")
    if exam_data.get("weak_kps_covered"):
        print(f"  - 错题回灌 KP：{', '.join(exam_data['weak_kps_covered'])}")
    print()
    print(f"📝 Markdown 版已生成。PDF/Word 版可后续用 pandoc 转（暂未集成）")


if __name__ == "__main__":
    main()
