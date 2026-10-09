#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-judge-v4.py — 4 票制投票：MiniMax-M3 / kimi-k3 / deepseek-flash / jev(System One)

在 v3 基础上加入 jev 作为第 4 票（结构化判定：noul×4 + score×1，Node CLI 直调）。

用法：
  python vote-judge-v4.py                  # 全量：3 LLM + jev（新题）
  python vote-judge-v4.py --jev-only       # 补票：只跑 jev，合并 v3 结果 → _vote_results_v4.json
  python vote-judge-v4.py --jev-only --limit=10   # 小规模测试

输出：
  _vote_results_v4.json  （含每票明细 + jev 原始 noul 概率）
"""
import json, os, re, sys, time, subprocess
from pathlib import Path
import requests
from datetime import datetime

NEWAPI_BASE = 'http://127.0.0.1:13000/v1'
INTER_CALL_SLEEP = 4.0

NODE = r"D:\hermes-data\node\node.exe"
CLI_JS = r"D:\hermes-data\node\node_modules\command-code\dist\index.mjs"
NODE_WORKDIR = r"D:\hermes-data\node"

BASE = Path(r'D:\家教\系统\scripts')
OUT_FILE = BASE / '_vote_results_v4.json'
V3_FILE = BASE / '_vote_results_v3.json'


def load_env():
    for path in [r'D:\hermes-data\.env', r'/d/hermes-data/.env']:
        if os.path.exists(path):
            env = {}
            with open(path, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line: continue
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.split('#')[0].strip()
            return env
    raise FileNotFoundError

ENV = load_env()

JUDGE_PROMPT = """你是深圳小学六年级{subject}教研组长，审核一道候选题是否适合入库。

【题目】
- 题干：{stem}
- 选项：{options_text}
- 题型：{q_type}

【目标 KP】
- KP ID：{kp_id}
- KP 名称：{kp_name}
- KP 定义：{kp_definition}

【KP 范围理解 — 重要】
课本 KP 不仅是"课文内容理解"，还包括**本课/本单元要掌握的所有学习点**：
- 课文字词（生字、拼音、词语、书写）
- 课文内容理解与赏析
- 课文写法、修辞、文学常识
- 与本课主题相关的拓展练习
- 数学 KP 同理：含概念、公式、计算、应用题、变式

只要题目考的是**本课/本单元**应掌握的内容（不超纲、符合六年级水平），就视为 kp_match=true。

【审核 4 项 — 只看题目质量本身，不评答案/解析】
1. **kp_match**：本题考点是否属于本课/本单元要掌握的内容？
2. **out_of_scope**：是否涉及初中概念/过大数字/超标词汇？
3. **stem_clear**：题干是否清晰完整、无语病、无歧义？
4. **age_appropriate**：语言/数字/情境是否符合六年级水平？

【难度自标】：易 / 中 / 难（按六年级标准）

【通过规则】
- kp_match=true AND out_of_scope=false AND stem_clear=true AND age_appropriate=true → passed=true

【输出】严格 JSON（不要 markdown 围栏）：
{{"passed": true|false,
  "kp_match": true|false,
  "out_of_scope": true|false,
  "stem_clear": true|false,
  "age_appropriate": true|false,
  "difficulty": "易"|"中"|"难",
  "fail_reason": "如果 passed=false，说哪个不达标" | null,
  "overall_reason": "一句话评题"}}
