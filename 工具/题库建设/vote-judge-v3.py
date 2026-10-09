#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-judge-v3.py — 只评题目质量，不评答案解析"""
import json, os, re, sys, time
from pathlib import Path
import requests

NEWAPI_BASE = 'http://127.0.0.1:13000/v1'
INTER_CALL_SLEEP = 4.0

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

def call_minimax(prompt):
    r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
        headers={'Authorization': f'Bearer {ENV["MINIMAX_CN_API_KEY"]}', 
                 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
        json={'model': 'MiniMax-M3', 'max_tokens': 1500,
              'messages': [{'role': 'user', 'content': prompt}]}, timeout=120)
    r.raise_for_status()
    return r.json()['content'][0]['text']

def call_openai(prompt, model):
    # DS-Pro 是 reasoning 模型，max_tokens 要 >= 3000
    max_tok = 3000 if 'pro' in model.lower() else 1500  # flash 用 1500
    r = requests.post(f'{NEWAPI_BASE}/chat/completions',
        headers={'Authorization': f'Bearer {ENV["NEWAPI_CLIENT_TOKEN"]}', 'Content-Type': 'application/json'},
        json={'model': model, 'max_tokens': max_tok,
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

def judge_one(q, kp_detail, subject):
    prompt = build_prompt(q, kp_detail, subject)
    votes = []
    
    for name, caller in [('MiniMax-M3', lambda: call_minimax(prompt)),
                          ('kimi-k3', lambda: call_openai(prompt, 'kimi-k3')),
                          ('deepseek-flash', lambda: call_openai(prompt, 'deepseek-flash'))]:
        try:
            text = caller()
            v = parse_verdict(text)
            if v: votes.append({'model': name, 'verdict': v})
        except Exception as e:
            print(f"      {name} err: {str(e)[:60]}", flush=True)
        time.sleep(INTER_CALL_SLEEP)
    
    n_total = len(votes)
    n_pass = sum(1 for v in votes if v['verdict'].get('passed'))
    # 阈值规则（修复）：1 票听 1 票，2 票要 2 票，3 票要 2 票
    if n_total == 0:
        threshold = 1
    elif n_total == 1:
        threshold = 1
    elif n_total == 2:
        threshold = 2
    else:  # 3+
        threshold = 2
    return {
        'votes': votes, 'n_total': n_total, 'n_pass': n_pass,
        'threshold': threshold, 'passed': n_pass >= threshold,
    }

def main():
    sample = json.loads(Path(r'D:\家教\系统\scripts\_vote_sample.json').read_text(encoding='utf-8'))
    
    all_qs = {}
    for subj in ['数学','语文','英语']:
        base = Path(rf'D:\家教\{subj}\测验')
        for p in sorted(base.rglob('*.json')):
            if p.parent.name.startswith(('u','sp','r')) and p.stem.count('.')==1:
                try:
                    qs = json.loads(p.read_text(encoding='utf-8'))
                    for q in qs:
                        if q.get('qid'):
                            q['subject'] = subj
                            all_qs[q['qid']] = q
                except: pass
    print(f"题库总: {len(all_qs)}", flush=True)
    
    kp_pools = {}
    for subj in ['数学','语文','英语']:
        kp_pools[subj] = json.loads(Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json').read_text(encoding='utf-8'))
    
    out_file = Path(r'D:\家教\系统\scripts\_vote_results_v3.json')
    results = []
    done_qids = set()
    if out_file.exists():
        results = json.loads(out_file.read_text(encoding='utf-8'))
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
            kp_detail = kp_pools[subj].get(q.get('kp_id',''), {})
            
            print(f"  [{i}/{len(sample_qs)}] {qid[-45:]}", flush=True)
            r = judge_one(q, kp_detail, subj)
            r['qid'] = qid
            r['kp_id'] = q.get('kp_id')
            r['unit_id'] = q.get('unit_id')
            r['subject'] = subj
            r['ai_generated'] = q.get('ai_generated', False)
            r['stem_preview'] = q.get('stem','')[:60]
            results.append(r)
            n_done += 1
            
            if n_done % 10 == 0:
                out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
                n_pass = sum(1 for x in results if x['passed'])
                print(f"    ckpt n={n_done}, 通过 {n_pass}/{len(results)}", flush=True)
    
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    n_pass = sum(1 for x in results if x['passed'])
    print(f"\n=== 完成: {n_pass}/{len(results)} 通过 ({100*n_pass/max(1,len(results)):.0f}%) ===", flush=True)

if __name__ == '__main__':
    main()
