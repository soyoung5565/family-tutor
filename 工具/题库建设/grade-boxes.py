#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
grade-boxes.py — 方框级盲读实验（最终版）

v3 的设计修正：
  v2 把整行裁下来送模型，但 Q2 的第4个方框在【下一行】，
     模型按"从左到右"会把它排到最前面；而且模型用「、」做分隔符，
     被我的正则当成标点一起数了 —— 实验本身有歧义。

v3：把每个方框单独抠出来，按阅读顺序横向拼成一张干净的对照条，
    每个框下面标 A/B/C/D，再让模型只输出这 4 个位置各写了什么。
    没有上下文、没有题干、没有句子 —— 模型无法用语感补全。
"""
import argparse
import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

OCR_REDO = Path(r"D:\家教\_demo_周末模拟_20260927\_ocr_redo")
OUT = Path(r"D:\家教\_demo_周末模拟_20260927\_zoom_test")
OUT.mkdir(parents=True, exist_ok=True)
BASE = Image.open(OCR_REDO / "img2_bottom.jpg").convert("RGB")

# 在 img2_bottom.jpg(970x842) 上手工定位的方框 (x1,y1,x2,y2)
BOXES = {
    "Q2": [  # 清早…送行  四个方框（detect-boxes.py 检测 + build-sheet.py 肉眼校验通过）
        (237, 349, 272, 382),   # A 清早后   → ，
        (503, 350, 538, 383),   # B 欢迎后   → ；
        (580, 352, 616, 386),   # C 傍晚后   → ；
        (157, 394, 190, 428),   # D 行后     → ∅（空）
    ],
    "Q3": [  # 银杏叶… 两行共六个方框
        (196, 441, 232, 478),   # A
        (386, 441, 426, 478),   # B
        (566, 443, 604, 480),   # C
        (378, 488, 418, 526),   # D
        (538, 488, 578, 526),   # E
        (712, 488, 752, 526),   # F
    ],
}
GT = {"Q2": "，；；∅", "Q3": "，；，。；。"}
STD = {"Q2": "，；，。", "Q3": "，；，；，。"}

ENV = {}
for line in Path(r"D:\hermes-data\.env").read_text(encoding="utf-8", errors="replace").splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        ENV[k.strip()] = v.strip().strip('"').strip("'")

MODELS = {
    "volc": {"label": "火山·ds4.1-flash", "kind": "openai",
             "url": "https://ark.cn-beijing.volces.com/api/plan/v3/chat/completions",
             "headers": {"Content-Type": "application/json",
                         "Authorization": "Bearer " + ENV.get("VOLCENGINE_API_KEY", "")},
             "model": "deepseek-v4-1-flash"},
    "mm": {"label": "MiniMax·M3.1-Flash", "kind": "anthropic",
           "url": "https://api.minimaxi.com/anthropic/v1/messages",
           "headers": {"Content-Type": "application/json",
                       "x-api-key": ENV.get("MINIMAX_CN_API_KEY", ""),
                       "anthropic-version": "2023-06-01"},
           "model": "MiniMax-M3.1-Flash-Preview"},
    "k3": {"label": "newapi·kimi-k3", "kind": "openai",
           "url": "http://127.0.0.1:13000/v1/chat/completions",
           "headers": {"Content-Type": "application/json",
                       "Authorization": "Bearer " + ENV.get("NEWAPI_CLIENT_TOKEN", "")},
           "model": "kimi-k3"},
}

MARKS = "，；。！？、："
MARK_RE = re.compile(f"[{MARKS}]")
LETTERS = "ABCDEF"

PROMPT = """这张图里有几个小方框，每个方框下方有一个字母标签（A、B、C...）。
每个方框里是学生手写的一个标点符号，有些方框里是空的。

