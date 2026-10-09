#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
init-learning-state.py
======================
初始化学习规划.md + 学习状态.json

参考：
- references/state-schema.md（完整 schema）
- references/weekly-plan-engine.md（周计划模式）

输入：
  --student  学生标识（如 "六年级学生"）
  --grade    年级（数字 6）
  --location 城市（默认深圳）
  --base-dir 家教根目录（默认 D:/家教）

输出：
  - D:/家教/系统/学习规划.md（骨架）
  - D:/家教/系统/学习状态.json（完整 schema 初版）
  - 控制台汇总报告

执行：
  python init-learning-state.py \
      --student "六年级学生" \
      --grade 6 \
      --location 深圳

作者：Hermes 家庭教师系统
最后更新：2026-09-12
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 中国标准时间
CST = timezone(timedelta(hours=8))


def now_cst() -> str:
    """返回 ISO 格式的当前 CST 时间"""
    return datetime.now(CST).strftime("%Y-%m-%dT%H:%M:%S")


def load_kp_index(subject_dir: Path) -> dict:
    """读取某科的 KP 索引"""
    kp_dir = subject_dir / "知识点及掌握情况"
    index_file = kp_dir / "index.json"
    if not index_file.exists():
        raise FileNotFoundError(f"未找到 KP 索引：{index_file}")
    return json.loads(index_file.read_text(encoding="utf-8"))


def build_subject_block(subject_name: str, subject_dir: Path) -> dict:
    """为某科构建 学习状态.json 中的 subjects 块"""
    kp_index = load_kp_index(subject_dir)

    kps_block = {}
    for unit in kp_index["units"]:
        unit_id = unit["id"]
        for kp_id in unit.get("kp_ids", []):
            kps_block[kp_id] = {
                "name": "",  # 由 weekly-plan 生成时按需补全
                "unit_id": unit_id,
                "master": 0,
                "attempts": 0,
                "correct": 0,
                "last_seen": None,
                "last_correct": None,
                "mistake_types": [],
                "consecutive_correct": 0,
                "consecutive_wrong": 0,
                "enabled_in_pool": True,
            }

    return {
        "subject_meta": {
            "publisher": kp_index.get("publisher", ""),
            "version": kp_index.get("version", ""),
            "isbn": kp_index.get("isbn", ""),
            "total_pages": kp_index.get("total_pages", 0),
            "total_kps": kp_index.get("total_kps", 0),
            "total_units": len(kp_index["units"]),
            "kp_index_path": str(
                (subject_dir / "知识点及掌握情况/index.json").relative_to(subject_dir.parent)
            ),
        },
        "current_unit": kp_index["units"][0]["id"] if kp_index["units"] else None,
        "current_kps_in_progress": kp_index["units"][0].get("kp_ids", [])[:2] if kp_index["units"] else [],
        "kps": kps_block,
        "mistakes_recent": [],
        "exams_history": [],
        "quiz_pool_meta": {
            "total_questions": 0,
            "enabled_questions": 0,
            "last_index_update": None,
            "kp_coverage_pct": 0,
        },
    }


def build_learning_state(student: str, grade: int, location: str, base_dir: Path) -> dict:
    """构建完整的 学习状态.json 字典"""
    subjects = {}
    for subject_name in ["数学", "语文", "英语"]:
        subject_dir = base_dir / subject_name
        if not subject_dir.exists():
            print(f"⚠ 跳过：未找到科目目录 {subject_dir}")
            continue
        subjects[subject_name] = build_subject_block(subject_name, subject_dir)

    state = {
        "schema_version": "2026-09-12",
        "student": {
            "name": student,
            "grade": grade,
            "semester": "2026 秋",
            "location": location,
            "active_date": now_cst()[:10],
        },
        "subjects": subjects,
        "global": {
            "current_mode": "预习周",
            "current_mode_detail": {s: "预习周" for s in subjects.keys()},
            "last_mode_change": None,
            "weak_kps_global": [],
        },
        "weekly_history": [],
        "next_actions": [
            "周日下午自动跑 generate-weekly-plan.py",
            "grade-mistake.py 完成首次作业后会自动更新状态",
        ],
    }
    return state


