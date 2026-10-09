#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""build-sheet.py — 用完整方框（检测所得）拼成干净的对照条，并肉眼校验"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image, ImageDraw

SRC = Path(r"D:\家教\_demo_周末模拟_20260927\_ocr_redo\img2_bottom.jpg")
OUT = Path(r"D:\家教\_demo_周末模拟_20260927\_zoom_test")
OUT.mkdir(parents=True, exist_ok=True)
BASE = Image.open(SRC).convert("RGB")

# A/B/C 为 detect-boxes.py 自动检测所得；D 检测所得；其余手工补（据可见版式）
SETS = {
    "Q2": [(237, 349, 272, 382),    # A 清早后      ← 检测
           (503, 350, 538, 383),    # B 欢迎后
           (580, 352, 616, 386),    # C 傍晚后
           (157, 394, 190, 428)],   # D 行后        ← 检测
    "Q3": [(196, 441, 232, 478),    # A 飘落
           (386, 441, 426, 478),    # B 小路        ← 检测(G)
           (566, 443, 604, 480),    # C 红叶
           (378, 488, 418, 526),    # D 摇曳
           (538, 488, 578, 526),    # E 叽喳        ← 检测
           (712, 488, 752, 526)],   # F 歌谣
}
GT = {"Q2": "，；；∅", "Q3": "，；，。；。"}
L = "ABCDEF"


def build(key, factor=8):
    tiles = []
    for (x1, y1, x2, y2) in SETS[key]:
        t = BASE.crop((x1, y1, x2, y2))
        tiles.append(t.resize((t.width * factor, t.height * factor), Image.LANCZOS))
    pad, gap = 26, 44
    tw, th = max(t.width for t in tiles), max(t.height for t in tiles)
    W = pad * 2 + len(tiles) * tw + (len(tiles) - 1) * gap
    H = pad * 2 + th + 44
    sh = Image.new("RGB", (W, H), (250, 250, 250))
    d = ImageDraw.Draw(sh)
    x = pad
    for i, t in enumerate(tiles):
        sh.paste(t, (x, pad))
        d.rectangle([x - 3, pad - 3, x + t.width + 3, pad + t.height + 3],
                    outline=(0, 0, 190), width=4)
        d.text((x + t.width // 2 - 5, pad + t.height + 14), L[i], fill=(190, 0, 0))
        x += tw + gap
    p = OUT / f"{key}_sheet_x{factor}.png"
    sh.save(p)
    print(f"{key}: {sh.size} -> {p}")
    print(f"  家长指认真值: {GT[key]}")
    return p


if __name__ == "__main__":
    for k in (sys.argv[1:] or ["Q2", "Q3"]):
        build(k, 8)
