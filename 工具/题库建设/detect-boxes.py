#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""detect-boxes.py — 自动定位作业照里的手写标点方框（按蓝色墨框找，纯 PIL，无 numpy）"""
import sys
from pathlib import Path
from collections import deque

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

SRC = Path(r"D:\家教\_demo_周末模拟_20260927\_ocr_redo\img2_bottom.jpg")
im = Image.open(SRC).convert("RGB")
W, H = im.size
px = im.load()

blue = bytearray(W * H)
for y in range(H):
    for x in range(W):
        r, g, b = px[x, y]
        # 纸是暖色调：印刷文字偏棕（B-R 明显为负）。
        # 手绘方框是【中性深灰】描边（R≈G≈B）且偏暗 —— 用中性度把它和印刷体分开。
        mx = max(r, g, b)
        mn = min(r, g, b)
        if mx - mn <= 20 and mx < 120:
            blue[y * W + x] = 1
print("neutral-dark pixels:", sum(blue))

boxes = []
seen = bytearray(W * H)
for i in range(W * H):
    if not blue[i] or seen[i]:
        continue
    q = deque([i])
    seen[i] = 1
    minx = maxx = i % W
    miny = maxy = i // W
    n = 0
    while q:
        j = q.popleft()
        n += 1
        x, y = j % W, j // W
        if x < minx: minx = x
        if x > maxx: maxx = x
        if y < miny: miny = y
        if y > maxy: maxy = y
        for nx, ny in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
            if 0 <= nx < W and 0 <= ny < H:
                k = ny * W + nx
                if blue[k] and not seen[k]:
                    seen[k] = 1
                    q.append(k)
    w, h = maxx - minx, maxy - miny
    # 只保留正方形的"答题方框"（约 30x33px）；16x16 的是汉字笔画碎块
    if n > 150 and 24 <= w <= 48 and 24 <= h <= 48:
        boxes.append((minx, miny, maxx, maxy, n))

boxes.sort(key=lambda b: (b[1] // 16, b[0]))   # 按行分组后从左到右
print(f"\n找到 {len(boxes)} 个蓝色方框:")
for i, (x1, y1, x2, y2, n) in enumerate(boxes):
    tag = "ABCDEFGH"[i] if i < 8 else "?"
    print(f"  {tag}: ({x1},{y1})-({x2},{y2})  {x2-x1}x{y2-y1}  px={n}")
