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
  --format question     题目卷（Markdown + HTML）
  --format dictation    默写卷
  --format remediation  错题回灌卷（★必做）
  --format listening    听写包
  --format recitation   背诵检查表

2026-09-27 调整（用户要求）：
  ① 出卷自动带「错题回灌」——从错题集抽历史错题（原题优先），卷面标 ★必做；
  ② 卷尾固定附「错题本提醒」；含回灌题时附「必做」提示；
  ③ 落「试卷标记_{subject}_{ts}.json」——批改时用于识别历史错题再次做错；
  ④ 选题质量过滤：剔除空答案/“略”/“见题干”；难度按规范分布；KP 覆盖优先；
  ⑤ 新增 --count / --kp-filter / --reflow-max / --label；新增 HTML 版输出。

执行示例：
  # 单元复习卷（数学 u1）
  python generate-exam.py \
      --subject 数学 --format question --scope u1 --type unit-review \
      --output D:/家教/数学/试卷/

  # 周末小测（学到第二单元第 4 课，只覆盖已学 KP）
  python generate-exam.py \
      --subject 数学 --format question --scope u2 \
      --kp-filter u2.k1,u2.k2,u2.k3,u2.k4,u2.k5 \
      --label "第二单元·周末小测" --count 18 \
      --output D:/家教/数学/试卷/

  # 错题回灌
  python generate-exam.py \
      --subject 数学 --format remediation --kp-ids u5.k3 \
      --output D:/家教/数学/试卷/

