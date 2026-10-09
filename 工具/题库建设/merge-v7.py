#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v7 合并：v6（PaddleOCR 文字+坐标） + vision 公式层 + 修正 unit 字段 bug

- 读取 vision_formulas/slide_NNN.json 的输出，写入每页 formulas 字段
- 用权威 slide_to_page_map 修正每页 unit（v6 里 unit 全是 u1 的 bug）
- 输出 D:/家教/数学/知识库/math_grade6_v7.json（不覆盖 v6）
"""
import json
import os

V6 = r"D:\家教\数学\知识库\math_grade6_v6.json"
VISION_DIR = r"D:\家教\数学\知识库\vision_formulas"
V7 = r"D:\家教\数学\知识库\math_grade6_v7.json"

# 权威单元边界（= v6.index.slide_to_page_map 的反推）
UNIT_STARTS = [
    (7, "u1"), (16, "u2"), (38, "u3"), (49, "sp1"), (54, "u4"), (62, "u5"),
    (72, "u6"), (78, "sp_math"), (80, "u7"), (91, "u8"), (96, "u9"),
    (108, "sp2"), (113, "r1"), (121, "appendix"),
]
NO_FORMULA_MARKERS = {"无", "该页无公式", "无公式", "本页没有公式", "本页无公式", "没有公式",
                      "本页没有任何公式或算式", "无公式或算式"}


def unit_for_slide(n: int) -> str:
    unit = "unknown"
    for start, uid in UNIT_STARTS:
        if start <= n:
            unit = uid
        else:
            break
    return unit


def parse_formulas(raw: str) -> list:
    lines = [ln.strip() for ln in (raw or "").splitlines() if ln.strip()]
    out = []
    for ln in lines:
        # 去掉"无"类整行标记和模型格式噪音
        if ln in NO_FORMULA_MARKERS or ln.startswith("无：") or ln.startswith("本页"):
            continue
        if ln.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")) and len(ln) > 2:
            ln = ln.split(".", 1)[1].strip()
        out.append(ln)
    return out


def main():
    with open(V6, encoding="utf-8") as f:
        v6 = json.load(f)

    # 收集 vision 输出
    vision = {}
    if os.path.isdir(VISION_DIR):
        for fn in sorted(os.listdir(VISION_DIR)):
            if not fn.startswith("slide_") or not fn.endswith(".json"):
                continue
            slide = int(fn.split("_")[1].split(".")[0])
            with open(os.path.join(VISION_DIR, fn), encoding="utf-8") as f:
                vision[slide] = json.load(f)

    total_formula_lines = 0
    pages_with_formulas = 0
    vision_ok = 0
    vision_err = 0

    for slide_key, page in v6["page_text"].items():
        n = int(slide_key)
        page["unit"] = unit_for_slide(n)  # 修 bug
        vf = vision.get(n)
        if vf and vf.get("status") == "ok":
            vision_ok += 1
            lines = parse_formulas(vf.get("formulas", ""))
            page["formulas"] = lines
            page["formulas_source"] = "vision:MiniMax-M3"
            if lines:
                pages_with_formulas += 1
                total_formula_lines += len(lines)
        else:
            vision_err += 1
            page["formulas"] = []
            page["formulas_source"] = "vision:none(跳过/失败)" if vf else "vision:未提取"

    # metadata / index 升级
    v6["metadata"]["version"] = "v7"
    v6["metadata"]["extraction_status"] = "v7 — PaddleOCR 文字+坐标 + MiniMax-M3 vision 公式层（2026-09-10）"
    v6["metadata"]["description"] = "v7 = v6 + 每页公式（vision 提取）+ unit 修正"
    v6["metadata"]["vision_extraction"] = {
        "date": "2026-09-10",
        "model": "MiniMax-M3 (Anthropic-compatible endpoint)",
        "pages_targeted": 121,
        "pages_ok": vision_ok,
        "pages_error_skipped": vision_err,
        "prompt_note": "只提取公式/算式，忽略测试题目文字",
    }
    v6["index"]["total_formula_lines"] = total_formula_lines
    v6["index"]["pages_with_formulas"] = pages_with_formulas
    v6["index"]["vision_pages_ok"] = vision_ok

    with open(V7, "w", encoding="utf-8") as f:
        json.dump(v6, f, ensure_ascii=False, indent=2)

    print(f"v7 已保存: {V7} ({os.path.getsize(V7)/1024:.0f} KB)")
    print(f"  vision 成功页: {vision_ok}，失败/跳过: {vision_err}")
    print(f"  含公式页: {pages_with_formulas}，公式总行数: {total_formula_lines}")
    print(f"  unit 已修正（旧版全为 u1）")
    print()
    print("=== 抽查 ===")
    for s in ["10", "43", "100", "107", "118"]:
        pg = v6["page_text"][s]
        print(f"slide_{s}: book_page={pg.get('book_page')} unit={pg.get('unit')} formulas={len(pg.get('formulas', []))}行")


if __name__ == "__main__":
    main()
