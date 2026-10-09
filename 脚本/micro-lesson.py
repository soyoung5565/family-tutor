#!/usr/bin/env python3
"""
Micro-Lesson Generator

Generates a focused micro-lesson (micro-lesson) for a student's mistakes
using OpenMAIC with a hard-constrained requirement text.

No OpenMAIC source code changes are required. This script constructs a
super-specific requirement string that forces the default
REQUIREMENTS_TO_OUTLINES prompt to produce a slide-only, mistake-by-mistake
classroom.

Usage:
    python micro-lesson.py --subject math --mistakes mistakes.json --scope scope.json
    python micro-lesson.py --demo    # run a built-in demo

Input formats:
    mistakes.json: list of mistake dicts:
        {
          "id": "q1",
          "question": "原题文字...",
          "question_image_path": "optional/path/to/image.png",
          "student_answer": "...",
          "correct_answer": "...",
          "correct_solution": "标准解法步骤...",
          "common_mistakes": ["错法1", "错法2"]
        }
    scope.json: dict of knowledge scope:
        {
          "knowledge_points": [
            {
              "id": "math_day1_kp2",
              "name": "单位1的识别",
              "definition": "...",
              "example": "..."
            }
          ]
        }

Output:
    D:/家教/{subject}/课件/micro_{timestamp}.json  (the generated classroom)
    D:/家教/{subject}/课件/micro_{timestamp}_requirement.txt  (the requirement we sent)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path


OPENMAIC_BASE = "http://localhost:3000"
DEFAULT_TUTOR_ROOT = Path("D:/家教")

# subject 中英映射（用户真实目录是中文：数学/语文/英语）
SUBJECT_ALIAS = {
    'math': '数学', 'chinese': '语文', 'english': '英语',
    '数学': '数学', '语文': '语文', '英语': '英语',
}


def resolve_subject(subject: str) -> str:
    """把 math/chinese/english 映射成真实中文目录名"""
    return SUBJECT_ALIAS.get(str(subject).strip().lower(), SUBJECT_ALIAS.get(str(subject).strip(), subject))


# ---------------------------------------------------------------------------
# Requirement builder
# ---------------------------------------------------------------------------

def build_micro_lesson_requirement(mistakes: list, scope: dict, subject: str) -> str:
    """Construct a hard-constrained requirement that forces a micro-lesson.

    The text is deliberately verbose. The default OpenMAIC outline prompt
    uses the requirement as the primary instruction source; pushing every
    constraint into the requirement is the only way to get a consistent
    short, slide-only lesson without patching the prompt itself.
    """
    kp_index = {kp["id"]: kp for kp in scope.get("knowledge_points", [])}

    persona_block = (
        "你是一位中国小学六年级的数学老师，正在给学生讲他做错的题。\n"
        "学生已经学过本学期内容，但在某些知识点上有漏洞。\n\n"
        "你的教学风格：\n"
        "- 把抽象概念一步一步拆开，从学生已经会的内容开始往上搭\n"
        "- 用视觉辅助（白板画图、写公式），让抽象概念变具体\n"
        "- 用词要符合六年级水平，不能超过小学六年级的范围\n"
    )

    constraints_block = (
        "\n## 硬性约束（必须严格遵守）\n\n"
        "1. 每一道错题生成 (知识点数 + 2) 个场景：\n"
        "   - 场景 1：错题还原。在白板写出原题，圈出错处。不给正确答案。\n"
        "   - 场景 2 ~ N+1：每个知识点一页讲解。\n"
        "   - 场景 N+2：回归错题。用刚讲的方法做对，写正确答案。\n\n"
        "2. 禁止任何开场白、总结页、错题之间的过渡页。\n\n"
        "3. 只能使用 slide 场景。禁止任何 widget（simulation / diagram / "
        "game / visualization3d / code / quiz）。\n\n"
        "4. 一页只能讲一个知识点。\n\n"
        "5. 只能使用下方 knowledgeScope 列出的概念和例子。"
        "严禁引入 knowledgeScope 之外的概念。\n"
    )

    # Mistake blocks
    mistake_blocks = []
    for i, m in enumerate(mistakes, 1):
        kps = m.get("knowledge_points", [])
        kp_names = [kp_index.get(kp_id, {}).get("name", kp_id) for kp_id in kps]

        common_mistakes = m.get("common_mistakes", [])
        mistakes_text = "\n".join(f"  - {cm}" for cm in common_mistakes) if common_mistakes else "  （暂无）"

        kp_count = len(kps)
        scene_count = kp_count + 2

        block = f"""