"""


def build_prompt(q, kp_detail, subject):
    options = q.get('options') or []
    options_text = '\n'.join(f"  {chr(65+i)}. {o}" for i, o in enumerate(options)) if options else '（无选项）'
    return JUDGE_PROMPT.format(
        subject=subject,
        stem=q.get('stem', '')[:600],
        options_text=options_text,
        q_type=q.get('type', ''),
        kp_id=q.get('kp_id', ''),
        kp_name=kp_detail.get('name', ''),
        kp_definition=kp_detail.get('definition', '')[:300],
    )


# ---------------- LLM 调用（沿用 v3） ----------------

def call_minimax(prompt):
    r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
        headers={'Authorization': f'Bearer {ENV["MINIMAX_CN_API_KEY"]}',
                 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
        json={'model': 'MiniMax-M3', 'max_tokens': 1500,
              'messages': [{'role': 'user', 'content': prompt}]}, timeout=120)
    r.raise_for_status()
    return r.json()['content'][0]['text']


def call_openai(prompt, model):
    r = requests.post(f'{NEWAPI_BASE}/chat/completions',
        headers={'Authorization': f'Bearer {ENV["NEWAPI_CLIENT_TOKEN"]}', 'Content-Type': 'application/json'},
        json={'model': model, 'max_tokens': 1500,
              'messages': [{'role': 'user', 'content': prompt}]}, timeout=180)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']


def parse_verdict(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text)
    s = text.find('{'); e = text.rfind('}')
    if s >= 0 and e > s:
        try: return json.loads(text[s:e+1])
        except:
            try:
                import json_repair
                return json_repair.loads(text[s:e+1])
            except: return None
    return None


# ---------------- jev 调用（新增） ----------------

def call_jev(state, questions, timeout=90):
    """Node CLI 直调 jev，返回 (answers_dict, elapsed) 或 (None, elapsed)"""
    prompt = json.dumps({"state": state, "questions": questions}, ensure_ascii=False)
    t0 = time.perf_counter()
    try:
        res = subprocess.run(
            [NODE, CLI_JS, "-p", prompt, "-m", "typesafe/jev",
             "--output-format", "json", "--skip-onboarding"],
            capture_output=True, text=True, timeout=timeout,
            cwd=NODE_WORKDIR, env={**os.environ, "CI": "1"},
        )
    except subprocess.TimeoutExpired:
        return None, time.perf_counter() - t0
    elapsed = time.perf_counter() - t0
    if res.returncode != 0:
        return None, elapsed
    lines = [ln for ln in res.stdout.strip().splitlines() if ln.startswith("{")]
    if not lines:
        return None, elapsed
    try:
        return json.loads(lines[-1]), elapsed
    except Exception:
        return None, elapsed


def build_jev_payload(q, kp_detail, subject):
    """构造 jev 的 state + questions（与 LLM 审核 4 项同构）"""
    opts = q.get('options') or []
    opt_txt = ' '.join(f"{chr(65+i)}.{str(o)[:60]}" for i, o in enumerate(opts[:4])) if opts else ''
    state = {
        "subject": f"{subject}（小学六年级）",
        "question": (q.get('stem', '')[:500] + (f"  选项：{opt_txt}" if opt_txt else '')),
        "type": q.get('type', ''),
        "kp_id": q.get('kp_id', ''),
        "kp_name": kp_detail.get('name', ''),
        "kp_definition": kp_detail.get('definition', '')[:200],
    }
    questions = {
        "kp_match": {
            "type": "noul",
            "instructions": (
                f"本题考点是否属于本课/本单元要掌握的内容？"
                f"目标KP：{q.get('kp_id','')} {kp_detail.get('name','')}（{kp_detail.get('definition','')[:120]}）。"
                "属于答yes，不属于答no。注意：课文字词、内容理解、写法修辞、拓展练习都算本课范围。"
            ),
        },
        "out_of_scope": {
            "type": "noul",
            "instructions": "本题是否超纲（涉及初中概念/过大数字/超标词汇）？超纲答yes，不超纲答no。",
        },
        "stem_clear": {
            "type": "noul",
            "instructions": "题干是否清晰完整、无语病、无歧义？清晰答yes，不清晰答no。",
        },
        "age_appropriate": {
            "type": "noul",
            "instructions": "语言/数字/情境是否符合小学六年级水平？符合答yes，不符合答no。",
        },
        "difficulty": {
            "type": "score",
            "instructions": "评估难度（按六年级标准）",
            "criteria": ["易", "中", "难"],
        },
    }
    return state, questions


def jev_verdict(ans):
    """把 jev answers 转成与 LLM 同构的 verdict"""
    if not ans or 'answers' not in ans:
        return None
    a = ans['answers']
    kp = float(a.get('kp_match', {}).get('noul', 0))
    oos = float(a.get('out_of_scope', {}).get('noul', 0))
    sc = float(a.get('stem_clear', {}).get('noul', 0))
    aa = float(a.get('age_appropriate', {}).get('noul', 0))
    d = a.get('difficulty', {}).get('score', 1)
    di = int(round(float(d))) if isinstance(d, (int, float)) else 1
    di = max(0, min(2, di))
    passed = (kp >= 0.5) and (oos < 0.5) and (sc >= 0.5) and (aa >= 0.5)
    reasons = []
    if kp < 0.5: reasons.append('KP不匹配')
    if oos >= 0.5: reasons.append('超纲')
    if sc < 0.5: reasons.append('题干不清')
    if aa < 0.5: reasons.append('年龄不适')
    return {
        'passed': passed,
        'kp_match': kp >= 0.5,
        'out_of_scope': oos >= 0.5,
        'stem_clear': sc >= 0.5,
        'age_appropriate': aa >= 0.5,
        'difficulty': ['易', '中', '难'][di],
        'fail_reason': ('+'.join(reasons) if reasons else None),
        'overall_reason': f"jev: kp={kp:.2f} oos={oos:.2f} sc={sc:.2f} aa={aa:.2f}",
        'noul_raw': {'kp_match': kp, 'out_of_scope': oos, 'stem_clear': sc, 'age_appropriate': aa},
    }


def judge_jev(q, kp_detail, subject):
    """jev 单票判定，返回 (vote_dict, elapsed)"""
    state, questions = build_jev_payload(q, kp_detail, subject)
    ans, dt = call_jev(state, questions)
    v = jev_verdict(ans)
    if v is None:
        return None, dt
    return {'model': 'jev', 'verdict': v, 'elapsed': round(dt, 2)}, dt


# ---------------- 阈值 & 汇总 ----------------

def apply_threshold(votes):
    """投票规则（2026-09-24 改）：去 M3 后 = kimi + deepseek + jev 共 3 票，
    多数决：3票要2票，2票要2票，1票要1票。
    （M3 的判断已由第一层入库 self_review 承担，不再重复投票）"""
    n_total = len(votes)
    n_pass = sum(1 for v in votes if v['verdict'].get('passed'))
    if n_total <= 1: threshold = 1
    elif n_total == 2: threshold = 2
    elif n_total == 3: threshold = 2
    else: threshold = 3
    return n_total, n_pass, threshold, n_pass >= threshold


def judge_one_llm(q, kp_detail, subject):
    """2 个独立 LLM 并行判定

    2026-09-24 用户决策：
      - M3 的票 = 第一层入库 self_review 的自我复读，无独立信息 → 去掉
      - 实测并行比串行更快且成功率更高 → 改 ThreadPoolExecutor
      - 429 自动重试一次
    与 jev 合计 = 3 票；阈值 2（多数决）
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    prompt = build_prompt(q, kp_detail, subject)
    jobs = [('kimi-k3', lambda: call_openai(prompt, 'kimi-k3')),
            ('deepseek-flash', lambda: call_openai(prompt, 'deepseek-flash'))]

    def _run(item):
        name, caller = item
        for attempt in (1, 2):
            try:
                text = caller()
                v = parse_verdict(text)
                if v:
                    return {'model': name, 'verdict': v}
            except Exception as e:
                msg = str(e)[:60]
                if '429' in msg and attempt == 1:
                    time.sleep(5)
                    continue
                print(f"      {name} err: {msg}", flush=True)
                break
        return None

    votes = []
    with ThreadPoolExecutor(max_workers=len(jobs)) as ex:
        for fut in as_completed([ex.submit(_run, j) for j in jobs]):
            r = fut.result()
            if r:
                votes.append(r)
    return votes


