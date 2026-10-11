#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generate-weekly-plan.py — 周计划生成器（2026-09-26 新建）

背景（用户 2026-09-25 深夜明确）：
  - 不用 cron（电脑不常开）：由 time-inject-hook 在"跨周未更新"时注入提醒，
    由当次交互触发本脚本；本脚本完成后回写 周计划状态.json（hook 看这个文件）。
  - 周计划 = 「学期知识点 + 学校进度（作业判定） + 薄弱KP」落到每周的可执行安排。

输入：D:/家教/系统/学习状态.json + {科目}/知识点及掌握情况/ + {科目}/错题集/
输出：D:/家教/系统/学习规划.md（本周块 增量更新 + 顶部横幅刷新） + 系统/周计划状态.json

用法：
  D:/Python312/python.exe generate-weekly-plan.py --dry-run   # 只看结果不写
  D:/Python312/python.exe generate-weekly-plan.py             # 正式生成/更新
"""
import argparse
import json
import os
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

TERM_START = date(2026, 9, 1)          # 学期首周基准（用于 Week N 编号）
MODE_NEW = "预习周"
MODE_UNIT = "单元复习周"
MODE_EXAM = "期中/期末周"


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def load_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default


def kp_name(subject_dir: Path, kp_id: str) -> str:
    d = load_json(subject_dir / "知识点及掌握情况" / f"{kp_id}.json", {}) or {}
    return d.get("name") or kp_id


def unit_of(kp_id: str) -> str:
    return kp_id.split(".")[0] if "." in kp_id else kp_id


def monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def week_label(week_start: date) -> str:
    n = (week_start - TERM_START).days // 7 + 1
    week_end = week_start + timedelta(days=6)
    return f"Week {n}（{week_start.isoformat()} ~ {week_end.isoformat()}）"


def collect_subject(base: Path, subject: str, sub_state: dict, today: date = None):
    """收集某科的：模式 / 薄弱KP / 最近错题 / 进度"""
    today = today or date.today()
    sdir = base / subject
    kps = sub_state.get("kps", {})
    weak, seen = [], []
    for kp_id, v in kps.items():
        name = v.get("name") or kp_name(sdir, kp_id)
        if not v.get("name"):
            v["name"] = name
        attempts = v.get("attempts", 0)
        if attempts > 0:
            seen.append(kp_id)
        if attempts > 0 and (v.get("master", 0) < 60 or v.get("consecutive_wrong", 0) >= 2):
            weak.append((kp_id, name, v.get("master", 0)))
    weak.sort(key=lambda x: x[2])
    recent = [m for m in sub_state.get("mistakes_recent", [])][-8:]
    # 错题集近 7 天
    bank = []
    bk_dir = sdir / "错题集"
    if bk_dir.exists():
        cutoff = (today - timedelta(days=7)).isoformat()
        for f in bk_dir.glob("错题集_*.json"):
            d = load_json(f, {}) or {}
            for r in d.get("records", []):
                if str(r.get("date", "")) >= cutoff:
                    bank.append(r)
    return {"weak": weak, "recent": recent, "bank": bank,
            "mode": None,  # 由调用方填
            "unit": sub_state.get("current_unit", ""),
            "kp_count": len(kps),
            "seen_count": len(seen)}


def remaining_section(td: date, base_dir="D:/家教") -> str:
    """「📍 剩余安排」段（2026-10-10 用户要求）：学生周六才上传 / 长假第 N 天才交，
    剩余每一天都要有安排、不能空着；今天在周末/≥3天假期中途时返回该段，否则空串。
    数据来自 day-schedule.py（同目录）。"""
    script = Path(__file__).resolve().parent / "day-schedule.py"
    if not script.exists():
        return ""
    try:
        import subprocess as _sp
        r = _sp.run(["D:/Python312/python.exe", str(script), "--date", td.isoformat(),
                     "--base-dir", str(base_dir), "--json"],
                    capture_output=True, timeout=60)
        data = json.loads(r.stdout.decode("utf-8", errors="replace") or "{}")
    except Exception:
        return ""
    if not data.get("active"):
        return ""
    return ("<!-- REMAINING:BEGIN -->\n"
            f"## 📍 剩余安排（生成：{td.isoformat()}）\n\n"
            + data.get("text", "") + "\n\n<!-- REMAINING:END -->\n\n---\n\n")


def holiday_block_for_week(week_start: date) -> str:
    """节假日周块（2026-09-29 用户要求）：≤3天=1周期；≥5天=2周期+预习1课时。数据：系统/holidays.json"""
    hp = Path("D:/家教/系统/holidays.json")
    if not hp.exists():
        hp = Path("/d/家教/系统/holidays.json")
    if not hp.exists():
        return ""
    try:
        data = json.loads(hp.read_text(encoding="utf-8"))
    except Exception:
        return ""
    we = week_start + timedelta(days=6)
    hs_all = sorted((hh for ys in data.get("years", {}).values() for hh in ys), key=lambda x: x["start"])
    for h in hs_all:
        hs, he = date.fromisoformat(h["start"]), date.fromisoformat(h["end"])
        if hs <= we and he >= week_start and h.get("days", 0) >= 3:
            out = [f"### 🎉 {h['name']}假期安排（{h['days']}天 → {h['cycles']} 个周期）"]
            out.append(f"- 周期数：{h['cycles']} 个（每周期 = 复习 + 查漏补缺错题卷 1 套，generate-exam.py 出卷）")
            if h.get("preview"):
                out.append("- 预习：向前预习 1 课时（裁剪课本下一课时 → OpenMAIC 上课 → 预习小试卷 → 记录漏洞 → 查漏补缺 ≤2 轮）")
            if h.get("makeup_workdays"):
                out.append("- 调休上班：" + "、".join(h["makeup_workdays"]))
            out.append("")
            return "\n".join(out) + "\n"
    return ""


def build_week_block(week_start: date, state: dict, per_sub: dict) -> str:
    label = week_label(week_start)
    modes = {}
    for s in per_sub:
        modes[s] = state.get("global", {}).get("current_mode_detail", {}).get(s, MODE_NEW)
    gmode = state.get("global", {}).get("current_mode", MODE_NEW)
    header_mode = "；".join(f"{s} {m}" for s, m in modes.items())

    lines = [f"## {label}", f"**当前模式**：{header_mode}"]

    # 最近表现
    perf = []
    for s, info in per_sub.items():
        if info["recent"]:
            last = info["recent"][-1]
            perf.append(f"{s} {last.get('type', last.get('kp_id', ''))}（{last.get('stem_summary', '')[:40]}）")
    lines.append(f"**学生最近表现**：" + ("；".join(perf) if perf else "（暂无新错题记录）"))
    lmc = state.get("global", {}).get("last_mode_change") or {}
    if lmc.get("at"):
        lines.append(f"**触发信号**：{lmc.get('at', '')[:10]} {lmc.get('trigger_signal', '')}（{lmc.get('old_mode','')} → {lmc.get('new_mode','')}）")
    lines.append("")

    # 每日安排（按模式）
    lines.append("### 每日安排")
    subs = [s for s in ("数学", "语文", "英语") if s in per_sub]
    if MODE_NEW in modes.values():
        days = ["周一", "周二", "周三", "周四", "周五"]
        for i, s in enumerate(subs):
            info = per_sub[s]
            weak_txt = "；".join(f"{n}（master={m}）" for _, n, m in info["weak"][:2]) or "无标记薄弱"
            lines.append(f"**{days[i] if i < len(days) else '机动'}（{s}）**")
            lines.append(f"- 薄弱点强化：{weak_txt}")
            lines.append(f"- 课后练习：{s} {info['unit'] or '当前单元'}（同 KP 错题追加同类题）")
            if info["bank"]:
                lines.append(f"- 错题回灌：近 7 天错题 {len(info['bank'])} 条，抽 1 道重做")
        lines.append("**周末**")
        lines.append("- 周测：单元小测卷（generate-exam.py，含错题回灌 ≥ 1 道；回灌题标 ★必做）")
        lines.append("- 错题本：把本周错题全部整理进错题本；做周末卷前先翻一遍错题本")
        lines.append("- 预习：下周新课（按 KP 顺序）")
    if MODE_UNIT in modes.values():
        lines.append("**周一–周三（每日一科）**")
        for s in subs:
            info = per_sub[s]
            lines.append(f"- {s} {info['unit'] or ''} 单元复习（{info['kp_count']} 个 KP 过一遍，薄弱优先）")
        lines.append("**周四–周五（错题集中攻克）**")
        lines.append("- 各科错题集本周新增 → 重做 + 同类题回灌")
        lines.append("**周末**")
        lines.append("- 单元复习卷（各科 1 套）+ 错题回灌（≥1 道/科，标 ★必做）")
        lines.append("- 错题本：本周错题全部整理进错题本；对照错题本复盘一遍（盖住答案重做）")
    if MODE_EXAM in modes.values():
        lines.append("**周一–周二（KP 全面回顾）**")
        for s in subs:
            info = per_sub[s]
            lines.append(f"- {s} 按掌握度排序过 KP（薄弱先复习；共 {info['kp_count']} 个）")
        lines.append("**周三–周五（模拟卷 + 错题）**")
        lines.append("- 期中/期末模拟卷（各科）；错题集中攻克（回灌 ≥2 道/科）")
        lines.append("**周末**")
        lines.append("- 计时模拟 1 套 + 背诵/默写清单过一遍")
        lines.append("- 错题本：全部错题过一遍，最常错的几题抄进错题本重点标注")
    lines.append("")

    hblk = holiday_block_for_week(week_start)
    if hblk:
        lines.append(hblk)

    # 回灌清单
    lines.append("### 错题回灌清单")
    any_bank = False
    for s, info in per_sub.items():
        for r in info["bank"][:5]:
            any_bank = True
            kps = "、".join(r.get("kp_names") or r.get("kp_ids") or [])
            lines.append(f"- {s} {kps}：{str(r.get('question',''))[:42]}（{r.get('date','')}）")
        for kp_id, name, m in info["weak"][:3]:
            any_bank = True
            lines.append(f"- {s} {name}（master={m}）→ 同类题 1 道")
    if not any_bank:
        lines.append("- （本周暂无回灌项；新错题入库后自动补）")
    lines.append("")

    # 薄弱 KP
    lines.append("### 薄弱 KP（master < 60%）")
    any_weak = False
    for s, info in per_sub.items():
        for kp_id, name, m in info["weak"][:6]:
            any_weak = True
            lines.append(f"- {s} {kp_id} {name}（master={m}%）")
    if not any_weak:
        lines.append("- （暂无；继续积累做题数据）")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", default="D:/家教")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--today", default=None, help="按指定日期生成（YYYY-MM-DD；默认今天）——测试/补排用")
    args = ap.parse_args()

    td = date.fromisoformat(args.today) if args.today else (
        date.fromisoformat(os.environ["FAMTUTOR_TODAY"]) if os.environ.get("FAMTUTOR_TODAY") else date.today())
    base = Path(args.base_dir)
    state_p = base / "系统/学习状态.json"
    plan_p = base / "系统/学习规划.md"
    mark_p = base / "系统/周计划状态.json"
    state = load_json(state_p)
    if not state:
        print("[x] 读不到学习状态.json，先跑 init-learning-state.py")
        sys.exit(1)

    subjects = state.get("subjects", {})
    per_sub = {s: collect_subject(base, s, v, td) for s, v in subjects.items()}

    # 薄弱汇总写回（不 dry-run 时）
    weak_global = []
    for s, info in per_sub.items():
        weak_ids = [k for k, _, _ in info["weak"]]
        state["subjects"][s]["weak_kps"] = weak_ids
        weak_global += [f"{s}/{k}" for k in weak_ids]
    new_mode = state.get("global", {}).get("current_mode", MODE_NEW)

    # 周块
    ws = monday_of(td)
    block = build_week_block(ws, state, per_sub)

    # 组装 学习规划.md
    old = plan_p.read_text(encoding="utf-8") if plan_p.exists() else ""
    weak_count = len(weak_global)
    goal_by_mode = {
        MODE_NEW: "查漏补缺 + 预习",
        MODE_UNIT: "查漏补缺 + 单元复习",
        MODE_EXAM: "查漏补缺 + 全面复习",
    }
    banner = (f"# 学习规划（{state.get('student', {}).get('grade', 6)}年级"
              f"{state.get('student', {}).get('semester', '')}）\n\n"
              f"> ⚡ 当前模式：**{new_mode}**\n"
              f"> 📅 更新时间：{td.isoformat()}\n"
              f"> 📊 薄弱 KP 数：{weak_count}\n"
              f"> 🎯 本周目标：{goal_by_mode.get(new_mode, '')}\n")
    lmc = state.get("global", {}).get("last_mode_change") or {}
    banner += f"\n> 上次模式切换：{lmc.get('at', '—')}（{lmc.get('old_mode','')} → {lmc.get('new_mode','')}）\n\n---\n\n"

    # 学期总览（保留原文或重生）
    overview = "## 📖 学期总览\n\n"
    for s, v in subjects.items():
        meta = v.get("subject_meta", {})
        overview += (f"### {s}（{meta.get('publisher', '')}）\n"
                     f"共 {meta.get('total_kps', len(v.get('kps', {})))} KP / {meta.get('total_units', '?')} 单元\n\n")
    overview += "> ⚠ **学期关键节点仅供参考，最终看作业信号**（详见 weekly-plan-engine.md）\n\n---\n\n"

    # 每周计划段：按周 label 去重 upsert（旧的保留、同周替换）
    import re as _re
    existing_weeks = []
    if old:
        m = _re.search(r"## 📅 每周计划\s*\n(.*?)(?=\n## 🎯 |\Z)", old, _re.S)
        if m:
            body = m.group(1)
            parts = _re.split(r"(?m)^(?=## Week \d+（)", body)
            existing_weeks = [_re.sub(r"\n?-{3,}\s*$", "", p).strip() for p in parts if p.strip()]
    label = block.splitlines()[0][3:]  # "Week N（...）"
    upserted = False
    for i, wk in enumerate(existing_weeks):
        if wk.splitlines()[0][3:] == label:
            existing_weeks[i] = block
            upserted = True
    if not upserted:
        existing_weeks.append(block)

    weeks_sec = "## 📅 每周计划\n\n" + "\n".join(w.strip() + "\n\n---\n\n" for w in existing_weeks)
    goals = ("## 🎯 学期目标\n\n"
             "- [ ] 三科所有 KP 掌握度 ≥ 80%\n- [ ] 期中/期末各科 ≥ 85 分\n"
             "- [ ] 错题回灌覆盖率 100%\n- [ ] 薄弱 KP 数量 < 总 KP 数的 10%\n")
    # 剩余安排段（周末/假期中途进入——2026-10-10 用户要求）
    rem_sec = remaining_section(td, base)

    new_plan = banner + rem_sec + overview + weeks_sec + goals

    if args.dry_run:
        print("===== (dry-run) 将要写入 学习规划.md =====")
        print(new_plan[:3200])
        print(f"...（共 {len(new_plan)} 字符）")
        print("\n[dry-run] 未写入任何文件")
        return

    # 备份 + 写入
    bak_dir = base / "系统/_backup"
    bak_dir.mkdir(exist_ok=True)
    if plan_p.exists():
        import shutil as _sh
        _sh.copyfile(plan_p, bak_dir / f"学习规划_{td.isoformat()}.md.bak")
    plan_p.write_text(new_plan, encoding="utf-8")
    state_p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    mark_p.write_text(json.dumps({
        "last_generated": td.isoformat(),
        "week": week_label(ws),
        "generated_at": now_str(),
        "modes": state.get("global", {}).get("current_mode_detail", {}),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.quiet:
        print(f"✓ 学习规划.md 已更新（{label}；薄弱 {weak_count} 个）")
        print(f"✓ 周计划状态.json 已写回（last_generated={td.isoformat()}）")
        if rem_sec:
            print("✓ 「📍 剩余安排」段已写入（今天在周末/假期中途）")
        for s, info in per_sub.items():
            names = "、".join(n for _, n, _ in info["weak"][:3]) or "无"
            print(f"  · {s}: 薄弱 {len(info['weak'])} 个 [{names}]；近7天错题 {len(info['bank'])} 条")


if __name__ == "__main__":
    main()