## 错题 {i}（涉及 {kp_count} 个知识点 → 必须生成 {scene_count} 个场景）

原题：
{m.get('question', '（无）')}

标准答案：{m.get('correct_answer', '（无）')}
标准解法：
{m.get('correct_solution', '（无）')}

涉及的知识点：
""" + "\n".join(f"  - {name}" for name in kp_names) + f"""

学生写的答案：{m.get('student_answer', '（无）')}
学生常见错法：
{mistakes_text}
"""
        mistake_blocks.append(block)

    # Knowledge scope block
    scope_lines = []
    for kp in scope.get("knowledge_points", []):
        scope_lines.append(
            f"### {kp.get('name', kp.get('id', '?'))}\n"
            f"- 定义：{kp.get('definition', '（无）')}\n"
            f"- 例子：{kp.get('example', '（无）')}\n"
        )
    scope_block = "\n".join(scope_lines) if scope_lines else "（无相关知识点，按错题还原+回归错题两页处理）"

    full_requirement = (
        f"# 微课堂：错题讲解\n\n"
        f"{persona_block}\n"
        f"{constraints_block}\n\n"
        f"## 学科\n{subject}\n\n"
        f"## knowledgeScope（严格边界，只用这里列的概念）\n{scope_block}\n"
        + "\n".join(mistake_blocks)
        + "\n\n请按上述要求生成大纲 JSON。\n"
    )
    return full_requirement


# ---------------------------------------------------------------------------
# Knowledge scope lookup
# ---------------------------------------------------------------------------

def load_scope_for_mistakes(mistakes: list, knowledge_points_root: Path, subject: str) -> dict:
    """For each mistake's knowledge_points, load the relevant KP definitions
    from D:/家教/{subject}/知识点及掌握情况/*.md or .json."""
    out = {"knowledge_points": []}
    seen_ids = set()
    subject = resolve_subject(subject)   # math → 数学
    subj_dir = knowledge_points_root / subject / "知识点及掌握情况"

    for m in mistakes:
        for kp_id in m.get("knowledge_points", []):
            if kp_id in seen_ids:
                continue
            seen_ids.add(kp_id)
            # Try .json first, fall back to .md
            json_path = subj_dir / f"{kp_id}.json"
            md_path = subj_dir / f"{kp_id}.md"
            if json_path.exists():
                try:
                    kp = json.loads(json_path.read_text(encoding="utf-8"))
                    out["knowledge_points"].append(kp)
                    continue
                except Exception:
                    pass
            if md_path.exists():
                # Minimal parse from markdown
                text = md_path.read_text(encoding="utf-8")
                kp = {
                    "id": kp_id,
                    "name": kp_id,
                    "definition": text[:200],
                    "example": "",
                }
                out["knowledge_points"].append(kp)
    return out


# ---------------------------------------------------------------------------
# OpenMAIC call
# ---------------------------------------------------------------------------

def submit_classroom(requirement: str, requirement_log_path: Path,
                     question_image_paths: list = None) -> str:
    """POST /api/generate-classroom, return jobId."""
    question_image_paths = question_image_paths or []
    images_b64 = []
    for p in question_image_paths:
        try:
            import base64
            with open(p, "rb") as f:
                images_b64.append(base64.b64encode(f.read()).decode("ascii"))
        except Exception as e:
            print(f"[warn] cannot read image {p}: {e}", file=sys.stderr)

    payload = {
        "requirement": requirement,
        "enableTTS": True,
        "enableImageGeneration": False,
        "enableWebSearch": False,
        "agentMode": "default",
    }
    if images_b64:
        payload["pdfContent"] = {"text": "", "images": images_b64}

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENMAIC_BASE}/api/generate-classroom",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            job_id = data.get("jobId")
            print(f"[submit] jobId={job_id}")
            requirement_log_path.write_text(requirement, encoding="utf-8")
            print(f"[submit] requirement saved to {requirement_log_path}")
            return job_id
    except urllib.error.URLError as e:
        print(f"[error] OpenMAIC not reachable at {OPENMAIC_BASE}: {e}", file=sys.stderr)
        print("        Start OpenMAIC with: cd /d/projects/OpenMAIC && pnpm dev", file=sys.stderr)
        sys.exit(2)


def poll_job(job_id: str, timeout_s: int = 600, interval_s: int = 5) -> dict:
    """Poll job status until completed/failed or timeout."""
    deadline = time.time() + timeout_s
    last_progress = -1
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{OPENMAIC_BASE}/api/generate-classroom/{job_id}",
                                         timeout=10) as resp:
                data = json.loads(resp.read())
                status = data.get("status", "unknown")
                progress = data.get("progress", 0)
                step = data.get("step", "?")
                if progress != last_progress:
                    print(f"[poll] {status} {progress}% step={step}")
                    last_progress = progress
                if status == "completed":
                    return data
                if status == "failed":
                    print(f"[poll] FAILED: {data.get('error', '?')}", file=sys.stderr)
                    sys.exit(3)
        except Exception as e:
            print(f"[warn] poll error: {e}", file=sys.stderr)
        time.sleep(interval_s)
    print(f"[error] timed out after {timeout_s}s", file=sys.stderr)
    sys.exit(4)


def fetch_classroom(classroom_id: str) -> dict:
    """Fetch the generated classroom JSON from OpenMAIC's data dir."""
    # OpenMAIC stores classrooms at D:/projects/OpenMAIC/data/classrooms/{id}.json
    p = Path(f"D:/projects/OpenMAIC/data/classrooms/{classroom_id}.json")
    if not p.exists():
        print(f"[error] classroom file not found: {p}", file=sys.stderr)
        sys.exit(5)
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_micro_lesson(classroom: dict) -> dict:
    """Sanity check the generated classroom. Returns a verification report."""
    scenes = classroom.get("scenes", [])
    report = {
        "total_scenes": len(scenes),
        "slide_only": all(s.get("type") == "slide" for s in scenes),
        "has_intro_greeting": False,
        "has_summary": False,
        "speech_texts": [],
    }
    greeting_patterns = ["同学们好", "今天我们", "欢迎来到", "今天我们来", "Hello everyone", "Welcome"]
    summary_patterns = ["今天我们学了", "总结一下", "我们来回顾", "Let's review", "Summary"]

    for s in scenes:
        for a in s.get("actions", []):
            if a.get("type") == "speech":
                txt = a.get("text", "")
                report["speech_texts"].append(txt[:80])
                if any(p in txt for p in greeting_patterns):
                    report["has_intro_greeting"] = True
                if any(p in txt for p in summary_patterns):
                    report["has_summary"] = True
    return report


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

DEMO_MISTAKES = [
    {
        "id": "q1",
        "question": "摄影小组有12人，是气象小组的1/3，航模小组的人数是摄影小组的3/4，求航模小组的人数。",
        "student_answer": "36",
        "correct_answer": "3",
        "correct_solution": "1. 摄影小组=12×1/3=4人  2. 航模小组=4×3/4=3人",
        "knowledge_points": ["math_day1_kp2"],
        "common_mistakes": ["未识别第二个单位1", "直接用12乘以两个分率"],
    },
    {
        "id": "q2",
        "question": "一根绳子长5米，剪去2/5，还剩多少米？",
        "student_answer": "2米",
        "correct_answer": "3米",
        "correct_solution": "5×(1-2/5)=5×3/5=3米",
        "knowledge_points": ["math_day1_kp1"],
        "common_mistakes": ["忘记减去已剪的部分", "分率理解错"],
    },
]

DEMO_SCOPE = {
    "knowledge_points": [
        {
            "id": "math_day1_kp1",
            "name": "求剩余部分（单位1乘以剩余分率）",
            "definition": "当题目说'剪去/用去/剩下几分之几'时，用 总量×(1-分率) 算出剩余。",
            "example": "5米的绳子剪去2/5，剩下=5×(1-2/5)=5×3/5=3米。",
        },
        {
            "id": "math_day1_kp2",
            "name": "单位1的识别",
            "definition": "单位1是被比较的基准量。题目里'是...的几分之几'，分母指向的就是单位1。",
            "example": "摄影小组12人，是气象小组的1/3。这里单位1是气象小组（12人）。",
        },
    ]
}


def main():
    parser = argparse.ArgumentParser(description="Generate a micro-lesson via OpenMAIC")
    parser.add_argument("--subject", default="math", help="Subject name (math/chinese/english)")
    parser.add_argument("--mistakes", help="Path to mistakes.json")
    parser.add_argument("--scope", help="Path to scope.json (otherwise auto-loaded from knowledge-points)")
    parser.add_argument("--tutor-root", default=str(DEFAULT_TUTOR_ROOT))
    parser.add_argument("--demo", action="store_true", help="Run a built-in demo")
    parser.add_argument("--no-submit", action="store_true", help="Only print the requirement, do not submit")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()

    tutor_root = Path(args.tutor_root)
    out_dir = tutor_root / resolve_subject(args.subject) / "课件"
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.demo:
        mistakes = DEMO_MISTAKES
        scope = DEMO_SCOPE
    else:
        if not args.mistakes:
            print("[error] --mistakes required (or use --demo)", file=sys.stderr)
            sys.exit(1)
        mistakes = json.loads(Path(args.mistakes).read_text(encoding="utf-8"))
        if args.scope:
            scope = json.loads(Path(args.scope).read_text(encoding="utf-8"))
        else:
            scope = load_scope_for_mistakes(mistakes, tutor_root, args.subject)
            print(f"[info] auto-loaded {len(scope['knowledge_points'])} knowledge points")

    requirement = build_micro_lesson_requirement(mistakes, scope, args.subject)

    if args.no_submit:
        print("=" * 60)
        print(requirement)
        print("=" * 60)
        print(f"\nRequirement length: {len(requirement)} chars")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    req_log = out_dir / f"micro_{ts}_requirement.txt"

    job_id = submit_classroom(requirement, req_log)

    print(f"[info] Polling job {job_id}...")
    final = poll_job(job_id, timeout_s=args.timeout)

    classroom_id = final.get("classroomId") or final.get("stageId") or job_id
    print(f"[info] Classroom id: {classroom_id}")

    classroom = fetch_classroom(classroom_id)

    # Save a copy under tutor root
    out_path = out_dir / f"micro_{ts}.json"
    out_path.write_text(json.dumps(classroom, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[ok] saved to {out_path}")

    # Verify
    report = verify_micro_lesson(classroom)
    print("\n=== Verification ===")
    print(f"Total scenes: {report['total_scenes']}")
    print(f"All slides (no widgets): {report['slide_only']}")
    print(f"Has intro greeting: {report['has_intro_greeting']}")
    print(f"Has summary: {report['has_summary']}")
    if report["speech_texts"]:
        print("\nFirst 5 speech snippets:")
        for t in report["speech_texts"][:5]:
            print(f"  - {t}")


if __name__ == "__main__":
    main()