# ---------------- 题库加载 ----------------

def load_all_questions():
    all_qs = {}
    for subj in ['数学', '语文', '英语']:
        d = Path(rf'D:\家教\{subj}\测验')
        for p in sorted(d.rglob('*.json')):
            if p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1:
                try:
                    for q in json.loads(p.read_text(encoding='utf-8')):
                        if q.get('qid'):
                            q['subject'] = subj
                            all_qs[q['qid']] = q
                except: pass
    return all_qs


def load_kp_pools():
    kp_pools = {}
    for subj in ['数学', '语文', '英语']:
        kp_pools[subj] = json.loads(Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json').read_text(encoding='utf-8'))
    return kp_pools


# ---------------- 模式 1：jev 补票 ----------------

def run_targets(qids=None, subject=None, kp_id=None, limit=None):
    """定向投票（C 方案：按需投票，出卷前质检某单元/某 KP）"""
    all_qs = load_all_questions()
    kp_pools = load_kp_pools()
    targets = []
    if qids:
        for qid in qids:
            q = all_qs.get(qid)
            if q:
                targets.append(q)
    else:
        for qid, q in all_qs.items():
            if subject and q.get('subject') != subject:
                continue
            if kp_id and q.get('kp_id') != kp_id:
                continue
            if q.get('vote_review'):
                continue
            targets.append(q)
    if limit:
        targets = targets[:limit]
    print(f"目标: {len(targets)} 题（subject={subject} kp={kp_id}）", flush=True)
    if not targets:
        print("无待投题（可能都已投过）")
        return
    out_file = BASE / '_vote_results_target.json'
    results = json.loads(out_file.read_text(encoding='utf-8')) if out_file.exists() else []
    done = {r['qid'] for r in results}
    n_pass = 0
    t0 = time.perf_counter()
    for i, q in enumerate(targets, 1):
        if q['qid'] in done:
            continue
        subj = q.get('subject', '语文')
        kp_detail = kp_pools.get(subj, {}).get(q.get('kp_id', ''), {})
        votes = judge_one_llm(q, kp_detail, subj)     # 一次返回 3 个 LLM 的票
        vj, _dt = judge_jev(q, kp_detail, subj)
        if vj:
            votes.append(vj)
        n_total, n_pass_i, threshold, passed = apply_threshold(votes)
        results.append({'qid': q['qid'], 'subject': subj, 'kp_id': q.get('kp_id'),
                        'votes': votes, 'n_total': n_total, 'n_pass': n_pass_i,
                        'threshold': threshold, 'passed': passed,
                        'voted_at': time.strftime('%Y-%m-%dT%H:%M:%S')})
        if passed:
            n_pass += 1
        print(f"  [{i}/{len(targets)}] {q['qid'][-45:]} {n_pass_i}/{n_total} "
              f"{'PASS' if passed else 'x'} [{','.join(v['model'] for v in votes)}]", flush=True)
        if i % 10 == 0:
            out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    dt = time.perf_counter() - t0
    print(f"\n完成: {n_pass}/{len(targets)} 通过 ({n_pass/max(1,len(targets))*100:.1f}%) | {dt/60:.1f} 分钟")
    print(f"输出: {out_file}")


def run_jev_only(limit=None):
    """读 _vote_results_v3.json，补 jev 票 → _vote_results_v4.json"""
    v3 = json.loads(V3_FILE.read_text(encoding='utf-8'))
    all_qs = load_all_questions()
    kp_pools = load_kp_pools()
    print(f"v3 结果: {len(v3)} 条 | 题库: {len(all_qs)}", flush=True)

    results = []
    done = set()
    if OUT_FILE.exists():
        results = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        done = {r['qid'] for r in results if any(v.get('model') == 'jev' for v in r.get('votes', []))}
        print(f"已补 jev: {len(done)}", flush=True)

    todo = [r for r in v3 if r['qid'] not in done]
    if limit:
        todo = todo[:limit]
    print(f"待补: {len(todo)}", flush=True)

    t_start = time.perf_counter()
    n_ok = n_fail = 0
    lat = []
    for i, r in enumerate(todo, 1):
        qid = r['qid']
        q = all_qs.get(qid)
        if not q:
            r2 = dict(r)
            r2['jev_error'] = 'question_not_found'
            results.append(r2)
            continue
        subj = r['subject']
        kp_detail = kp_pools[subj].get(q.get('kp_id', ''), {})
        vote, dt = judge_jev(q, kp_detail, subj)
        r2 = dict(r)
        if vote:
            votes = [v for v in r2.get('votes', []) if v.get('model') != 'jev']
            votes.append(vote)
            r2['votes'] = votes
            n_total, n_pass, threshold, passed = apply_threshold(votes)
            r2['n_total'] = n_total
            r2['n_pass'] = n_pass
            r2['threshold'] = threshold
            r2['passed_v4'] = passed
            r2['passed_v3_orig'] = r.get('passed')
            lat.append(dt)
            n_ok += 1
            flag = 'OK' if vote['verdict']['passed'] else 'X'
            print(f"  [{i}/{len(todo)}] {qid[-42:]} jev={flag} ({dt:.1f}s) | v3={r.get('passed')} v4={passed}", flush=True)
        else:
            r2['jev_error'] = 'call_failed'
            n_fail += 1
            print(f"  [{i}/{len(todo)}] {qid[-42:]} jev=ERR ({dt:.1f}s)", flush=True)
        results.append(r2)
        if i % 10 == 0:
            OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f"    ckpt n={len(results)}", flush=True)

    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    total_t = time.perf_counter() - t_start
    import statistics
    print(f"\n=== jev 补票完成: {n_ok} ok / {n_fail} err | 总耗时 {total_t/60:.1f} 分钟 ===", flush=True)
    if lat:
        print(f"单题耗时: p50={statistics.median(lat):.1f}s avg={statistics.mean(lat):.1f}s max={max(lat):.1f}s", flush=True)
    print(f"输出: {OUT_FILE}", flush=True)


