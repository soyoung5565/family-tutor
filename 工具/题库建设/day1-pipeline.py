#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
day1-pipeline.py — 「Day-1 三件套」流水线（2026-09-26 新建）

用户要求（2026-09-25 晚）：拿到孩子当天的错题，第一时间完成——
  ① 知识点漏洞分析（KP 归属 / 薄弱标记）
  ② 通过作业确定学校学习进度（复习信号 → 周模式 → 触发周计划更新）
  ③ 立刻记录入库错题库（{科目}/错题集/）
  ④ 如今天在周末/≥3 天假期中途：附「📅 剩余安排」（今天+剩余每天+「明天再来」提示 → day-schedule.py）
即便家长真人讲解、孩子不回流订正，这三件套也照常执行；微课件只是可选分支。

输入（三选一）：
  --mistakes <json>   结构化错题（grade-mistake.py 输出 / 手工整理；本流水线主入口）
  --hw-text "..."     额外作业文本（供进度信号判定；缺省用错题题干拼接）
  （拍照→结构化 由 grade-mistake.py 完成，可先跑它）

用法：
  D:/Python312/python.exe day1-pipeline.py --mistakes <file> --dry-run       # 试跑
  D:/Python312/python.exe day1-pipeline.py --mistakes <file>                 # 正式
  D:/Python312/python.exe day1-pipeline.py --mistakes <file> --no-plan      # 跳过周计划刷新
