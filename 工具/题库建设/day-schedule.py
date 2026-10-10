#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
day-schedule.py — 中途进入的「剩余安排」引擎（2026-10-10 用户要求）

背景（用户原话）：
  「遇到了周末，学生周六才上传作业。ai 应该安排周日的学习计划告知学生，
   让学生明天再来找 ai 完成明天的学习任务，而不是周日空着。
   长假也是——比如五一/十一第三天才提交作业，应该安排后几天的学习安排。」

规则（承接 2026-09-29「法定节假日周期规则」，数据=系统/holidays.json）：
  · 周末（1 个周期）        = 周测卷 → 错题本复盘 → 预习下周新课
  · 3 天小长假（1 个周期）  = 复习 → 错题卷 → 查漏补缺 + 错题本
  · 5/7 天（2 周期+预习）   = 周期1（复习→错题卷→补漏）→ 周期2（同）→ 预习课
  · 调休上班日按工作日（不生成剩余安排）

摊派算法：把「步骤」按剩余天数从左到右均衡铺开（每天取 ceil(剩余步骤/剩余天数)）；
  · 剩余天数 < 步骤数 → 合并执行（压缩版；提示做不完优先顺延「订正/错题本」）
  · 剩余天数 > 步骤数 → 富余的日子标「机动（订正/薄弱加练/休息）」

落点（详见 skill family-tutor；三处缺一不可）：
  ① generate-weekly-plan.py 刷新时写进 学习规划.md 的「📍 剩余安排」段；
  ② day1-pipeline.py 把该段附进 错题清单 末尾（交付消息带上）；
  ③ Hermes 交付消息必须含该段 + 「明天记得再来找 AI」提示。

用法：
  python day-schedule.py                      # 今天
  python day-schedule.py --date 2026-10-03    # 指定日期
  python day-schedule.py --date 2026-10-03 --json
环境变量：FAMTUTOR_TODAY=YYYY-MM-DD 可覆盖「今天」（自测/补排用）。
"""
import argparse
import importlib.util
import json
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
WD = "一二三四五六日"


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


def block_steps(b: dict):
    """把一个学习块拆成有序步骤（供按天摊派）。"""
    if b["type"] == "weekend":
        return ["周测卷（完成 + 订正）",
                "错题本复盘（本周错题盖住答案重做）",
                "预习下周新课（按 KP 顺序）"]
    if b["cycles"] <= 1:
        return ["复习（薄弱 KP 优先）",
                "错题卷（回灌★必做）+ 订正",
                "查漏补缺 + 错题本"]
    steps = []
    for i in range(1, b["cycles"] + 1):
        steps += [f"周期{i} 复习（薄弱 KP 优先）",
                  f"周期{i} 错题卷（回灌★必做）+ 订正",
                  f"周期{i} 查漏补缺 + 错题本"]
    if b["preview"]:
        steps.append("预习课（1 课时）+ 预习小试卷")
    return steps


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


def build(dstr: str) -> dict:
    b = find_block(dstr)
    if not b:
        return {"active": False, "date": dstr}
    d0 = date.fromisoformat(dstr)
    rem_days = [d0 + timedelta(days=i) for i in range(b["remaining"])]
    steps = block_steps(b)
    chunks = distribute(steps, len(rem_days))

    if b["type"] == "holiday":
        head = f"📅 剩余安排（{b['name']}·假期第{b['day_index']}天/共{b['total']}天，还剩 {b['remaining']} 天）"
    else:
        head = f"📅 剩余安排（周末·还剩 {b['remaining']} 天）"

    lines, days = [], []
    for i, (dd, ch) in enumerate(zip(rem_days, chunks)):
        tag = "今天" if i == 0 else ("明天" if i == 1 else "")
        content = "；".join(ch) if ch else "机动（订正遗留 / 薄弱加练 / 休息）"
        prefix = f"{tag}（{dd.strftime('%m-%d')} {wd_cn(dd)}）" if tag else f"{dd.strftime('%m-%d')}（{wd_cn(dd)}）"
        lines.append(f"- {prefix}：{content}")
        days.append({"date": dd.isoformat(), "weekday": wd_cn(dd), "label": tag, "steps": ch})

    if b["remaining"] > 1:
        nd = rem_days[1]
        prompt = f"→ 明天（{nd.strftime('%m-%d')} {wd_cn(nd)}）记得再来找 AI，完成当天的学习任务。"
    else:
        tail = "假期" if b["type"] == "holiday" else "周末"
        prompt = f"→ 今天是本{tail}最后一天，把上面的任务完成；明天起按周计划正常学习。"

    note = ""
    if b["remaining"] < b["total"]:
        note = "进入较晚——完整计划已按剩余天数合并执行；做不完的优先完成「订正/错题本」，其余往后顺延"

    text = "\n".join([head] + lines + ([f"- 注：{note}"] if note else []) + ["", prompt])
    return {"active": True, "date": dstr, "block": b, "steps": steps,
            "days": days, "prompt": prompt, "note": note, "text": text}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="指定日期 YYYY-MM-DD（默认今天）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    dstr = args.date or os.environ.get("FAMTUTOR_TODAY") or date.today().isoformat()
    r = build(dstr)
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return
    if not r["active"]:
        print(f"[剩余安排] {dstr}：今天不是周末/假期中途（工作日或调休上班日）——按周计划正常执行。")
        return
    print(r["text"])


if __name__ == "__main__":
    main()
