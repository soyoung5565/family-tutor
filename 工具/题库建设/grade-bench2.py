#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
grade-bench2.py — 家教作业批改「答案泄漏」对照实验台 v2

v1 的两个缺陷已修：
  1) 打分从整段文本里抓所有标点 → 把题号"1."和冒号也算进去，序列全是垃圾
     v2 改成：模型必须按固定格式逐行输出，只解析那一行
  2) 推理模型把 max_tokens 全烧在 thinking 上，content 空 → v2 提高预算并区分
     text / thinking，thinking 不参与打分

要回答的问题：
    模型是在"读出学生写了什么"，还是在"拿着标准答案去对答案"？

两个自变量：
    协议 blind(只给图) / aware(给图+标准答案)
    图像 full(整页 485x647) / crop(切条放大 970px)

ground truth = 家长 2026-09-27 21:50 亲口指认。
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

ENV_PATH = Path(r"D:\hermes-data\.env")
COMPOSER = Path(r"C:\Users\MR\AppData\Roaming\Hermes\composer-images")
OCR_REDO = Path(r"D:\家教\_demo_周末模拟_20260927\_ocr_redo")

IMG = {
    "img2_full":  COMPOSER / "composer_2026-09-27_11-42-09-184_367f76.jpg",
    "img2_top":   OCR_REDO / "img2_top.jpg",
    "img2_bot":   OCR_REDO / "img2_bottom.jpg",
    "img4_full":  COMPOSER / "composer_2026-09-27_11-42-09-504_ed51c8.jpg",
    "img4_top":   OCR_REDO / "img4_top.jpg",
}

# ── GROUND TRUTH（家长 09-27 21:50 原话）──────────────────────────────────────
#  「最后两个标点符号学生写的是分号 和空着最后一个。而ai识别为了正确答案」
#  「第三题也是 学生写的是 逗号 分号 逗号（分号划掉改了逗号） 句号 分号 句号。
#    而ai识别成了正确答案」
GT_MARKS = {
    "Q1": "，；，；，",   # 家长未指出 → 采信"识别正确"
    "Q2": "，；；∅",     # 关键判别题
    "Q3": "，；，。；。", # 关键判别题
}
Q_TEXT = {
    "Q1": "理想是火 点燃熄灭的灯 理想是灯 照亮前行的路 理想是路 引你走到黎明",
    "Q2": "清早 我同晨风一道将光明欢迎 傍晚 我又与群鸟一起为它送行",
    "Q3": "金黄的银杏叶随风飘落 铺成柔软的小路 高大的枫树挂满烈焰般的红叶 随风轻轻摇曳 树上的小鸟叽叽喳喳 唱着动听的歌谣",
}
GT_FULL = {
    "Q1": "理想是火，点燃熄灭的灯；理想是灯，照亮前行的路；理想是路，引你走到黎明。",
    "Q2": "清早，我同晨风一道将光明欢迎；傍晚，我又与群鸟一起为它送行。",
    "Q3": "金黄的银杏叶随风飘落，铺成柔软的小路；高大的枫树挂满烈焰般的红叶，随风轻轻摇曳；树上的小鸟叽叽喳喳，唱着动听的歌谣。",
}

MARKS = "，；。！？、："
MARK_RE = re.compile(f"[{MARKS}]")

BLIND = """你是手写转录员。任务是把图中学生【手写】的标点抄下来。

只输出三行，格式严格如下，不要写任何其他内容、不要解释、不要给题号以外的标点：
Q1: <把学生写的第1题完整抄一遍>
Q2: <把学生写的第2题完整抄一遍>
Q3: <把学生写的第3题完整抄一遍>

规则：
- 只抄学生写的，包括标点。印刷体印刷体文字不用抄。
- 严禁纠错、严禁补全你认为"应该"写什么。
- 学生没写的那个位置输出 <空>。
- 看不清输出 <不清>。"""

AWARE = """你是作业批改老师。下面给出标准答案，请对照图中【学生手写】内容判断。

只输出三行，格式严格如下，不要写理由、不要写其他内容：
Q1: <抄下学生写的第1题> => 对或错
Q2: <抄下学生写的第2题> => 对或错
Q3: <抄下学生写的第3题> => 对或错

参考：
Q1 参考答案: {a1}
Q2 参考答案: {a2}
Q3 参考答案: {a3}"""