"""
import argparse
import difflib
import json
import os
import re
import subprocess
import sys
from collections import Counter, OrderedDict
from datetime import date, datetime, timedelta
from pathlib import Path

SCRIPTS = Path(__file__).parent
CST_FMT = "%Y-%m-%dT%H:%M:%S"
NEW, UNIT, EXAM = "预习周", "单元复习周", "期中/期末周"
REVIEW_MODES = (UNIT, EXAM)


def today() -> str:
    return os.environ.get("FAMTUTOR_TODAY") or date.today().isoformat()


def now() -> str:
    return datetime.now().strftime(CST_FMT)


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(p: Path, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 历史错题检测（2026-09-27 用户要求：「历史错题又错 → 必做提醒」） ──
REPEAT_SIM = 0.78


def _norm_text(s) -> str:
    return re.sub(r"[\s\u3000，。、：；（）()【】\[\]！？!?\"'“”‘’·—\-_/\\|]+", "", str(s or ""))


def text_similar(a, b) -> float:
    a, b = _norm_text(a), _norm_text(b)
    if len(a) < 6 or len(b) < 6:
        return 0.0
    if a == b:
        return 1.0
    if len(a) >= 12 and len(b) >= 12 and (a in b or b in a):
        return 0.95
    return difflib.SequenceMatcher(None, a, b).ratio()


def load_history(base: Path, subject: str, max_mark_files: int = 8) -> dict:
    """历史错题来源：错题集全部记录 + 最近试卷标记（含回灌题存底）"""
    ledger = []
    mdir = base / subject / "错题集"
    if mdir.exists():
        for f in sorted(mdir.glob("错题集_*.json")):
            d = load_json(f, {}) or {}
            for r in d.get("records", []):
                ledger.append({
                    "where": "错题集", "date": str(r.get("date", "")),
                    "question": str(r.get("question", "")),
                    "kp": "、".join(r.get("kp_names") or r.get("kp_ids") or []),
                })
    papers = []
    pdir = base / subject / "试卷"
    if pdir.exists():
        for f in sorted(pdir.glob("试卷标记_*.json"), reverse=True)[:max_mark_files]:
            d = load_json(f, {}) or {}
            for it in d.get("items", []):
                papers.append({
                    "where": f"试卷《{d.get('title', '')}》", "date": str(d.get("ts", ""))[:10],
                    "question": str(it.get("stem", "")),
                    "kp": str(it.get("kp_id", "")),
                    "reflow": bool(it.get("reflow")),
                })
    return {"ledger": ledger, "papers": papers}


def detect_history_repeats(base: Path, subject: str, records: list) -> list:
    """检出「历史错题又错」：与错题集/历史试卷比对（相似度 ≥ REPEAT_SIM）。
    返回 [(record, [evidence, ...]), ...]"""
    hist = load_history(base, subject)
    out = []
    for rec in records:
        qtext = str(rec.get("question", ""))
        evs = []
        for src in hist["ledger"] + hist["papers"]:
            sim = text_similar(qtext, src["question"])
            if sim >= REPEAT_SIM:
                evs.append({"where": src["where"], "date": src["date"], "kp": src["kp"], "sim": round(sim, 2)})
        if evs:
            seen, uniq = set(), []
            for e in evs:
                k = (e["where"], e["date"])
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(e)
            out.append((rec, uniq[:3]))
    return out


def kp_meta(subject_dir: Path, kp_id: str) -> dict:
    d = load_json(subject_dir / "知识点及掌握情况" / f"{kp_id}.json", {}) or {}
    return {"name": d.get("name") or kp_id, "unit": d.get("unit") or kp_id.split(".")[0]}


def run_classify(base: Path, subject: str, hw_text: str, kp_ids: list):
    """调 classify-homework.py（--no-write）取信号建议"""
    cmd = ["D:/Python312/python.exe", str(SCRIPTS / "classify-homework.py"),
           "--text", hw_text, "--subject", subject, "--base-dir", str(base), "--no-write"]
    if kp_ids:
        cmd += ["--kps", ",".join(kp_ids)]
    r = subprocess.run(cmd, capture_output=True)
    out = r.stdout.decode("utf-8", errors="replace")
    if "JSON 输出" not in out:
        out2 = r.stdout.decode("gbk", errors="replace")
        if "JSON 输出" in out2:
            out = out2
    sig = None
    i = out.rfind("JSON 输出")
    if i >= 0:
        j = out.find("{", i)
        if j >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(out[j:])
                if isinstance(obj, dict):
                    sig = obj.get("signal") or None
            except Exception as e:
                print(f"[debug] 信号解析失败: {e}")
    if sig is None:
        print(f"[debug] classify rc={r.returncode} out_len={len(out)} err={(r.stderr or b'').decode('utf-8','replace')[:160]!r}")
    return sig, out


def apply_mode_change(state: dict, subject: str, signal: dict, dry: bool):
    """防抖 + 冷却 后决定是否切换模式；返回 (changed, note)"""
    g = state.setdefault("global", {})
    detail = g.setdefault("current_mode_detail", {})
    cur = detail.get(subject, NEW)
    log = g.setdefault("signal_log", [])
    if not signal or not (signal.get("signal_type") in ("new-content", "unit-review", "exam")):
        log.append({"date": today(), "subject": subject, "type": "none", "confidence": 0})
        g["signal_log"] = log[-30:]
        return False, f"无有效信号，模式保持（{cur}）"
    sig_type = signal.get("signal_type")
    conf = float(signal.get("confidence") or 0)
    # 只有明确的复习信号才可能切模式；new-content（0.5 兜底）不主动回切
    if sig_type == "new-content" and cur in REVIEW_MODES:
        log.append({"date": today(), "subject": subject, "type": sig_type, "confidence": conf})
        g["signal_log"] = log[-30:]
        return False, f"新模式信号(弱)，复习期不回切（保持 {cur}）"
    target = {"new-content": NEW, "unit-review": UNIT, "exam": EXAM}.get(sig_type, cur)
    log.append({"date": today(), "subject": subject, "type": sig_type, "confidence": conf})
    g["signal_log"] = log[-30:]
    if target == cur:
        return False, f"模式未变（{cur}）"
    lmc = g.get("last_mode_change") or {}
    # 冷卻：复习模式 → 预习周 需 7 天
    if target == NEW and cur in REVIEW_MODES and lmc.get("at"):
        try:
            if (datetime.now() - datetime.strptime(lmc["at"], CST_FMT)).days < 7 and lmc.get("subject") == subject:
                return False, f"防抖：{cur}→{NEW} 冷却中（<7天），保持"
        except Exception:
            pass
    # 防抖：非关键词信号（density，conf<0.9）需最近 3 条日志中同型 ≥2 次
    if conf < 0.9 and target in REVIEW_MODES:
        same = [e for e in log[-3:] if e.get("subject") == subject and e.get("type") == sig_type]
        if len(same) < 2:
            return False, f"防抖：{sig_type} 首次信号（需≥2次确认），暂不切换"
    detail[subject] = target
    all_modes = list(detail.values())
    g["current_mode"] = EXAM if EXAM in all_modes else (UNIT if UNIT in all_modes else NEW)
    g["last_mode_change"] = {"at": now(), "subject": subject, "old_mode": cur, "new_mode": target,
                             "trigger_signal": (signal or {}).get("matched_keywords") or (signal or {}).get("reason") or sig_type,
                             "confidence": conf}
    return True, f"模式切换：{cur} → {target}"


def update_kp_state(state: dict, subject: str, subject_dir: Path, records: list, batch_id: str):
    """① KP 漏洞分析 + 状态写入（attempts/master/连错/错因）"""
    sub = state.setdefault("subjects", {}).setdefault(subject, {})
    kps = sub.setdefault("kps", {})
    recent = sub.setdefault("mistakes_recent", [])
    analysis = OrderedDict()
    for rec in records:
        for kp_id in rec.get("knowledge_points", []):
            meta = kp_meta(subject_dir, kp_id)
            v = kps.setdefault(kp_id, {"name": "", "unit_id": kp_id.split(".")[0], "master": 0,
                                       "attempts": 0, "correct": 0, "last_seen": None, "last_correct": None,
                                       "mistake_types": [], "consecutive_correct": 0, "consecutive_wrong": 0,
                                       "enabled_in_pool": True})
            v["name"] = v.get("name") or meta["name"]
            v["attempts"] = v.get("attempts", 0) + 1
            v["last_seen"] = today()
            v["last_correct"] = False
            v["consecutive_wrong"] = v.get("consecutive_wrong", 0) + 1
            v["consecutive_correct"] = 0
            delta = 5 + (10 if v["consecutive_wrong"] >= 3 else 0)
            v["master"] = max(0, min(100, v.get("master", 0) - delta))
            for cm in rec.get("common_mistakes", [])[:3]:
                if cm not in v["mistake_types"]:
                    v["mistake_types"].append(cm)
            v["mistake_types"] = v["mistake_types"][-6:]
            a = analysis.setdefault(kp_id, {"name": meta["name"], "unit": meta["unit"],
                                            "count": 0, "mistake_types": [], "questions": []})
            a["count"] += 1
            a["questions"].append(str(rec.get("question", ""))[:50])
            for cm in rec.get("common_mistakes", []):
                if cm not in a["mistake_types"]:
                    a["mistake_types"].append(cm)
        recent.append({"date": today(), "batch": batch_id, "qid": rec.get("id", ""),
                       "kp_id": (rec.get("knowledge_points") or [""])[0],
                       "type": kp_meta(subject_dir, (rec.get("knowledge_points") or ["?"])[0])["name"],
                       "stem_summary": f"{str(rec.get('question',''))[:48]}｜学生答: {str(rec.get('student_answer',''))[:16]}"})
    sub["mistakes_recent"] = recent[-60:]
    # 薄弱重算
    weak_sub = [k for k, v in kps.items() if v.get("attempts", 0) > 0 and (v.get("master", 0) < 60 or v.get("consecutive_wrong", 0) >= 2)]
    sub["weak_kps"] = weak_sub
    return analysis


def ingest_ledger(base: Path, subject: str, records: list, batch_id: str, dry: bool):
    """③ 错题入库（{科目}/错题集/错题集_YYYY-MM.json，幂等去重）"""
    d = base / subject / "错题集"
    f = d / f"错题集_{date.today().strftime('%Y-%m')}.json"
    data = load_json(f, None) or {"subject": subject, "records": []}
    existing = {(r.get("date"), str(r.get("question", ""))[:60]) for r in data["records"]}
    added = 0
    for rec in records:
        key = (today(), str(rec.get("question", ""))[:60])
        if key in existing:
            continue
        data["records"].append({
            "date": today(), "batch": batch_id, "id": rec.get("id", ""),
            "question": rec.get("question", ""), "student_answer": rec.get("student_answer", ""),
            "correct_answer": rec.get("correct_answer", ""), "correct_solution": rec.get("correct_solution", ""),
            "kp_ids": rec.get("knowledge_points", []),
            "kp_names": [kp_meta(base / subject, k)["name"] for k in rec.get("knowledge_points", [])],
            "common_mistakes": rec.get("common_mistakes", []),
            "history_repeat": bool(rec.get("history_repeat")),
            "repeat_of": rec.get("repeat_of", ""),
            "source": "day1-pipeline",
        })
        added += 1
    data["updated_at"] = now()
    if not dry:
        save_json(f, data)
    return f, added, len(data["records"])


def write_mistake_list(base: Path, subject: str, records: list, dry: bool = False, repeats: list = None, typo: dict = None, day_plan: str = None):
    """学生/家长版错题文字清单（无答案）——批改完立刻发出去的那份。
    2026-09-27 起：① 历史错题又错 → 清单顶部置顶「必做提醒」；② 清单末尾固定附「错题本提醒」。"""
    d = base / subject
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"错题清单_{today()}.md"
    lines = [f"# {subject}·今日错题清单（{today()}）", "", f"今天批改：共 {len(records)} 道题做错了，详情如下（正确答案先不给，孩子先自己订正）：", ""]
    if repeats:
        lines.append("## ⚠️ 必做提醒（历史错题又错了！）")
        lines.append("")
        for r, evs in repeats:
            kps = "、".join(kp_meta(d, k)["name"] for k in r.get("knowledge_points", []))
            qflat = " ".join(str(r.get("question", "")).split())
            src = "；".join(f"{e['where']}（{e['date']}）" for e in evs[:2])
            lines.append(f"- **{str(r.get('part_label') or '').strip()}{qflat[:52]}**（{kps or '—'}）")
            lines.append(f"  {src} 错过，这次又错了——**这几题是必做的**：先看讲解，把错因写进错题本，再重做一遍。")
        lines.append("")
    for i, r in enumerate(records, 1):
        kps = "、".join(kp_meta(d, k)["name"] for k in r.get("knowledge_points", []))
        qflat = " ".join(str(r.get("question", "")).split())
        mark = " ⚠️必做" if r.get("history_repeat") else ""
        lines.append(f"**{i}. {str(r.get('part_label') or '').strip()}{qflat[:64]}**{mark}")
        lines.append(f"- 孩子写的：{str(r.get('student_answer',''))[:60]}")
        if kps:
            lines.append(f"- 涉及知识点：{kps}")
        cm = "；".join(r.get("common_mistakes", [])[:1])
        if cm:
            lines.append(f"- 错因提示：{cm}")
        lines.append("")
    lines.append("> 处理进度：错题已入库；错题讲解课堂正在生成，稍后把链接发来。")
    lines.append("")
    if typo and typo.get("checked"):
        lines.append("## ✏️ 错字/拼写检查（独立于对错批改）")
        lines.append("")
        errs = typo.get("errors") or []
        if errs:
            for e in errs[:12]:
                if not isinstance(e, dict):
                    continue
                tx = str(e.get("text", "")).strip()
                dt = str(e.get("detail", "")).strip()
                cr = str(e.get("correct", "")).strip()
                if cr:
                    lines.append(f"- 「{tx}」拼写错误 → 应为「{cr}」" + (f"：{dt}" if dt else ""))
                else:
                    lines.append(f"- 「{tx}」写错" + (f"：{dt}" if dt else ""))
        else:
            lines.append("本次未发现错字/拼写问题。")
        lines.append("")
        lines.append("> 错字检查为 AI 辅助识别，请以实卷复核为准。")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📒 错题本提醒")
    lines.append("")
    lines.append("把今天做错的题整理进错题本：① 抄题目；② 写清楚自己错在哪（错因）；③ 写正确解法。")
    lines.append("订正时先自己重做一遍，再看讲解；周末会把这些错题做成回灌题再抽查。")
    if day_plan:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 📅 剩余安排（周末/长假中途）")
        lines.append("")
        lines.append(day_plan)
        lines.append("")
    content = "\n".join(lines)
    if dry:
        return content
    try:
        f.write_text(content, encoding="utf-8")
        return f
    except Exception:
        return content


def launch_micro_lesson(base: Path, records: list) -> tuple:
    """批改完自动生成错题讲解课堂（后台曝光，日志见 系统/_runs/）"""
    import os as _os
    tmp = base / "系统/_runs"
    tmp.mkdir(parents=True, exist_ok=True)
    mkf = tmp / f"mistakes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    mkf.write_text(json.dumps({"subject": records[0].get("_subject", "数学"), "date": today(), "mistakes": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    logf = tmp / f"micro_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    env = dict(_os.environ, PYTHONIOENCODING="utf-8")
    flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    with open(logf, "a", encoding="utf-8") as out:
        subprocess.Popen(["D:/Python312/python.exe", str(SCRIPTS / "micro-lesson.py"),
                          "--mistakes", str(mkf), "--concurrency", "1", "--timeout", "1800"],
                         stdout=out, stderr=subprocess.STDOUT, cwd=str(SCRIPTS),
                         env=env, creationflags=flags)
    return mkf, logf


def run_day_schedule(as_of: str = None, base_dir=None) -> str:
    """④/⑦ 剩余安排（周末/假期中途进入——2026-10-10 用户要求）：
    今天在周末/≥3天假期中途 → 返回「今天+剩余每天+明天再来」文本；否则空串。"""
    try:
        cmd = ["D:/Python312/python.exe", str(SCRIPTS / "day-schedule.py")]
        if as_of:
            cmd += ["--date", as_of]
        if base_dir:
            cmd += ["--base-dir", str(base_dir)]
        r = subprocess.run(cmd, capture_output=True, timeout=60)
        out = r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip()
        return out if "📅 剩余安排" in out else ""
    except Exception as e:
        print(f"[debug] day-schedule 调用失败：{e}")
        return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mistakes", required=True)
    ap.add_argument("--subject", default=None)
    ap.add_argument("--base-dir", default="D:/家教")
    ap.add_argument("--hw-text", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-plan", action="store_true")
    ap.add_argument("--batch-id", default=None)
    ap.add_argument("--no-microlesson", action="store_true", help="仅当明确不需要视频时才加（默认会生成课堂）")
    args = ap.parse_args()

    base = Path(args.base_dir)
    mk = load_json(Path(args.mistakes))
    if not mk:
        print(f"[x] 读不到错题文件：{args.mistakes}")
        sys.exit(1)
    subject = args.subject or mk.get("subject") or "数学"
    records = mk.get("mistakes", [])
    n_all = len(records)
    skipped = [r for r in records if r.get("is_correct")]
    if skipped:
        records = [r for r in records if not r.get("is_correct")]
        print(f"（跳过已判定做对的 {len(skipped)} 题：{[str(s.get('id','')) + str(s.get('part_label','')) for s in skipped]}）")
    if not records:
        print("[i] 没有做错的题，三件套无需处理（可提示家长无订正项）")
        _dp = run_day_schedule(base_dir=base)
        if _dp:
            print("\n📅 剩余安排（周末/假期中途进入）——【交付消息里必须带上】：")
            print(_dp)
        sys.exit(0)
    batch_id = args.batch_id or f"{subject}-{today()}-{len(records)}题"
    sdir = base / subject

    # ── ⓪ 历史错题检测（历史错题又错 → 必做） ──
    repeats = detect_history_repeats(base, subject, records)
    for r, evs in repeats:
        r["history_repeat"] = True
        r["repeat_of"] = "；".join(f"{e['where']}（{e['date']}）" for e in evs[:2])

    print(f"═══ Day-1 三件套流水线 ═══")
    print(f"科目：{subject}｜错题 {len(records)} 条｜批次 {batch_id}｜{'（试跑）' if args.dry_run else ''}")

    state_p = base / "系统/学习状态.json"
    state = load_json(state_p)
    if not state:
        print("[x] 读不到学习状态.json；先跑 init-learning-state.py")
        sys.exit(1)

    if not args.dry_run:  # 备份
        bak = base / "系统/_backup" / f"学习状态_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json.bak"
        bak.parent.mkdir(parents=True, exist_ok=True)
        bak.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    # ── ① KP 漏洞分析 + 状态更新 ──
    analysis = update_kp_state(state, subject, sdir, records, batch_id)
    print(f"\n① 知识点漏洞分析（{len(analysis)} 个 KP）：")
    for kp_id, a in analysis.items():
        v = state["subjects"][subject]["kps"][kp_id]
        print(f"   · {kp_id} {a['name']}：本次错 {a['count']} 题｜master={v['master']}｜连错={v['consecutive_wrong']}"
              + (f"｜错因: {'、'.join(a['mistake_types'][:2])}" if a["mistake_types"] else ""))

    if repeats:
        print(f"\n★ 历史错题又错 {len(repeats)} 题（必做，已置顶写入清单）：")
        for r, evs in repeats:
            print(f"   · {r.get('part_label', '') or r.get('id', '')} ← {r.get('repeat_of')}")
    else:
        print("\n· 历史错题检测：本次无「历史错题又错」")

    # ── ② 学校进度判定（作业信号 → 周模式） ──
    hw_text = args.hw_text or "\n".join(str(r.get("question", "")) for r in records)
    sig, _ = run_classify(base, subject, hw_text, [k for r in records for k in r.get("knowledge_points", [])])
    changed, note = apply_mode_change(state, subject, sig, args.dry_run)
    print(f"\n② 学校进度判定：信号={(sig or {}).get('signal_type')}（{float((sig or {}).get('confidence') or 0):.0%}）→ {note}")
    if changed:
        print(f"   触发：{(sig or {}).get('matched_keywords') or (sig or {}).get('reason')}")

    # ── ③ 错题入库 ──
    lf, added, total = ingest_ledger(base, subject, records, batch_id, args.dry_run)
    print(f"\n③ 错题入库：+{added} 条（当月累计 {total}）→ {lf.name}")
    weak = state["subjects"][subject].get("weak_kps", [])
    print(f"   薄弱 KP 现计 {len(weak)} 个" + (f"：{'、'.join(weak[:5])}" if weak else ""))

    # 全局薄弱汇写
    wg = []
    for s, v in state["subjects"].items():
        wg += [f"{s}/{k}" for k in v.get("weak_kps", [])]
    state["global"]["weak_kps_global"] = wg[:30]

    if not args.dry_run:
        save_json(state_p, state)
        print("\n✓ 学习状态.json 已更新")
    else:
        print("\n[dry-run] 未写任何文件")

    # ── 周计划刷新（可选） ──
    if not args.no_plan:
        print("\n④ 周计划刷新：")
        cmd = ["D:/Python312/python.exe", str(SCRIPTS / "generate-weekly-plan.py"), "--base-dir", str(base)]
        if args.dry_run:
            cmd.append("--dry-run")
        else:
            cmd.append("--quiet")
        r = subprocess.run(cmd, capture_output=True)
        if args.dry_run:
            print(r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n")[:500] + " …")
        else:
            print(r.stdout.decode("utf-8", errors="replace").replace("\r\n", "\n").replace("\r", "\n").strip() or "（已安静更新）")

    # ── ⑤ 错题文字清单（批改完立刻发给孩子/家长的那份）──
    #    2026-10-10：周末/假期中途进入 → 清单末尾附「📅 剩余安排（今天+剩余每天+明天再来）」
    day_plan = run_day_schedule(base_dir=base)
    listf = write_mistake_list(base, subject, records, dry=args.dry_run, repeats=repeats,
                               typo=mk.get("typo_check"), day_plan=day_plan)
    shown = listf if isinstance(listf, str) else str(listf)
    where = "（dry-run 预览·未落盘）" if args.dry_run else f"→ {listf}"
    print(f"\n⑤ 错题文字清单（学生版·无答案）{where}")
    print("──── 清单内容 ────")
    print(shown if isinstance(listf, str) else Path(listf).read_text(encoding="utf-8"))
    print("──────────────────")
    print("📒 交付给孩子/家长时：清单中的【必做提醒】【错题本提醒】不得删改（skill §0.5）。")
    if day_plan:
        print("📅 剩余安排已附在清单末尾（今天在周末/假期中途）——交付消息里必须带上，含「明天再来」提示。")
    else:
        print("📅 剩余安排：今天非周末/假期中途（无）。")

    # ── ⑥ 自动生成错题讲解课堂（流程默认步骤；--no-microlesson 才跳过）──
    for _r in records:
        _r["_subject"] = subject
    if args.no_microlesson:
        print("\n⑥ 已按 --no-microlesson 跳过课堂生成（如需：python micro-lesson.py --mistakes", args.mistakes, "）")
    elif args.dry_run:
        print(f"\n⑥ [dry-run] 将自动启动课堂生成（后台，日志见 系统/_runs/）")
    else:
        mkf, logf = launch_micro_lesson(base, records)
        print(f"\n⑥ 错题讲解课堂已后台生成中：日志 {logf.name}（生成完链接会写入课件索引）")

    print("═══ 完成 ═══")


if __name__ == "__main__":
    main()
