#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
classify-homework.py
====================
学生作业识别器（KP 归属 + 复习信号检测）

参考：
- references/weekly-plan-engine.md（复习模式识别 SOP）
- references/state-schema.md（学情写入）
- references/quiz-bank-design.md（题型判定）

职责：
1. 输入学生作业（图片/文字/文档）
2. 用 vision（图片）或文本解析（文字）提取题目列表
3. 对每道题执行 KP 归属（基于 KP 索引 + 题库匹配）
4. 聚合复习信号（关键词 + KP 覆盖密度）
5. 更新 学习状态.json（current_mode + last_mode_change）
6. 输出识别结果供其他脚本使用

执行示例：
  python classify-homework.py \
      --input "C:/path/to/homework.jpg" \
      --subject 数学

  python classify-homework.py \
      --text "六年级数学期中复习题：分数除法、百分数..." \
      --subject 数学

作者：Hermes 家庭教师系统
最后更新：2026-09-12
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

CST = timezone(timedelta(hours=8))


def now_cst() -> str:
    return datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S")


def auto_detect_base_dir() -> Path:
    for cand in [Path("D:/家教"), Path("/d/家教"), Path("D:\\家教")]:
        if cand.exists():
            return cand
    raise FileNotFoundError("未找到家教根目录，请用 --base-dir 显式指定")


def load_kp_index(subject_dir: Path) -> dict:
    kp_file = subject_dir / "知识点及掌握情况/index.json"
    if not kp_file.exists():
        raise FileNotFoundError(f"未找到 KP 索引：{kp_file}")
    return json.loads(kp_file.read_text(encoding="utf-8"))


def load_state(base_dir: Path) -> dict:
    state_file = base_dir / "系统/学习状态.json"
    if not state_file.exists():
        raise FileNotFoundError(f"未找到 学习状态.json：{state_file}")
    return json.loads(state_file.read_text(encoding="utf-8"))


def save_state(base_dir: Path, state: dict):
    state_file = base_dir / "系统/学习状态.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


# 复习信号关键词词典（详见 weekly-plan-engine.md §2.2）
UNIT_REVIEW_KEYWORDS = [
    "单元复习", "单元小结", "单元综合", "单元检测", "单元测试",
    "Unit Review", "Unit Test", "综合练习", "回顾与整理",
    "单元达标", "过关检测", "阶段练习",
]

EXAM_KEYWORDS = [
    "期中复习", "期中测试", "期中模拟", "期中考试",
    "期末复习", "期末测试", "期末模拟", "期末考试",
    "月考", "阶段测试", "综合检测",
    "Midterm", "Final Exam", "期中试卷", "期末试卷",
]


def detect_review_signal(text: str, kp_unit_distribution: dict) -> dict:
    """检测复习信号
    Returns: {
        'signal_type': 'unit-review' | 'exam' | 'new-content' | 'unknown',
        'confidence': 0.0–1.0,
        'matched_keywords': [...],
        'kp_unit_density': {...}
    }
    """
    matched_exam = [kw for kw in EXAM_KEYWORDS if kw in text]
    matched_unit = [kw for kw in UNIT_REVIEW_KEYWORDS if kw in text]

    if matched_exam:
        return {
            "signal_type": "exam",
            "confidence": 0.95,
            "matched_keywords": matched_exam,
            "kp_unit_density": kp_unit_distribution,
        }
    if matched_unit:
        return {
            "signal_type": "unit-review",
            "confidence": 0.9,
            "matched_keywords": matched_unit,
            "kp_unit_density": kp_unit_distribution,
        }

    # KP 分布密度判断
    if kp_unit_distribution:
        max_unit_kps = max(kp_unit_distribution.values())
        if max_unit_kps >= 5:
            return {
                "signal_type": "unit-review",
                "confidence": 0.7,
                "matched_keywords": [],
                "kp_unit_density": kp_unit_distribution,
                "reason": f"单次作业中同单元 KP 数 ≥ 5（{max_unit_kps}）",
            }
        if len(kp_unit_distribution) >= 4:
            return {
                "signal_type": "exam",
                "confidence": 0.65,
                "matched_keywords": [],
                "kp_unit_density": kp_unit_distribution,
                "reason": f"KP 覆盖 ≥ 4 个不同单元（{len(kp_unit_distribution)}）",
            }

    return {
        "signal_type": "new-content",
        "confidence": 0.5,
        "matched_keywords": [],
        "kp_unit_density": kp_unit_distribution,
    }


def classify_text_to_kp(text: str, kp_index: dict) -> dict:
    """根据题目文本粗略判断 KP 归属（关键词匹配 + 上下文）
    这是简化版，真实环境应该调 vision/LLM

    Returns: {
        'questions': [
            {'text_snippet': '...', 'kp_id': 'u1.k1' | None, 'unit_id': 'u1' | None, 'confidence': 0.0-1.0}
        ],
        'kp_distribution': {'u1.k1': 2, 'u1.k2': 1, ...},
        'unit_distribution': {'u1': 3, 'u2': 1, ...}
    }
    """
    questions = []
    # 简单按题号分割
    question_pattern = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]|\b\d+[.、。)]\s')
    splits = question_pattern.split(text)

    for snippet in splits:
        snippet = snippet.strip()
        if len(snippet) < 5:
            continue

        # 简化：找 KP name 关键词
        kp_match = None
        for unit in kp_index["units"]:
            for kp_id in unit.get("kp_ids", []):
                kp_file = Path(kp_index.get("kp_index_path", "")).parent / f"{kp_id}.json"
                # 跳过 — 这里太复杂，返回 None 让真实 LLM 处理
                # 真实环境调用 LLM 做归属
                pass

        questions.append({
            "text_snippet": snippet[:200],
            "kp_id": kp_match,
            "unit_id": None,
            "confidence": 0.0,
            "note": "真实环境应调 vision/LLM 做 KP 归属（见 classify-homework-prompt.md）",
        })

    return {
        "questions": questions,
        "kp_distribution": {},
        "unit_distribution": {},
    }


