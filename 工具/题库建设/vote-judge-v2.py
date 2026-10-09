#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""vote-judge-v2 跑抽样题库"""
import json, os, re, sys, time
from pathlib import Path
import requests

NEWAPI_BASE = 'http://127.0.0.1:13000/v1'
INTER_CALL_SLEEP = 2.0

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

JUDGE_PROMPT = """你是一位严谨的六年级{subject}老师，审核一道入库候选题。

【题目信息】
- 题干：{stem}
- 选项：{options_text}
- 候选答案：{answer_text}
- 解析：{explanation}

【目标知识点（KP）】
- KP ID：{kp_id}
- KP 名称：{kp_name}
- KP 定义：{kp_definition}

【审核 5 项】
1. **考点对照**：本题考点是否落在 KP 范围内？
2. **超纲判定**：是否涉及初中概念/过大数字/超标词汇？
3. **年级情境**：是否符合六年级水平？
4. **答案正确性**：候选答案是否正确？
5. **解析质量**：解析是否含思路？

【难度自标】：易 / 中 / 难

【输出】严格 JSON：
{{"passed": true|false, "kp_match": true|false, "out_of_scope": true|false,
  "age_appropriate": true|false, "answer_correct": true|false,
  "explanation_quality": "good"|"fair"|"poor",
  "difficulty": "易"|"中"|"难",
  "overall_reason": "一句话总结"}}
"""

def build_prompt(q, kp_detail, subject):
    options = q.get('options') or []
    options_text = '\n'.join(f"  {chr(65+i)}. {o}" for i, o in enumerate(options)) if options else '（无选项）'
    ans = q.get('answer', '')
    if isinstance(ans, int) and options and ans < len(options):
        answer_text = f"{chr(65+ans)} ({options[ans]})"
    elif isinstance(ans, str) and ans.isdigit() and options:
        idx = int(ans)
        if idx < len(options):
            answer_text = f"{chr(65+idx)} ({options[idx]})"
        else:
            answer_text = str(ans)
    else:
        answer_text = str(ans)
    return JUDGE_PROMPT.format(
        subject=subject,
        stem=q.get('stem', '')[:500],
        options_text=options_text,
        answer_text=answer_text,
        explanation=(q.get('explanation', '') or '（无）')[:300],
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
    r = requests.post(f'{NEWAPI_BASE}/chat/completions',
        headers={'Authorization': f'Bearer {ENV["NEWAPI_CLIENT_TOKEN"]}', 'Content-Type': 'application/json'},
        json={'model': model, 'max_tokens': 1500,
              'messages': [{'role': 'user', 'content': prompt}]}, timeout=120)
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
    
    try:
        text = call_minimax(prompt)
        v = parse_verdict(text)
        if v: votes.append({'model': 'MiniMax-M3', 'verdict': v})
    except Exception as e:
        print(f"      mm err: {str(e)[:60]}", flush=True)
    time.sleep(INTER_CALL_SLEEP)
    
    try:
        text = call_openai(prompt, 'kimi-k3')
        v = parse_verdict(text)
        if v: votes.append({'model': 'kimi-k3', 'verdict': v})
    except Exception as e:
        print(f"      k3 err: {str(e)[:60]}", flush=True)
    time.sleep(INTER_CALL_SLEEP)
    
    try:
        text = call_openai(prompt, 'deepseek-flash')
        v = parse_verdict(text)
        if v: votes.append({'model': 'deepseek-flash', 'verdict': v})
    except Exception as e:
        print(f"      ds err: {str(e)[:60]}", flush=True)
    time.sleep(INTER_CALL_SLEEP)
    
    n_total = len(votes)
    n_pass = sum(1 for v in votes if v['verdict'].get('passed'))
    threshold = max(2, (n_total // 2) + 1)
    return {
        'votes': votes, 'n_total': n_total, 'n_pass': n_pass,
        'threshold': threshold, 'passed': n_pass >= threshold,
    }

def main():
    # 读 sample
    sample = json.loads(Path(r'D:\家教\系统\scripts\_vote_sample.json').read_text(encoding='utf-8'))
    
    # 读所有题（按 qid 索引）
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
    
    # KP 池
    kp_pools = {}
    for subj in ['数学','语文','英语']:
        kp_pools[subj] = json.loads(Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json').read_text(encoding='utf-8'))
    
    # 断点
    out_file = Path(r'D:\家教\系统\scripts\_vote_results.json')
    results = []
    done_qids = set()
    if out_file.exists():
        results = json.loads(out_file.read_text(encoding='utf-8'))
        done_qids = {r['qid'] for r in results}
        print(f"已审: {len(done_qids)}", flush=True)
    
    # 跑三科
    n_done = 0
    for subj in ['语文', '数学', '英语']:  # 先语文（AI 生成多）
        sample_qs = sample[subj]
        print(f"\n===== {subj} 抽 {len(sample_qs)} 题 =====", flush=True)
        for i, item in enumerate(sample_qs, 1):
            qid = item['qid']
            if qid in done_qids: continue
            q = all_qs.get(qid)
            if not q: continue
            kp_detail = kp_pools[subj].get(q.get('kp_id',''), {})
            
            print(f"  [{i}/{len(sample_qs)}] {qid[-50:]}", flush=True)
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
                print(f"    checkpoint n={n_done}, 通过 {n_pass}/{len(results)}", flush=True)
    
    out_file.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    n_pass = sum(1 for x in results if x['passed'])
    print(f"\n=== 完成: {n_pass}/{len(results)} 通过 ===", flush=True)

if __name__ == '__main__':
    main()
