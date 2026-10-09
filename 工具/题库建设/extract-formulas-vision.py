#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
家庭教师 v7 收尾：用 minimax-M3（Anthropic 兼容端点）对课本每页做公式提取。

分工约定（用户确认）：
- PaddleOCR 已负责"跑字 + 定位坐标"（v6 里 130 页全有，见 math_grade6_v6.json）
- 本脚本只补"公式层"：把带公式的页丢给视觉模型，输出每页公式清单
- 书中的测试题目/例题文字忽略，只提取公式与算式

用法：
  python extract-formulas-vision.py            # 批量跑（跳过已有输出 = 断点续跑）
  python extract-formulas-vision.py --test 10  # 只跑 slide_010（自测用）

输出：
  D:/jiajiao/math/kb/vision_formulas/slide_NNN.json
  {"slide": N, "status": "ok", "formulas": "<模型返回的公式文本>"}

端点事实（2026-09-10 核实，与 Hermes auxiliary.vision 同路径）：
- minimax-cn provider = https://api.minimaxi.com/anthropic + X-Api-Key: MINIMAX_CN_API_KEY (sk-cp-)
- 模型 MiniMax-M3，消息格式 Anthropic Messages，图片走 base64 image block
"""
import base64
import json
import os
import sys
import time

SLIDES_DIR = r"D:\家教\数学\课本\45fe27cf-8cb3-4670-8397-a482731412fc"
OUT_DIR = r"D:\家教\数学\知识库\vision_formulas"
ENV_FILE = r"D:\hermes-data\.env"
API_URL = "https://api.minimaxi.com/anthropic/v1/messages"
MODEL = "MiniMax-M3"

# 这 9 页 OCR 无任何公式特征（封面/扉页/版权/附录页），跳过
SKIP_PAGES = {2, 3, 4, 121, 123, 125, 127, 129, 130}

PROMPT = """这是小学六年级数学课本的一页（北师大版）。请只做一件事：把本页出现的所有【公式】和【数学算式】完整、准确地列出来，每行一个，保持分数、除号、乘号、等号的原样写法（例如：2/5÷3/4=2/5×4/3；5÷1/6=5×6=30）。

要求：
1. 只抄写图中真实出现的公式/算式，不要补充、不要推断、不要计算补全；
2. 横向拆成多行的公式合并为一行；
3. 栏目标题（如"试一试""练一练"）和练习题的文字不要抄；
4. 如果本页没有任何公式或算式，只回答"无"。"""


def load_api_key() -> str:
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("MINIMAX_CN_API_KEY="):
                    return line.split("=", 1)[1]
    return os.environ.get("MINIMAX_CN_API_KEY", "")


def extract_formulas(slide_n: int, api_key: str, timeout: int = 150) -> str:
    """调 minimax Anthropic 兼容端点，返回模型文本回答。"""
    import httpx

    img = os.path.join(SLIDES_DIR, f"slide_{slide_n:03d}.jpg")
    with open(img, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    headers = {
        "X-Api-Key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": MODEL,
        "max_tokens": 2048,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}},
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    }
    resp = httpx.post(API_URL, json=payload, headers=headers, timeout=timeout)
    if resp.status_code in (400, 404) and "model" in (resp.text or "").lower():
        # 模型名大小写兜底：再试小写
        payload["model"] = "minimax-m3"
        resp = httpx.post(API_URL, json=payload, headers=headers, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    if not text:
        # 有些实现把文本放在 content[0].text 之外，兜底取整个 content 的字符串表示
        text = str(data.get("content", "")).strip()
    return text


def main() -> int:
    api_key = load_api_key()
    if not api_key:
        print("错误: 环境变量 MINIMAX_CN_API_KEY 未找到", file=sys.stderr)
        return 2

    test_only = None
    if "--test" in sys.argv:
        i = sys.argv.index("--test")
        test_only = int(sys.argv[i + 1])

    os.makedirs(OUT_DIR, exist_ok=True)

    if test_only:
        todo = [test_only]
        print(f"自测模式: slide_{test_only:03d}")
    else:
        all_slides = [n for n in range(1, 131) if n not in SKIP_PAGES]
        done = set()
        for fn in os.listdir(OUT_DIR):
            if fn.startswith("slide_") and fn.endswith(".json"):
                try:
                    done.add(int(fn.split("_")[1].split(".")[0]))
                except (IndexError, ValueError):
                    pass
        todo = [n for n in all_slides if n not in done]
        print(f"待提取 {len(todo)}/{len(all_slides)} 页（已完成 {len(done)}）", flush=True)

    ok = 0
    for i, n in enumerate(todo, 1):
        out = os.path.join(OUT_DIR, f"slide_{n:03d}.json")
        for attempt in range(1, 4):
            try:
                text = extract_formulas(n, api_key)
                with open(out, "w", encoding="utf-8") as f:
                    json.dump({"slide": n, "status": "ok", "formulas": text}, f, ensure_ascii=False, indent=1)
                ok += 1
                print(f"[{i}/{len(todo)}] slide_{n:03d} OK 返回{len(text)}字", flush=True)
                break
            except Exception as e:
                print(f"[{i}/{len(todo)}] slide_{n:03d} 尝试{attempt}失败: {type(e).__name__}: {str(e)[:150]}", flush=True)
                time.sleep(8 * attempt)
        else:
            with open(out, "w", encoding="utf-8") as f:
                json.dump({"slide": n, "status": "error"}, f, ensure_ascii=False)
            print(f"[{i}/{len(todo)}] slide_{n:03d} XX 3次失败已标记", flush=True)
        if not test_only:
            time.sleep(4)

    print(f"完成: 成功 {ok}/{len(todo)}", flush=True)
    return 0 if ok == len(todo) else 1


if __name__ == "__main__":
    sys.exit(main())