# ---------------- 模式 2：全量 4 票 ----------------

def run_full():
    sample = json.loads((BASE / '_vote_sample.json').read_text(encoding='utf-8'))
    all_qs = load_all_questions()
    kp_pools = load_kp_pools()
    print(f"题库总: {len(all_qs)}", flush=True)

    results = []
    done_qids = set()
    if OUT_FILE.exists():
        results = json.loads(OUT_FILE.read_text(encoding='utf-8'))
        done_qids = {r['qid'] for r in results}
        print(f"已审: {len(done_qids)}", flush=True)

    n_done = 0
    for subj in ['语文', '数学', '英语']:
        sample_qs = sample[subj]
        print(f"\n===== {subj} {len(sample_qs)} 题 =====", flush=True)
        for i, item in enumerate(sample_qs, 1):
            qid = item['qid']
            if qid in done_qids: continue
            q = all_qs.get(qid)
            if not q: continue
            kp_detail = kp_pools[subj].get(q.get('kp_id', ''), {})

            print(f"  [{i}/{len(sample_qs)}] {qid[-45:]}", flush=True)
            votes = judge_one_llm(q, kp_detail, subj)
            vote_jev, dt = judge_jev(q, kp_detail, subj)
            if vote_jev:
                votes.append(vote_jev)
            n_total, n_pass, threshold, passed = apply_threshold(votes)
            r = {'votes': votes, 'n_total': n_total, 'n_pass': n_pass,
                 'threshold': threshold, 'passed': passed,
                 'qid': qid, 'kp_id': q.get('kp_id'), 'unit_id': q.get('unit_id'),
                 'subject': subj, 'ai_generated': q.get('ai_generated', False),
                 'stem_preview': q.get('stem', '')[:60]}
            results.append(r)
            n_done += 1

            if n_done % 10 == 0:
                OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
                n_pass = sum(1 for x in results if x['passed'])
                print(f"    ckpt n={n_done}, 通过 {n_pass}/{len(results)}", flush=True)

    OUT_FILE.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    n_pass = sum(1 for x in results if x['passed'])
    print(f"\n=== 完成: {n_pass}/{len(results)} 通过 ({100*n_pass/max(1,len(results)):.0f}%) ===", flush=True)


if __name__ == '__main__':
    if '--targets' in sys.argv:
        def _arg(nm, dflt=None):
            if nm in sys.argv:
                k = sys.argv.index(nm)
                return sys.argv[k + 1] if k + 1 < len(sys.argv) else dflt
            return dflt
        _q = _arg('--qids')
        run_targets(qids=[x for x in _q.split(',') if x] if _q else None,
                    subject=_arg('--subject'), kp_id=_arg('--kp'),
                    limit=int(_arg('--limit')) if _arg('--limit') else None)
    elif '--jev-only' in sys.argv:
        limit = None
        for a in sys.argv:
            if a.startswith('--limit='):
                limit = int(a.split('=', 1)[1])
        run_jev_only(limit)
    else:
        run_full()
