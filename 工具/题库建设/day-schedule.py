#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
day-schedule.py — 中途进入的「剩余安排」引擎（2026-10-10 用户要求；2026-10-11 v2 相位重排）

背景（用户原话）：
  「遇到了周末，学生周六才上传作业……让学生明天再来找 AI 完成明天的学习任务，
   而不是周日空着。长假也是——比如五一/十一第三天才提交作业，应该安排后几天的学习安排。」
  「day1 复习；day2 及以后看情况——若需要查漏补缺复习的知识点过多，则不安排或少安排
   预习；若正常，则 day2 及以后开始预习。例如 51 假期 day1-2 查漏补缺、day3-5 预习，
   并且要规划好每日内容。」

结构（v2 相位重排，对应用户样例）：
  · 前段 = 补漏相位：day1 复习（薄弱 KP 定位）→ 错题卷★订正 → 查漏补缺＋错题本；
    5/7/9 天假期含 2 轮（两轮复习+查漏补缺）。天数随「缺口量」评估加档。
  · 后段 = 预习相位：每天一科向前预习（数学→语文→英语轮转）1 课时 ＋ 预习小试卷；
    周末 = 预习下周新课（按 KP 顺序）。
  · 调休上班日按工作日；周末、3 天小长假走同一相位逻辑（周期内容 1 轮）。

缺口量评估（assess）：三科薄弱 KP 合计 + 近 7 天错题数 →
  · 正常（≤6 个 / ≤12 条）→ 按基准天数（周末 1+1；3天 1+2；5/7/9天 2+剩余）
  · 偏多（≤12 个 / ≤24 条）→ 补漏 +1 天，预习顺延压缩
  · 过多 → 预习「少安排」（≥3 天块给 1 天）或不安排（小块全补漏）

落点（三处，缺一不可，见 skill family-tutor）：
  ① generate-weekly-plan.py → 学习规划.md「📍 剩余安排」段；② day1-pipeline.py → 错题清单末尾；
  ③ Hermes 交付消息带该段 + 「明天记得再来找 AI」。

用法：
  python day-schedule.py [--date YYYY-MM-DD] [--base-dir D:/家教] [--json]
