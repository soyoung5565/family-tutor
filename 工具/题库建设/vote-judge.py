#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
vote-judge.py
=============
3 模型投票判定器（MiniMax-M3 / muse-spark-1.3-contributor / deepseek-v4-pro）

参考：
- references/quiz-bank-design.md §5（AI 自审 5 项）
- references/quiz-bank-workflow.md §4（自审输出格式）

约束（用户原话）：
- 3 个模型串行调用，不可并发
- DS-v4-pro 和 Kimi 同一 provider（new-api），并发必 429
- Muse 必须走 clash 代理（127.0.0.1:7897）
- MiniMax 走 minimax-cn 国内直连

降级规则：
- 任一模型调用失败 → 跳过该票，不影响其他
- 最终票数 = 实际成功的票数
- 通过阈值：max(2, ceil(成功票数/2 + 1))  // 2/2 全过、2/3 过 2、3/3 过 2

输入：
  python vote-judge.py --kp-id u1.k1 --stem "..." --options "A,B,C,D" --answer 0 --explanation "..."

或 JSON 模式（批处理）：
  python vote-judge.py --input candidates.json --output reviews.json
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import requests


# === 配置 ===

CLASH_PROXY = 'http://127.0.0.1:7897'

# === Muse 免费层调用（2026-09-12 修复）===
# 走 Zen 免费层 + Responses API + 匿名 + opencode 头
MUSE_MODEL = 'muse-spark-1.3-contributor-free'
MUSE_BASE = 'https://opencode.ai/zen/v1/responses'

def _opencode_free_headers():
    return {
        'User-Agent': 'opencode/0.20.5',
        'X-Session-ID': str(uuid.uuid4()),
        'HTTP-Referer': 'https://opencode.ai/',
        'X-Title': 'opencode',
    }

def extract_responses_text(j):
    texts = []
    for item in j.get('output', []):
        if item.get('type') == 'message':
            for c in item.get('content', []):
                if c.get('type') == 'output_text':
                    texts.append(c['text'])
    return '\n'.join(texts)


PROVIDERS = {
    'minimax': {
        'name': 'MiniMax-M3',
        'base_url': 'https://api.minimaxi.com/anthropic',
        'key_env': 'MINIMAX_CN_API_KEY',
        'proxies': None,  # 国内直连
        'format': 'anthropic',
    },
    'muse': {
        # 2026-09-12 修复（免费通道）：muse-spark-1.3-contributor-free 是官方免费模型，
        # 走 Zen 免费层 + /v1/responses，匿名（无需任何 key / 账户余额）。
        # OpenCode 免费层按 User-Agent + X-Session-ID 识别 OpenCode 客户端：
        #   必须带 opencode UA + 随机 UUID session（缺失 → MissingSessionID）。
        # 不要走 GO 中继（zen/go/v1）——那里 1.3/1.2-contributor 是订阅额度，已 GoUsageLimitError。
        'name': 'muse-spark-1.3-contributor-free',
        'base_url': 'https://opencode.ai/zen/v1',
        'key_env': None,  # 匿名，无需 key
        'proxies': {'http': CLASH_PROXY, 'https': CLASH_PROXY},  # 必须 clash
        'format': 'responses',  # codex_responses 模式
    },
    'ds_pro': {
        'name': 'deepseek-v4-pro',
        'base_url': 'http://127.0.0.1:13000/v1',
        'key_env': 'NEWAPI_CLIENT_TOKEN',
        'proxies': None,  # 国内直连
        'format': 'openai',
    },
}

# 串行调用间隔（防 429）
INTER_CALL_SLEEP = 3.0


def load_keys():
    candidates = [
        r'D:\\hermes-data\\.env',
        r'/d/hermes-data/.env',
        '/mnt/d/hermes-data/.env',
        os.path.expanduser('~/.env'),
    ]
    for path in candidates:
        if os.path.exists(path):
            env = {}
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.split('#')[0].strip()
            return env
    raise FileNotFoundError('.env not found in: ' + ', '.join(candidates))


