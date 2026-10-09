#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
grade-zoom.py — 决定性实验：把标点方框超高倍放大后盲读

前面的结果：即使【完全不提供标准答案】，火山 deepseek-v4-1-flash 在 970px 切条上
仍然输出"标准答案"而不是家长指认的真实手写内容。

两种可能：
  (A) 分辨率不够 → 标点只有十几像素，模型读不出，用语言先验补全
  (B) 模型有"作弊/先验"倾向 → 就算看得清也倾向输出标准答案

判别方法：把方框区域放到 8 倍原生分辨率再读。
  读出真值 → (A) 分辨率问题
  仍是标准答案 → (B) 先验问题
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
from PIL import Image

OCR_REDO = Path(r"D:\家教\_demo_周末模拟_20260927\_ocr_redo")
OUT = Path(r"D:\家教\_demo_周末模拟_20260927\_zoom_test")
OUT.mkdir(parents=True, exist_ok=True)

# (题号, 在 img2_bottom.jpg(970x842) 上的裁剪框) —— 手工按图定位
# Q2「清早…送行」一行；Q3「银杏叶…」两行
CROPS = {
    "Q2": ("img2_bottom.jpg", (130, 335, 700, 425)),
    "Q3a": ("img2_bottom.jpg", (130, 430, 700, 500)),
    "Q3b": ("img2_bottom.jpg", (130, 485, 700, 545)),
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

PROMPT = """图里是几个方框，每个方框里是学生手写的一个标点符号。

请从左到右、按方框顺序，只输出这些方框里实际写的符号，用顿号或空格分开：
答案：

规则：只写你在图里【真实看到】的符号。没有内容的方框写"空"。看不清写"不清"。
禁止根据句子应该填什么标点来猜。"""


def make_zoom(key, factor):
    src, box = CROPS[key]
    im = Image.open(OCR_REDO / src).convert("RGB").crop(box)
    w, h = im.size
    im = im.resize((w * factor, h * factor), Image.LANCZOS)
    p = OUT / f"{key}_x{factor}.png"
    im.save(p)
    return p, im.size


def call(name, image_path, max_tokens=16000):
    cfg = MODELS[name]
    raw = Path(image_path).read_bytes()
    b64 = base64.b64encode(raw).decode()
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
                rt = (d.get("usage", {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
                return (t if t.strip() else None), rt
            t = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            return (t if t.strip() else None), None
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read(250).decode('utf-8','replace')[:150]}"
            if e.code in (400, 401, 403, 503):
                return None, err
            time.sleep(5)
        except Exception as e:
            err = f"{type(e).__name__}: {str(e)[:120]}"
            time.sleep(5)
    return None, err


def norm(text):
    if not text:
        return None
    if re.search(r"空|未作答|没写", text) and not MARK_RE.search(text):
        return "∅"
    ms = MARK_RE.findall(text)
    return "".join(ms) if ms else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--factors", default="4,8")
    ap.add_argument("--models", default="volc,mm,k3")
    ap.add_argument("--keys", default="Q2")
    a = ap.parse_args()
    factors = [int(x) for x in a.factors.split(",")]
    models = [m for m in a.models.split(",") if m in MODELS]
    keys = a.keys.split(",")

    for key in keys:
        for f in factors:
            path, size = make_zoom(key, f)
            print(f"\n{'='*92}\n{key} @ {f}x  → {size[0]}x{size[1]}  ({path.name})\n{'='*92}")
            for m in models:
                out, meta = call(m, path)
                if out is None:
                    print(f"  {MODELS[m]['label']:<26} ❌ {meta}")
                    continue
                time.sleep(2)
                got = norm(out)
                verdict = "?"
                if got:
                    gt = GT[key]
                    if got == gt:
                        verdict = "✅ 读出家长指认的真实手写"
                    elif got == STD[key]:
                        verdict = "❌ 输出的是标准答案"
                    else:
                        verdict = "⚠️ 两者都不是"
                print(f"  {MODELS[m]['label']:<26} 读出={str(got):<8} {verdict}")
                print(f"      原文: {out.strip()[:110]}")


if __name__ == "__main__":
    main()
