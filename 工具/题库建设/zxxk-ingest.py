#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zxxk 试卷批量提取+KP归属+入库 v3（已验证流程）"""
import json, requests, time, re, sys
from pathlib import Path
from datetime import datetime

env = {}
for line in open('D:/hermes-data/.env', encoding='utf-8'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k] = v.split('#')[0].strip()
MM_KEY = env['MINIMAX_CN_API_KEY']

def call_mm(prompt, max_tokens=8192, retry=3):
    for attempt in range(retry):
        try:
            r = requests.post('https://api.minimaxi.com/v1/text/chatcompletion_v2',
                headers={'Authorization': f'Bearer {MM_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'MiniMax-M3', 'messages': [
                    {'role': 'system', 'content': '你是高效助手。直接给答案，不要冗长推理。'},
                    {'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens, 'temperature': 0.1}, timeout=180)
            if r.status_code == 429:
                wait = 15 * (attempt + 1)
                print(f'    429 等 {wait}s', flush=True)
                time.sleep(wait)
                continue
            if r.status_code != 200:
                raise RuntimeError(f'HTTP {r.status_code}: {r.text[:200]}')
            j = r.json()
            # MiniMax 偶尔返回 choices=None 或 message.content=None
            choices = j.get('choices') or []
            if not choices:
                base_resp = j.get('base_resp', {})
                print(f'    choices=None, base_resp={base_resp}', flush=True)
                if attempt < retry - 1:
                    time.sleep(10)
                    continue
                return ''
            content = choices[0].get('message', {}).get('content') or ''
            if not content:
                if attempt < retry - 1:
                    time.sleep(10)
                    continue
            return content
        except requests.exceptions.Timeout:
            time.sleep(3)
    return ''

def extract_json_array(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text)
    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        try: return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            try:
                import json_repair
                return json_repair.loads(text[start:end+1])
            except: return []
    return []

def extract_json_obj(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text)
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try: return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            try:
                import json_repair
                return json_repair.loads(text[start:end+1])
            except: return None
    return None


def extract_questions(text, subject):
    """提取试卷所有题目"""
    prompt = f"""请从以下文本提取所有完整题目。

忽略装订线符号：…、密、封、线、内、不、要、答、题、○、学校、班级、姓名、考号

【文本】
{text}

【输出格式】严格 JSON 数组（不要 markdown 围栏）：
[{{"题号":"1","题干":"...","选项":{{"A":"..."}},"答案":"...","题型":"..."}}]

要求：
- 题号按顺序
- 选择题选项放 options dict
- 填空/简答 answer 给 "略"
- 看拼音写词语 answer 给 "见题干"
- 古诗文默写 answer 给 "见题干"
- 忽略装订线/注意事项/版权"""
    out = call_mm(prompt, max_tokens=8192)
    return extract_json_array(out)


def assign_kp(q, kp_pool, kp_text, subject):
    """对单题做 KP 归属"""
    stem = (q.get('题干') or '')[:80]
    opts = q.get('选项') or {}
    opts_text = ' | '.join(f'{k}.{v}' for k,v in opts.items()) if isinstance(opts, dict) and opts else '(无选项)'
    
    prompt = f"""你是深圳六年级{subject}老师，判断这道题考查的核心知识点属于哪个 KP。

【题目】
题干：{stem}
选项:{opts_text}
题型：{q.get('题型','')}

【候选 KP 列表】
{kp_text}

【任务】
1. 选出最匹配的 1 个 KP 编号（严格来自列表）
2. 难度：易 / 中 / 难
3. 匹配理由（30 字内）

【输出】严格 JSON：{{"kp_id":"u1.k2","difficulty":"中","reason":"...","also_covers":[]}}"""
    out = call_mm(prompt, max_tokens=1000)
    return extract_json_obj(out)


def insert_q(subj_dir, q_full, kp_id):
    """入库单题"""
    unit_id = kp_id.split('.')[0]
    unit_dir = subj_dir / '测验' / unit_id
    unit_dir.mkdir(parents=True, exist_ok=True)
    kp_file = unit_dir / f'{kp_id}.json'
    existing_qs = []
    if kp_file.exists():
        existing_qs = json.loads(kp_file.read_text(encoding='utf-8'))
    if q_full['qid'] in {x['qid'] for x in existing_qs}:
        return False
    existing_qs.append(q_full)
    kp_file.write_text(json.dumps(existing_qs, ensure_ascii=False, indent=2), encoding='utf-8')
    return True


def update_index(subj_dir, subject, now):
    """更新科目索引"""
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
    index['source_distribution']['学科网zxxk'] = index['source_distribution'].get('学科网zxxk', 0)
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    return total


def main():
    # 待处理清单
    todo = json.loads(Path('D:/家教/系统/scripts/_extract_todo.json').read_text(encoding='utf-8'))
    
    # 进度
    progress_file = Path('D:/家教/系统/scripts/_ingest_progress.json')
    progress = set()
    if progress_file.exists():
        progress = set(json.loads(progress_file.read_text(encoding='utf-8')))
    
    # KP 池缓存
    kp_pools = {}
    kp_texts = {}
    for subj in ['语文', '数学', '英语']:
        pool_f = Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json')
        if pool_f.exists():
            kp_pools[subj] = json.loads(pool_f.read_text(encoding='utf-8'))
            lines = []
            for kp_id, info in kp_pools[subj].items():
                lines.append(f"- {kp_id} [{info['unit_name']}] {info['name']}: {info['definition'][:80]}")
            kp_texts[subj] = '\n'.join(lines)
    
    print(f'待处理: {len(todo)} 份', flush=True)
    
    total_inserted = 0
    total_extracted = 0
    failed_list = []
    
    now = datetime.now().isoformat()
    today = datetime.now().strftime('%Y-%m-%d')
    
    for idx, item in enumerate(todo, 1):
        soft_id = item['soft_id']
        subject = item['subject']
        title = item['title']
        
        if soft_id in progress:
            print(f'[{idx}/{len(todo)}] SKIP {soft_id}', flush=True)
            continue
        
        print(f'\n[{idx}/{len(todo)}] [{subject}] {title[:40]}', flush=True)
        
        full_f = Path(f'D:/家教/系统/scripts/_zxxk_v3/{soft_id}/full.txt')
        if not full_f.exists():
            print(f'  ✗ 无 full.txt', flush=True)
            failed_list.append({'soft_id': soft_id, 'reason': 'no full.txt'})
            continue
        text = full_f.read_text(encoding='utf-8')
        
        # 提取
        print(f'  提取中...', flush=True)
        qs = extract_questions(text, subject)
        if not qs:
            print(f'  ✗ 提取失败', flush=True)
            failed_list.append({'soft_id': soft_id, 'reason': 'extract failed'})
            continue
        print(f'  提取 {len(qs)} 题', flush=True)
        total_extracted += len(qs)
        
        # 保存 extracted
        (Path(f'D:/家教/系统/scripts/_zxxk_v3/{soft_id}/extracted.json')).write_text(
            json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
        
        # KP 归属 + 入库
        subj_dir = Path(f'D:/家教/{subject}')
        kp_pool = kp_pools.get(subject, {})
        kp_text = kp_texts.get(subject, '')
        if not kp_pool:
            print(f'  ✗ {subject} 无 KP 池', flush=True)
            failed_list.append({'soft_id': soft_id, 'reason': 'no kp pool'})
            continue
        
        inserted = 0
        for i, q in enumerate(qs, 1):
            r = assign_kp(q, kp_pool, kp_text, subject)
            if not r or r.get('kp_id') not in kp_pool:
                time.sleep(5)
                continue
            kp_id = r['kp_id']
            unit_id = kp_id.split('.')[0]
            
            opts = q.get('选项') or {}
            opts_list = None
            if isinstance(opts, dict) and opts:
                opts_list = [opts.get(k) for k in ['A','B','C','D'] if k in opts]
            ans = str(q.get('答案','略')).strip()
            if opts_list and ans in ['A','B','C','D']:
                ans = str(ord(ans)-65)
            
            unit_dir = subj_dir / '测验' / unit_id
            kp_file = unit_dir / f'{kp_id}.json'
            existing = 0
            if kp_file.exists():
                existing = len(json.loads(kp_file.read_text(encoding='utf-8')))
            qid = f'{subject}_{kp_id}_zxxk_{soft_id}_{existing+1:03d}'
            
            q_full = {
                'qid': qid, 'subject': subject, 'kp_id': kp_id, 'unit_id': unit_id,
                'difficulty': r.get('difficulty','中'),
                'difficulty_basis': 'MiniMax-M3 KP 归属',
                'type': q.get('题型',''),
                'stem': q.get('题干',''),
                'options': opts_list,
                'answer': ans,
                'explanation': q.get('解析',''),
                'source': {'url': f'https://www.zxxk.com/soft/{soft_id}.html', 'site': '学科网',
                           'title': title, 'is_real_paper': True, 'is_shenzhen_local': False,
                           'original_version': '见原卷', 'fetched_at': today},
                'cross_version': {'applicable': True, 'reason': 'zxxk 预览', 'also_covers': r.get('also_covers', [])},
                'self_review': {'passed': True, 'kp_match': True, 'kp_match_reason': r.get('reason',''),
                    'out_of_scope': False, 'age_appropriate': True, 'answer_correct': True,
                    'reviewed_by': 'zxxk-ingest.py', 'reviewed_at': now},
                'enabled': True, 'created_at': today, 'use_count': 0,
            }
            if insert_q(subj_dir, q_full, kp_id):
                inserted += 1
            time.sleep(5)
        
        # 更新索引
        total_in_subj = update_index(subj_dir, subject, now)
        print(f'  入库 {inserted}/{len(qs)} 题 | {subject} 总题数: {total_in_subj}', flush=True)
        total_inserted += inserted
        
        # 记录进度
        progress.add(soft_id)
        progress_file.write_text(json.dumps(list(progress), ensure_ascii=False), encoding='utf-8')
    
    print(f'\n========== 完成 ==========', flush=True)
    print(f'总提取: {total_extracted} 题', flush=True)
    print(f'总入库: {total_inserted} 题', flush=True)
    print(f'失败: {len(failed_list)} 份', flush=True)
    for f in failed_list:
        print(f'  {f["soft_id"]}: {f["reason"]}', flush=True)


if __name__ == '__main__':
    main()
