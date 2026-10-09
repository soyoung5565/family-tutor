#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
homework-triage.py — 作业页型判定（2026-09-29 用户要求）

目的：不是每天的作业都有题目（抄写/默写/听写类不需要批改）。
本工具先判定一页作业的类型，决定走「批改」还是「仅记录」：
  exercise  → 走批改流水线（grade-mistake.py / grade-batch.py）
  copy/dictation → 仅记录（写进 系统/作业记录.log + 当日消息一行）；不批改、不进错题
  blank     → 跳过
  other     → 人工判定

用法：
  python homework-triage.py --image 作业.jpg
  python homework-triage.py --image 作业.jpg --no-log
"""
import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("grademistake", HERE / "grade-mistake.py")
gm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gm)

LOG = Path("D:/家教/系统/作业记录.log")

PROMPT = ("这是一页学生上传的作业照片。请判断这页属于哪种类型（只输出 JSON）：\n"
          '{"type":"exercise|copy|dictation|blank|other","subject_guess":"语文|数学|英语|其他","reason":"一句话理由"}\n'
          "判定标准：\n"
          "- exercise：有需要判分的题目（练习/试卷/习题册页），适合批改；\n"
          "- copy：抄写类（整页在抄词/抄课文/抄句子，没有题目-作答结构）；\n"
          "- dictation：默写/听写类（默写词语/古诗/单词等，或听写记录）；\n"
          "- blank：空白页/无内容；\n"
          "- other：其他（手工、阅读记录、课外内容等）。\n"
          "注意：有题目+作答结构的都算 exercise；纯抄写/默写内容算 copy/dictation。")

HINT = {
    "exercise": "→ 走批改流水线（grade-mistake.py / grade-batch.py）",
    "copy": "→ 仅记录（抄写类，不批改、不进错题）",
    "dictation": "→ 仅记录（默写/听写类，不批改；如家长要求可加'错字检查'）",
    "blank": "→ 跳过（空白页）",
    "other": "→ 人工判定",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()
    img = Path(args.image)
    if not img.exists():
        sys.exit("[x] 图片不存在：%s" % img)

    try:
        d = gm._chat_json([{"role": "user", "content": [
            {"type": "text", "text": PROMPT},
            {"type": "image_url", "image_url": {"url": gm._data_url(img)}},
        ]}], max_tokens=600, model=gm.VOLC_MODEL_VISION)
    except Exception as e:
        out = {"file": str(img), "type": "unknown", "error": "%s: %s" % (type(e).__name__, str(e)[:150]),
               "hint": "→ 判定失败，按人工检查处理"}
        print(json.dumps(out, ensure_ascii=False, indent=2))
        sys.exit(2)

    if not isinstance(d, dict):
        d = {}
    t = d.get("type") or "other"
    out = {"file": str(img), "type": t, "subject_guess": d.get("subject_guess") or "",
           "reason": d.get("reason") or "", "hint": HINT.get(t, HINT["other"])}
    print(json.dumps(out, ensure_ascii=False, indent=2))

    if not args.no_log and t in ("copy", "dictation", "exercise", "blank"):
        try:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            line = "%s\t类型=%s\t科目=%s\t文件=%s\t理由=%s\n" % (
                datetime.now().strftime("%Y-%m-%d %H:%M"), t, out["subject_guess"], img.name, out["reason"])
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass


if __name__ == "__main__":
    main()
