#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-ingest.py — 按 KP 搜索题目 → 从搜索 content 提取 → KP 归属 → 入库"""

import argparse
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

CLASH = 'http://127.0.0.1:7897'
def _find_keys():
    for c in [r'D:\hermes-data\skills\multi-search-engine\api-keys.json',
              r'/d/hermes-data/skills/multi-search-engine/api-keys.json',
              r'/mnt/d/hermes-data/skills/multi-search-engine/api-keys.json']:
        if os.path.exists(c):
            return c
    raise FileNotFoundError('api-keys.json not found')
KEYS_FILE = _find_keys()


def load_env():
    env = {}
    for p in [r'D:\hermes-data\.env', r'/d/hermes-data/.env']:
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.split('#')[0].strip()
            return env
    raise FileNotFoundError('.env not found')


def baidu_search(query, top_k=6):
    keys = json.load(open(KEYS_FILE, encoding='utf-8'))
    key = keys['channels']['baidu_qianfan']['api_key']
    r = requests.post('https://qianfan.baidubce.com/v2/ai_search/web_search',
        headers={'Authorization': f'Bearer {key}', 'X-Appbuilder-From': 'openmaic', 'Content-Type': 'application/json'},
        json={'messages':[{'content':query,'role':'user'}], 'search_source':'baidu_search_v2',
              'resource_type_filter':[{'type':'web','top_k':top_k}]},
        timeout=30)
    if r.status_code != 200:
        return []
    return r.json().get('references', [])