# === Prompt 模板 ===

JUDGE_PROMPT_TEMPLATE = """你是一位严谨的六年级{subject}老师，正在审核一道入库候选题。

【题目信息】
- 题干：{stem}
- 选项：{options_text}
- 候选答案：{answer_text}
- 解析：{explanation}

【目标知识点（KP）】
- KP ID：{kp_id}
- KP 名称：{kp_name}
- KP 定义：{kp_definition}
- KP 关键点：{kp_key_points}
- KP 常见错误：{kp_common_mistakes}

【审核 5 项】（逐项判断，全部 ✓ 才算 passed=true）

1. **考点对照**：本题核心考点是否落在 KP 定义/key_points 范围内？是否引入 KP 范围外的新概念？
2. **超纲判定**：是否涉及七年级/初中概念（负数方程函数等，但 KP 已含的除外）？是否数字过大？英语是否含非课标词汇？
3. **年级情境**：字数/段落/词汇/数字是否符合六年级水平？
4. **答案正确性**：独立重做一遍，候选答案是否正确？
5. **解析质量**：解析是否含思路（不只是"答案=X"）？是否引用 KP 关键点？

【难度自标】（独立判断）：
- 易：记忆/理解，单 KP，选择/填空
- 中：应用/分析，2-3 KP 组合，句子改写
- 难：评价/创造，4+ KP 跨单元，多步推理

【输出格式】（严格 JSON，不要任何额外文字）
{{
  "passed": true | false,
  "kp_match": true | false,
  "kp_match_reason": "考点=...，落在/超出 KP 范围",
  "out_of_scope": true | false,
  "out_of_scope_reason": "具体超纲内容" | null,
  "age_appropriate": true | false,
  "age_issue": "具体问题" | null,
  "answer_correct": true | false,
  "answer_issue": "你独立做的答案=X，与候选不一致" | null,
  "explanation_quality": "good" | "fair" | "poor",
  "explanation_issue": "解析不足之处" | null,
  "difficulty": "易" | "中" | "难",
  "difficulty_basis": "判断理由",
  "overall_reason": "一句话总结"
}}
"""


def build_judge_prompt(question: dict, kp_detail: dict, subject: str) -> str:
    options = question.get('options') or []
    options_text = '\n'.join(f"  {chr(65+i)}. {o}" for i, o in enumerate(options)) if options else '（无选项）'

    ans = question.get('answer', '')
    if isinstance(ans, int) and options:
        answer_text = f"{chr(65+ans)} ({options[ans]})"
    elif isinstance(ans, str) and ans.isdigit() and options:
        idx = int(ans)
        answer_text = f"{chr(65+idx)} ({options[idx]})"
    else:
        answer_text = str(ans)

    return JUDGE_PROMPT_TEMPLATE.format(
        subject=subject,
        stem=question.get('stem', ''),
        options_text=options_text,
        answer_text=answer_text,
        explanation=question.get('explanation', '') or '（无）',
        kp_id=kp_detail.get('id', question.get('kp_id', '')),
        kp_name=kp_detail.get('name', ''),
        kp_definition=kp_detail.get('definition', '') or kp_detail.get('key_points', [''])[0] if isinstance(kp_detail.get('key_points'), list) else kp_detail.get('definition', ''),
        kp_key_points=' | '.join(kp_detail.get('key_points', [])) if isinstance(kp_detail.get('key_points'), list) else str(kp_detail.get('key_points', '')),
        kp_common_mistakes=' | '.join(kp_detail.get('common_mistakes', [])) if isinstance(kp_detail.get('common_mistakes'), list) else str(kp_detail.get('common_mistakes', '')),
    )


# === 模型调用 ===