环境变量 FAMTUTOR_TODAY 可覆盖「今天」（测试/补排用）。
"""
import argparse
import importlib.util
import json
import math
import os
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
WD = "一二三四五六日"
DEFAULT_BASE = "D:/家教"
SUBJ_ORDER = ["数学", "语文", "英语"]

# 缺口量阈值：正常 / 偏多（超过 → 过多）
TH_NORMAL = {"kp": 6, "err": 12}
TH_HIGH = {"kp": 12, "err": 24}


def _load_holiday_cycles():
    spec = importlib.util.spec_from_file_location("holiday_cycles", HERE / "holiday-cycles.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def wd_cn(d: date) -> str:
    return "周" + WD[d.weekday()]


def makeup_set():
    hc = _load_holiday_cycles()
    s = set()
    for h in hc.all_holidays():
        for x in (h.get("makeup_workdays") or []):
            s.add(x)
    return s


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


# ───────────────────────── 块判定 ─────────────────────────

def find_block(dstr: str):
    """判定今天所处的「学习块」（周末 / ≥3 天假期中途）。工作日、调休上班日 → None。"""
    hc = _load_holiday_cycles()
    d = date.fromisoformat(dstr)
    mk = makeup_set()
    # ① 假期（含假期内的周末）优先
    for h in hc.all_holidays():
        if h["start"] <= dstr <= h["end"] and h.get("days", 0) >= 3:
            start, end = date.fromisoformat(h["start"]), date.fromisoformat(h["end"])
            return {"type": "holiday", "name": h["name"],
                    "day_index": (d - start).days + 1, "total": h["days"],
                    "remaining": (end - d).days + 1,
                    "start": h["start"], "end": h["end"],
                    "cycles": h.get("cycles", 1), "preview": bool(h.get("preview"))}
    # ② 调休上班日 → 按工作日
    if dstr in mk:
        return None
    # ③ 周末（剔除调休上班的周六/周日）
    if d.weekday() >= 5:
        sat = d - timedelta(days=d.weekday() - 5)
        days = [x for x in (sat, sat + timedelta(days=1)) if x.isoformat() not in mk]
        if dstr not in [x.isoformat() for x in days]:
            return None
        return {"type": "weekend", "name": "周末",
                "day_index": days.index(d) + 1, "total": len(days),
                "remaining": len([x for x in days if x >= d]),
                "start": days[0].isoformat(), "end": days[-1].isoformat(),
                "cycles": 1, "preview": False}
    return None


# ───────────────────────── 缺口量评估 ─────────────────────────

def assess(base: Path, ref: date) -> dict:
    """缺口量 = 三科薄弱 KP 合计 + 近 7 天新增错题数（相对 ref 日期）。
    返回 {level, kp_n, err_n, weak_names, note}；读不到状态按正常处理。"""
    st = load_json(base / "系统/学习状态.json")
    if not st:
        return {"level": "正常", "kp_n": 0, "err_n": 0, "weak_names": [],
                "note": "（未读取到学习状态，按正常安排）"}
    kp_n, weak_names = 0, []
    cutoff = (ref - timedelta(days=7)).isoformat()
    err_n = 0
    for s in SUBJ_ORDER:
        v = (st.get("subjects", {}) or {}).get(s) or {}
        for kp_id, kv in (v.get("kps") or {}).items():
            if kv.get("attempts", 0) > 0 and (kv.get("master", 0) < 60 or kv.get("consecutive_wrong", 0) >= 2):
                kp_n += 1
                name = kv.get("name") or kp_id
                weak_names.append({"subject": s, "id": kp_id, "name": name, "master": kv.get("master", 0)})
        for m in (v.get("mistakes_recent") or []):
            if str(m.get("date", "")) >= cutoff:
                err_n += 1
    weak_names.sort(key=lambda x: x.get("master", 0))
    if kp_n <= TH_NORMAL["kp"] and err_n <= TH_NORMAL["err"]:
        level = "正常"
    elif kp_n <= TH_HIGH["kp"] and err_n <= TH_HIGH["err"]:
        level = "偏多"
    else:
        level = "过多"
    return {"level": level, "kp_n": kp_n, "err_n": err_n,
            "weak_names": weak_names, "note": ""}


# ───────────────────────── 相位与步骤 ─────────────────────────

def plan_phases(block: dict, remaining: int, level: str):
    """返回 (补漏天数, 预习天数)。"""
    if block["type"] == "weekend" or block.get("cycles", 1) <= 1:
        base_fill = 1          # 周末/3天：day1 补漏，day2+ 起预习
    else:
        base_fill = 2          # 5/7/9 天：day1-2 补漏（两轮），之后预习
    if level == "偏多":
        fill = min(base_fill + 1, remaining)     # 加档可占满（短块预习归零）
        return fill, remaining - fill
    elif level == "过多":
        preview = 1 if remaining >= 3 else 0     # 「少安排」：大块给 1 天，小块不安排
        fill = max(1, remaining - preview)
        return fill, remaining - fill
    else:
        fill = base_fill
    if remaining > 1:
        fill = min(fill, remaining - 1)          # 正常至少留 1 天预习
    else:
        fill = 1
    return fill, remaining - fill


def fill_steps(block: dict, weak_names: list):
    """补漏相位步骤。周末=1 套；3天=1 轮；5/7/9天=2 轮（复习→错题卷→查漏补缺）。"""
    wk = "、".join(x["name"] for x in weak_names[:3]) if weak_names else ""
    wk_txt = f"（薄弱 KP：{wk}）" if wk else "（按作业错题定位）"
    if block["type"] == "weekend":
        return [f"复习：错题本复盘 ＋ 薄弱强化{wk_txt}",
                "周测卷（回灌★必做）＋ 订正",
                "查漏补缺 ＋ 错题本"]
    cyc = max(1, block.get("cycles", 1))
    steps = []
    for i in range(1, cyc + 1):
        if i == 1:
            steps += [f"复习{wk_txt}",
                      "错题卷（回灌★必做）＋ 订正",
                      "查漏补缺 ＋ 错题本"]
        else:
            steps += [f"复习（第{i}轮·错题主攻）",
                      f"错题卷（第{i}轮）＋ 订正",
                      "查漏补缺 ＋ 错题本"]
    return steps


def preview_steps(block: dict, n: int):
    """预习相位步骤：每天一科（数→语→英轮转）向前预习 1 课时 + 预习小试卷。"""
    if n <= 0:
        return []
    if block["type"] == "weekend":
        return ["预习下周新课（数/语/英，按 KP 顺序）"] * n
    out = []
    for i in range(n):
        s = SUBJ_ORDER[i % len(SUBJ_ORDER)]
        rnd = i // len(SUBJ_ORDER) + 1
        head = f"【{s}】向前预习：下一课时" if rnd == 1 else f"【{s}】再向前预习 1 课时"
        out.append(head + " ＋ 预习小试卷")
    return out


def distribute(steps, k):
    """把 steps 从左到右均衡铺到 k 天：每天取 ceil(剩余步骤/剩余天数)。"""
    out, idx, left_s, left_d = [], 0, len(steps), k
    for _ in range(k):
        if left_s <= 0:
            out.append([])
            left_d -= 1
            continue
        take = min(max(1, math.ceil(left_s / left_d)), left_s)
        out.append(steps[idx: idx + take])
        idx += take
        left_s -= take
        left_d -= 1
    return out


# ───────────────────────── 组装 ─────────────────────────

def build(dstr: str, base_dir: str = None) -> dict:
    base = Path(base_dir or DEFAULT_BASE)
    b = find_block(dstr)
    if not b:
        return {"active": False, "date": dstr}
    d0 = date.fromisoformat(dstr)
    rem_days = [d0 + timedelta(days=i) for i in range(b["remaining"])]
    a = assess(base, d0)
    fill_d, prev_d = plan_phases(b, len(rem_days), a["level"])
    fchunks = distribute(fill_steps(b, a["weak_names"]), fill_d)
    psteps = preview_steps(b, prev_d)

    if b["type"] == "holiday":
        head = f"📅 剩余安排（{b['name']}·假期第{b['day_index']}天/共{b['total']}天，还剩 {b['remaining']} 天）"
    else:
        head = f"📅 剩余安排（周末·还剩 {b['remaining']} 天）"

    if a["level"] == "正常":
        if prev_d <= 0:
            phase = f"评估：需查漏补缺 {a['kp_n']} 个薄弱点、近 7 天错题 {a['err_n']} 条 → 正常；本次 {fill_d} 天全部用于补漏"
        else:
            phase = (f"评估：需查漏补缺 {a['kp_n']} 个薄弱点、近 7 天错题 {a['err_n']} 条 → 正常；"
                     f"前 {fill_d} 天补漏 → 后 {prev_d} 天预习")
    elif a["level"] == "偏多":
        if prev_d <= 0:
            phase = (f"评估：需查漏补缺 {a['kp_n']} 个薄弱点、近 7 天错题 {a['err_n']} 条 → 偏多；"
                     f"本次 {fill_d} 天全部用于补漏（不安排预习）")
        else:
            phase = (f"评估：需查漏补缺 {a['kp_n']} 个薄弱点、近 7 天错题 {a['err_n']} 条 → 偏多；"
                     f"补漏加至 {fill_d} 天 → 预习压缩为 {prev_d} 天")
    else:
        if prev_d <= 0:
            phase = (f"评估：需查漏补缺 {a['kp_n']} 个薄弱点、近 7 天错题 {a['err_n']} 条 → 过多；"
                     f"本次 {fill_d} 天全部用于补漏（不安排预习）")
        else:
            phase = (f"评估：需查漏补缺 {a['kp_n']} 个薄弱点、近 7 天错题 {a['err_n']} 条 → 过多；"
                     f"补漏 {fill_d} 天 → 预习仅 {prev_d} 天（少安排）")

    lines, days = [], []
    for i, dd in enumerate(rem_days):
        tag = "今天" if i == 0 else ("明天" if i == 1 else "")
        prefix = f"{tag}（{dd.strftime('%m-%d')} {wd_cn(dd)}）" if tag else f"{dd.strftime('%m-%d')}（{wd_cn(dd)}）"
        if i < fill_d:
            content = "；".join(fchunks[i]) if fchunks[i] else "查漏补缺"
            kind = "补漏"
        else:
            j = i - fill_d
            content = psteps[j] if j < len(psteps) else "机动（订正遗留 / 选中科目加练）"
            kind = "预习"
        lines.append(f"- {prefix}：{content}")
        days.append({"date": dd.isoformat(), "weekday": wd_cn(dd), "label": tag,
                     "phase": kind, "content": content})

    if b["remaining"] > 1:
        nd = rem_days[1]
        prompt = f"→ 明天（{nd.strftime('%m-%d')} {wd_cn(nd)}）记得再来找 AI，完成当天的学习任务。"
    else:
        tail = "假期" if b["type"] == "holiday" else "周末"
        prompt = f"→ 今天是本{tail}最后一天，把上面的任务完成；明天起按周计划正常学习。"

    note = ""
    if b["remaining"] < b["total"]:
        note = "进入较晚——完整计划已按剩余天数合并执行；做不完的优先完成「订正/错题本」，其余往后顺延"

    extra = [f"- 注：{note}"] if note else []
    if a.get("note"):
        extra.insert(0, f"- 注：{a['note']}")
    text = "\n".join([head, f"- {phase}"] + lines + extra + ["", prompt])
    return {"active": True, "date": dstr, "block": b, "assessment": a,
            "fill_days": fill_d, "preview_days": prev_d, "days": days,
            "prompt": prompt, "note": note, "text": text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--base-dir", default=None, help="数据根目录（默认 D:/家教）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    dstr = args.date or os.environ.get("FAMTUTOR_TODAY") or date.today().isoformat()
    r = build(dstr, args.base_dir)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if not r["active"]:
        print(f"[剩余安排] {dstr}：今天不是周末/假期中途（工作日或调休上班日）——按周计划正常执行。")
        return
    print(r["text"])


if __name__ == "__main__":
    main()
