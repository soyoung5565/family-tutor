#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verify-micro-lesson.py -- 校验微课堂生成器（一题一课）的 requirement 硬约束

对 micro-lesson.py --demo --no-submit 输出做检查：
  · 每组（按大题分组）的硬约束是否齐全
  · 场景数公式 N + M + 1 是否成立（声明值与推导值一致）
  · demo 组数、题号标签、小题块数量

用法: python verify-micro-lesson.py
"""
import os
import re
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent / "micro-lesson.py"


def pick_python():
    for cand in (r"D:\Python312\python.exe", sys.executable):
        if cand and Path(cand).exists():
            return cand
    return sys.executable


PYTHON = pick_python()

REQUIRED_CONSTRAINTS = [
    ("persona (teacher)", r"中国小学六年级的数学老师"),
    ("word-level rule", r"用词要符合六年级水平"),
    ("scene formula", r"总场景数必须为\s*\(N\s*\+\s*M\s*\+\s*1\)"),
    ("N/M declared", r"本课 N=\d+、M=\d+ → 必须生成 \d+ 个场景"),
    ("scene 1 rule", r"场景\s*1：错题还原"),
    ("scene 1 no-answer", r"不给正确答案和正确解法"),
    ("scene 1 circle parts", r"圈出学生做错的小题"),
    ("kp pages 2~N+1", r"场景\s*2\s*~\s*\d+：每个知识点一页讲解"),
    ("one kp per page", r"一页只讲一个知识点"),
    ("regression scenes", r"场景\s*\d+\s*~\s*\d+：回归错题"),
    ("regression solve", r"用刚讲的方法把它做对"),
    ("no opening", r"禁止任何开场白"),
    ("no widget", r"禁止任何 widget"),
    ("only slide", r"只能使用 slide 场景"),
    ("knowledgeScope", r"knowledgeScope"),
    ("scope rule", r"严禁引入 knowledgeScope 之外"),
]

MERGE_CONSTRAINTS = [
    ("merge rule (M>1)", r"合并为一堂课"),
    ("multi-part intro", r"个小题都做错了"),
]

SINGLE_CONSTRAINTS = [
    ("single-part intro", r"只有 1 个小题做错"),
]

def run_and_capture():
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    result = subprocess.run(
        [PYTHON, str(SCRIPT), "--demo", "--no-submit"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env,
    )
    if result.returncode != 0:
        print(f"[error] micro-lesson.py exited {result.returncode}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout


def split_requirements(out):
    """把输出切成 {标签: requirement 正文}"""
    reqs = {}
    pat = re.compile(
        r"【(.+?)】requirement\s*\((\d+) chars\)\s*\n=+\n(.*?)(?=\n=+\n【|\[no-submit\]|\Z)",
        re.DOTALL,
    )
    for m in pat.finditer(out):
        reqs[m.group(1)] = m.group(3).strip()
    return reqs


def check_scene_formula(reqs):
    ok = True
    print("=== Scene count formula (N + M + 1) ===")
    for label, req in reqs.items():
        ms = re.search(r"本课 N=(\d+)、M=(\d+) → 必须生成 (\d+) 个场景", req)
        if not ms:
            print(f"  FAIL  [{label}] N/M 声明缺失")
            ok = False
            continue
        n, m, sc = (int(x) for x in ms.groups())
        if sc != n + m + 1:
            print(f"  FAIL  [{label}] N={n} M={m} 声明 {sc}，公式应为 {n + m + 1}")
            ok = False
        else:
            print(f"  PASS  [{label}] N={n} M={m} -> {sc} 个场景")
    return ok


def check_demo_content(reqs):
    ok = True
    print("=== Demo content & grouping ===")
    expected_labels = {"第5题", "第2题"}
    got = set(reqs)
    if got != expected_labels:
        print(f"  FAIL  期望组 {sorted(expected_labels)}，实得 {sorted(got)}")
        return False
    print("  PASS  两组（第5题 / 第2题）齐全")

    req5 = reqs.get("第5题", "")
    req2 = reqs.get("第2题", "")
    if "圆形花坛" in req5 and "剪去" in req2:
        print("  PASS  demo 内容（圆形花坛 / 绳子剪去）")
    else:
        print("  FAIL  demo 内容缺失")
        ok = False

    blocks5 = re.findall(r"做错的小题 \d+", req5)
    blocks2 = re.findall(r"做错的小题 \d+", req2)
    if len(blocks5) == 3 and len(blocks2) == 1:
        print("  PASS  小题块数量（第5题 3 个 / 第2题 1 个）")
    else:
        print(f"  FAIL  小题块数量（第5题 {len(blocks5)} 个 / 第2题 {len(blocks2)} 个）")
        ok = False
    return ok

def main():
    out = run_and_capture()
    reqs = split_requirements(out)
    print(f"Captured {len(reqs)} requirement(s): {', '.join(reqs)}")
    print()
    all_pass = True

    for label, req in reqs.items():
        print(f"=== [{label}] required constraints ===")
        for cname, pattern in REQUIRED_CONSTRAINTS:
            if re.search(pattern, req):
                print(f"  PASS  {cname}")
            else:
                print(f"  FAIL  {cname}")
                all_pass = False
        m_multi = re.search(r"本课 N=(\d+)、M=(\d+)", req)
        multi = bool(m_multi and int(m_multi.group(2)) > 1)
        for cname, pattern in (MERGE_CONSTRAINTS if multi else SINGLE_CONSTRAINTS):
            if re.search(pattern, req):
                print(f"  PASS  {cname}")
            else:
                print(f"  FAIL  {cname}")
                all_pass = False
        print()

    if not check_demo_content(reqs):
        all_pass = False
    print()
    if not check_scene_formula(reqs):
        all_pass = False
    print()

    if all_pass:
        print("[verify] ALL CHECKS PASSED")
        return 0
    print("[verify] SOME CHECKS FAILED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
