#!/usr/bin/env python3
"""
Mistake Grading Pipeline

Processes a homework image and produces structured mistake records.
Designed to be called by Hermes when the student sends a photo, but can
also run standalone for testing.

Pipeline (the key idea: do NOT trust the student's handwriting):
  Step 1: vision_extract_question(image)      -> question text only
  Step 2: llm_solve(question)                  -> standard answer + solution
  Step 3: vision_extract_student_answer(image) -> student answer (+confidence)
  Step 4: compare(student, standard)            -> is_correct
  Step 5: llm_candidate_kps(question, answer, is_correct)
                                                -> list of candidate knowledge points
  Step 6: match_to_knowledge_points(candidates, kp_db)
                                                -> final structured mistake record

Usage:
  python grade-mistake.py --image homework.png --subject math --kp-db D:/家教/数学/知识点及掌握情况
  python grade-mistake.py --demo
"""

import argparse
import base64 as b64mod
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Hermes / vision helpers (call the user's installed toolset)
# ---------------------------------------------------------------------------

def call_llm(prompt: str, image_b64: str = None, model: str = None) -> str:
    """Call the user-specified LLM (white-listed models only).

    This stub invokes `hermes` via subprocess — the actual hermes is a TUI,
    so for now we expose a hook so the user can plug in their preferred
    model client (opencode-go relay, muse-spark, kimi-k3, etc.).
    """
    # The Hermes platform exposes vision_analyze and LLM calls directly.
    # Inside this script we cannot call them directly, so the user runs
    # this via `python -c "..."` and we shell out to a python helper.
    raise NotImplementedError(
        "call_llm must be wired to your LLM client. "
        "See README.md for the recommended pattern using hermes's "
        "vision_analyze and chat completions."
    )


def vision_extract_question(image_path: Path) -> str:
    """Use a vision model to extract only the question text from the image.

    We deliberately do NOT extract the student's answer here — we want
    the model to focus on the question without being biased by what the
    student wrote.
    """
    raise NotImplementedError("wire to vision_analyze / multimodal")


def vision_extract_student_answer(image_path: Path) -> dict:
    """Extract the student's handwritten answer + confidence.

    Returns: {"text": "...", "confidence": "high|medium|low", "alternatives": [...]}
    """
    raise NotImplementedError("wire to vision_analyze / multimodal")


# ---------------------------------------------------------------------------
# Knowledge point database helpers
# ---------------------------------------------------------------------------

def load_kp_db(kp_dir: Path) -> list:
    """Load all knowledge points from D:/家教/{subject}/知识点及掌握情况/.

    Supports .json files (one KP per file) or .md files with H1 titles.
    """
    if not kp_dir.exists():
        return []
    out = []
    for p in sorted(kp_dir.iterdir()):
        if p.suffix == ".json":
            try:
                out.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception as e:
                print(f"[warn] cannot parse {p}: {e}", file=sys.stderr)
        elif p.suffix == ".md":
            # Minimal parse: first H1 is name, rest is definition
            text = p.read_text(encoding="utf-8")
            m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
            name = m.group(1).strip() if m else p.stem
            out.append({
                "id": p.stem,
                "name": name,
                "definition": text[:500],
                "example": "",
                "source_file": str(p),
            })
    return out


def match_candidates_to_kp(candidates: list, kp_db: list) -> list:
    """Given LLM-suggested candidate knowledge points, match to KP database.

    Strategy:
      1. If a candidate has an "id" matching a KP, use it directly
      2. Else, fuzzy-match by name (Chinese substring / Levenshtein-lite)
      3. Else, return as-is with in_scope=False for human review
    """
    out = []
    for c in candidates:
        cid = c.get("id")
        cname = c.get("name", "")
        matched = None
        if cid:
            for kp in kp_db:
                if kp.get("id") == cid:
                    matched = kp
                    break
        if not matched and cname:
            for kp in kp_db:
                if cname in kp.get("name", "") or kp.get("name", "") in cname:
                    matched = kp
                    break
        if matched:
            out.append({
                "id": matched["id"],
                "name": matched["name"],
                "definition": matched.get("definition", ""),
                "example": matched.get("example", ""),
                "in_scope": True,
            })
        else:
            out.append({
                "id": cid or "",
                "name": cname,
                "in_scope": False,
                "reason": "未在知识点库中找到，可能超纲或知识点尚未录入",
            })
    return out


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

DEMO_RESULT = {
    "subject": "math",
    "questions": [
        {
            "question_id": "q1",
            "question_text": "摄影小组有12人，是气象小组的1/3，航模小组的人数是摄影小组的3/4，求航模小组的人数。",
            "standard_answer": "3",
            "standard_solution": "1. 摄影小组=12×1/3=4人  2. 航模小组=4×3/4=3人",
            "student_answer": {"text": "36", "confidence": "high", "alternatives": []},
            "is_correct": False,
            "voted_knowledge_points": ["math_day1_kp2"],
            "common_mistakes": ["未识别第二个单位1", "直接用12乘以两个分率"],
        }
    ],
    "knowledge_scope": {
        "knowledge_points": [
            {
                "id": "math_day1_kp2",
                "name": "单位1的识别",
                "definition": "单位1是被比较的基准量。题目里'是...的几分之几'，分母指向的就是单位1。",
                "example": "摄影小组12人，是气象小组的1/3。这里单位1是气象小组（12人）。",
            }
        ]
    },
}


def main():
    parser = argparse.ArgumentParser(description="Grade homework image → structured mistakes")
    parser.add_argument("--image", help="Path to homework image")
    parser.add_argument("--subject", default="math")
    parser.add_argument("--kp-db", default="D:/家教/数学/知识点及掌握情况",
                        help="Path to knowledge-points directory")
    parser.add_argument("--tutor-root", default="D:/家教")
    parser.add_argument("--demo", action="store_true",
                        help="Print a built-in demo mistake record")
    parser.add_argument("--print-prompt-only", action="store_true",
                        help="Print the prompts that would be sent (no API calls)")
    args = parser.parse_args()

    if args.demo:
        print(json.dumps(DEMO_RESULT, ensure_ascii=False, indent=2))
        return

    if not args.image:
        print("[error] --image required (or use --demo)", file=sys.stderr)
        sys.exit(1)

    if args.print_prompt_only:
        print("=== Step 1 prompt: extract question ===")
        print("Extract ONLY the original question text from this homework image. "
              "Ignore the student's handwritten answer. Output: plain text.")
        print()
        print("=== Step 2 prompt: solve independently ===")
        print("Here is a math problem. Solve it step by step. "
              "Output: standard answer + step-by-step solution.")
        print()
        print("=== Step 3 prompt: extract student answer (with confidence) ===")
        print("Extract the student's handwritten answer. For each character, "
              "rate confidence high/medium/low. If uncertain, list alternatives.")
        print()
        print("=== Step 5 prompt: identify knowledge points ===")
        print("This student got this question wrong. Which knowledge points "
              "from the database are involved? List up to 3 candidates.")
        return

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"[error] image not found: {image_path}", file=sys.stderr)
        sys.exit(1)

    # The actual pipeline wiring lives in your hermes conversation.
    # This script prints the steps and a JSON scaffold.
    print(f"[info] Processing {image_path} for subject={args.subject}")
    print(f"[info] KP database: {args.kp_db}")
    print()
    print("To wire this script into hermes:")
    print("  1. When user sends an image, call vision_extract_question()")
    print("  2. Call llm_solve() with the question text only")
    print("  3. Call vision_extract_student_answer() on the same image")
    print("  4. Compare; if mismatch, run llm_candidate_kps() and match_to_kp()")
    print("  5. Write the structured mistake record to D:/家教/{subject}/错题集/")
    print()
    print("See skill 'family-tutor' for the integrated workflow.")


if __name__ == "__main__":
    main()
