#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grade-mistake.py — 作业批改流水线（2026-09-26 接活：火山方舟 vision + LLM）
升级（2026-09-29）：【对错批改】＋【错字/拼写专项】两遍设计——错字专项仅语文/英语，
与主流程并发执行；视读（提取/错字检查）默认用 seed（doubao-seed-2.1-pro，对比实测定为最准）。

Pipeline（关键设计：不信任学生手写，按顺序分离提取）：
  Step 1: vision 提取题目文本（忽略手写）
  Step 2: LLM 独立求解（标准答案 + 步骤）
  Step 3: vision 提取学生作答（按题号对齐）
  Step 4: LLM 对照判卷（is_correct + 常见错误）
  Step 5: LLM 给出候选知识点（从 KP 库清单里选）
  Step 6: 匹配 KP 库 → 结构化错题记录（直接喂 day1-pipeline / micro-lesson）

用法：
  D:/Python312/python.exe grade-mistake.py --image homework.jpg --subject 数学 [--out result.json]
  D:/Python312/python.exe grade-batch.py --images a.jpg b.jpg c.jpg --subject 语文   # 多页并行壳
  D:/Python312/python.exe grade-mistake.py --demo
  D:/Python312/python.exe grade-mistake.py --print-prompt-only

输出 JSON 格式 = mistakes 文件格式（可直接给 day1-pipeline.py / micro-lesson.py）：
  {"subject": "数学", "date": "YYYY-MM-DD", "mistakes": [{id, group, part_label, question,
    student_answer, correct_answer, correct_solution, knowledge_points, common_mistakes}]}