def render_learning_plan_md(state: dict, base_dir: Path) -> str:
    """渲染 学习规划.md 的 Markdown 骨架"""
    s = state["student"]
    lines = []

    lines.append(f"# 学习规划（{s['grade']}年级{s['semester']}）")
    lines.append("")
    lines.append(f"> ⚡ 当前模式：**{state['global']['current_mode']}**")
    lines.append(f"> 📅 今日：{s['active_date']}")
    lines.append(f"> 📊 薄弱 KP 数：0")
    lines.append(f"> 🎯 本周目标：开学报到，建立初始 KP 状态机")
    lines.append("")
    lines.append(f"> 上次模式切换：—（初始）")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📖 学期总览")
    lines.append("")

    week_counter = 1
    for subject_name, block in state["subjects"].items():
        meta = block["subject_meta"]
        lines.append(f"### {subject_name}（{meta['publisher']}）")
        lines.append(f"共 {meta['total_kps']} KP / {meta['total_units']} 单元")
        lines.append("")

        kp_index_path = base_dir / subject_name / meta["kp_index_path"]
        if kp_index_path.exists():
            kp_index = json.loads(kp_index_path.read_text(encoding="utf-8"))
            for unit in kp_index["units"]:
                uid = unit["id"]
                uname = unit.get("name", "")
                kp_n = unit.get("kp_count", len(unit.get("kp_ids", [])))
                week_start = week_counter
                week_end = week_counter + max(1, kp_n // 3) - 1
                lines.append(f"- **{uid}** {uname}（{kp_n} KP）— Week {week_start}-{week_end}")
                week_counter = week_end + 1

        lines.append("")

    lines.append("> ⚠ **学期关键节点仅供参考，最终看作业信号**（详见 weekly-plan-engine.md）")
    lines.append("> - 期中：约 Week 8-10")
    lines.append("> - 期末：约 Week 18-20")
    lines.append("> - 寒暑假：自主预习模式")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 📅 每周计划")
    lines.append("")
    lines.append("### Week 1（开学报到）")
    lines.append("**模式**：预习周")
    lines.append("")
    lines.append("本周为初始周，KP 状态全部归零。")
    lines.append("- 完成三科第一课的预习（按 KP 顺序）")
    lines.append("- 拍照上传第一次作业 → grade-mistake.py 自动更新状态")
    lines.append("- 下周日 22:00 自动生成 Week 2 完整计划")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 学期目标")
    lines.append("")
    lines.append("- [ ] 三科所有 KP 掌握度 ≥ 80%")
    lines.append("- [ ] 期中/期末各科 ≥ 85 分")
    lines.append("- [ ] 错题回灌覆盖率 100%")
    lines.append("- [ ] 薄弱 KP 数量 < 总 KP 数的 10%")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="初始化家庭教师学习规划+状态")
    parser.add_argument("--student", default="六年级学生", help="学生标识")
    parser.add_argument("--grade", type=int, default=6, help="年级")
    parser.add_argument("--location", default="深圳", help="城市")
    parser.add_argument("--base-dir", default=None, help="自动探测 D:/家教 或 /d/家教")
    parser.add_argument("--force", action="store_true", help="覆盖已有文件")
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
    if not base_dir.exists():
        print(f"❌ 未找到家教根目录：{base_dir}")
        sys.exit(1)

    system_dir = base_dir / "系统"
    system_dir.mkdir(parents=True, exist_ok=True)

    state_file = system_dir / "学习状态.json"
    plan_file = system_dir / "学习规划.md"

    if (state_file.exists() or plan_file.exists()) and not args.force:
        print(f"⚠ 文件已存在：")
        if state_file.exists():
            print(f"  - {state_file}")
        if plan_file.exists():
            print(f"  - {plan_file}")
        print("  使用 --force 强制覆盖（会丢失旧数据，建议先备份）")
        sys.exit(1)

    if state_file.exists() and args.force:
        backup = system_dir / "_backup" / f"学习状态_{now_cst()[:10]}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        state_file.rename(backup)
        print(f"✓ 旧状态已备份到 {backup}")
    if plan_file.exists() and args.force:
        backup = system_dir / "_backup" / f"学习规划_{now_cst()[:10]}.md"
        backup.parent.mkdir(parents=True, exist_ok=True)
        plan_file.rename(backup)
        print(f"✓ 旧规划已备份到 {backup}")

    print(f"⏳ 扫描三科 KP 索引（base_dir={base_dir}）...")
    state = build_learning_state(args.student, args.grade, args.location, base_dir)

    state_file.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"✓ 已写入 {state_file}")

    plan_md = render_learning_plan_md(state, base_dir)
    plan_file.write_text(plan_md, encoding="utf-8")
    print(f"✓ 已写入 {plan_file}")

    total_kps = sum(b["subject_meta"]["total_kps"] for b in state["subjects"].values())
    total_units = sum(b["subject_meta"]["total_units"] for b in state["subjects"].values())

    print()
    print("=" * 50)
    print("初始化完成")
    print("=" * 50)
    print(f"学生：{args.student}（{args.grade}年级 2026 秋）")
    print(f"城市：{args.location}")
    print(f"科目数：{len(state['subjects'])}")
    print(f"总 KP 数：{total_kps}")
    print(f"总单元数：{total_units}")
    print(f"初始模式：{state['global']['current_mode']}")
    print(f"生成时间：{now_cst()}")
    print()
    print("下一步：")
    print("  1. 检查 学习规划.md 内容是否符合预期")
    print("  2. 开始第一次作业 → grade-mistake.py 自动更新状态")
    print("  3. 周日 22:00 自动跑 generate-weekly-plan.py")


if __name__ == "__main__":
    main()
