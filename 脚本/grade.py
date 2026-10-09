#!/usr/bin/env python3
"""
grade.py - 端到端错题批改 + 微课生成

用法（在 Hermes chat 里执行）：
  1. 用户发作业图
  2. agent 用 vision_analyze 提取题目 + 学生答案
  3. agent 自己用 LLM 解题（独立）
  4. agent 比对，错的→写入错题集
  5. agent 自动调 micro-lesson.py 生成微课

CLI 子命令：
  python grade.py --mistakes mistakes.json --subject 数学  # 已知错题 → 微课
  python grade.py --list-mistakes --subject 数学             # 列出所有错题
"""

import argparse
import json
import sys
import subprocess
from pathlib import Path

DEFAULT_TUTOR_ROOT = Path(r"D:\家教")
SCRIPTS = DEFAULT_TUTOR_ROOT / "系统" / "scripts"


def list_mistakes(subject, tutor_root=DEFAULT_TUTOR_ROOT):
    md = tutor_root / subject / "错题集"
    if not md.is_dir():
        print(f"[info] no mistakes dir: {md}")
        return
    files = sorted(md.glob("*.json"))
    print(f"=== {subject} 错题集 ({len(files)}) ===")
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            q = data.get("question_text", "?")[:50]
            ok = "Y" if data.get("is_correct") else "X"
            kps = [k.get("name", "?") for k in data.get("knowledge_points", [])]
            print(f"  [{ok}] {f.name}  {q}...  KP: {kps}")
        except Exception as e:
            print(f"  [?] {f.name}  (parse err: {e})")


def trigger_micro_lesson(mistakes_path, subject, tutor_root=DEFAULT_TUTOR_ROOT, timeout=600):
    py = r"D:\Python312\python.exe"
    script = SCRIPTS / "micro-lesson.py"
    out_dir = tutor_root / subject / "课件"
    out_dir.mkdir(parents=True, exist_ok=True)
    log = Path(r"D:\tmp\grade_micro_lesson.log")

    cmd = [py, str(script), "--subject", subject,
           "--mistakes", str(mistakes_path), "--timeout", str(timeout)]
    print(f"[exec] {' '.join(cmd)}")
    with open(log, "w", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout+60)
        lf.write("STDOUT:\n" + proc.stdout)
        lf.write("\nSTDERR:\n" + proc.stderr)
    print(proc.stdout)
    if proc.returncode != 0:
        print(f"[error] exit {proc.returncode}")
        sys.exit(proc.returncode)
    files = sorted(out_dir.glob("micro_*.json"), key=lambda p: p.stat().st_mtime)
    if files:
        latest = files[-1]
        print(f"[ok] classroom: {latest}")
        return latest
    return None


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--subject", default="数学")
    p.add_argument("--mistakes", help="path to mistakes.json")
    p.add_argument("--list-mistakes", action="store_true")
    p.add_argument("--tutor-root", default=str(DEFAULT_TUTOR_ROOT))
    p.add_argument("--timeout", type=int, default=600)
    args = p.parse_args()
    tr = Path(args.tutor_root)

    if args.list_mistakes:
        list_mistakes(args.subject, tr)
        return

    if args.mistakes:
        if not Path(args.mistakes).exists():
            print(f"[error] {args.mistakes} not found")
            sys.exit(1)
        trigger_micro_lesson(args.mistakes, args.subject, tr, args.timeout)
        return

    p.print_help()


if __name__ == "__main__":
    main()
