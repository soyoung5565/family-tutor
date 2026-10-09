#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
micro-lesson.py — 微课堂生成器（按“一道题一个微课堂”）

2026-09-25 升级（用户需求）：
  - 一道（大）题 = 一个微课堂：错题按“大题”分组，每组生成一课
  - 一道大题错了多个小题（如 3 个小题）= 只生成 1 个微课堂（不拆开）
  - 场景数 = 知识点去重数 N + 做错小题数 M + 1
      · 场景 1            错题还原（整道大题，圈出做错的小题）
      · 场景 2 ~ N+1      每个知识点一页讲解
      · 场景 N+2 ~ N+M+1  回归错题（每个做错的小题各用一页）
  - 学生订正期间先预生成（本脚本），订正后由 micro-publish.py 决定
    “直接复用 / 针对仍错小题重新生成 / 不需要”。

用法:
  预生成（按大题分组，每组生成一课；学生订正期间提前跑）:
    python micro-lesson.py --subject 数学 --mistakes mistakes.json
  单课模式（把传入的所有错题合并为一课，旧行为）:
    python micro-lesson.py --subject 数学 --mistakes x.json --single
  只看要求文本、不提交:
    python micro-lesson.py --demo --no-submit
  内置演示:
    python micro-lesson.py --demo

输入 mistakes.json：错题列表，每项：
    { "id": "q5_1", "group": "q5", "part_label": "(1)",
      "question": "...", "student_answer": "...",
      "correct_answer": "...", "correct_solution": "...",
      "knowledge_points": ["u2.k5"], "common_mistakes": ["..."] }
  分组规则：优先取 group/group_id/parent_id 字段；否则从 id 里
  第一个数字推断大题号（q5_1 / 5(2) / 第5题(1) → 第5题）。

输出:
    D:/家教/{subject}/课件/micro_{ts}_{组}.json            生成的课件
    D:/家教/{subject}/课件/micro_{ts}_{组}_requirement.txt  发出去的要求
    D:/家教/{subject}/课件/微课索引_{date}.json             预生成索引（微课发布用）