作者：Hermes 家庭教师系统
最后更新：2026-09-27
"""

import argparse
import html as html_mod
import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


# ────────────────────────── 基础工具 ──────────────────────────

# 不可用答案（空答/略/见题干等）——出卷时剔除，避免答案页开天窗
_BAD_ANSWERS = {"", "略", "略。", "（略）", "见题干", "见原卷", "答案略", "无", "..."}

DIFF_ORDER = ["易", "中", "难"]
_ORD = "一二三四五六七八九十"


def answer_usable(q: dict) -> bool:
    a = q.get("answer")
    if a is None:
        return False
    a = str(a).strip()
    if a in _BAD_ANSWERS or len(a) > 200:
        return False
    opts = q.get("options") or []
    if opts and re.fullmatch(r"\d{1,2}", a) and not (0 <= int(a) < len(opts)):
        # 数字型答案只看：选项文本里有没有它；没有且索引越界 → 视为坏答案
        if a not in [str(o).strip() for o in opts]:
            return False
    return True


def _norm_stem(s: str) -> str:
    return re.sub(r"[\s\u3000，。、：；（）()【】\[\]！？!?\"'“”‘’·—\-_/\\|]+", "", str(s or ""))


def _stem_key(s: str) -> str:
    return _norm_stem(s)[:60]


# 引用外部短文/选段或配图、无法独立作答的题——选题时降级
_PASSAGE_REF = re.compile(r"选文|上文|下文|文中|选段|短文|阅读材料|画线|联系选|本段|自然段|语段|以下文段|根据对话|听录音|听音")


_FIGURE_REF = re.compile(r"如下图|下图|上图|如图|图中|看图|照片|图片|图\s*[1-9①-⑨①-⑨]|[A-D]\s*点|在图形上|影子|方格|格子|画图说明|能看到|图形中")


_CROSSGRADE = re.compile(r"真命题|边心距|中心角")

_CLOZE_BLANK = re.compile(r"_{2,}\s*\d+\s*_{2,}")  # 完形填空带编号空（____24____）


def _selfcontained(q: dict) -> bool:
    stem = str(q.get("stem", "")).strip()
    if len(stem) < 6:
        return False
    # 语文/数学必须是中文题（防题库混入英文题）
    if str(q.get("subject", "")) in ("数学", "语文"):
        if len(re.findall(r"[\u4e00-\u9fff]", stem)) < 4:
            return False
    if _PASSAGE_REF.search(stem) and len(stem) < 140:
        return False
    if _FIGURE_REF.search(stem):
        return False
    if "看拼音" in stem and not re.search(r"[a-zA-Z]", stem):
        return False  # "看拼音写字词"但卷面没有拼音 → 缺材料
    if "填写序号" in stem and not re.search(r"[①②③④]|[A-D][．.、]", stem):
        return False  # "填写序号"但没有可选序号列表 → 缺材料
    if re.search(r"的一项是\s*[（(]", stem) and not q.get("options"):
        return False  # "…的一项是（ ）"但无选项列表 → 缺材料
    if "思维导图" in stem:
        return False  # 补全思维导图 → 卷面缺导图
    if "空格处应填" in stem:
        return False  # 机翻碎片题（缺上下文/选项）
    if _CROSSGRADE.search(stem):
        return False
    if _CLOZE_BLANK.search(stem):
        return False
    opts = q.get("options")
    if opts:
        # 题干里自带一套选项（会与选项区重复）
        if len(re.findall(r"[ABCD]\s*[．.、]", stem)) >= 2:
            return False
        # 多小题合并成一道带选项的题（渲染会乱）
        if len(re.findall(r"[（(]\d[）)]", stem)) >= 2:
            return False
    # 多选答案但题干说“一项”（自相矛盾）
    ans = str(q.get("answer") or "").strip()
    if re.fullmatch(r"[A-D]{2,4}", ans) and "一项" in stem:
        return False
    t = str(q.get("type", ""))
    if ("阅读" in t) and len(stem) < 100 and ("《" not in stem) and ("“" not in stem):
        return False
    return True


def _get_kp_name(kp_id: str, subject: str, base_dir: str) -> str:
    """读取 KP 名称"""
    try:
        kp_file = Path(base_dir) / subject / "知识点及掌握情况" / f"{kp_id}.json"
        if kp_file.exists():
            data = json.loads(kp_file.read_text(encoding="utf-8"))
            return data.get("name", kp_id)
    except Exception:
        pass
    return kp_id


def _parse_scope(scope: str) -> list:
    if "-" in scope:
        return [f"u{i}" for i in range(int(scope.split("-")[0][1:]), int(scope.split("-")[1][1:]) + 1)]
    if "," in scope:
        return [s.strip() for s in scope.split(",")]
    return [scope]


def _difficulty_buckets(target: int, exam_type: str) -> dict:
    dist = {
        "unit-review": {"易": 0.50, "中": 0.35, "难": 0.15},
        "midterm":     {"易": 0.30, "中": 0.50, "难": 0.20},
        "final":       {"易": 0.25, "中": 0.50, "难": 0.25},
    }.get(exam_type, {"易": 0.50, "中": 0.35, "难": 0.15})
    want = {d: int(round(target * r)) for d, r in dist.items()}
    diff = target - sum(want.values())
    if diff:
        want["中"] += diff
    return want


def recent_mistake_records(subject: str, base_dir: Path, days: int = 21) -> list:
    """读错题集近 N 天记录（用于错题回灌，旧→新排序）"""
    out = []
    mdir = base_dir / subject / "错题集"
    if not mdir.exists():
        return out
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for f in sorted(mdir.glob("错题集_*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for r in data.get("records", []):
            if str(r.get("date", "")) >= cutoff:
                out.append(r)
    out.sort(key=lambda r: str(r.get("date", "")))
    return out


def format_answer(q: dict) -> str:
    """答案展示：选择题还原成 字母．选项文本（先文本匹配，再索引）"""
    ans = q.get("answer")
    if ans is None:
        return "（略）"
    ans = str(ans)
    opts = q.get("options") or []
    if opts:
        idx = None
        for i, o in enumerate(opts):
            if str(o).strip() == ans.strip():
                idx = i
                break
        if idx is None and re.fullmatch(r"\d{1,2}", ans):
            i = int(ans)
            if 0 <= i < len(opts):
                idx = i
        if idx is not None:
            return f"{chr(65 + idx)}．{opts[idx]}"
    return ans


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


def get_weak_kps(state: dict, subject: str, restrict: set = None) -> list:
    """从学习状态.json 取薄弱 KP（master < 60）；restrict=只在这些 KP 里取"""
    kps = state["subjects"][subject]["kps"]
    out = []
    for kp_id, kp in kps.items():
        if restrict is not None and kp_id not in restrict:
            continue
        if kp["master"] < 60:
            out.append(kp_id)
    return out


_LETTER_REF = re.compile(r"(?:故选|所以选|选)\s*[A-D]|[ABCD]\s*[项对错．.、]")


def _shuffle_safe(q: dict) -> bool:
    """选项打乱安全性：多选字母答案 / 解析引用选项字母的题不打乱"""
    ans = str(q.get("answer", "")).strip()
    if re.fullmatch(r"[A-D]{1,4}", ans):
        return False
    expl = str(q.get("explanation", "") or "")
    if _LETTER_REF.search(expl):
        return False
    return True


def _clean_expl(q: dict) -> str:
    """清理解析：去掉与选项顺序失配的“故选A”类片段"""
    e = str(q.get("explanation") or "").strip()
    e = re.sub(r"(?:故选|所以选|答案为)\s*[A-D][。．.；;，,]?", "", e).strip()
    if e in ("略", "略。"):
        e = ""
    return e


def shuffle_options(question: dict) -> dict:
    """打乱选项（沿用 answer-distribution-randomization 规则；兼容答案为文本/索引）"""
    if not question.get("options"):
        return question

    correct_answer = question["answer"]
    options = list(question["options"])

    correct_value = None
    if isinstance(correct_answer, str):
        for o in options:
            if str(o).strip() == correct_answer.strip():
                correct_value = o
                break
    if correct_value is None:
        idx = None
        if isinstance(correct_answer, int):
            idx = correct_answer
        elif isinstance(correct_answer, str) and re.fullmatch(r"\d{1,2}", correct_answer.strip()):
            idx = int(correct_answer)
        if idx is not None and 0 <= idx < len(options):
            correct_value = options[idx]
    if correct_value is None:
        return question  # 无法定位答案 → 不打乱，保安全

    indices = list(range(len(options)))
    random.shuffle(indices)
    new_options = [options[i] for i in indices]

    new_correct_idx = new_options.index(correct_value)

    q = dict(question)
    q["options"] = new_options
    q["answer"] = new_correct_idx  # 统一存索引（int）；渲染时按 字母．选项文本 展示
    return q


# ────────────────────────── 出卷：题目卷 ──────────────────────────

def _make_reflow_items(subject: str, args, scoped_kps: set, max_n: int, pool: dict = None) -> list:
    """构造错题回灌题（错题集原题优先；P9 规则：每周小测强制含）"""
    base = Path(getattr(args, "_base_dir", "D:/家教"))
    recs = recent_mistake_records(subject, base, days=21)
    cand = []
    for r in recs:
        rk = [k for k in (r.get("kp_ids") or []) if (scoped_kps is None or k in scoped_kps)]
        if rk:
            cand.append(r)
    seen, picked = set(), []
    for r in sorted(cand, key=lambda x: str(x.get("date", "")), reverse=True):
        key = _stem_key(r.get("question", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        picked.append(r)
    # 题库原题索引（补全选项/答案格式用）
    bank_by_key = {}
    if pool:
        for q in pool["questions"].values():
            bank_by_key.setdefault(_stem_key(q.get("stem", "")), q)
    items = []
    for r in picked[:max_n]:
        kp0 = (r.get("kp_ids") or ["复习"])[0]
        note = "上次错在：" + ("；".join((r.get("common_mistakes") or [])[:2]) or "见错题本")
        bank_q = bank_by_key.get(_stem_key(r.get("question", "")))
        ans = r.get("correct_answer") or (bank_q or {}).get("answer") or "（见错题本订正）"
        items.append({
            "qid": f"reflow_{r.get('date', '')}_{len(items) + 1}",
            "subject": subject,
            "kp_id": kp0,
            "unit_id": kp0.split(".")[0] if "." in kp0 else kp0,
            "difficulty": "中",
            "type": "错题回灌",
            "stem": r.get("question", ""),
            "options": (bank_q or {}).get("options"),
            "answer": ans,
            "explanation": r.get("correct_solution") or (bank_q or {}).get("explanation") or "",
            "reflow": True,
            "reflow_date": r.get("date", ""),
            "reflow_note": note,
            "source": "错题集原题回灌",
        })
    return items


def generate_question_exam(args, state, pool) -> dict:
    """生成题目卷（Markdown + HTML）：KP 覆盖 + 难度分布 + 错题回灌（★必做）"""
    subject = args.subject
    scope = args.scope
    exam_type = args.type
    target_count = int(getattr(args, "count", 0) or 0) or {
        "unit-review": 10, "midterm": 12, "final": 15,
    }.get(exam_type, 9)

    unit_ids = _parse_scope(scope)
    kp_filter = [s.strip() for s in args.kp_filter.split(",")] if getattr(args, "kp_filter", None) else None
    scoped_kps = set(kp_filter) if kp_filter else None

    # 候选池：范围 + 已启用 + 答案可用
    available = []
    for qid, q in pool["questions"].items():
        if not q.get("enabled") or q.get("unit_id") not in unit_ids:
            continue
        if scoped_kps is not None and q.get("kp_id") not in scoped_kps:
            continue
        if not answer_usable(q):
            continue
        available.append(q)

    # ── 错题回灌（历史错题；卷面标 ★必做） ──
    reflow_max = int(getattr(args, "reflow_max", 0) or 2)
    reflow_items = _make_reflow_items(subject, args, scoped_kps, reflow_max, pool)

    # ── 组卷：KP 覆盖优先 → 难度分布补足 ──
    used_keys = {_stem_key(i["stem"]) for i in reflow_items}
    bank_all = [q for q in available if _stem_key(q.get("stem", "")) not in used_keys]
    bank_pref = [q for q in bank_all if _selfcontained(q)]
    remaining = max(0, target_count - len(reflow_items))
    bank = bank_pref if len(bank_pref) >= remaining * 2 else bank_all
    want = _difficulty_buckets(remaining, exam_type)

    sub_state = state["subjects"].get(subject, {})
    target_kps = []
    for kp_id, kp in sub_state.get("kps", {}).items():
        if kp.get("unit_id") in unit_ids and (scoped_kps is None or kp_id in scoped_kps):
            target_kps.append(kp_id)
    target_kps = [k for k in sorted(target_kps) if any(q["kp_id"] == k for q in bank)]

    selected = []
    used_keys = set(used_keys)

    def _take(q):
        selected.append(q)
        used_keys.add(_stem_key(q.get("stem", "")))

    # 1) 每个 KP 先保 1 题（优先难度仍有额度的）
    for kp in target_kps:
        if len(selected) >= remaining:
            break
        cands = [q for q in bank if q["kp_id"] == kp and _stem_key(q.get("stem", "")) not in used_keys]
        if not cands:
            continue
        q = None
        for d in DIFF_ORDER:
            if want.get(d, 0) <= 0:
                continue
            ds = [c for c in cands if c.get("difficulty") == d]
            if ds:
                q = random.choice(ds)
                break
        if q is None:
            q = random.choice(cands)
        d = q.get("difficulty", "中")
        want[d] = max(0, want.get(d, 0) - 1)
        _take(q)

    # 2) 按难度额度补足（难→中→易：先抢稀缺难度；守 KP 上限，防大题库 KP 刷屏）
    kp_cap = max(2, int(remaining / max(1, len(target_kps)) * 1.6)) if target_kps else remaining

    def _count_kp(k):
        return sum(1 for q in selected if q["kp_id"] == k)

    def _pools(d=None, cap=True):
        out = []
        for q in bank:
            if d and q.get("difficulty") != d:
                continue
            if _stem_key(q.get("stem", "")) in used_keys:
                continue
            if cap and _count_kp(q["kp_id"]) >= kp_cap:
                continue
            out.append(q)
        return out

    for d in ("难", "中", "易"):
        while want.get(d, 0) > 0 and len(selected) < remaining:
            cands = _pools(d, cap=True)
            if not cands:
                break
            _take(random.choice(cands))
            want[d] -= 1

    # 3) 数量不够：先守上限补，再放开上限
    for use_cap in (True, False):
        if len(selected) >= remaining:
            break
        cands = _pools(None, cap=use_cap)
        random.shuffle(cands)
        for q in cands:
            if len(selected) >= remaining:
                break
            _take(q)

    # 排序：易→中→难；回灌题固定在最后；选择题打乱选项（不安全的不打乱）
    selected.sort(key=lambda q: DIFF_ORDER.index(q.get("difficulty", "中")) if q.get("difficulty") in DIFF_ORDER else 1)
    selected = [shuffle_options(q) if _shuffle_safe(q) else q for q in selected]
    all_items = selected + reflow_items

    weak_kps = get_weak_kps(state, subject, scoped_kps)
    minutes_per_q = {"易": 1, "中": 2, "难": 3}
    est_minutes = sum(minutes_per_q.get(q.get("difficulty"), 2) for q in selected) + 3 * len(reflow_items)

    label = getattr(args, "label", None)
    if label:
        title = f"六年级{subject}·{label}"
    else:
        title = f"六年级{subject} {exam_type.replace('-review', '复习').replace('midterm', '期中模拟').replace('final', '期末模拟')}卷"

    return {
        "format": "question",
        "subject": subject,
        "scope": scope,
        "type": exam_type,
        "title": title,
        "questions": all_items,
        "reflow_items": reflow_items,
        "estimated_minutes": est_minutes,
        "difficulty_distribution": {
            d: sum(1 for q in selected if q.get("difficulty") == d)
            for d in DIFF_ORDER
        },
        "weak_kps_covered": list(dict.fromkeys(q["kp_id"] for q in selected if q["kp_id"] in weak_kps)),
    }


# ────────────────────────── 出卷：其他 4 种 ──────────────────────────

def generate_dictation(args, state, pool) -> dict:
    """生成默写卷骨架"""
    subject = args.subject
    scope = args.scope

    pool_dir = Path(getattr(args, "_base_dir", "D:/家教")) / subject / "测验"
    by_type_file = pool_dir / "by-type"

    type_name = "字音字形" if subject == "语文" else "单词拼写" if subject == "英语" else None
    if type_name and (by_type_file / f"{type_name}.json").exists():
        candidates = json.loads((by_type_file / f"{type_name}.json").read_text(encoding="utf-8"))
    else:
        candidates = []

    if "-" in scope:
        unit_ids = [f"u{i}" for i in range(int(scope.split("-")[0][1:]), int(scope.split("-")[1][1:]) + 1)]
    else:
        unit_ids = [scope]
    scoped = [q for q in candidates if q["unit_id"] in unit_ids and q.get("enabled")]

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
    """生成错题回灌卷（★必做）"""
    subject = args.subject
    kp_ids = [s.strip() for s in args.kp_ids.split(",")] if args.kp_ids else []
    base = Path(getattr(args, "_base_dir", "D:/家教"))

    recs = recent_mistake_records(subject, base, days=30)
    if kp_ids:
        recs = [r for r in recs if set(r.get("kp_ids") or []) & set(kp_ids)]
    else:
        recs = recs[-3:]

    selected, source_mistakes = [], []
    for m in recs:
        kps = [k for k in (m.get("kp_ids") or []) if k]
        if not kps:
            continue
        kp0 = kps[0]
        same_kp = [
            q for q in pool["questions"].values()
            if q.get("kp_id") == kp0 and q.get("enabled") and answer_usable(q)
            and _stem_key(q.get("stem", "")) != _stem_key(m.get("question", ""))
        ]
        if same_kp:
            item = dict(random.choice(same_kp))
            item["reflow"] = True
            item["reflow_note"] = "上次错在：" + ("；".join((m.get("common_mistakes") or [])[:1]) or "见错题本")
        else:
            item = {
                "qid": f"reflow_{m.get('date', '')}",
                "subject": subject, "kp_id": kp0, "unit_id": kp0.split(".")[0] if "." in kp0 else kp0,
                "difficulty": "中", "type": "错题回灌",
                "stem": m.get("question", ""), "options": None,
                "answer": m.get("correct_answer", "") or "（见错题本订正）",
                "explanation": m.get("correct_solution", ""),
                "reflow": True, "reflow_note": "上次错题原题重做",
            }
        selected.append(item)
        source_mistakes.append(m)

    return {
        "format": "remediation",
        "subject": subject,
        "kp_ids": kp_ids,
        "title": f"错题回灌 - {'/'.join(kp_ids) if kp_ids else '近期错题'}",
        "questions": selected,
        "source_mistakes": source_mistakes,
        "estimated_minutes": max(5, 3 * len(selected)),
    }


def generate_listening(args, state, pool) -> dict:
    """生成听写包（MP3 + Word 答案）"""
    subject = args.subject
    scope = args.scope

    pool_dir = Path(getattr(args, "_base_dir", "D:/家教")) / subject / "测验"
    by_type_file = pool_dir / "by-type"

    type_name = "单词拼写" if subject == "英语" else "字音字形"
    candidates = []
    if (by_type_file / f"{type_name}.json").exists():
        candidates = json.loads((by_type_file / f"{type_name}.json").read_text(encoding="utf-8"))

    mistake_words = []
    base = Path(getattr(args, "_base_dir", "D:/家教"))
    for r in recent_mistake_records(subject, base, days=14):
        if r.get("kp_names") and ("拼写" in "、".join(r.get("kp_names")) or "字音" in "、".join(r.get("kp_names"))):
            mistake_words.append(str(r.get("student_answer", ""))[:30])

    return {
        "format": "listening",
        "subject": subject,
        "scope": scope,
        "title": f"六年级{subject} {scope} 听写包",
        "candidates": candidates[:30],
        "must_include_mistakes": mistake_words[:10],
        "estimated_minutes": 15,
    }


def generate_recitation(args, state, pool) -> dict:
    """生成背诵检查表"""
    subject = args.subject
    scope = args.scope

    kp_index_path = Path(getattr(args, "_base_dir", "D:/家教")) / subject / "知识点及掌握情况/index.json"
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
            kp_file = Path(getattr(args, "_base_dir", "D:/家教")) / subject / "知识点及掌握情况" / f"{kp_id}.json"
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


# ────────────────────────── 输出：Markdown ──────────────────────────

def paper_sections(exam_data: dict) -> list:
    """题目卷分节：[(节标题, [(编号, q), ...]), ...]；回灌题固定最后一节"""
    qs = list(exam_data.get("questions") or [])
    reflow = [q for q in qs if q.get("reflow")]
    normal = [q for q in qs if not q.get("reflow")]

    groups = []
    for title, d in (("基础闯关（易）", "易"), ("能力提升（中）", "中"), ("思维挑战（难）", "难")):
        g = [q for q in normal if q.get("difficulty") == d]
        if g:
            groups.append((title, g))
    rest = [q for q in normal if q.get("difficulty") not in DIFF_ORDER]
    if rest:
        groups.append(("综合练习", rest))
    if reflow:
        groups.append(("★ 错题回灌（必做）", reflow))

    out, n = [], 0
    for i, (title, g) in enumerate(groups):
        items = []
        for q in g:
            n += 1
            items.append((n, q))
        if title.startswith("★"):
            out.append((title, items))
        else:
            out.append((f"{_ORD[i]}、{title}", items))
    return out


def reflow_numbers(exam_data: dict) -> list:
    """回灌必做题的卷面编号列表"""
    nums = []
    for title, items in paper_sections(exam_data):
        if title.startswith("★"):
            nums = [n for n, q in items]
    return nums


def _reminder_lines(exam_data: dict, for_html: bool = False) -> list:
    """卷尾提醒（必做）——交付时不得删除；错题本提醒由 Hermes 直接发送，不进文档"""
    nums = reflow_numbers(exam_data)
    out = []
    if nums:
        ns = "、".join(f"第{n}题" for n in nums)
        out.append(f"- **必做**：{ns}是之前错过的题（回灌必做题），必须保证全对；如果又错，先看讲解再重做一遍。")
    return out


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
        lines.append(f"**薄弱 KP 覆盖**：{', '.join(exam_data['weak_kps_covered'])}")
    lines.append("")

    if fmt == "question":
        sections = paper_sections(exam_data)
        nums = reflow_numbers(exam_data)
        lines.append("**姓名**：__________　**日期**：__________　**得分**：______")
        lines.append("")
        if nums:
            ns = "、".join(f"第{n}题" for n in nums)
            lines.append(f"> ⭐ **本卷必做题：{ns}**（历史错题回灌）。这几题必须做完 + 订正 + 讲出错因。")
            lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(f"## 题目（{len(exam_data['questions'])} 道）")
        lines.append("")
        for title, items in sections:
            lines.append(f"### {title}")
            lines.append("")
            for n, q in items:
                tag = "　★必做" if q.get("reflow") else ""
                lines.append(f"**{n}.**（{q.get('difficulty', '')}）{q['stem']}{tag}")
                if q.get("reflow_note"):
                    lines.append(f"> {q['reflow_note']}")
                if q.get("options"):
                    for j, opt in enumerate(q["options"]):
                        lines.append(f"- {chr(65 + j)}. {opt}")
                lines.append("")
        lines.extend(_reminder_lines(exam_data))
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 知识点分布")
        lines.append("")
        # 按 KP 分组统计
        kp_groups = {}
        for title, items in sections:
            for n, q in items:
                kp = q.get("kp_id", "未知")
                if kp not in kp_groups:
                    kp_groups[kp] = []
                kp_groups[kp].append(str(n))
        for kp, nums in sorted(kp_groups.items()):
            kp_name = _get_kp_name(kp, exam_data["subject"], exam_data.get("_base_dir", "D:/家教"))
            lines.append(f"- {kp}（{kp_name}）：第 {'、'.join(nums)} 题")
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
        src = exam_data.get("source_mistakes") or []
        lines.append(f"## 错题回灌（{len(exam_data['questions'])} 道，★必做）")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            lines.append(f"### {i}. [{q.get('difficulty', '')}]（{q.get('kp_id', '')}）★必做")
            note = q.get("reflow_note") or ""
            if not note and i - 1 < len(src):
                sm = src[i - 1]
                note = "上次错在：" + ("；".join((sm.get("common_mistakes") or [])[:2]) or "")
            if note:
                lines.append(f"> {note}")
            lines.append("")
            lines.append(q["stem"])
            if q.get("options"):
                for j, opt in enumerate(q["options"]):
                    lines.append(f"- {chr(65 + j)}. {opt}")
            lines.append("")
        lines.extend(_reminder_lines(exam_data))
        lines.append("")
        lines.append("## 答案与解析")
        lines.append("")
        for i, q in enumerate(exam_data["questions"], 1):
            seg = f"{i}. **{format_answer(q)}**"
            expl = _clean_expl(q)
            if expl and expl not in ("略", "略。"):
                seg += f" → {expl}"
            lines.append(seg)
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


# ────────────────────────── 输出：HTML（预览/打印可读版） ──────────────────────────

_HTML_STYLE = """
:root{--ink:#26221c;--muted:#7a746a;--line:#d8d2c6;--accent:#b03a2e;--ok:#2e7d4f;}
*{box-sizing:border-box}
body{font-family:"Noto Serif SC","Source Han Serif SC","Songti SC","SimSun",Georgia,serif;color:var(--ink);
     max-width:820px;margin:0 auto;padding:28px 34px 60px;line-height:1.85;font-size:15px;background:#fffdf8;}
h1{font-size:23px;text-align:center;margin:4px 0 6px;letter-spacing:1px;}
.meta{color:var(--muted);font-size:12.5px;text-align:center;margin-bottom:14px;}
.info{display:flex;gap:26px;justify-content:center;color:#333;font-size:14px;border-bottom:1.6px solid var(--ink);
      padding-bottom:10px;margin:0 0 6px;}
h2{font-size:17px;margin:28px 0 10px;padding-left:9px;border-left:4px solid var(--accent);}
h3{font-size:15.5px;margin:22px 0 10px;color:#544c40;}
.q{margin:16px 0;}
.q .stem{white-space:pre-wrap;}
.q .tag{color:var(--accent);font-weight:700;font-size:12.5px;}
.opts{margin:6px 0 0 24px;display:grid;grid-template-columns:1fr 1fr;gap:2px 18px;font-size:14.5px;}
.opts.one{grid-template-columns:1fr;}
.note{color:#8a5a00;background:#fff8e6;border:1px dashed #e5c07b;border-radius:6px;padding:6px 10px;
      font-size:13px;margin:6px 0 8px 24px;}
.must{border:1.6px solid var(--accent);border-radius:10px;padding:12px 16px;margin:16px 0;background:#fff5f4;font-size:14px;}
.must b{color:var(--accent);}
.remind{background:#f2f7f2;border:1px solid #cfe0cf;border-radius:8px;padding:10px 16px;font-size:13.5px;margin:22px 0;}
.remind h4{margin:0 0 6px;font-size:14px;color:var(--ok);}
.answers{border-top:2px solid var(--ink);margin-top:34px;padding-top:12px;}
.ans{font-size:13.5px;color:#333;margin:7px 0;}
.ans b{color:#111;}
@media print{.q,.must,.remind{break-inside:avoid;} .answers{page-break-before:always;} body{padding:10mm 8mm;font-size:14px;}}
"""


def _esc(s) -> str:
    return html_mod.escape(str(s or ""))


def _q_html(n: int, q: dict) -> str:
    tag = ' <span class="tag">★必做</span>' if q.get("reflow") else ""
    parts = [f'<div class="q"><div class="stem"><b>{n}.</b>（{_esc(q.get("difficulty", ""))}）{_esc(q["stem"])}{tag}</div>']
    if q.get("reflow_note"):
        parts.append(f'<div class="note">{_esc(q["reflow_note"])}</div>')
    opts = q.get("options")
    if opts:
        cls = "opts one" if len(opts) <= 2 or max(len(str(o)) for o in opts) > 14 else "opts"
        cells = "".join(f"<div>{chr(65 + j)}. {_esc(o)}</div>" for j, o in enumerate(opts))
        parts.append(f'<div class="{cls}">{cells}</div>')
    parts.append("</div>")
    return "\n".join(parts)


def write_html(exam_data: dict, output_dir: Path) -> Path | None:
    """写 HTML 版（自包含；预览/打印用）。主要服务 question/remediation 两种形式。"""
    fmt = exam_data["format"]
    if fmt not in ("question", "remediation"):
        return None
    ts = now_str()
    html_file = output_dir / f"{exam_data['title']}_{ts}.html"
    output_dir.mkdir(parents=True, exist_ok=True)

    b = []
    b.append(f"<h1>{_esc(exam_data['title'])}</h1>")
    b.append(
        f'<div class="meta">科目：{_esc(exam_data["subject"])}　|　生成时间：{ts}　|　'
        f'建议用时：{exam_data.get("estimated_minutes", "?")} 分钟</div>'
    )

    if fmt == "question":
        sections = paper_sections(exam_data)
        nums = reflow_numbers(exam_data)
        b.append('<div class="info"><span>姓名：__________</span><span>日期：__________</span><span>得分：______</span></div>')
        if nums:
            ns = "、".join(f"第{n}题" for n in nums)
            b.append(
                f'<div class="must">⭐ <b>本卷必做题：{ns}</b>（历史错题回灌）。'
                "这几题必须做完 + 订正 + 讲出错因；如果又错，先看讲解再重做一遍。</div>"
            )
        for title, items in sections:
            b.append(f"<h2>{_esc(title)}</h2>")
            for n, q in items:
                b.append(_q_html(n, q))
        rem = _reminder_lines(exam_data)
        if rem:
            rm_items = "".join(f"<div>{_esc(x.lstrip('- '))}</div>" for x in rem)
            b.append(f'<div class="remind"><h4>📒 做完之后</h4>{rm_items}</div>')
        # 知识点分布（替代答案区）
        kp_groups = {}
        for title, items in sections:
            for n, q in items:
                kp = q.get("kp_id", "未知")
                if kp not in kp_groups:
                    kp_groups[kp] = []
                kp_groups[kp].append(str(n))
        b.append('<div class="answers"><h2>知识点分布</h2>')
        for kp, nums in sorted(kp_groups.items()):
            kp_name = _get_kp_name(kp, exam_data["subject"], exam_data.get("_base_dir", "D:/家教"))
            nums_str = "、".join(nums)
            b.append(f'<div class="ans"><b>{kp}</b>（{kp_name}）：第 {nums_str} 题</div>')
        b.append("</div>")

    elif fmt == "remediation":
        src = exam_data.get("source_mistakes") or []
        b.append('<div class="info"><span>姓名：__________</span><span>日期：__________</span><span>得分：______</span></div>')
        b.append('<div class="must">★ <b>本卷全部为必做题</b>：这些都是之前错过的题——必须做完、订正、讲出错因。</div>')
        for i, q in enumerate(exam_data["questions"], 1):
            note = q.get("reflow_note") or ""
            if not note and i - 1 < len(src):
                sm = src[i - 1]
                note = "上次错在：" + ("；".join((sm.get("common_mistakes") or [])[:2]) or "")
            qq = dict(q)
            if note:
                qq["reflow_note"] = note
            b.append(_q_html(i, qq))
        rem = _reminder_lines(exam_data)
        rm_items = "".join(f"<div>{_esc(x.lstrip('- '))}</div>" for x in rem[1:])
        b.append(f'<div class="remind"><h4>{_esc(rem[0].lstrip("# "))}</h4>{rm_items}</div>')
        b.append('<div class="answers"><h2>答案与解析</h2>')
        for i, q in enumerate(exam_data["questions"], 1):
            expl = _clean_expl(q)
            seg = f'<div class="ans"><b>{i}.</b> {_esc(format_answer(q))}'
            if expl and expl not in ("略", "略。"):
                seg += f' → {_esc(expl)}'
            seg += "</div>"
            b.append(seg)
        b.append("</div>")

    doc = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        f"<title>{_esc(exam_data['title'])}</title>"
        f"<style>{_HTML_STYLE}</style></head><body>"
        + "\n".join(b)
        + "</body></html>"
    )
    html_file.write_text(doc, encoding="utf-8")
    return html_file


# ────────────────────────── 输出：Word（方便打印） ──────────────────────────

def write_word(exam_data: dict, output_dir: Path) -> Path | None:
    """写 Word 版（.docx）——方便打印交付"""
    try:
        from docx import Document
        from docx.shared import Pt, Cm, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.oxml.ns import qn
    except ImportError:
        return None

    fmt = exam_data["format"]
    if fmt not in ("question", "remediation"):
        return None  # 其他格式暂不支持 Word

    ts = now_str()
    docx_file = output_dir / f"{exam_data['title']}_{ts}.docx"
    output_dir.mkdir(parents=True, exist_ok=True)

    doc = Document()

    # 页面设置：A4，上下左右 2cm
    for section in doc.sections:
        section.page_height = Cm(29.7)
        section.page_width = Cm(21.0)
        section.top_margin = Cm(2)
        section.bottom_margin = Cm(2)
        section.left_margin = Cm(2)
        section.right_margin = Cm(2)

    # 默认字体：宋体 12pt（小四）
    style = doc.styles["Normal"]
    style.font.name = "宋体"
    style.font.size = Pt(12)
    style._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    # 标题
    title = doc.add_heading(exam_data["title"], level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for run in title.runs:
        run.font.name = "宋体"
        run.font.size = Pt(16)
        run.font.bold = True
        run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    # 信息行
    info = doc.add_paragraph()
    info.add_run(f"生成时间：{ts}　　科目：{exam_data['subject']}　　建议用时：{exam_data.get('estimated_minutes', '?')} 分钟")
    if exam_data.get("weak_kps_covered"):
        info.add_run(f"　　薄弱 KP：{', '.join(exam_data['weak_kps_covered'])}")
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    info.paragraph_format.space_after = Pt(12)

    # 姓名行
    name_line = doc.add_paragraph()
    name_line.add_run("姓名：__________　　日期：__________　　得分：______")
    name_line.alignment = WD_ALIGN_PARAGRAPH.CENTER
    name_line.paragraph_format.space_after = Pt(12)

    sections = paper_sections(exam_data)
    nums = reflow_numbers(exam_data)

    # 必做提醒
    if nums:
        ns = "、".join(f"第{n}题" for n in nums)
        p = doc.add_paragraph()
        run = p.add_run(f"⭐ 本卷必做题：{ns}（历史错题回灌）。这几题必须做完 + 订正 + 讲出错因。")
        run.font.bold = True
        run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
        p.paragraph_format.space_after = Pt(12)

    doc.add_paragraph("─" * 40)

    # 题目区
    doc.add_heading(f"题目（{len(exam_data['questions'])} 道）", level=1)
    for title_text, items in sections:
        h = doc.add_heading(title_text, level=2)
        for run in h.runs:
            run.font.name = "宋体"
            run._element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

        for n, q in items:
            # 题号 + 难度 + 题干
            p = doc.add_paragraph()
            tag = "　★必做" if q.get("reflow") else ""
            run = p.add_run(f"{n}. ")
            run.font.bold = True
            run = p.add_run(f"（{q.get('difficulty', '')}）{q['stem']}{tag}")
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(3)

            # 回灌题备注
            if q.get("reflow_note"):
                note_p = doc.add_paragraph()
                note_p.paragraph_format.left_indent = Cm(0.75)
                note_run = note_p.add_run(f"💡 {q['reflow_note']}")
                note_run.font.size = Pt(10)
                note_run.font.color.rgb = RGBColor(0x7F, 0x8C, 0x8D)
                note_p.paragraph_format.space_after = Pt(3)

            # 选项
            if q.get("options"):
                for j, opt in enumerate(q["options"]):
                    opt_p = doc.add_paragraph()
                    opt_p.paragraph_format.left_indent = Cm(0.75)
                    opt_p.add_run(f"{chr(65 + j)}. {opt}")
                    opt_p.paragraph_format.space_after = Pt(1)
                doc.add_paragraph()  # 选项后空一行

    # 卷尾提醒
    doc.add_paragraph()
    doc.add_heading("📒 做完之后", level=2)
    for line in _reminder_lines(exam_data):
        if line.startswith("## "):
            continue
        p = doc.add_paragraph(line.lstrip("- ").replace("**", ""))
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.space_after = Pt(3)

    # 知识点分布（替代答案区）
    doc.add_page_break()
    doc.add_heading("知识点分布", level=1)
    kp_groups = {}
    for title_text, items in sections:
        for n, q in items:
            kp = q.get("kp_id", "未知")
            if kp not in kp_groups:
                kp_groups[kp] = []
            kp_groups[kp].append(str(n))
    for kp, nums in sorted(kp_groups.items()):
        kp_name = _get_kp_name(kp, exam_data["subject"], exam_data.get("_base_dir", "D:/家教"))
        p = doc.add_paragraph()
        run = p.add_run(f"{kp}（{kp_name}）")
        run.font.bold = True
        nums_str = "、".join(nums)
        p.add_run(f"：第 {nums_str} 题")
        p.paragraph_format.space_after = Pt(4)

    doc.save(str(docx_file))
    return docx_file


# ────────────────────────── 试卷标记（批改匹配用） ──────────────────────────

def write_paper_marks(exam_data: dict, output_dir: Path) -> Path | None:
    """落 试卷标记_{subject}_{ts}.json——批改时用于识别「历史错题再次做错」"""
    if exam_data.get("format") != "question":
        return None
    ts = now_str()
    sections = paper_sections(exam_data)
    items, must_do = [], []
    for title, pairs in sections:
        for n, q in pairs:
            rec = {
                "no": n,
                "qid": q.get("qid", ""),
                "kp_id": q.get("kp_id"),
                "stem": str(q.get("stem", ""))[:160],
                "answer": format_answer(q),  # 批改对答案用（不进卷面）
                "reflow": bool(q.get("reflow")),
            }
            items.append(rec)
            if q.get("reflow"):
                must_do.append(rec)
    marks = {
        "subject": exam_data["subject"],
        "title": exam_data["title"],
        "ts": ts,
        "scope": exam_data.get("scope"),
        "counts": {"total": len(items), "reflow": len(must_do)},
        "must_do": must_do,
        "items": items,
    }
    f = output_dir / f"试卷标记_{exam_data['subject']}_{ts}.json"
    f.write_text(json.dumps(marks, ensure_ascii=False, indent=2), encoding="utf-8")
    return f


# ────────────────────────── 入口 ──────────────────────────

def main():
    parser = argparse.ArgumentParser(description="生成试卷/默写/听写包/背诵检查表")
    parser.add_argument("--subject", required=True, choices=["数学", "语文", "英语"])
    parser.add_argument("--format", required=True, choices=list(GENERATORS.keys()))
    parser.add_argument("--scope", help="覆盖范围，如 u1 / u1-u4")
    parser.add_argument("--type", choices=["unit-review", "midterm", "final"], default="unit-review",
                        help="题目卷类型（仅 question 形式用）")
    parser.add_argument("--kp-ids", help="错题回灌 KP 列表（仅 remediation 形式用），逗号分隔")
    parser.add_argument("--kp-filter", help="只出这些 KP 的题（逗号分隔，如 u2.k1,u2.k2；学到第几课就用它）")
    parser.add_argument("--count", type=int, default=0, help="题目总数（含回灌题；默认按类型）")
    parser.add_argument("--reflow-max", type=int, default=2, help="最多嵌入几道错题回灌（默认 2）")
    parser.add_argument("--label", help="自定义卷面抬头，如 第二单元·周末小测")
    parser.add_argument("--base-dir", default=None, help="自动探测 D:/家教 或 /d/家教")
    parser.add_argument("--output", help="输出目录（默认 {科目}/试卷/）")
    args = parser.parse_args()

    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        for cand in [Path("D:/家教"), Path("/d/家教"), Path("D:\\\\家教")]:
            if cand.exists():
                base_dir = cand
                break
        else:
            print("❌ 未找到家教根目录，请用 --base-dir 显式指定")
            sys.exit(1)

    args._base_dir = str(base_dir)
    subject_dir = base_dir / args.subject

    if not subject_dir.exists():
        print(f"❌ 未找到科目目录：{subject_dir}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else (base_dir / args.subject / "试卷")

    state = load_state(base_dir)
    pool = load_question_pool(args.subject, base_dir)

    generator = GENERATORS[args.format]
    exam_data = generator(args, state, pool)
    exam_data["_base_dir"] = args._base_dir  # writer 函数（md/html/word）读 KP 名称用

    md_file = write_markdown(exam_data, output_dir)
    html_file = write_html(exam_data, output_dir)
    marks_file = write_paper_marks(exam_data, output_dir)

    # ── Word 文档（方便打印）──
    docx_file = write_word(exam_data, output_dir)

    print(f"✓ 已生成 {md_file}")
    if html_file:
        print(f"✓ 已生成 {html_file}")
    if docx_file:
        print(f"✓ 已生成 {docx_file}（方便打印）")
    if marks_file:
        print(f"✓ 已生成 {marks_file}（批改用：识别历史错题再次做错）")
    print(f"  - 形式：{args.format}")
    print(f"  - 范围：{args.scope or args.kp_ids}")
    if exam_data.get("estimated_minutes"):
        print(f"  - 建议用时：{exam_data['estimated_minutes']} 分钟")
    if exam_data.get("questions"):
        print(f"  - 题目数：{len(exam_data['questions'])}")
    if exam_data.get("reflow_items"):
        print(f"  - 错题回灌：{len(exam_data['reflow_items'])} 道（★必做，见试卷标记）")
    if exam_data.get("difficulty_distribution"):
        d = exam_data["difficulty_distribution"]
        print(f"  - 难度分布：易 {d.get('易', 0)} / 中 {d.get('中', 0)} / 难 {d.get('难', 0)}")
    if exam_data.get("weak_kps_covered"):
        print(f"  - 薄弱 KP 覆盖：{', '.join(exam_data['weak_kps_covered'])}")
    print()
    print("📒 提醒：交付给孩子/家长时，必须带上卷尾【错题本提醒】与【必做】语句（skill §0.5）。")


if __name__ == "__main__":
    main()