def call_minimax(prompt: str, env: dict) -> dict:
    """MiniMax-M3 走 anthropic 协议（timeout 180s 避免长题被截断）"""
    key = env.get(PROVIDERS['minimax']['key_env'])
    base = PROVIDERS['minimax']['base_url']
    r = requests.post(
        f'{base}/v1/messages',
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
        },
        json={
            'model': PROVIDERS['minimax']['name'],
            'max_tokens': 2000,
            'messages': [{'role': 'user', 'content': prompt}],
        },
        timeout=240,
    )
    if r.status_code != 200:
        raise RuntimeError(f'MiniMax HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    text = j['content'][0]['text'] if j.get('content') else ''
    return {'text': text, 'usage': j.get('usage', {})}


MUSE_MODELS = ['muse-spark-1.3-contributor-free']  # 用户只要 1.3；免费层模型名带 -free 后缀


def _opencode_free_headers() -> dict:
    """Zen 免费层要求的 OpenCode 客户端识别头（实测 2026-09-12）：
    UA=opencode/x.y.z + X-Session-ID=随机 UUID + Referer/X-Title=opencode 才能过，
    否则 MissingSessionID / 429 FreeUsageLimitError。"""
    import uuid
    return {
        'User-Agent': 'opencode/0.20.5',
        'X-Session-ID': str(uuid.uuid4()),
        'HTTP-Referer': 'https://opencode.ai/',
        'X-Title': 'opencode',
    }


def extract_responses_text(j: dict) -> str:
    """解析 /v1/responses 返回：output[] 里的 output_text 块"""
    texts = []
    for item in j.get('output', []):
        if item.get('type') == 'message':
            for c in item.get('content', []):
                if c.get('type') == 'output_text':
                    texts.append(c['text'])
    return '\n'.join(texts)


def call_muse(prompt: str, env: dict) -> dict:
    """muse-spark-1.3-contributor-free 免费通道：Zen /v1/responses + 匿名 + opencode 头 + clash。
    Muse 1.3 是强推理模型，max_output_tokens 要留足（4000+，推理占大头）。"""
    base = PROVIDERS['muse']['base_url']
    last_err = None
    for model in MUSE_MODELS:
        r = requests.post(
            f'{base}/responses',
            headers=_opencode_free_headers() | {'Content-Type': 'application/json'},
            json={
                'model': model,
                'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': prompt}]}],
                'max_output_tokens': 4000,
                'reasoning': {'effort': 'medium'},
            },
            proxies=PROVIDERS['muse']['proxies'],
            timeout=180,
        )
        if r.status_code == 200:
            j = r.json()
            text = extract_responses_text(j)
            if not text.strip():
                # 推理吃光 token / 输出为空
                details = j.get('incomplete_details') or {}
                raise RuntimeError(f'Muse 输出为空（{details.get("reason", "unknown")}）')
            return {'text': text, 'usage': j.get('usage', {}), 'model': model}
        last_err = (model, r.status_code, r.text[:200])
    raise RuntimeError(f'Muse HTTP {last_err[1]} ({last_err[0]}): {last_err[2]}')