"""
import argparse
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

OPENMAIC_BASE = "http://localhost:3000"
DEFAULT_TUTOR_ROOT = Path("D:/家教")

SUBJECT_ALIAS = {
    "chinese": "语文", "语文": "语文",
    "english": "英语", "英语": "英语",
    "math": "数学", "mathematics": "数学", "数学": "数学",
}

# 分组：显式字段优先，其次从 id 推断
GROUP_FIELDS = ("group", "group_id", "parent_id", "major_id")

_PRINT_LOCK = threading.Lock()


def log(*args, **kwargs):
    """线程安全的 print（并发生成时输出不打架）"""
    with _PRINT_LOCK:
        print(*args, **kwargs, flush=True)


class MicroLessonError(Exception):
    """微课堂生成过程中的可预期错误"""


class OpenMAICUnreachable(MicroLessonError):
    pass


class JobFailed(MicroLessonError):
    pass


class JobTimeout(MicroLessonError):
    pass


class ClassroomNotFound(MicroLessonError):
    pass


def resolve_subject(subject):
    """规范化学科名（math → 数学）"""
    key = str(subject).strip().lower()
    if key in SUBJECT_ALIAS:
        return SUBJECT_ALIAS[key]
    return str(subject).strip()


def _natural_key(s):
    """自然排序键（q2 排在 q10 前面）"""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", str(s))]


def major_key(m):
    """判断一道错题属于哪个“大题”（微课堂的粒度单位）。"""
    for f in GROUP_FIELDS:
        v = m.get(f)
        if v is not None and str(v).strip():
            return str(v).strip()
    qid = str(m.get("id", "") or "")
    mm = re.search(r"\d+", qid)
    if mm:
        return "g" + mm.group(0)
    return qid or "g?"


def group_label(key):
    """组键 → 人类可读标签：q5 / g5 → 第5题"""
    mm = re.fullmatch(r"[a-zA-Z]*(\d+)", str(key))
    return f"第{mm.group(1)}题" if mm else str(key)


def group_mistakes(mistakes):
    """错题按大题分组：返回 OrderedDict{组键: [错题...]}（组内自然排序）"""
    groups = OrderedDict()
    for m in mistakes:
        groups.setdefault(major_key(m), []).append(m)
    for key in groups:
        groups[key].sort(key=lambda m: _natural_key(str(m.get("id", ""))))
    return groups


# ---------------------------------------------------------------------------
# Knowledge scope lookup
# ---------------------------------------------------------------------------

def load_scope_for_mistakes(mistakes, knowledge_points_root, subject):
    """For each mistake's knowledge_points, load the relevant KP definitions
    from D:/家教/{subject}/知识点及掌握情况/*.json or *.md."""
    out = {"knowledge_points": []}
    seen_ids = set()
    subject = resolve_subject(subject)
    subj_dir = Path(knowledge_points_root) / subject / "知识点及掌握情况"

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
                text = md_path.read_text(encoding="utf-8")
                out["knowledge_points"].append({
                    "id": kp_id,
                    "name": kp_id,
                    "definition": text[:200],
                    "example": "",
                })
    return out


# ---------------------------------------------------------------------------
# Requirement builder（一题一课：一道大题 = 一个微课堂）
# ---------------------------------------------------------------------------

def build_group_requirement(group_key, group_items, scope, subject):
    """给“一道大题”（含若干做错的小题）构建硬约束 requirement 文本。

    场景公式：N + M + 1（N = 知识点去重数，M = 做错的小题个数）
      · 场景 1            错题还原（整道大题，圈出做错的小题）
      · 之后按小题逐个交错：小题 i 的知识点页（一页一个） → 回到小题 i（做对并写出答案）
    """
    label = group_label(group_key)
    M = len(group_items)

    # 组内知识点去重（顺序稳定）
    kp_ids = []
    for m in group_items:
        for kp_id in m.get("knowledge_points", []):
            if kp_id not in kp_ids:
                kp_ids.append(kp_id)
    N = len(kp_ids)
    scene_count = N + M + 1

    kp_index = {kp["id"]: kp for kp in scope.get("knowledge_points", [])}

    persona_block = (
        "你是一位中国小学六年级的数学老师，正在给学生讲他做错的题。\n"
        "学生已经学过本学期内容，但在某些知识点上有漏洞。\n\n"
        "你的教学风格：\n"
        "- 把抽象概念一步一步拆开，从学生已经会的内容开始往上搭\n"
        "- 用视觉辅助（白板画图、写公式），让抽象概念变具体\n"
        "- 用词要符合六年级水平，不能超过小学六年级的范围\n"
    )

    if M == 1:
        intro = "这堂课只讲你面前这一道题（只有 1 个小题做错）。"
    else:
        intro = f"这堂课只讲你面前这一道大题（{M} 个小题都做错了），合并为一堂课讲，不要拆开。"

    # 场景清单：按「小题」逐个交错 —— 该小题知识点 → 回到该小题（用户 2026-09-25 要求）
    scene_lines = []
    taught = set()
    sn = 2
    for i, m in enumerate(group_items, 1):
        part = str(m.get("part_label") or m.get("id", "?"))
        new_kps = [k for k in m.get("knowledge_points", []) if k not in taught]
        if new_kps:
            names = "、".join(kp_index.get(k, {}).get("name", k) for k in new_kps)
            if len(new_kps) == 1:
                scene_lines.append(
                    f"   - 场景 {sn}：小题 {i}（{part}）的知识点讲解——{names}（一页只讲这一个知识点，直接精讲、无引入）。")
            else:
                scene_lines.append(
                    f"   - 场景 {sn} ~ {sn + len(new_kps) - 1}：小题 {i}（{part}）的知识点讲解（每个知识点一页，直接精讲、无引入）——{names}。")
            sn += len(new_kps)
            taught.update(new_kps)
        extra = "（沿用前面小题已讲过的知识点）" if not new_kps else ""
        scene_lines.append(
            f"   - 场景 {sn}：回到小题 {i}（{part}）：用刚讲的方法把它做对，写出这个小题的正确答案{extra}。")
        sn += 1
    scene_list_text = "\n".join(scene_lines)

    constraints_block = (
        "\n## 硬性约束（必须严格遵守）\n\n"
        + intro + "\n\n"
        f"1. 总场景数必须为 (N + M + 1)，其中 N = 知识点数（去重后），M = 做错的小题个数。"
        f"本课 N={N}、M={M} → 必须生成 {scene_count} 个场景，顺序严格如下：\n"
        "   - 场景 1：错题还原 + 题目分析。在白板写出这道题的完整原题（所有小题都要写出），圈出学生做错的小题；\n"
        "   讲解必须对题目本身做分析（像老师带读题一样拆解）：题目在问什么、已知哪些条件、关键句和数量关系是什么、\n"
        "   每个小题/选项该怎么读；并把学生的错误答案与题意对照（点出他当时大概怎么想的、错在哪个环节）。\n"
        "   但不给正确答案、不揭晓正确解法。\n"
        + scene_list_text + "\n"
        "   ⚠️ 必须按『小题』逐个讲解：先讲该小题对应的知识点，紧接着就回到这道小题把它做对；"
        "严禁把几个小题的知识点集中在一起讲完、再统一回归错题。\n\n"
        "2. 禁止任何开场白、总结页、过渡页。知识点讲解页必须直接精讲：严禁「同学们好」「欢迎」「今天我们来学习/认识…」\n"        "   等新课引入口吻，严禁预习式铺垫（生活例子预热、「新朋友」式比喻开场、课程目标介绍）；每页第一句话就要切入知识点本体\n"        "   （它是什么、和做错的小题什么关系）。禁止词清单（知识点页第一句里绝对不允许出现）：\n"
        "   「同学们好」「大家好」「欢迎」「今天我们一起来认识/学习」「我们一起来看」「新朋友」；\n"
        "   第一句请直接写成如「这道小题用到的是——…」或「我们先把…弄清楚：」这类入手句。\n\n"
        "3. 只能使用 slide 场景。禁止任何 widget（simulation / diagram / game / visualization3d / code / quiz）。\n\n"
        "4. 一页只能讲一个知识点。\n\n"
        "5. 只能使用下方 knowledgeScope 列出的概念和例子。严禁引入 knowledgeScope 之外的概念。\n"
        "6. 本课面对一位学生（一对一错题订正）：人称只能用「你 / 我们 / 咱们」；严禁任何班级群体词——全班、班里、同学们、大家、各位、课堂上、举手、上台；更要禁止编造题目之外的情节（如「全班都做错了」「课上讲过」「大家都看到了」）。\n"
    )

    # Mistake blocks（逐小题展开）
    mistake_blocks = []
    for i, m in enumerate(group_items, 1):
        kps = m.get("knowledge_points", [])
        kp_names = [kp_index.get(kp_id, {}).get("name", kp_id) for kp_id in kps]

        common_mistakes = m.get("common_mistakes", [])
        mistakes_text = "\n".join(f"  - {cm}" for cm in common_mistakes) if common_mistakes else "  （暂无）"

        part_label = str(m.get("part_label") or m.get("id", "?"))
        block = f"""
### 做错的小题 {i}（{part_label}）

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
    scope_block = "\n".join(scope_lines) if scope_lines else "（无相关知识点，按错题还原+回归错题处理）"

    if M == 1:
        title = f"## 这道题（{label}）"
    else:
        title = f"## 这道大题（{label}，做错 {M} 个小题，合并为一堂课）"

    full_requirement = (
        f"# 微课堂：错题讲解（{label}）\n\n"
        f"{persona_block}\n"
        f"{constraints_block}\n\n"
        f"## 学科\n{subject}\n\n"
        f"## knowledgeScope（严格边界，只用这里列的概念）\n{scope_block}\n"
        f"\n{title}\n"
        + "".join(mistake_blocks)
        + "\n\n请按上述要求生成大纲 JSON。\n"
    )
    return full_requirement


# ---------------------------------------------------------------------------
# OpenMAIC call
# ---------------------------------------------------------------------------

def submit_classroom(requirement, requirement_log_path, question_image_paths=None):
    """POST /api/generate-classroom 返回 jobId。提交前把 requirement 落盘。
    失败抛 OpenMAICUnreachable。"""
    question_image_paths = question_image_paths or []
    images_b64 = []
    for p in question_image_paths:
        try:
            import base64
            with open(p, "rb") as f:
                images_b64.append(base64.b64encode(f.read()).decode("ascii"))
        except Exception as e:
            log(f"[warn] cannot read image {p}: {e}")

    payload = {
        "requirement": requirement,
        "enableTTS": True,
        "enableImageGeneration": False,
        "enableWebSearch": False,
        "agentMode": "default",
    }
    if images_b64:
        payload["pdfContent"] = {"text": "", "images": images_b64}

    requirement_log_path.write_text(requirement, encoding="utf-8")

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{OPENMAIC_BASE}/api/generate-classroom",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data.get("jobId")
    except urllib.error.URLError as e:
        raise OpenMAICUnreachable(
            f"OpenMAIC 不可达（{OPENMAIC_BASE}）：{e}；请先启动 OpenMAIC（cd /d/projects/OpenMAIC && pnpm dev）"
        )


def poll_job(job_id, timeout_s=600, interval_s=5, label=""):
    """轮询 job 直到 completed / failed / 超时。
    completed 返回 data；failed 抛 JobFailed；超时抛 JobTimeout。"""
    prefix = f"[{label}] " if label else ""
    deadline = time.time() + timeout_s
    last_progress = -1
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{OPENMAIC_BASE}/api/generate-classroom/{job_id}", timeout=10
            ) as resp:
                data = json.loads(resp.read())
            status = data.get("status", "unknown")
            progress = data.get("progress", 0)
            step = data.get("step", "?")
            if progress != last_progress:
                log(f"{prefix}[poll] {status} {progress}% step={step}")
                last_progress = progress
            if status == "failed":
                raise JobFailed(f"生成失败：{data.get('error', '?')}")
            if status in ("completed", "succeeded") or data.get("done"):
                return data
        except JobFailed:
            raise
        except Exception as e:
            log(f"{prefix}[warn] poll error: {e}")
        time.sleep(interval_s)
    raise JobTimeout(f"生成超时（{timeout_s}s）")


def fetch_classroom(classroom_id):
    """从 OpenMAIC 数据目录读取生成的课件 JSON。找不到抛 ClassroomNotFound。"""
    # OpenMAIC stores classrooms at D:/projects/OpenMAIC/data/classrooms/{id}.json
    p = Path(f"D:/projects/OpenMAIC/data/classrooms/{classroom_id}.json")
    if not p.exists():
        raise ClassroomNotFound(f"课件文件不存在：{p}")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify_micro_lesson(classroom):
    """对生成的课件做基础校验，返回报告 dict。"""
    scenes = classroom.get("scenes", [])
    report = {
        "total_scenes": len(scenes),
        "slide_only": all(s.get("type") == "slide" for s in scenes) if scenes else False,
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
# Group generation（一个组 = 一个微课堂）
# ---------------------------------------------------------------------------

def generate_group(group_key, group_items, subject, tutor_root, out_dir, timeout, ts,
                   scope=None, tag=""):
    """生成一个微课堂（一道大题）。成功返回结果 dict；
    失败抛 MicroLessonError 子类（由 generate_groups 捕获并记录）。"""
    label = group_label(group_key)
    subject = resolve_subject(subject)

    if scope is None:
        scope = load_scope_for_mistakes(group_items, tutor_root, subject)
        log(f"[{label}] 知识点加载：{len(scope['knowledge_points'])} 个")

    requirement = build_group_requirement(group_key, group_items, scope, subject)
    req_log = out_dir / f"micro_{ts}_{group_key}{tag}_requirement.txt"
    out_path = out_dir / f"micro_{ts}_{group_key}{tag}.json"

    log(f"[{label}] 提交生成（{len(group_items)} 个小题，requirement {len(requirement)} 字符）...")
    job_id = submit_classroom(requirement, req_log)
    if not job_id:
        raise JobFailed("提交后未返回 jobId")
    log(f"[{label}] jobId={job_id}，等待生成...")

    final = poll_job(job_id, timeout_s=timeout, label=label)
    _res = final.get("result") or {}
    classroom_id = (
        final.get("classroomId")
        or (_res.get("classroomId") if isinstance(_res, dict) else None)
        or final.get("stageId")
        or job_id
    )

    classroom = fetch_classroom(classroom_id)
    out_path.write_text(json.dumps(classroom, ensure_ascii=False, indent=2), encoding="utf-8")
    report = verify_micro_lesson(classroom)

    log(f"[{label}] OK 完成 -> {out_path.name}（{report['total_scenes']} 个场景，全 slide={report['slide_only']}）")
    return {
        "group_key": group_key,
        "label": label,
        "mistake_ids": [str(m.get("id")) for m in group_items],
        "status": "ready",
        "job_id": job_id,
        "classroom_id": classroom_id,
        "lesson_file": str(out_path),
        "requirement_file": str(req_log),
        "verified": report,
        "error": None,
    }


def generate_groups(groups, subject, tutor_root, out_dir, timeout, ts,
                    concurrency=2, scopes=None, tag=""):
    """并发生成多个微课堂。返回 OrderedDict{组键: 结果 dict}（失败项也包含在内）。"""
    items = list(groups.items())
    results = {}

    def work(key, gitems):
        scope = (scopes or {}).get(key)
        try:
            return generate_group(key, gitems, subject, tutor_root, out_dir, timeout, ts,
                                  scope=scope, tag=tag)
        except Exception as e:
            label = group_label(key)
            log(f"[{label}] 生成失败：{type(e).__name__}: {e}")
            return {
                "group_key": key, "label": label,
                "mistake_ids": [str(m.get("id")) for m in gitems],
                "status": "failed", "job_id": None, "classroom_id": None,
                "lesson_file": None, "requirement_file": None,
                "verified": None, "error": f"{type(e).__name__}: {e}",
            }

    if concurrency and concurrency > 1 and len(items) > 1:
        with ThreadPoolExecutor(max_workers=min(concurrency, len(items))) as ex:
            futs = {ex.submit(work, k, v): k for k, v in items}
            for fut in as_completed(futs):
                res = fut.result()
                results[res["group_key"]] = res
    else:
        for k, v in items:
            res = work(k, v)
            results[res["group_key"]] = res

    return OrderedDict((k, results[k]) for k, _ in items)


# ---------------------------------------------------------------------------
# Micro-lesson index（预生成索引；micro-publish.py 依赖它判断“能不能复用”）
# ---------------------------------------------------------------------------

def index_date_str():
    return datetime.now().strftime("%Y-%m-%d")


def write_index(index_path, subject, mistakes_file, results):
    """写/合并索引文件。其他组条目保留；本次更新到的组，post 字段重置为 None。"""
    index_path = Path(index_path)
    data = {}
    if index_path.exists():
        try:
            data = json.loads(index_path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data["subject"] = resolve_subject(subject)
    data["date"] = index_date_str()
    data["updated_at"] = datetime.now().isoformat(timespec="seconds")
    if mistakes_file:
        data["mistakes_file"] = str(mistakes_file)
    groups = data.setdefault("groups", {})
    for key, res in results.items():
        groups[key] = {
            "group_key": key,
            "label": res.get("label"),
            "mistake_ids": res.get("mistake_ids", []),
            "status": res.get("status"),
            "job_id": res.get("job_id"),
            "classroom_id": res.get("classroom_id"),
            "lesson_file": res.get("lesson_file"),
            "requirement_file": res.get("requirement_file"),
            "verified": res.get("verified"),
            "error": res.get("error"),
            "post": None,
        }
    index_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def read_index(index_path):
    p = Path(index_path)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def update_index_post(index_path, group_key, post):
    """把订正阶段的决定写回索引（micro-publish.py 用）。"""
    data = read_index(index_path)
    if data is None:
        return False
    g = data.get("groups", {}).get(group_key)
    if g is None:
        return False
    g["post"] = post
    Path(index_path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def find_latest_index(kecheng_dir):
    """在课件目录里找最新的 微课索引_*.json。"""
    cands = sorted(Path(kecheng_dir).glob("微课索引_*.json"),
                   key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

DEMO_MISTAKES = [
    # 大题 5：圆的周长与面积（3 个小题都做错 -> 只生成 1 个微课堂）
    {
        "id": "q5_1", "group": "q5", "part_label": "(1)",
        "question": "一个圆形花坛的半径是 3 米，它的周长是多少米？（π 取 3.14）",
        "student_answer": "18.84 平方米",
        "correct_answer": "18.84 米",
        "correct_solution": "C = 2πr = 2 × 3.14 × 3 = 18.84（米）。周长单位是米，不是平方米。",
        "knowledge_points": ["demo_kp_c"],
        "common_mistakes": ["单位写成平方米"],
    },
    {
        "id": "q5_2", "group": "q5", "part_label": "(2)",
        "question": "同一个花坛，它的面积是多少平方米？",
        "student_answer": "18.84 平方米",
        "correct_answer": "28.26 平方米",
        "correct_solution": "S = πr² = 3.14 × 3² = 28.26（平方米）。",
        "knowledge_points": ["demo_kp_s"],
        "common_mistakes": ["用周长公式算面积"],
    },
    {
        "id": "q5_3", "group": "q5", "part_label": "(3)",
        "question": "在花坛外围铺一条 1 米宽的小路，小路的面积是多少平方米？",
        "student_answer": "3.14 平方米",
        "correct_answer": "21.98 平方米",
        "correct_solution": "外圆半径 4 米：S外 = 3.14 × 16 = 50.24；S内 = 3.14 × 9 = 28.26；小路 = 50.24 - 28.26 = 21.98（平方米）。",
        "knowledge_points": ["demo_kp_s", "demo_kp_ring"],
        "common_mistakes": ["只算了一个圆", "忘记减去内圆面积"],
    },
    # 单题 2（只有 1 个小题做错）
    {
        "id": "q2", "part_label": "",
        "question": "一根绳子长 5 米，剪去 2/5，还剩多少米？",
        "student_answer": "2 米",
        "correct_answer": "3 米",
        "correct_solution": "5 × (1 - 2/5) = 5 × 3/5 = 3（米）。",
        "knowledge_points": ["demo_kp_frac"],
        "common_mistakes": ["直接算出剪去的部分当作剩余"],
    },
]

DEMO_SCOPE = {
    "knowledge_points": [
        {
            "id": "demo_kp_c",
            "name": "圆的周长",
            "definition": "圆一周的长度：C = 2πr（或 πd）。",
            "example": "半径 3 米的花坛，周长 = 2 × 3.14 × 3 = 18.84 米。",
        },
        {
            "id": "demo_kp_s",
            "name": "圆的面积",
            "definition": "S = πr²，先平方半径再乘 π。",
            "example": "半径 3 米，面积 = 3.14 × 9 = 28.26 平方米。",
        },
        {
            "id": "demo_kp_ring",
            "name": "环形（小路）面积",
            "definition": "环形面积 = 外圆面积 - 内圆面积。",
            "example": "半径 3 米的花坛外包 1 米小路：小路 = π(4² - 3²) = 3.14 × 7 = 21.98 平方米。",
        },
        {
            "id": "demo_kp_frac",
            "name": "求剩余部分",
            "definition": "剪去/用去几分之几后，剩余 = 总量 × (1 - 分率)。",
            "example": "5 米绳子剪去 2/5，剩 5 × 3/5 = 3 米。",
        },
    ]
}


def _demo_scope_for(group_items):
    """demo 用：按组内知识点过滤 DEMO_SCOPE"""
    kp_ids = set()
    for m in group_items:
        kp_ids.update(m.get("knowledge_points", []))
    return {"knowledge_points": [kp for kp in DEMO_SCOPE["knowledge_points"] if kp["id"] in kp_ids]}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate micro-lesson(s): one per major question")
    parser.add_argument("--subject", default=None, help="Subject (math/chinese/english/中文); 缺省时自动读 mistakes 文件的 subject")
    parser.add_argument("--mistakes", help="Path to mistakes.json")
    parser.add_argument("--scope", help="Path to scope.json (otherwise auto-loaded)")
    parser.add_argument("--tutor-root", default=str(DEFAULT_TUTOR_ROOT))
    parser.add_argument("--demo", action="store_true", help="Built-in demo (group of 3 + single)")
    parser.add_argument("--no-submit", action="store_true", help="Only print requirement(s), do not submit")
    parser.add_argument("--single", action="store_true", help="Legacy: merge all mistakes into ONE lesson")
    parser.add_argument("--timeout", type=int, default=900, help="Per-lesson generation timeout (s)")
    parser.add_argument("--concurrency", type=int, default=2, help="Parallel lessons (default 2)")
    args = parser.parse_args()

    tutor_root = Path(args.tutor_root)
    # subject 解析：优先 --subject；否则读 mistakes 文件的 subject 字段；最后兜底 math
    auto_subject = None
    if args.mistakes:
        try:
            auto_subject = json.loads(Path(args.mistakes).read_text(encoding="utf-8")).get("subject")
            print(f"[学科] 自动识读 mistakes 文件 subject = {auto_subject}")
        except Exception as e:
            print(f"[学科] 读取 mistakes subject 失败: {e}")
    subject_cn = resolve_subject(args.subject or auto_subject or "math")
    out_dir = tutor_root / subject_cn / "课件"
    out_dir.mkdir(parents=True, exist_ok=True)

    mistakes_file = None
    manual_scope = None
    if args.demo:
        mistakes = DEMO_MISTAKES
    else:
        if not args.mistakes:
            print("[error] --mistakes required (or use --demo)", file=sys.stderr)
            sys.exit(1)
        mistakes_file = Path(args.mistakes)
        mistakes = json.loads(mistakes_file.read_text(encoding="utf-8"))
        if isinstance(mistakes, dict):
            mistakes = mistakes.get("mistakes") or mistakes.get("items") or []
        if args.scope:
            manual_scope = json.loads(Path(args.scope).read_text(encoding="utf-8"))

    if args.single:
        groups = OrderedDict([("single", list(mistakes))])
    else:
        groups = group_mistakes(mistakes)

    # 每组 scope：demo=按组过滤；manual=统一；否则自动加载（延迟到组内执行）
    scopes = {}
    for key, gitems in groups.items():
        if args.demo:
            scopes[key] = _demo_scope_for(gitems)
        elif manual_scope is not None:
            scopes[key] = manual_scope
        else:
            scopes[key] = None

    log(f"共 {len(groups)} 个微课堂任务：")
    for key, gitems in groups.items():
        ids = ", ".join(str(m.get("id")) for m in gitems)
        log(f"  - {group_label(key)}（{len(gitems)} 个小题）: {ids}")

    if args.no_submit:
        for key, gitems in groups.items():
            scope = scopes[key]
            if scope is None:
                scope = load_scope_for_mistakes(gitems, tutor_root, subject_cn)
            req = build_group_requirement(key, gitems, scope, subject_cn)
            print("=" * 60)
            print(f"【{group_label(key)}】requirement ({len(req)} chars)")
            print("=" * 60)
            print(req)
            print()
        print(f"[no-submit] 共 {len(groups)} 个 requirement，未提交。")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = generate_groups(groups, subject_cn, tutor_root, out_dir, args.timeout, ts,
                              concurrency=args.concurrency, scopes=scopes)

    ok = [r for r in results.values() if r["status"] == "ready"]
    failed = [r for r in results.values() if r["status"] != "ready"]

    if not args.single:
        index_path = out_dir / f"微课索引_{index_date_str()}.json"
        write_index(index_path, subject_cn, str(mistakes_file) if mistakes_file else "[demo]", results)
        log(f"\n[ok] {len(ok)}/{len(results)} 个微课堂生成成功")
        for r in ok:
            log(f"    {r['label']}: {Path(r['lesson_file']).name}"
                f"（{r['verified']['total_scenes']} 场景）"
                f" -> {OPENMAIC_BASE}/classroom/{r['classroom_id']}")
        for r in failed:
            log(f"    [失败] {r['label']}: {r['error']}")
        log(f"[ok] 索引：{index_path}")
        if failed:
            sys.exit(1)
    else:
        r = results.get("single")
        if r and r["status"] == "ready":
            log(f"\n[ok] 已保存：{r['lesson_file']}")
            rep = r["verified"]
            log(f"    总场景数：{rep['total_scenes']}  全 slide：{rep['slide_only']}"
                f"  开场白：{rep['has_intro_greeting']}  总结页：{rep['has_summary']}")
        else:
            log(f"[error] 生成失败：{r['error'] if r else '未知'}")
            sys.exit(1)


if __name__ == "__main__":
    main()
