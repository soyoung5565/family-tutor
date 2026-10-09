#!/usr/bin/env python3
"""
Verification script for micro-lesson requirement.

Runs `micro-lesson.py --demo --no-submit`, captures the requirement, and
checks that all hard constraints are present. Use this to verify changes
to `build_micro_lesson_requirement()` haven't accidentally dropped
constraints.

Usage:
  python verify-micro-lesson.py
"""

import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "micro-lesson.py"
PYTHON = r"D:\Python312\python.exe"

REQUIRED_CONSTRAINTS = [
    ("persona (teacher)", r"中国小学六年级的数学老师"),
    ("word-level rule", r"用词要符合六年级水平"),
    ("scene formula", r"\(?知识点数\s*\+\s*2\)?|\(N\s*\+\s*2\)"),
    ("scene 1 rule", r"场景\s*1.*错题还原"),
    ("scene N+2 rule", r"场景\s*N\s*\+\s*2.*回归错题"),
    ("no opening", r"禁止任何开场白"),
    ("no widget", r"禁止任何 widget|禁止.*widget"),
    ("only slide", r"只能使用 slide 场景"),
    ("knowledge scope", r"knowledgeScope"),
    ("scope rule", r"严禁引入.*之外"),
]


def run_and_capture() -> str:
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--demo", "--no-submit"],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"[error] micro-lesson.py exited {result.returncode}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(1)
    # Strip the = bars
    out = result.stdout
    out = re.sub(r"^=+\n?", "", out, flags=re.MULTILINE)
    out = re.sub(r"^Requirement length:.*$", "", out, flags=re.MULTILINE)
    return out


def main():
    req = run_and_capture()
    print(f"Captured requirement: {len(req)} chars\n")

    print("=== Constraint checks ===")
    all_pass = True
    for label, pattern in REQUIRED_CONSTRAINTS:
        if re.search(pattern, req, re.IGNORECASE):
            print(f"  PASS  {label}")
        else:
            print(f"  FAIL  {label}  (pattern: {pattern})")
            all_pass = False

    # Check that demo mistakes are present
    print("\n=== Demo content checks ===")
    if "摄影小组" in req and "航模小组" in req:
        print("  PASS  Mistake 1 (摄影小组) present")
    else:
        print("  FAIL  Mistake 1 missing")
        all_pass = False
    if "绳子长5米" in req:
        print("  PASS  Mistake 2 (绳子) present")
    else:
        print("  FAIL  Mistake 2 missing")
        all_pass = False

    # Check the scene counts claimed
    scene_counts = re.findall(r"必须生成 (\d+) 个场景", req)
    print(f"\n=== Scene count claims ===")
    for c in scene_counts:
        print(f"  - claims: {c} scenes")
    expected = ["3", "3"]  # both demo mistakes have 1 KP -> 3 scenes each
    if scene_counts == expected:
        print("  PASS  Scene counts match expectations")
    else:
        print(f"  FAIL  expected {expected}, got {scene_counts}")
        all_pass = False

    print("\n" + ("=" * 40))
    if all_pass:
        print("ALL CHECKS PASSED")
        sys.exit(0)
    else:
        print("SOME CHECKS FAILED — review the requirement above")
        sys.exit(1)


if __name__ == "__main__":
    main()
