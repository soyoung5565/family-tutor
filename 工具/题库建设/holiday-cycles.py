#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
holiday-cycles.py — 节假日周期引擎（2026-09-29 用户要求）

规则（数据源：D:/家教/系统/holidays.json）：
  · 周末 = 1 个周期（复习 + 查漏补缺错题卷 1 套）
  · 3 天小长假 = 与正常周末一致 = 1 个周期
  · 5 天 / 7 天（及春节 9 天）= 2 个周期 ＋ 向前预习 1 课时
  · 调休上班日按工作日处理

用法：
  python holiday-cycles.py                       # 今天 + 下一个节假日
  python holiday-cycles.py --date 2026-10-03     # 指定日期判定
  python holiday-cycles.py --week 2026-09-28     # 该周触达的节假日
"""
import argparse
import json
from datetime import date, timedelta
from pathlib import Path

CANDIDATES = [Path("D:/家教/系统/holidays.json"),
              Path("/d/家教/系统/holidays.json"),
              Path(__file__).resolve().parent.parent / "holidays.json"]


def load() -> dict:
    for p in CANDIDATES:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("holidays.json 未找到（应为 D:/家教/系统/holidays.json）")


def all_holidays() -> list:
    d = load()
    out = []
    for ys in d.get("years", {}).values():
        out += ys
    return sorted(out, key=lambda h: h["start"])


def classify(dstr: str) -> dict:
    d = date.fromisoformat(dstr)
    for h in all_holidays():
        if h["start"] <= dstr <= h["end"]:
            return {"date": dstr, "type": "holiday", "name": h["name"], "days": h["days"],
                    "cycles": h["cycles"], "preview": bool(h.get("preview")),
                    "range": "%s~%s" % (h["start"], h["end"])}
    for h in all_holidays():
        if dstr in (h.get("makeup_workdays") or []):
            return {"date": dstr, "type": "makeup_workday", "name": h["name"] + "调休上班",
                    "days": 0, "cycles": 0, "preview": False, "range": dstr}
    if d.weekday() >= 5:
        return {"date": dstr, "type": "weekend", "name": "周末", "days": 2, "cycles": 1,
                "preview": False, "range": dstr}
    return {"date": dstr, "type": "workday", "name": "工作日", "days": 0, "cycles": 0,
            "preview": False, "range": dstr}


def next_holiday(from_str: str = None) -> dict:
    from_str = from_str or date.today().isoformat()
    for h in all_holidays():
        if h["end"] >= from_str:
            return h
    return None


def week_hint(any_day_in_week: str) -> list:
    d = date.fromisoformat(any_day_in_week)
    ws = d - timedelta(days=d.weekday())
    we = ws + timedelta(days=6)
    hit = []
    for h in all_holidays():
        hs, he = date.fromisoformat(h["start"]), date.fromisoformat(h["end"])
        if hs <= we and he >= ws and h.get("days", 0) >= 3:
            hit.append(h)
    return hit


def _fmt(h: dict) -> str:
    extra = " + 向前预习 1 课时" if h.get("preview") else ""
    mk = ("；调休上班：" + "、".join(h.get("makeup_workdays") or [])) if h.get("makeup_workdays") else ""
    return "%s %s~%s（%d天）→ %d 个周期%s%s" % (h["name"], h["start"], h["end"], h["days"], h["cycles"], extra, mk)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="指定日期 YYYY-MM-DD")
    ap.add_argument("--week", help="指定周内任意一天，输出该周触达的节假日")
    args = ap.parse_args()

    if args.date:
        c = classify(args.date)
        print(json.dumps(c, ensure_ascii=False, indent=2))
        return
    if args.week:
        hits = week_hint(args.week)
        if not hits:
            print("[周] %s 所在周：无 ≥3 天节假日（按普通周末处理）" % args.week)
        for h in hits:
            print("[周] 触达：" + _fmt(h))
        return

    today = date.today().isoformat()
    c = classify(today)
    print("[今天] %s = %s%s" % (today, c["name"],
          ("（%d 天 → %d 个周期%s）" % (c["days"], c["cycles"], " + 预习" if c["preview"] else "")) if c["type"] == "holiday" else ""))
    nh = next_holiday(today)
    if nh:
        print("[下一节假日] " + _fmt(nh))
    else:
        print("[下一节假日] （数据文件里没有未来了——去更新 holidays.json！）")


if __name__ == "__main__":
    main()