def update_state_mode(state: dict, subject: str, signal: dict):
    """根据信号更新 学习状态.json 的 current_mode"""
    signal_type = signal["signal_type"]
    mode_map = {
        "new-content": "预习周",
        "unit-review": "单元复习周",
        "exam": "期中/期末周",
    }
    new_mode = mode_map.get(signal_type, "预习周")
    old_mode = state["global"]["current_mode_detail"].get(subject, "预习周")

    if new_mode == old_mode:
        return False, None

    # 模式切换（含防抖：复习周切换需要 2 次信号，已在调用方聚合）
    state["global"]["current_mode_detail"][subject] = new_mode

    # 全局模式优先级：exam > unit-review > 预习周
    all_modes = state["global"]["current_mode_detail"].values()
    if "期中/期末周" in all_modes:
        state["global"]["current_mode"] = "期中/期末周"
    elif "单元复习周" in all_modes:
        state["global"]["current_mode"] = "单元复习周"
    else:
        state["global"]["current_mode"] = "预习周"

    state["global"]["last_mode_change"] = {
        "at": now_cst(),
        "subject": subject,
        "old_mode": old_mode,
        "new_mode": new_mode,
        "trigger_signal": signal.get("matched_keywords") or signal.get("reason") or signal_type,
        "confidence": signal.get("confidence", 0),
    }

    return True, state["global"]["last_mode_change"]


def main():
    parser = argparse.ArgumentParser(description="学生作业识别（KP 归属 + 复习信号）")
    parser.add_argument("--input", help="作业图片路径")
    parser.add_argument("--text", help="作业文本（OCR 后或手输）")
    parser.add_argument("--subject", required=True, choices=["数学", "语文", "英语"])
    parser.add_argument("--base-dir", default=None)
    parser.add_argument("--no-write", action="store_true", help="只计算不写状态（供 day1-pipeline 编排用）")
    parser.add_argument("--kps", default=None, help="逗号分隔的 KP id 列表（来自错题记录，用于密度判定）")
    args = parser.parse_args()

    if not args.input and not args.text:
        print("❌ 必须提供 --input（图片路径）或 --text（文本）")
        sys.exit(1)

    base_dir = auto_detect_base_dir() if not args.base_dir else Path(args.base_dir)
    subject_dir = base_dir / args.subject
    state = load_state(base_dir)
    kp_index = load_kp_index(subject_dir)

    # 获取作业文本
    if args.text:
        text = args.text
    else:
        # 真实环境：调 vision 提取（参考 mimo-multimodal.md）
        print(f"⚠ 图片识别尚未集成，先用 vision 提取文字。参考 mimo-multimodal.md")
        print(f"   input: {args.input}")
        sys.exit(1)

    print(f"⏳ 识别作业文本（共 {len(text)} 字符）...")

    # Step 1: KP 归属（--kps 时直接用外部提供的 KP 列表做密度统计）
    classification = classify_text_to_kp(text, kp_index)
    if args.kps:
        from collections import Counter
        ids = [x.strip() for x in args.kps.split(",") if x.strip()]
        classification["kp_distribution"] = dict(Counter(ids))
        classification["unit_distribution"] = dict(Counter(i.split(".")[0] for i in ids))
    print(f"✓ KP 归属完成：识别到 {len(classification['questions'])} 道题"
          f"（KP 分布：{classification.get('kp_distribution') or '空'}）")

    # Step 2: 信号聚合
    signal = detect_review_signal(text, classification["unit_distribution"])
    print(f"✓ 信号检测：type={signal['signal_type']}, confidence={signal['confidence']:.0%}")

    # Step 3: 更新状态
    changed, change_info = update_state_mode(state, args.subject, signal)
    if changed:
        if args.no_write:
            state["global"]["current_mode_detail"][args.subject] = change_info["old_mode"]  # 回滚内存
            print(f"✓ 建议模式切换（--no-write 未落盘）：{change_info['old_mode']} → {change_info['new_mode']}")
        else:
            save_state(base_dir, state)
            print(f"✓ 模式切换：{change_info['old_mode']} → {change_info['new_mode']}")
            print(f"  触发：{change_info['trigger_signal']}")
            print(f"  时间：{change_info['at']}")
    else:
        print(f"✓ 模式未变（{state['global']['current_mode_detail'].get(args.subject, '预习周')}）")

    # 输出 JSON 结果
    result = {
        "subject": args.subject,
        "classification": classification,
        "signal": signal,
        "mode_change": change_info,
    }
    print()
    print("JSON 输出：")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
