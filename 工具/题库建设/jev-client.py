"""JEV (TypeSafe System One) client for family-tutor KB adjudication.

直接走官方 https://api.commandcode.ai/provider/v1/systemone 端点
COMMANDCODE_API_KEY 已在 D:\\hermes-data\\.env
JEV 不生成文本，只返回结构化 judgments（noul/choice/score）+ 概率
单次请求 70-500ms，可并行多个独立 question
"""
from __future__ import annotations
import os, time, json, urllib.request, urllib.error
from typing import Any

CMD_URL = "https://api.commandcode.ai/provider/v1/systemone"
API_KEY = os.environ["COMMANDCODE_API_KEY"]

COMMON_KPS = ["u1.k1", "u1.k2", "u2.k1", "u2.k2", "u2.k3", "u3.k1", "u3.k2",
              "u4.k1", "u5.k1", "u6.k1", "u6.k2", "u7.k1", "u8.k1"]


def jev_decide(model: str = "typesafe/jev",
               state: Any = None,
               questions: dict | None = None,
               timeout: float = 10.0) -> dict:
    """调 jev；state=题干+KP候选；questions=判定项"""
    payload = {"model": model, "state": state, "questions": questions}
    req = urllib.request.Request(
        CMD_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = json.loads(r.read())
    body["_latency_s"] = round(time.perf_counter() - t0, 4)
    return body


def adjudicate_kp(question: dict, kp_pool: list[str]) -> dict:
    """判定：这道题是否对应 KP + 难度 + 是否超纲"""
    kp_defs = "\n".join(f"- {kp}: KP 候选" for kp in kp_pool)
    state = {
        "subject": "数学（六年级 上册）",
        "question": question["stem"],
        "kp_candidates": kp_pool,
        "question_type": question.get("type", ""),
    }
    questions = {
        "kp_match": {
            "type": "noul",
            "instructions": (
                f"这道题的解题方法是否对应 KP 候选之一？"
                f"\n候选：{kp_defs}\n"
                "若贴近这些 KP 的核心方法，答 yes；"
                "否则答 no。"
            ),
        },
        "best_kp": {
            "type": "choice",
            "instructions": "在候选 KP 中选最匹配本题考查方法的那一个",
            "criteria": {kp: f"题目考查 KP {kp} 的核心方法" for kp in kp_pool},
        },
        "difficulty": {
            "type": "score",
            "instructions": "评估这道题对六年级学生的难度",
            "criteria": ["易（基础计算/直接套公式）",
                         "中（1-2 步推理）",
                         "难（多步推理/综合运用）"],
        },
    }
    return jev_decide(state=state, questions=questions)


if __name__ == "__main__":
    out = jev_decide(
        state="用户问：我信用卡被多扣了 300 块，怎么办？",
        questions={"urgent": {"type": "noul", "instructions": "是否需要紧急处理？"}},
    )
    print(json.dumps(out, ensure_ascii=False, indent=2))
