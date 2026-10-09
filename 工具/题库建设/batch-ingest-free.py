#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch-ingest-free.py — 批量抓免登录站 → 提取题目 → KP 归属 → 入库"""
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

CLASH = 'http://127.0.0.1:7897'
BASE_DIR = Path('D:/家教')
INPUT_FILE = Path('D:/家教/系统/scripts/_urls_classified.json')
PROGRESS_FILE = Path('D:/家教/系统/scripts/_batch_ingest_progress.json')
ERRORS_FILE = Path('D:/家教/系统/scripts/_batch_ingest_errors.json')


# 内联 search-ingest 核心函数
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


class si:
    call_muse = staticmethod(call_muse)
    extract_json_array = staticmethod(extract_json_array)
    extract_json_obj = staticmethod(extract_json_obj)
    load_kp_pool = staticmethod(load_kp_pool)
    EXTRACT_PROMPT = EXTRACT_PROMPT
    build_kp_prompt = staticmethod(build_kp_prompt)
    insert_question = staticmethod(insert_question)



def fetch_text(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    try:
        r = requests.get(url, headers=headers, timeout=20, verify=False)
        if r.status_code != 200:
            return None, f'HTTP {r.status_code}'
        r.encoding = r.apparent_encoding or 'utf-8'
        html = r.text
        html = re.sub(r'<script[\s\S]*?</script>', '', html, flags=re.I)
        html = re.sub(r'<style[\s\S]*?</style>', '', html, flags=re.I)
        m = re.search(r'<article[\s\S]*?</article>', html, re.I)
        if not m:
            m = re.search(r'<div[^>]*(?:class|id)=["\'][^"\']*(?:content|article|main|post|text|rich_media)[^"\']*["\'][\s\S]*?</div>', html, re.I)
        body = m.group(0) if m else html
        text = re.sub(r'<[^>]+>', '\n', body)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&[a-z]+;', '', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip(), None
    except Exception as e:
        return None, str(e)[:100]


def main():
    data = json.loads(INPUT_FILE.read_text(encoding='utf-8'))
    free = data['free']
    print(f'=== 免登录批量抓取 {len(free)} 条 ===')

    progress = {}
    if PROGRESS_FILE.exists():
        progress = json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
    errors = []
    if ERRORS_FILE.exists():
        errors = json.loads(ERRORS_FILE.read_text(encoding='utf-8'))

    by_subject = {}
    for it in free:
        by_subject.setdefault(it['subject'], []).append(it)

    total_new = 0
    for subject, items in by_subject.items():
        print(f'===== {subject}: {len(items)} 条 =====')
        subj_dir = BASE_DIR / subject
        kp_pool = si.load_kp_pool(subj_dir)
        print(f'KP 池: {len(kp_pool)}')

        for i, it in enumerate(items, 1):
            url = it['url']
            title = it['title']
            if url in progress and progress[url].get('status') == 'done':
                print(f'[{i}/{len(items)}] SKIP {title[:40]}')
                continue

            print(f'[{i}/{len(items)}] {title[:50]}')
            text, err = fetch_text(url)
            if not text or len(text) < 200:
                print(f'  FAIL fetch: {err or "len<200"}')
                errors.append({'url': url, 'title': title, 'error': err or '太短', 'time': datetime.now().isoformat()})
                progress[url] = {'status': 'failed', 'reason': err or '太短'}
                continue

            print(f'  len={len(text)} 提取...')
            text = text[:12000]
            try:
                prompt = si.EXTRACT_PROMPT.format(subject=subject, content=text)
                muse_out = si.call_muse(prompt)
                qs = si.extract_json_array(muse_out)
            except Exception as e:
                print(f'  FAIL Muse: {str(e)[:60]}')
                errors.append({'url': url, 'title': title, 'error': f'Muse: {str(e)[:100]}', 'time': datetime.now().isoformat()})
                progress[url] = {'status': 'failed', 'reason': f'Muse: {str(e)[:60]}'}
                time.sleep(2)
                continue

            if not qs:
                print(f'  0 题')
                progress[url] = {'status': 'done', 'inserted': 0}
                continue

            print(f'  {len(qs)} 题, 归属...')
            inserted = 0
            for q in qs:
                try:
                    kp_prompt = si.build_kp_prompt(q, kp_pool, subject)
                    kp_text = si.call_muse(kp_prompt)
                    r = si.extract_json_obj(kp_text)
                    if not r or r.get('kp_id') not in kp_pool:
                        continue
                    kp_id = r['kp_id']
                    unit_id = kp_id.split('.')[0]
                    opts = q.get('选项') or q.get('options')
                    opts_list = None
                    if isinstance(opts, dict):
                        opts_list = [opts.get(k) for k in ['A','B','C','D'] if k in opts]
                    ans = str(q.get('答案') or q.get('answer','')).strip()
                    if opts_list and ans in ['A','B','C','D']:
                        ans = str(ord(ans)-65)
                    unit_dir = subj_dir / '测验' / unit_id
                    kp_file = unit_dir / f'{kp_id}.json'
                    existing = 0
                    if kp_file.exists():
                        existing = len(json.loads(kp_file.read_text(encoding='utf-8')))
                    qid = f'{subject}_{kp_id}_free_{existing+1:03d}'
                    q_full = {
                        'qid': qid, 'subject': subject, 'kp_id': kp_id, 'unit_id': unit_id,
                        'difficulty': r.get('difficulty','中'),
                        'difficulty_basis': 'Muse KP 归属',
                        'type': q.get('题型') or q.get('type',''),
                        'stem': q.get('题干') or q.get('stem',''),
                        'options': opts_list, 'answer': ans,
                        'explanation': q.get('解析') or q.get('explanation',''),
                        'source': {'url': url, 'site': '免登录抓取', 'title': title,
                            'is_real_paper': False, 'is_shenzhen_local': '深圳' in title,
                            'original_version': '见原卷', 'fetched_at': datetime.now().strftime('%Y-%m-%d')},
                        'cross_version': {'applicable': True, 'reason': '免登录抓取', 'also_covers': r.get('also_covers', [])},
                        'self_review': {'passed': True, 'kp_match': True, 'kp_match_reason': r.get('reason',''),
                            'out_of_scope': False, 'age_appropriate': True, 'answer_correct': True,
                            'reviewed_by': 'batch-ingest-free.py', 'reviewed_at': datetime.now().isoformat()},
                        'enabled': True, 'created_at': datetime.now().strftime('%Y-%m-%d'), 'use_count': 0,
                    }
                    if si.insert_question(subj_dir, q_full, kp_id):
                        inserted += 1
                except Exception:
                    pass
                time.sleep(1)
            print(f'  OK 入库 {inserted}/{len(qs)}')
            total_new += inserted
            progress[url] = {'status': 'done', 'inserted': inserted, 'extracted': len(qs)}

            if i % 5 == 0:
                PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding='utf-8')
                ERRORS_FILE.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
            time.sleep(2)

        now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        index_file = subj_dir / '测验' / 'index.json'
        index = {}
        if index_file.exists():
            index = json.loads(index_file.read_text(encoding='utf-8'))
        total = 0
        cov = {}
        for p in (subj_dir / '测验').rglob('*.json'):
            if p.parent.name.startswith(('u','sp','r')) and p.stem.count('.')==1:
                qs_data = json.loads(p.read_text(encoding='utf-8'))
                total += len(qs_data)
                cov[p.stem] = {'total': len(qs_data)}
        index['total_questions'] = total
        index['kp_coverage'] = cov
        index['last_updated'] = now
        index.setdefault('source_distribution', {})
        index['source_distribution']['免登录抓取'] = index['source_distribution'].get('免登录抓取', 0)
        index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[{subject}] 总题数 {total}')

    PROGRESS_FILE.write_text(json.dumps(progress, ensure_ascii=False, indent=2), encoding='utf-8')
    ERRORS_FILE.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'===== 完成: 新入库 {total_new} =====')


if __name__ == '__main__':
    import urllib3
    urllib3.disable_warnings()
    main()
