#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""micro-publish.py — 订正完成后：微课堂发布决策（复用 / 重生成 / 跳过）

流程位置：
  【订正期间】micro-lesson.py 预生成每个大题一个微课堂 + 写索引
  【学生订正】通过后
  【本脚本】对每一道大题决定：
    · 全部订正正确         → skip       （不需要微课堂）
    · 覆盖集与预生成一致    → reuse      （直接发布预生成的微课堂）
    · 覆盖集变小（部分订正对）→ regenerate（只覆盖仍错的小题，重新生成一课）
    · 没有可用预生成        → generate   （现场生成）

用法:
  python micro-publish.py --subject 数学
  python micro-publish.py --subject 数学 --mistakes X.json --comparison 订正对比_X.json --index 微课索引_X.json
  python micro-publish.py --subject 数学 --dry-run    # 只决策，不生成

输出（D:/家教/{subject}/课件）:
  微课发布_{date}.json    发布清单（每组的决定 + 播放链接）
  微课发布_{date}.md      给人看的发布清单
"""
import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path


def _load_micro_lesson():
    """加载同目录的 micro-lesson.py（文件名带连字符，不能直接 import）。"""
    p = Path(__file__).resolve().parent / "micro-lesson.py"
    spec = importlib.util.spec_from_file_location("micro_lesson", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ml = _load_micro_lesson()

OPENMAIC_BASE = ml.OPENMAIC_BASE
DEFAULT_TUTOR_ROOT = ml.DEFAULT_TUTOR_ROOT


def find_latest(dir_path, pattern):
    """按 mtime 找目录里最新的匹配文件。"""
    cands = sorted(Path(dir_path).glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    return cands[0] if cands else None


def load_mistakes(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("mistakes") or data.get("items") or []
    return data


def decide(group_info, index_entry):
    """对一道大题做发布决策。返回 (decision, covered_ids, note)。"""
    target = list(group_info.get("unfixed", []))
    all_ids = list(group_info.get("mistake_ids", []))

    if not target:
        return "skip", [], "全部订正正确，不需要微课堂"

    ready = (
        index_entry is not None
        and index_entry.get("status") == "ready"
        and index_entry.get("lesson_file")
        and Path(index_entry["lesson_file"]).exists()
    )
    if ready:
        if set(target) == set(all_ids):
            return "reuse", target, "覆盖集不变，复用预生成的微课堂"
        return "regenerate", target, f"覆盖集变小（{len(all_ids)}→{len(target)} 个小题），重新生成"
    return "generate", target, "没有可用的预生成，现场生成"


def main():
    ap = argparse.ArgumentParser(description="Decide & publish micro-lessons after corrections")
    ap.add_argument("--subject", default="数学")
    ap.add_argument("--tutor-root", default=str(DEFAULT_TUTOR_ROOT))
    ap.add_argument("--date", help="日期（默认今天），用于定位 订正对比/微课索引")
    ap.add_argument("--mistakes", help="原 mistakes.json（缺省从订正对比里读 mistakes_file）")
    ap.add_argument("--comparison", help="订正对比_*.json（缺省自动找最新）")
    ap.add_argument("--index", help="微课索引_*.json（缺省自动找最新）")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true", help="只决策不生成")
    args = ap.parse_args()

    subject_cn = ml.resolve_subject(args.subject)
    tutor_root = Path(args.tutor_root)
    out_dir = tutor_root / subject_cn / "课件"
    out_dir.mkdir(parents=True, exist_ok=True)
    system_dir = Path("D:/家教/系统")
    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    # ---- 定位输入文件 ----
    comp_path = Path(args.comparison) if args.comparison else (
        find_latest(system_dir, f"订正对比_{date_str}.json") or find_latest(system_dir, "订正对比_*.json")
    )
    if not comp_path or not Path(comp_path).exists():
        print("[error] 找不到 订正对比_*.json（先跑 collect-corrections.py）", file=sys.stderr)
        sys.exit(1)
    comparison = json.loads(Path(comp_path).read_text(encoding="utf-8"))

    idx_path = Path(args.index) if args.index else (
        find_latest(out_dir, f"微课索引_{date_str}.json") or find_latest(out_dir, "微课索引_*.json")
    )
    index = {"groups": {}}
    if idx_path and Path(idx_path).exists():
        try:
            index = json.loads(Path(idx_path).read_text(encoding="utf-8"))
        except Exception:
            index = {"groups": {}}

    mistakes_path = args.mistakes or comparison.get("mistakes_file")
    mistakes = []
    if mistakes_path and Path(str(mistakes_path)).exists():
        mistakes = load_mistakes(mistakes_path)

    print(f"订正对比: {comp_path}")
    print(f"微课索引: {idx_path or '（无）'}")
    print(f"错题文件: {mistakes_path or '（无）'}")

    # ---- 逐组决策 ----
    byid = {str(m.get("id")): m for m in mistakes}
    items = {}
    need_gen = {}
    for key, g in comparison.get("groups", {}).items():
        idx_entry = (index.get("groups") or {}).get(key)
        dec, covered, note = decide(g, idx_entry)
        item = {
            "group_key": key,
            "label": g.get("label", key),
            "decision": dec,
            "covered_ids": covered,
            "note": note,
            "classroom_id": None,
            "lesson_file": None,
            "play_url": None,
            "status": "skipped" if dec == "skip" else ("reuse" if dec == "reuse" else "pending"),
            "error": None,
        }
        if dec == "reuse":
            item["classroom_id"] = idx_entry.get("classroom_id")
            item["lesson_file"] = idx_entry.get("lesson_file")
            item["play_url"] = f"{OPENMAIC_BASE}/classroom/{item['classroom_id']}"
            if set(covered) != set(g.get("mistake_ids", [])):
                item["note"] += "（注意：预生成覆盖与当前仍错小题不完全一致）"
        elif dec in ("generate", "regenerate"):
            missing_ids = [i for i in covered if i not in byid]
            if not mistakes or missing_ids:
                item["status"] = "failed"
                item["error"] = ("缺少错题文件（--mistakes）" if not mistakes
                                 else f"错题数据缺失: {missing_ids}")
            else:
                need_gen[key] = [byid[i] for i in covered]
        items[key] = item

    print(f"决策：需要生成/重生成 {len(need_gen)} 个，复用 {sum(1 for i in items.values() if i['decision']=='reuse')} 个，"
          f"跳过 {sum(1 for i in items.values() if i['decision']=='skip')} 个")

    # ---- 生成（generate / regenerate）----
    if need_gen and not args.dry_run:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        gen_plain = {k: v for k, v in need_gen.items() if items[k]["decision"] == "generate"}
        gen_v2 = {k: v for k, v in need_gen.items() if items[k]["decision"] == "regenerate"}
        results = {}
        if gen_plain:
            print(f"\n现场生成 {len(gen_plain)} 个微课堂...")
            results.update(ml.generate_groups(gen_plain, subject_cn, tutor_root, out_dir,
                                              args.timeout, ts, concurrency=args.concurrency, tag=""))
        if gen_v2:
            print(f"\n重新生成 {len(gen_v2)} 个微课堂（只覆盖仍错小题）...")
            results.update(ml.generate_groups(gen_v2, subject_cn, tutor_root, out_dir,
                                              args.timeout, ts, concurrency=args.concurrency, tag="_v2"))
        for key, res in results.items():
            it = items[key]
            if res.get("status") == "ready":
                it["status"] = "ready"
                it["classroom_id"] = res.get("classroom_id")
                it["lesson_file"] = res.get("lesson_file")
                it["play_url"] = f"{OPENMAIC_BASE}/classroom/{it['classroom_id']}"
                it["verified"] = res.get("verified")
            else:
                it["status"] = "failed"
                it["error"] = res.get("error")
    elif need_gen and args.dry_run:
        for key in need_gen:
            items[key]["status"] = "pending(dry-run)"

    # ---- 汇总 + 写发布清单 ----
    summary = {"reuse": 0, "regenerate": 0, "generate": 0, "skip": 0, "failed": 0, "pending": 0}
    for it in items.values():
        st = it["status"]
        if st == "skipped":
            summary["skip"] += 1
        elif st == "reuse":
            summary["reuse"] += 1
        elif st == "ready":
            summary[it["decision"]] = summary.get(it["decision"], 0) + 1
        elif st == "failed":
            summary["failed"] += 1
        else:
            summary["pending"] += 1

    publish = {
        "subject": subject_cn,
        "date": date_str,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "comparison_file": str(comp_path),
        "mistakes_file": str(mistakes_path) if mistakes_path else None,
        "index_file": str(idx_path) if idx_path else None,
        "items": items,
        "summary": summary,
    }
    pub_json = out_dir / f"微课发布_{date_str}.json"
    pub_json.write_text(json.dumps(publish, ensure_ascii=False, indent=2), encoding="utf-8")

    dec_zh = {"skip": "跳过（全对）", "reuse": "复用", "regenerate": "重新生成", "generate": "新生成"}
    lines = [f"# {subject_cn} 微课发布清单（{date_str}）", ""]
    lines.append("| 大题 | 决定 | 覆盖小题 | 微课堂 | 备注 |")
    lines.append("|---|---|---|---|---|")
    for key, it in items.items():
        if it.get("play_url"):
            link = f"[打开]({it['play_url']})"
        elif it["status"] == "skipped":
            link = "—"
        elif it["status"] == "failed":
            link = "生成失败"
        else:
            link = "（dry-run）"
        lines.append(f"| {it['label']} | {dec_zh.get(it['decision'], it['decision'])} | "
                     f"{', '.join(it['covered_ids']) or '—'} | {link} | {it['note']} |")
    lines.append("")
    lines.append(f"汇总：复用 {summary.get('reuse',0)} | 重新生成 {summary.get('regenerate',0)} | "
                 f"新生成 {summary.get('generate',0)} | 跳过 {summary.get('skip',0)} | 失败 {summary.get('failed',0)}")
    pub_md = out_dir / f"微课发布_{date_str}.md"
    pub_md.write_text("\n".join(lines), encoding="utf-8")

    # ---- 回写索引 post ----
    if idx_path and Path(idx_path).exists():
        for key, it in items.items():
            ml.update_index_post(idx_path, key, {
                "decision": it["decision"],
                "covered_ids": it["covered_ids"],
                "classroom_id": it["classroom_id"],
                "lesson_file": it["lesson_file"],
                "play_url": it["play_url"],
                "status": it["status"],
                "at": datetime.now().isoformat(timespec="seconds"),
            })

    # ---- 打印 ----
    print("\n=== 发布决定 ===")
    for key, it in items.items():
        line = f"  {it['label']}: {it['decision']} -> {it['status']}（覆盖 {', '.join(it['covered_ids']) or '—'}）"
        if it.get("play_url"):
            line += f" {it['play_url']}"
        if it.get("error"):
            line += f" [error] {it['error']}"
        print(line)
    print(f"\n发布清单: {pub_json}")
    print(f"发布清单(md): {pub_md}")

    if summary.get("failed", 0) > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