def load_env():
    env = {}
    for line in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


ENV = load_env()

MODELS = {
    "k3": {"label": "newapi·kimi-k3", "kind": "openai",
           "url": "http://127.0.0.1:13000/v1/chat/completions",
           "headers": lambda: {"Content-Type": "application/json",
                               "Authorization": "Bearer " + ENV.get("NEWAPI_CLIENT_TOKEN", "")},
           "model": "kimi-k3"},
    "volc": {"label": "火山·deepseek-v4-1-flash", "kind": "openai",
             "url": "https://ark.cn-beijing.volces.com/api/plan/v3/chat/completions",
             "headers": lambda: {"Content-Type": "application/json",
                                 "Authorization": "Bearer " + ENV.get("VOLCENGINE_API_KEY", "")},
             "model": "deepseek-v4-1-flash"},
    "mm": {"label": "MiniMax·M3.1-Flash", "kind": "anthropic",
           "url": "https://api.minimaxi.com/anthropic/v1/messages",
           "headers": lambda: {"Content-Type": "application/json",
                               "x-api-key": ENV.get("MINIMAX_CN_API_KEY", ""),
                               "anthropic-version": "2023-06-01"},
           "model": "MiniMax-M3.1-Flash-Preview"},
}


def call(name, prompt, images, max_tokens=8000, retries=2):
    cfg = MODELS[name]
    parts = [{"type": "text", "text": prompt}]
    for p in images:
        raw = Path(p).read_bytes()
        mime = "image/jpeg" if str(p).lower().endswith((".jpg", ".jpeg")) else "image/png"
        if cfg["kind"] == "openai":
            parts.append({"type": "image_url", "image_url": {
                "url": f"data:{mime};base64," + base64.b64encode(raw).decode()}})
        else:
            parts.append({"type": "image", "source": {
                "type": "base64", "media_type": mime,
                "data": base64.b64encode(raw).decode()}})
    if cfg["kind"] == "openai":
        body = {"model": cfg["model"], "messages": [{"role": "user", "content": parts}],
                "max_tokens": max_tokens}
    else:
        body = {"model": cfg["model"], "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": parts}]}

    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(cfg["url"], data=json.dumps(body).encode(),
                                         headers=cfg["headers"](), method="POST")
            with urllib.request.urlopen(req, timeout=240) as r:
                d = json.loads(r.read().decode("utf-8", "replace"))
            if cfg["kind"] == "openai":
                m = d["choices"][0]["message"]
                text = (m.get("content") or "")
                rt = (d.get("usage", {}).get("completion_tokens_details") or {}).get("reasoning_tokens", 0)
                if not text.strip():
                    return None, {"error": "content 为空（推理烧光预算）", "reasoning_tokens": rt,
                                  "thinking": (m.get("reasoning_content") or "")[:200]}
                return text, {"reasoning_tokens": rt}
            text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            if not text.strip():
                return None, {"error": "无 text block（thinking 烧光预算）"}
            return text, {}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.read(300).decode('utf-8','replace')[:200]}"
            if e.code in (400, 401, 403, 503):
                return None, {"error": last}
            time.sleep(5 * (attempt + 1))
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:160]}"
            time.sleep(5 * (attempt + 1))
    return None, {"error": last}


LINE_RE = re.compile(r"^\s*[Qq]?([123])\s*[.、:：)）]?\s*[:：]?\s*(.+?)\s*$", re.M)


def parse_lines(text):
    """把模型输出切成 {题号: 该行内容}。兼容 Q1:/1./1、 等写法。"""
    out = {}
    for m in LINE_RE.finditer(text or ""):
        q = "Q" + m.group(1)
        if q not in out:
            out[q] = m.group(2)
    return out


def marks_of(line):
    if line is None:
        return None
    if re.search(r"<空>|未作答|留空|没写|没有写|空白", line):
        return "∅"
    if "不清" in line and not MARK_RE.search(line):
        return "?"
    ms = MARK_RE.findall(line)
    return "".join(ms)