请只输出一行，格式为：A=<符号> B=<符号> C=<符号> D=<符号>
规则：
- 只写你在方框里【真实看到】的符号。
- 方框里没有内容就写"空"。
- 看不清就写"不清"。
- 严禁根据任何句子推断应该填什么。没有句子给你看。
- 不要用顿号或逗号做分隔符，请用空格分隔。"""


def build_sheet(key, factor=8):
    boxes = BOXES[key]
    tiles = []
    for (x1, y1, x2, y2) in boxes:
        t = BASE.crop((x1, y1, x2, y2))
        t = t.resize((t.width * factor, t.height * factor), Image.LANCZOS)
        tiles.append(t)
    pad, gap = 24, 36
    tw = max(t.width for t in tiles)
    th = max(t.height for t in tiles)
    W = pad * 2 + len(tiles) * tw + (len(tiles) - 1) * gap
    H = pad * 2 + th + 40
    sheet = Image.new("RGB", (W, H), (245, 245, 245))
    d = ImageDraw.Draw(sheet)
    x = pad
    for i, t in enumerate(tiles):
        sheet.paste(t, (x, pad))
        d.rectangle([x - 2, pad - 2, x + t.width + 2, pad + t.height + 2],
                    outline=(0, 0, 200), width=3)
        d.text((x + t.width // 2 - 6, pad + t.height + 10), LETTERS[i], fill=(0, 0, 0))
        x += tw + gap
    p = OUT / f"{key}_boxes_x{factor}.png"
    sheet.save(p)
    return p, sheet.size


def call(name, image_path, max_tokens=16000):
    cfg = MODELS[name]
    # 推理模型（尤其 MiniMax M3.1）会把预算烧在 thinking 上，
    # 正文一个字都没输出。对这类模型直接翻倍预算。
    if name == "mm":
        max_tokens = 40000
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    if cfg["kind"] == "openai":
        parts = [{"type": "text", "text": PROMPT},
                 {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]
        body = {"model": cfg["model"], "messages": [{"role": "user", "content": parts}],
                "max_tokens": max_tokens}
    else:
        parts = [{"type": "text", "text": PROMPT},
                 {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                              "data": b64}}]
        body = {"model": cfg["model"], "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": parts}]}
    for attempt in range(2):
        try:
            req = urllib.request.Request(cfg["url"], data=json.dumps(body).encode(),
                                         headers=cfg["headers"], method="POST")
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if cfg["kind"] == "openai":
                t = d["choices"][0]["message"].get("content") or ""
                return (t if t.strip() else None), None
            t = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            return (t if t.strip() else None), None
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read(220).decode('utf-8','replace')[:140]}"
            if e.code in (400, 401, 403, 503):
                return None, err
            time.sleep(5)
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:110]}"
            time.sleep(5)
    return None, err


SLOT_RE = re.compile(r"([A-F])\s*[=:：]\s*([，；。！？：]|[空不清无]|\S)")


def parse_slots(text):
    """按 A=/B=/C= 逐槽位取符号，天然不受分隔符污染。"""
    out = {}
    for m in SLOT_RE.finditer(text or ""):
        k = m.group(1)
        v = m.group(2)
        if v in ("空", "无", "没", "未"):
            v = "∅"
        elif v in ("不清", "?"):
            v = "?"
        elif v not in MARKS:
            v = None
        if k not in out and v:
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="Q2")
    ap.add_argument("--factors", default="8")
    ap.add_argument("--models", default="volc,mm,k3")
    a = ap.parse_args()
    for key in a.keys.split(","):
        for f in [int(x) for x in a.factors.split(",")]:
            path, size = build_sheet(key, f)
            n = len(BOXES[key])
            print(f"\n{'='*94}\n{key} 方框对照条 @ {f}x  ({size[0]}x{size[1]})  → {path.name}\n{'='*94}")
            print(f"  家长指认真实手写: {GT[key]}   |   标准答案: {STD[key]}")
            for m in a.models.split(","):
                if m not in MODELS:
                    continue
                out, err = call(m, path)
                if out is None:
                    print(f"  {MODELS[m]['label']:<26} ❌ {err}")
                    continue
                time.sleep(2)
                slots = parse_slots(out)
                got = "".join(slots.get(LETTERS[i], "?") for i in range(n))
                tag = "✅ 读出真值" if got == GT[key] else ("❌ 输出标准答案" if got == STD[key] else "⚠️ 两者都不是")
                print(f"  {MODELS[m]['label']:<26} {got}   {tag}")
                print(f"      原文: {out.strip()[:150]}")


if __name__ == "__main__":
    main()
