"""Jev 基准测试：拿家庭教师 KB 里的真实数学题，模拟 KP 归属判定场景，跑 N 题测总耗时。

用法：
  python bench-jev.py 100
"""
from __future__ import annotations
import os, sys, json, time, subprocess, statistics
from pathlib import Path

NODE = r"D:\hermes-data\node\node.exe"
CLI_JS = r"D:\hermes-data\node\node_modules\command-code\dist\index.mjs"
WORKDIR = r"D:\hermes-data\node"
SAMPLE = Path(r"D:\家教\系统\scripts\_bench_sample.json")

KP_POOL = ["u1.k1", "u1.k2", "u2.k3", "u4.k1", "u6.k1", "u7.k1"]


def call_jev(prompt_dict):
    prompt = json.dumps(prompt_dict, ensure_ascii=False)
    t0 = time.perf_counter()
    res = subprocess.run(
        [NODE, CLI_JS, "-p", prompt, "-m", "typesafe/jev",
         "--output-format", "json", "--skip-onboarding"],
        capture_output=True, text=True, timeout=60,
        cwd=WORKDIR,
        env={**os.environ, "CI": "1"},
    )
    elapsed = time.perf_counter() - t0
    if res.returncode != 0:
        return {"error": res.stderr.strip()[-300:]}, elapsed
    last_line = [ln for ln in res.stdout.strip().splitlines() if ln.startswith("{")][-1]
    return json.loads(last_line), elapsed


def build_prompt(question):
    kp_defs = "\n".join(f"- {kp}: 六年级数学 KP" for kp in KP_POOL)
    state = {
        "subject": "数学（六年级上册）",
        "question": question["stem"],
        "question_type": question.get("type", ""),
        "kp_candidates": KP_POOL,
    }
    questions = {
        "kp_match": {
            "type": "noul",
            "instructions": (
                f"这道题的方法是否贴近以下 KP 之一？候选：\n{kp_defs}\n"
                "若方法匹配任何一个，答 yes；否则 no。"
            ),
        },
        "best_kp": {
            "type": "choice",
            "instructions": "在候选 KP 中选最匹配本题考查方法的",
            "criteria": {kp: f"题目考查 KP {kp} 的核心方法" for kp in KP_POOL},
        },
        "difficulty": {
            "type": "score",
            "instructions": "评估难度",
            "criteria": ["易", "中", "难"],
        },
    }
    return {"state": state, "questions": questions}


def run_benchmark(n=100):
    questions = json.loads(SAMPLE.read_text(encoding="utf-8"))[:n]
    print(f"\n题数: {len(questions)}")
    print("=" * 60)

    latencies = []
    api_latencies = []
    errors = 0
    samples = []

    t_start = time.perf_counter()
    for i, q in enumerate(questions, 1):
        prompt = build_prompt(q)
        resp, wall = call_jev(prompt)
        latencies.append(wall)
        if "error" in resp:
            errors += 1
        else:
            api_latencies.append(resp.get("durationMs", 0))
        if i <= 3:
            samples.append({"qid": q.get("qid"), "stem": q["stem"][:50], "resp": resp, "wall_s": round(wall, 3)})
        if i % 10 == 0 or i == len(questions):
            elapsed = time.perf_counter() - t_start
            print(f"  [{i:>3}/{len(questions)}] 累计 {elapsed:6.1f}s  | 错误 {errors}")
    total = time.perf_counter() - t_start

    print("=" * 60)
    print(f"总耗时: {total:.2f}s  | 错误: {errors}")
    if latencies:
        print(f"端到端单题耗时 (含 CLI 启动+JSON 解析):")
        print(f"  min={min(latencies):.2f}s  p50={statistics.median(latencies):.2f}s  avg={statistics.mean(latencies):.2f}s  max={max(latencies):.2f}s")
    if api_latencies:
        print(f"jev API 自身耗时 (durationMs 字段):")
        print(f"  min={min(api_latencies)}ms  p50={statistics.median(api_latencies):.0f}ms  avg={statistics.mean(api_latencies):.0f}ms  max={max(api_latencies)}ms")

    out = Path(r"D:\家教\系统\scripts\_bench_jev_result.json")
    out.write_text(json.dumps({
        "n": n, "total_s": round(total, 2), "errors": errors,
        "wall_latencies": [round(x, 3) for x in latencies],
        "api_latencies_ms": api_latencies, "samples": samples,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n原始数据: {out}")
    return total, errors


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    run_benchmark(n)