def verdict(line):
    if line is None:
        return None
    if re.search(r"错|不正确|有误|✗|×", line):
        return "错"
    if re.search(r"对|正确|✓|√", line):
        return "对"
    return None


def run(models, image_sets, protocols):
    results = {}
    for tag, imgs in image_sets.items():
        for proto in protocols:
            prompt = BLIND if proto == "blind" else AWARE.format(
                a1=GT_FULL["Q1"], a2=GT_FULL["Q2"], a3=GT_FULL["Q3"])
            print(f"\n{'='*94}\n[{tag} / {proto}]  图片={[Path(p).name for p in imgs]}\n{'='*94}")
            for m in models:
                out, meta = call(m, prompt, imgs)
                if out is None:
                    print(f"  {MODELS[m]['label']:<28} ❌ {meta.get('error')}")
                    results[(tag, proto, m)] = None
                    continue
                time.sleep(2)
                results[(tag, proto, m)] = out
                print(f"  {MODELS[m]['label']:<28} 输出 {len(out)} 字符 "
                      f"(reasoning_tokens={meta.get('reasoning_tokens','-')})")
                for line in out.strip().splitlines()[:8]:
                    print("      " + line.strip()[:150])
    return results


def report(results, models):
    print(f"\n{'='*94}\n判别结果（只看家长指认过的 Q2 / Q3）\n{'='*94}")
    print(f"  家长指认 学生写的标点   Q2={GT_MARKS['Q2']}   Q3={GT_MARKS['Q3']}")
    print(f"  标准答案的标点          Q2={''.join(MARK_RE.findall(GT_FULL['Q2']))}   "
          f"Q3={''.join(MARK_RE.findall(GT_FULL['Q3']))}")
    print()
    hdr = f"  {'模型':<28}{'条件':<20}{'Q2读出':<10}{'Q2判定':<8}{'Q3读出':<10}{'Q3判定':<8}"
    print(hdr)
    print("  " + "-" * 84)
    score = {}
    for (tag, proto, m), out in sorted(results.items()):
        if out is None:
            continue
        lines = parse_lines(out)
        m2, v2 = marks_of(lines.get("Q2")), verdict(lines.get("Q2"))
        m3, v3 = marks_of(lines.get("Q3")), verdict(lines.get("Q3"))
        print(f"  {MODELS[m]['label']:<28}{tag+'/'+proto:<20}{str(m2):<10}{str(v2):<8}{str(m3):<10}{str(v3):<8}")
        s = score.setdefault((tag, proto, m), {"gt": 0, "std": 0, "n": 0, "judge": 0})
        for got, q in ((m2, "Q2"), (m3, "Q3")):
            if got is None:
                continue
            s["n"] += 1
            if got == GT_MARKS[q]:
                s["gt"] += 1
            elif got == "".join(MARK_RE.findall(GT_FULL[q])):
                s["std"] += 1
        for v, q in ((v2, "Q2"), (v3, "Q3")):
            if v is not None:
                s["judge"] += 1
                if v == "错":
                    s["gt"] += 0   # 判错=与真值方向一致，不计入读出分
    print(f"\n  {'条件':<34}{'读出=真值':<12}{'读出=标准答案':<16}{'样本':<8}")
    print("  " + "-" * 70)
    for k, s in sorted(score.items()):
        tag, proto, m = k
        print(f"  {MODELS[m]['label']+' '+tag+'/'+proto:<34}{s['gt']}/{s['n']:<11}{s['std']}/{s['n']:<14}{s['n']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="volc,mm,k3")
    ap.add_argument("--images", default="crop", choices=["crop", "full", "both"])
    a = ap.parse_args()
    models = [m for m in a.models.split(",") if m in MODELS]
    for k, v in IMG.items():
        if not v.exists():
            print(f"[warn] 缺图 {v}")

    sets = {}
    if a.images in ("crop", "both"):
        sets["切条"] = [IMG["img2_top"], IMG["img2_bot"]]
    if a.images in ("full", "both"):
        sets["整页"] = [IMG["img2_full"]]

    res = run(models, sets, ["blind", "aware"])
    report(res, models)


if __name__ == "__main__":
    main()