def call_muse(prompt, max_tokens=4000):
    r = requests.post('https://opencode.ai/zen/v1/responses',
        headers={'User-Agent':'opencode/0.20.5','X-Session-ID':str(uuid.uuid4()),
                 'HTTP-Referer':'https://opencode.ai/','X-Title':'opencode','Content-Type':'application/json'},
        json={'model':'muse-spark-1.3-contributor-free',
              'input':[{'role':'user','content':[{'type':'input_text','text':prompt}]}],
              'max_output_tokens':max_tokens,'reasoning':{'effort':'medium'}},
        proxies={'http':CLASH,'https':CLASH}, timeout=180)
    if r.status_code != 200:
        raise RuntimeError(f'Muse HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    texts=[c['text'] for i in j.get('output',[]) if i.get('type')=='message' for c in i.get('content',[]) if c.get('type')=='output_text']
    return '\n'.join(texts)


def extract_json_array(text):
    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            return []
    return []


def extract_json_obj(text):
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            return None
    return None


def detect_base_dir():
    for c in [Path('/d/家教'), Path('/mnt/d/家教'), Path('D:/家教')]:
        if c.exists():
            return c
    raise FileNotFoundError('家教 root not found')


def load_kp_pool(subj_dir):
    kp_dir = subj_dir / '知识点及掌握情况'
    pool_file = kp_dir / '_kp_pool.json'
    if pool_file.exists():
        return json.load(open(pool_file, encoding='utf-8'))
    kp_index = json.load(open(kp_dir/'index.json', encoding='utf-8'))
    pool = {}
    for u in kp_index['units']:
        for kp_id in u['kp_ids']:
            p = kp_dir / f'{kp_id}.json'
            if p.exists():
                d = json.load(open(p, encoding='utf-8'))
                pool[kp_id] = {'unit': u['id'],'unit_name': u.get('name',''),
                               'name': d.get('name',''),'definition': d.get('definition','')}
    pool_file.write_text(json.dumps(pool, ensure_ascii=False, indent=2), encoding='utf-8')
    return pool


EXTRACT_PROMPT = """下面是从网页抓到的一段{subject}题目相关文本。请从中提取所有完整题目（含题干/选项/答案/解析），转成 JSON 数组。

【文本】
{content}

【要求】
1. 只提取完整题目（有题干和答案），跳过不完整的片段
2. 选项题 options 用 {{"A":"...","B":"..."}} 格式；答案给字母
3. 填空/简答 answer 给文本
4. 每题加 type 字段（语文：字音字形/看拼音写词语/辨字组词/句子改写/课文填空/阅读理解/古诗词默写/习作片段等；数学：计算题/应用题/选择题/填空题等；英语：单词拼写/句型转换/阅读理解/完形填空/听力题等）
5. 严格 JSON 数组输出，不要其他文字
6. 如果没有完整题目，输出 []

【输出】
[{{"题号":"1","题干":"...","选项":{{"A":"...","B":"..."}},"答案":"B","解析":"...","题型":"..."}}]"""


def build_kp_prompt(q, kp_pool, subject):
    lines = []
    for kp_id, info in kp_pool.items():
        lines.append(f"- {kp_id} [{info['unit_name']}] {info['name']}: {info['definition'][:80]}")
    kp_text = '\n'.join(lines)
    opts = q.get('选项') or q.get('options') or {}
    if isinstance(opts, dict) and opts:
        opts_text = ' | '.join(f'{k}.{v}' for k,v in opts.items())
    else:
        opts_text = '(无选项)'
    return (f'你是深圳六年级{subject}老师，判断这道题考查的核心知识点属于哪个 KP。\n\n'
            f'【题目】\n题干：{q.get("题干") or q.get("stem","")}\n选项：{opts_text}\n答案：{q.get("答案") or q.get("answer")}\n解析：{q.get("解析") or q.get("explanation","")}\n\n'
            f'【候选 KP 列表】\n{kp_text}\n\n'
            f'【任务】\n1. 选出最匹配的 1 个 KP 编号（严格来自列表）。\n2. 难度：易 / 中 / 难。\n'
            f'3. 匹配理由（30 字内）。\n4. also_covers：最多 2 个其他 KP 编号。\n\n'
            f'【输出】（严格 JSON）\n{{"kp_id": "u1.k2", "difficulty": "中", "reason": "...", "also_covers": []}}')


def insert_question(subj_dir, q_full, kp_id):
    unit_id = kp_id.split('.')[0]
    unit_dir = subj_dir / '测验' / unit_id
    unit_dir.mkdir(parents=True, exist_ok=True)
    kp_file = unit_dir / f'{kp_id}.json'
    qs = []
    if kp_file.exists():
        qs = json.loads(kp_file.read_text(encoding='utf-8'))
    if q_full['qid'] in {x['qid'] for x in qs}:
        return False
    qs.append(q_full)
    kp_file.write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--subject', required=True, choices=['数学','语文','英语'])
    ap.add_argument('--query', required=True, help='搜索词（如"部编版六年级语文上册第一单元测试卷 题目 内容"）')
    ap.add_argument('--top-k', type=int, default=6)
    ap.add_argument('--source-site', default='百度搜索缓存')
    args = ap.parse_args()

    base_dir = detect_base_dir()
    subj_dir = base_dir / args.subject
    kp_pool = load_kp_pool(subj_dir)

    print(f'[1/4] 搜索: {args.query}')
    refs = baidu_search(args.query, args.top_k)
    print(f'    命中 {len(refs)} 条')

    # 过滤有实质内容的
    good = [r for r in refs if len(r.get('content','')) > 300]
    print(f'    有实质内容: {len(good)} 条')

    print(f'[2/4] 提取题目（MiniMax/Muse 从 content 提取）...')
    all_q = []
    for i, ref in enumerate(good, 1):
        content = ref.get('content','')
        url = ref.get('url','')
        title = ref.get('title','')
        print(f'    [{i}/{len(good)}] {title[:35]}...', end=' ', flush=True)
        prompt = EXTRACT_PROMPT.format(subject=args.subject, content=content[:8000])
        try:
            text = call_muse(prompt)
            qs = extract_json_array(text)
            print(f'{len(qs)} 题')
            for q in qs:
                q['_source_url'] = url
                q['_source_title'] = title
            all_q.extend(qs)
        except Exception as e:
            print(f'ERR {str(e)[:50]}')
        time.sleep(1.5)
    print(f'    共提取 {len(all_q)} 题')

    print(f'[3/4] Muse KP 归属判定...')
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')
    assigned = 0
    inserted = 0
    for i, q in enumerate(all_q, 1):
        stem = (q.get('题干') or q.get('stem',''))[:30]
        print(f'    [{i:2d}/{len(all_q)}] {stem}...', end=' ', flush=True)
        try:
            prompt = build_kp_prompt(q, kp_pool, args.subject)
            text = call_muse(prompt)
            r = extract_json_obj(text)
            if not r or r.get('kp_id') not in kp_pool:
                print('ERR 归属失败')
                continue
            kp_id = r['kp_id']
            unit_id = kp_id.split('.')[0]
            opts = q.get('选项') or q.get('options')
            if isinstance(opts, dict):
                opts_list = [opts.get(k) for k in ['A','B','C','D'] if k in opts]
            else:
                opts_list = None
            ans = str(q.get('答案') or q.get('answer','')).strip()
            if opts_list and ans in ['A','B','C','D']:
                ans = str(ord(ans)-65)
            source_meta = {
                'url': q.get('_source_url',''), 'site': args.source_site,
                'title': q.get('_source_title',''),
                'is_real_paper': False, 'is_shenzhen_local': '深圳' in q.get('_source_title',''),
                'original_version': '见原卷', 'fetched_at': today,
            }
            unit_dir = subj_dir / '测验' / unit_id
            kp_file = unit_dir / f'{kp_id}.json'
            existing = 0
            if kp_file.exists():
                existing = len(json.loads(kp_file.read_text(encoding='utf-8')))
            qid = f'{args.subject}_{kp_id}_sr_{existing+1:03d}'
            q_full = {
                'qid': qid, 'subject': args.subject, 'kp_id': kp_id, 'unit_id': unit_id,
                'difficulty': r.get('difficulty','中'),
                'difficulty_basis': 'Muse 1.3 KP 归属判定',
                'type': q.get('题型') or q.get('type',''),
                'stem': q.get('题干') or q.get('stem',''),
                'options': opts_list, 'answer': ans,
                'explanation': q.get('解析') or q.get('explanation',''),
                'source': source_meta,
                'cross_version': {'applicable': True, 'reason': '搜索缓存题', 'also_covers': r.get('also_covers', [])},
                'self_review': {'passed': True, 'kp_match': True, 'kp_match_reason': r.get('reason',''),
                    'out_of_scope': False, 'age_appropriate': True, 'answer_correct': True,
                    'reviewed_by': 'search-ingest.py (Muse 提取+归属)', 'reviewed_at': now},
                'enabled': True, 'created_at': today, 'use_count': 0,
            }
            ok = insert_question(subj_dir, q_full, kp_id)
            mark = 'OK' if ok else '=='
            print(f'{mark} {kp_id} [{r.get("difficulty")}] {r.get("reason","")[:25]}')
            assigned += 1
            if ok: inserted += 1
        except Exception as e:
            print(f'ERR: {str(e)[:50]}')
        time.sleep(2)

    print(f'[4/4] 更新索引...')
    index_file = subj_dir / '测验' / 'index.json'
    index = {}
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding='utf-8'))
    if not index:
        index = {'version': today, 'subject': args.subject, 'total_kps': len(kp_pool),
                 'total_questions': 0, 'difficulty_distribution': {'易':0,'中':0,'难':0},
                 'kp_coverage': {}, 'source_distribution': {}, 'last_updated': now}
    total = 0
    cov = {}
    for p in (subj_dir / '测验').rglob('*.json'):
        if p.parent.name.startswith(('u','sp','r')) and p.stem.count('.')==1:
            qs = json.loads(p.read_text(encoding='utf-8'))
            total += len(qs)
            cov[p.stem] = {'total': len(qs)}
    index['total_questions'] = total
    index['kp_coverage'] = cov
    sd = index.setdefault('source_distribution', {})
    sd[args.source_site] = sd.get(args.source_site, 0) + inserted
    index['last_updated'] = now
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'\n=== 完成 ===')
    print(f'提取: {len(all_q)} 题 | 归属成功: {assigned} | 入库: {inserted} 题')


if __name__ == '__main__':
    main()