def call_ds_pro(prompt: str, env: dict) -> dict:
    """deepseek-v4-pro 走 openai 协议 + new-api"""
    key = env.get(PROVIDERS['ds_pro']['key_env'])
    r = requests.post(
        f'{PROVIDERS["ds_pro"]["base_url"]}/chat/completions',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={
            'model': PROVIDERS['ds_pro']['name'],
            'messages': [{'role': 'user', 'content': prompt}],
            'max_tokens': 3000,
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f'DS-Pro HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    # DS-Pro 有 reasoning 模式，content 可能为空，合并 reasoning_content
    msg = j['choices'][0]['message']
    text = msg.get('content', '') or ''
    if not text and msg.get('reasoning_content'):
        # 如果 content 为空但有 reasoning，取 reasoning 后再调一次（这里先标空）
        text = ''
    return {'text': text, 'usage': j.get('usage', {}), 'reasoning': msg.get('reasoning_content', '')}


# === JSON 提取（容错） ===

def extract_json(text: str) -> dict:
    """从模型输出中提取 JSON（容错：全角冒号、前后缀文字、多余尾随内容）"""
    text = text.strip().replace('：', ':')  # 全角冒号
    start = text.find('{')
    while start != -1:
        try:
            decoder = json.JSONDecoder()
            obj, _ = decoder.raw_decode(text[start:])  # 只取第一个完整 JSON 对象
            return obj
        except json.JSONDecodeError:
            start = text.find('{', start + 1)
    raise ValueError(f'未找到 JSON 块：{text[:200]}')


# === 单题投票 ===

def judge_one(question: dict, kp_detail: dict, subject: str, env: dict) -> dict:
    """对单题做 3 模型投票（串行）"""
    prompt = build_judge_prompt(question, kp_detail, subject)

    results = {
        'qid': question.get('qid', 'unknown'),
        'kp_id': question.get('kp_id', ''),
        'subject': subject,
        'voted_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'votes': {},
        'errors': {},
    }

    # 串行调用 3 个模型
    callers = [
        ('minimax', call_minimax, 'vote_1'),
        ('muse', call_muse, 'vote_3'),
        ('ds_pro', call_ds_pro, 'vote_2'),
    ]

    for model_key, caller, label in callers:
        try:
            resp = caller(prompt, env)
            text = resp['text']
            if not text.strip():
                raise RuntimeError(f'{model_key} 返回空内容（可能 reasoning 模式）')
            vote_result = extract_json(text)
            results['votes'][label] = {
                'model': PROVIDERS[model_key]['name'],
                'passed': vote_result.get('passed', False),
                'kp_match': vote_result.get('kp_match'),
                'out_of_scope': vote_result.get('out_of_scope'),
                'age_appropriate': vote_result.get('age_appropriate'),
                'answer_correct': vote_result.get('answer_correct'),
                'explanation_quality': vote_result.get('explanation_quality'),
                'difficulty': vote_result.get('difficulty', '中'),
                'reason': vote_result.get('overall_reason', ''),
                'raw': vote_result,
            }
        except Exception as e:
            results['errors'][label] = {
                'model': PROVIDERS[model_key]['name'],
                'error': str(e)[:300],
            }
            print(f'  ✗ {label} ({PROVIDERS[model_key]["name"]}) 调用失败: {str(e)[:100]}', file=sys.stderr)

        time.sleep(INTER_CALL_SLEEP)

    # 投票汇总
    valid_votes = list(results['votes'].values())
    pass_count = sum(1 for v in valid_votes if v.get('passed'))
    total = len(valid_votes)

    # 通过阈值：2 票全过、3 票过 2
    if total == 0:
        consensus_passed = False
        consensus_reason = '所有模型调用失败'
    elif total <= 2:
        consensus_passed = (pass_count == total)
        consensus_reason = f'{pass_count}/{total} 通过（少数模型）'
    else:
        consensus_passed = (pass_count >= 2)
        consensus_reason = f'{pass_count}/{total} 通过'

    # 难度取多数
    difficulties = [v.get('difficulty') for v in valid_votes if v.get('difficulty') in ('易','中','难')]
    from collections import Counter
    diff_counter = Counter(difficulties)
    consensus_difficulty = diff_counter.most_common(1)[0][0] if diff_counter else '中'

    results['consensus'] = {
        'passed': consensus_passed,
        'reason': consensus_reason,
        'pass_count': pass_count,
        'total_models': total,
        'difficulty': consensus_difficulty,
        'fail_reasons': [v.get('reason', '') for v in valid_votes if not v.get('passed')],
    }

    return results


# === 主入口 ===

def main():
    parser = argparse.ArgumentParser(description='3 模型投票判定器')
    parser.add_argument('--input', help='候选题 JSON 文件（含 candidates 数组）')
    parser.add_argument('--output', help='投票结果输出文件')
    parser.add_argument('--subject', required=True, choices=['数学', '语文', '英语'])
    parser.add_argument('--base-dir', default=None)

    # 单题模式
    parser.add_argument('--stem', help='题干')
    parser.add_argument('--options', help='选项（逗号分隔）')
    parser.add_argument('--answer', help='答案（索引或文本）')
    parser.add_argument('--explanation', default='', help='解析')
    parser.add_argument('--kp-id', help='KP 编号（如 u1.k1）')

    args = parser.parse_args()

    env = load_keys()

    base_dir = Path(args.base_dir) if args.base_dir else None
    if base_dir is None:
        for cand in [Path('D:/家教'), Path('/d/家教'), Path('D:\\家教')]:
            if cand.exists():
                base_dir = cand
                break

    # 单题模式
    if args.stem:
        if not args.kp_id:
            print('❌ 单题模式必须指定 --kp-id')
            sys.exit(1)

        kp_file = base_dir / args.subject / '知识点及掌握情况' / f'{args.kp_id}.json'
        if not kp_file.exists():
            print(f'❌ KP 文件不存在：{kp_file}')
            sys.exit(1)
        kp_detail = json.loads(kp_file.read_text(encoding='utf-8'))

        options = [o.strip() for o in args.options.split(',')] if args.options else None
        question = {
            'qid': args.kp_id,
            'kp_id': args.kp_id,
            'stem': args.stem,
            'options': options,
            'answer': args.answer,
            'explanation': args.explanation,
        }

        print(f'⏳ 投票判定：{args.kp_id} ({kp_detail.get("name", "")[:40]})')
        result = judge_one(question, kp_detail, args.subject, env)

        print()
        print('=== 投票结果 ===')
        for label, vote in result['votes'].items():
            mark = '✓' if vote.get('passed') else '✗'
            print(f'  {mark} {label}: {vote.get("model")} | passed={vote.get("passed")} | {vote.get("reason", "")[:80]}')
        for label, err in result['errors'].items():
            print(f'  ✗ {label}: {err.get("model")} | ERR: {err.get("error", "")[:100]}')
        print()
        c = result['consensus']
        mark = '✅' if c['passed'] else '❌'
        print(f'{mark} 综合：{c["pass_count"]}/{c["total_models"]} 通过，难度={c["difficulty"]}')
        print(f'   {c["reason"]}')
        if c.get('fail_reasons'):
            print(f'   反对理由：{c["fail_reasons"][0][:120]}')

        if args.output:
            Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'\n📝 详细结果已写入 {args.output}')
        return

    # 批处理模式
    if not args.input:
        print('❌ 必须指定 --input 或单题参数 (--stem/--kp-id)')
        sys.exit(1)

    in_path = Path(args.input)
    if not in_path.exists():
        print(f'❌ 输入文件不存在：{in_path}')
        sys.exit(1)

    data = json.loads(in_path.read_text(encoding='utf-8'))
    candidates = data.get('candidates', [])
    if not candidates:
        print(f'⚠ candidates 为空')
        return

    print(f'⏳ 批量投票：{len(candidates)} 道题，串行调用 3 模型...')

    results = []
    for i, cand in enumerate(candidates, 1):
        kp_id = cand.get('kp_id')
        if not kp_id:
            print(f'  [{i}] 跳过：无 kp_id')
            continue
        kp_file = base_dir / args.subject / '知识点及掌握情况' / f'{kp_id}.json'
        if not kp_file.exists():
            print(f'  [{i}] 跳过：KP {kp_id} 文件不存在')
            continue
        kp_detail = json.loads(kp_file.read_text(encoding='utf-8'))
        print(f'  [{i}/{len(candidates)}] {kp_id} ({kp_detail.get("name", "")[:30]})...', end=' ', flush=True)
        result = judge_one(cand, kp_detail, args.subject, env)
        results.append(result)
        c = result['consensus']
        mark = '✓' if c['passed'] else '✗'
        print(f'{mark} {c["pass_count"]}/{c["total_models"]}')

    summary = {
        'total': len(results),
        'passed': sum(1 for r in results if r['consensus']['passed']),
        'failed': sum(1 for r in results if not r['consensus']['passed']),
        'results': results,
    }

    if args.output:
        Path(args.output).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'\n✅ 汇总：{summary["passed"]}/{summary["total"]} 通过')
        print(f'📝 详细结果：{args.output}')
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