"""
import argparse
import base64 as b64mod
import json
import os
import re
import sys
import urllib.request
from datetime import date
from pathlib import Path

VOLC_URL = "https://ark.cn-beijing.volces.com/api/plan/v3/chat/completions"
VOLC_MODEL = "doubao-seed-2.1-pro"          # 全流程默认（2026-09-29 起统一 seed；glm-flash 在语文用例上曾输出非 JSON）
VOLC_MODEL_VISION = "doubao-seed-2.1-pro"   # 视读步骤（题目/作答提取、错字检查）用——2026-09-29 实测定为最准
TYPO_CHECK_SUBJECTS = ("语文", "英语")       # 错字/拼写专项仅对这些科目执行（数学跳过＝省时）


def _load_key() -> str:
    k = os.environ.get("VOLCENGINE_API_KEY")
    if k:
        return k
    for p in (Path("D:/hermes-data/.env"), Path.home() / ".hermes/.env"):
        try:
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.strip().startswith("VOLCENGINE_API_KEY="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass
    raise RuntimeError("未找到 VOLCENGINE_API_KEY（env 或 D:/hermes-data/.env）")


def _chat(messages: list, max_tokens: int = 2500, model: str = None) -> str:
    """调用火山方舟 chat（带 2 次重试）。model 缺省=VOLC_MODEL，视读步骤传 VOLC_MODEL_VISION。"""
    import time as _time
    last = None
    for _ in range(2):
        try:
            body = json.dumps({"model": model or VOLC_MODEL, "messages": messages,
                               "max_tokens": max_tokens}).encode("utf-8")
            req = urllib.request.Request(VOLC_URL, data=body, headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + _load_key(),
            })
            with urllib.request.urlopen(req, timeout=300) as resp:
                d = json.loads(resp.read().decode("utf-8"))
            m = (d.get("choices") or [{}])[0].get("message", {})
            return m.get("content") or m.get("reasoning_content") or ""
        except Exception as e:
            last = e
            _time.sleep(3)
    raise RuntimeError("模型调用失败（已重试2次）：%s: %s" % (type(last).__name__, last))


def _chat_json(messages: list, max_tokens: int = 2500, model: str = None):
    txt = _chat(messages, max_tokens, model=model)
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        # 重试一次：明确要求只输出 JSON（2026-09-29 加固）
        txt2 = _chat(messages + [{"role": "user",
                                  "content": "请严格只输出要求的 JSON 本身，不要输出任何其他文字、解释或思考过程。"}],
                     max_tokens, model=model)
        m = re.search(r"\{.*\}", txt2, re.S)
        if not m:
            raise RuntimeError(f"LLM 未返回 JSON：{txt[:200]}")
        txt = txt2
    return json.loads(m.group(0))


def _data_url(image_path: Path) -> str:
    ext = image_path.suffix.lstrip(".").lower() or "jpeg"
    return f"data:image/{ext};base64," + b64mod.b64encode(image_path.read_bytes()).decode()


# ── Step 1: 提取题目（忽略手写） ──
def vision_extract_questions(image_path: Path) -> list:
    d = _chat_json([{"role": "user", "content": [
        {"type": "text", "text": (
            "这是一页学生作业/试卷的照片。请只提取【印刷体的题目原文】，完全忽略手写作答。"
            "【完整性·硬要求】长文段（阅读题等）必须逐字完整收录进该小题的 text 字段，禁止省略、截断、删节、改写为省略号；宁可长，不可断。"
            "【重要】按小题拆分：大题里的每个小题（1）（2）（3）都必须作为独立条目输出；"
            "没有小题的题目本身作为一个条目。输出 JSON："
            '{"questions":[{"key":"1-1","big":"大题原文/大题编号（如：三、化简下面的比）",'
            '"sub":"小题编号（如 （1）；没有小题则空串）","text":"本小题的题目文本"}, ...]}'
            "key 规则：大题序号从 1 开始顺排（第一道大题=1），小题号沿用卷面（1、2、3…），格式 \"大题序号-小题号\"；无小题时 key=\"大题序号\"。")},
        {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
    ]}], max_tokens=4500, model=VOLC_MODEL_VISION)
    return d.get("questions", [])


# ── Step 3: 提取学生作答（按题号对齐；严格 OCR，禁纠正） ──
def vision_extract_student_answers(image_path: Path, questions: list) -> list:
    qlist = "\n".join(f'{q.get("key")}: {str(q.get("text",""))[:70]}' for q in questions)
    d = _chat_json([{"role": "user", "content": [
        {"type": "text", "text": (
            "这是同一页作业照片。小题清单（key: 题目）：\n" + qlist +
            "\n请【逐字扫描、忠实转录】学生手写在这些小题旁的解答/答案，按 key 对齐输出 JSON："
            '{"answers":[{"key":"1-1","student_answer":"学生写的内容（原样）","confidence":"high|medium|low"}]}'
            "\n铁律："
            "① 你只负责读字，禁止纠正/补全/按题目应有答案猜测——学生写的就是错的也必须原样记录；"
            "② 标点符号逐个分辨：「，」逗号、「。」句号、「；」分号、「、」顿号、「！」叹号、「？」问号 完全不同，逐个放大确认；"
            "③ 涂改：写成「（划掉：X）」或「（划掉X改Y）」；"
            "④ 空白/未填：student_answer 写「（未作答）」；"
            "⑤ 字迹潦草：宁可标 confidence=low 也不要脑补成通顺答案。")},
        {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
    ]}], max_tokens=3000, model=VOLC_MODEL_VISION)
    return d.get("answers", [])


# ── Step 3.5（2026-09-29 新增）: 错字/拼写专项 —— 与对错批改分开的第二遍（仅语文/英语） ──
def vision_typo_check(image_path: Path, subject: str = "语文") -> dict:
    """错字/拼写专项检查。实测注意：常规读法会把错字脑补成对的（"挺"三模型全漏），
    此专项能显著提高检出（"衬" k3/seed 抓到），但仍需人工兜底；结果显示时单独列出。"""
    if subject not in TYPO_CHECK_SUBJECTS:
        return {"checked": False, "reason": "%s 不适用（仅语文/英语）" % subject}
    if subject == "英语":
        prompt = ("这是一页学生英语作业照片。请做【拼写专项检查】（与批改对错无关）：\n"
                  "1. 逐词读出所有学生手写单词；\n"
                  "2. 逐个检查拼写：漏字母、多字母、字母顺序错、形近字母混淆；\n"
                  "3. 只依据真实看到的字母，禁止按常见单词脑补。\n"
                  '输出 JSON：{"errors":[{"text":"学生写的（原样）","correct":"正确应为","detail":"错在哪里"}],"note":"补充说明"}；'
                  "如无拼写错误，errors 输出空数组 []。")
    else:
        prompt = ("这是一页学生语文作业照片。请做【错字专项检查】（与批改对错无关）：\n"
                  "1. 逐区读出所有学生手写内容；\n"
                  "2. 逐字检查：有无错别字、有无字写错（偏旁部首写错如衤/礻、扌/木，缺笔、多笔、形近误写）；\n"
                  "3. 只依据真实看到的笔画，禁止因为词语常见就把写错的字脑补成对的；实在看不清标【不清】。\n"
                  '输出 JSON：{"errors":[{"text":"写错的字","detail":"错在哪里（例：衣字旁写成示字旁/少一横）","confidence":"high|medium|low"}],"note":"补充说明"}；'
                  "如无错字，errors 输出空数组 []。")
    try:
        d = _chat_json([{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
        ]}], max_tokens=3000, model=VOLC_MODEL_VISION)
    except Exception as e:
        return {"checked": False, "reason": "错字检查调用失败：%s: %s" % (type(e).__name__, str(e)[:120])}
    if not isinstance(d, dict):
        d = {}
    return {"checked": True, "model": VOLC_MODEL_VISION,
            "errors": d.get("errors") or [], "note": d.get("note") or ""}


# ── Step 2: 独立求解 ──
def llm_solve(question_text: str, subject: str = "数学") -> dict:
    return _chat_json([
        {"role": "system", "content": "你是一位严谨的小学/初中老师，解题必须准确。"},
        {"role": "user", "content": (
            f"科目：{subject}。请解答下面的题目，输出 JSON："
            '{"standard_answer":"最终答案","standard_solution":"分步骤解答（简洁）"}\n题目：\n' + question_text)},
    ], max_tokens=1500)


# ── Step 4+5: 判卷 + 候选知识点 ──
def llm_grade(question_text: str, student_answer: str, standard_answer: str, kp_names: list, subject: str) -> dict:
    kp_txt = "、".join(kp_names[:200])
    return _chat_json([
        {"role": "system", "content": "你是一位严谨的老师，批改时先自己核对学生答案与标准答案是否等价。"},
        {"role": "user", "content": (
            f"科目：{subject}\n题目：{question_text}\n标准答案：{standard_answer}\n学生答案：{student_answer}\n\n"
            "请输出 JSON："
            '{"is_correct":true/false,'
            '"common_mistakes":["学生这个错误反映的典型错因，1-3条"],'
            '"kp_candidates":["从下面知识点清单中选择最相关的（最多3个，按相关度排序）"]}\n'
            "知识点清单：" + kp_txt)},
    ], max_tokens=1200)


# ── KP 库 ──
def load_kp_db(kp_dir: Path) -> list:
    out = []
    if not kp_dir.exists():
        return out
    for p in sorted(kp_dir.iterdir()):
        if p.suffix == ".json" and not p.name.startswith("_"):
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(d, dict) and d.get("id"):
                    out.append(d)
            except Exception:
                pass
    return out


def match_candidates_to_kp(candidates: list, kp_db: list) -> list:
    out = []
    for c in candidates:
        cid = c if isinstance(c, str) and re.fullmatch(r"[\w\.\-]+", c) else None
        cname = c if isinstance(c, str) else str(c.get("name", ""))
        matched = None
        if cid:
            matched = next((kp for kp in kp_db if kp.get("id") == cid), None)
        if not matched and cname:
            matched = next((kp for kp in kp_db
                            if cname in (kp.get("name") or "") or (kp.get("name") or "") in cname
                            or cname == kp.get("id")), None)
        if matched:
            out.append(matched["id"])
        else:
            # 二次尝试：按名字在 kp_db 里找（候选可能写成名字）
            matched = next((kp for kp in kp_db if cname and (cname in kp.get("name", ""))), None)
            if matched:
                out.append(matched["id"])
    # 去重保序
    seen, res = set(), []
    for x in out:
        if x not in seen:
            seen.add(x)
            res.append(x)
    return res


DEMO_RESULT = {"subject": "数学", "note": "demo 模式：打印内置样例"}


def main():
    ap = argparse.ArgumentParser(description="Grade homework image → structured mistakes")
    ap.add_argument("--image")
    ap.add_argument("--subject", default="数学")
    ap.add_argument("--kp-db", default=None, help="默认 D:/家教/{subject}/知识点及掌握情况")
    ap.add_argument("--out", default=None, help="输出 JSON 文件路径（缺省打印到 stdout）")
    ap.add_argument("--no-grade-only-extract", action="store_true", help="只提取题目+答案（不判卷）")
    ap.add_argument("--concurrency", type=int, default=4, help="判卷并发数（默认4；错字专项与主流程始终并发；可上调如 6）")
    ap.add_argument("--no-typo-check", action="store_true", help="跳过错字/拼写专项（仅调试）")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--print-prompt-only", action="store_true")
    args = ap.parse_args()

    if args.demo:
        print(json.dumps(DEMO_RESULT, ensure_ascii=False, indent=2))
        return
    if args.print_prompt_only:
        print("Step1: 提取题目（忽略手写） → Step2: 独立求解 → Step3: 提取学生作答 → "
              "Step4: 判卷 → Step5: 候选KP → Step6: 匹配 KP 库 → 结构化输出")
        return
    if not args.image:
        print("[x] 需要 --image（或 --demo）", file=sys.stderr)
        sys.exit(1)

    img = Path(args.image)
    if not img.exists():
        print(f"[x] 图片不存在：{img}", file=sys.stderr)
        sys.exit(1)
    subject = args.subject
    kp_dir = Path(args.kp_db) if args.kp_db else Path(f"D:/家教/{subject}/知识点及掌握情况")
    kp_db = load_kp_db(kp_dir)
    kp_names = [kp.get("name", "") for kp in kp_db if kp.get("name")]
    print(f"[i] 科目={subject}｜KP 库 {len(kp_db)} 个｜图片 {img.name}", file=sys.stderr)

    from concurrent.futures import ThreadPoolExecutor
    pool = ThreadPoolExecutor(max_workers=max(1, args.concurrency))
    # ⓪ 错字/拼写专项（语文/英语）＝第二遍批改，与第一遍并发执行（2026-09-29）
    typo_fut = None if args.no_typo_check else pool.submit(vision_typo_check, img, subject)

    questions = vision_extract_questions(img)
    print(f"[1/5] 提取题目 {len(questions)} 个小条目", file=sys.stderr)
    answers = vision_extract_student_answers(img, questions)
    amap = {a.get("key"): a for a in answers if isinstance(a, dict)}
    print(f"[2/5] 提取作答 {len(amap)} 份（错字专项并行进行中）", file=sys.stderr)

    def _grade_one(i, q):
        key = str(q.get("key") or i)
        big_no = key.split("-")[0]
        sub = str(q.get("sub") or "").strip()
        big = str(q.get("big") or "").strip()
        qtext = str(q.get("text") or q.get("question_text") or "").strip()
        if not qtext:
            return None
        ans = amap.get(key) or {}
        s_ans = ans.get("student_answer")
        rec = {"id": f"{big_no}-{sub or i}".replace(" ", ""),
               "group": f"q{big_no}",
               "part_label": sub or f"（{i}）",
               "question": (f"{big}\n" if big else "") + (f"{sub} " if sub else "") + qtext,
               "student_answer": s_ans or "（未提取到作答）",
               "correct_answer": "", "correct_solution": "", "knowledge_points": [], "common_mistakes": []}
        if args.no_grade_only_extract:
            return rec
        try:
            sol = llm_solve(rec["question"], subject)
        except Exception as e:
            sol = {}
            rec["common_mistakes"].append("（求解步骤失败：%s）" % type(e).__name__)
        rec["correct_answer"] = sol.get("standard_answer", "")
        rec["correct_solution"] = sol.get("standard_solution", "")
        if re.search(r"不完整|无法作答|无法解答|请补充|信息不全", str(sol.get("standard_answer", "")) + str(sol.get("standard_solution", ""))):
            rec["common_mistakes"].append("（题干跨页/不完整，本题未判——如需要请补拍下一页）")
        if s_ans:
            try:
                g = llm_grade(rec["question"], str(s_ans), str(sol.get("standard_answer", "")), kp_names, subject)
                rec["common_mistakes"] = g.get("common_mistakes", [])[:3]
                rec["is_correct"] = bool(g.get("is_correct"))
                rec["knowledge_points"] = match_candidates_to_kp(g.get("kp_candidates", []), kp_db)
            except Exception as e:
                rec["common_mistakes"].append("（判卷步骤失败：%s）" % type(e).__name__)
        else:
            rec["common_mistakes"] = ["（未提取到作答，未判卷）"]
        return rec

    futures = [pool.submit(_grade_one, i, q) for i, q in enumerate(questions, 1)]
    mistakes = [r for r in (f.result() for f in futures) if r]
    for rec in mistakes:
        print(f"[3/5] {rec.get('id')} 判卷完成：{'✅对' if rec.get('is_correct') else '❌错/未定'}", file=sys.stderr)

    try:
        typo = typo_fut.result() if typo_fut else {"checked": False, "reason": "按 --no-typo-check 跳过"}
    except Exception as e:
        typo = {"checked": False, "reason": "%s: %s" % (type(e).__name__, str(e)[:120])}
    if typo.get("checked"):
        errs = typo.get("errors") or []
        print("[4/5] 错字专项完成：" + ("发现 %d 处" % len(errs) if errs else "未发现错字/拼写问题"), file=sys.stderr)
    else:
        print(f"[4/5] 错字专项未执行：{typo.get('reason', '')}", file=sys.stderr)

    result = {"subject": subject, "date": date.today().isoformat(),
              "mistakes": mistakes, "typo_check": typo}
    out = json.dumps(result, ensure_ascii=False, indent=2)
    print("[5/5] 输出结构化错题（含错字专项）", file=sys.stderr)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"✓ 已写 {args.out}", file=sys.stderr)
    print(out)


if __name__ == "__main__":
    main()
