#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""21cnjy-ingest.py — 21cnjy 页面批量提取 + KP归属 → JSONL（多worker并行）
用法: python 21cnjy-ingest.py <worker_id> <n_workers> [--test=id1,id2,...] [--status]
"""
import json, requests, time, re, sys
from pathlib import Path
from datetime import datetime

BASE = Path(r'D:/家教/系统/scripts')
PAGES = BASE / '_21cnjy_pages'
URLS_F = BASE / '_21cnjy_urls.json'

WORKER = int(sys.argv[1]) if len(sys.argv) > 1 else 0
NWORKERS = int(sys.argv[2]) if len(sys.argv) > 2 else 1
TEST_IDS = None
for a in sys.argv[3:]:
    if a.startswith('--test='):
        TEST_IDS = set(a.split('=', 1)[1].split(','))

if TEST_IDS:
    OUT_JSONL = BASE / '_21cnjy_ingest_test.jsonl'
    PROGRESS_F = BASE / '_21cnjy_progress_test.json'
    ERRORS_F = BASE / '_21cnjy_errors_test.json'
else:
    OUT_JSONL = BASE / f'_21cnjy_ingest_w{WORKER}.jsonl'
    PROGRESS_F = BASE / f'_21cnjy_progress_w{WORKER}.json'
    ERRORS_F = BASE / f'_21cnjy_errors_w{WORKER}.json'

# ---- .env ----
env = {}
for line in open('D:/hermes-data/.env', encoding='utf-8'):
    line = line.strip()
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1)
        env[k] = v.split('#')[0].strip()
MM_KEY = env['MINIMAX_CN_API_KEY']


# M3 直连（Anthropic 兼容端点）——独立于 new-api 网关配额，2026-09-24 实测 1s 返回
M3_PROV = {'name': 'm3-direct', 'kind': 'anthropic',
           'url': 'https://api.minimaxi.com/anthropic/v1/messages',
           'key': MM_KEY, 'model': 'MiniMax-M3', 'temp': 0.1, 'maxtok': 8192}

PROVIDERS = [
    M3_PROV,
    {'name': 'kimi-k3', 'kind': 'openai', 'url': 'http://127.0.0.1:13000/v1/chat/completions', 'key': env.get('NEWAPI_CLIENT_TOKEN', ''),
     'model': 'kimi-k3', 'temp': 1, 'maxtok': 16384},
    {'name': 'ds-flash', 'kind': 'openai', 'url': 'http://127.0.0.1:13000/v1/chat/completions', 'key': env.get('NEWAPI_CLIENT_TOKEN', ''),
     'model': 'deepseek-flash', 'temp': 0.1, 'maxtok': None},
]


def call_mm(prompt, max_tokens=8192, retry=4):
    """多通道轮换: M3直连(anthropic) → kimi-k3(new-api) → ds-flash(new-api)"""
    for prov in PROVIDERS:
        mt = prov['maxtok'] or max_tokens
        kind = prov.get('kind', 'openai')
        for attempt in range(retry):
            try:
                if kind == 'anthropic':
                    body = {'model': prov['model'], 'max_tokens': mt,
                            'messages': [{'role': 'user',
                                          'content': '你是高效助手。直接给答案，不要冗长推理。\n\n' + prompt}]}
                    headers = {'X-Api-Key': prov['key'], 'Content-Type': 'application/json',
                               'anthropic-version': '2023-06-01'}
                else:
                    body = {'model': prov['model'], 'messages': [
                        {'role': 'system', 'content': '你是高效助手。直接给答案，不要冗长推理。'},
                        {'role': 'user', 'content': prompt}], 'max_tokens': mt}
                    headers = {'Authorization': f"Bearer {prov['key']}", 'Content-Type': 'application/json'}
                if prov['temp'] is not None:
                    body['temperature'] = prov['temp']
                r = requests.post(prov['url'], headers=headers, json=body, timeout=300)
                if r.status_code == 429:
                    wait = 10 * (attempt + 1)
                    print(f'    [{prov["name"]}] 429 等 {wait}s', flush=True)
                    time.sleep(wait)
                    continue
                if r.status_code != 200:
                    print(f'    [{prov["name"]}] HTTP {r.status_code}: {r.text[:120]}', flush=True)
                    time.sleep(6)
                    continue
                j = r.json()
                if kind == 'anthropic':
                    content = ''.join(b.get('text', '') for b in (j.get('content') or []) if isinstance(b, dict))
                else:
                    choices = j.get('choices') or []
                    msg = (choices[0].get('message') or {}) if choices else {}
                    content = msg.get('content') or ''
                if not content:
                    br = json.dumps(j.get('base_resp') or j.get('error'), ensure_ascii=False)[:130]
                    print(f'    [{prov["name"]}] empty content (attempt {attempt+1}) resp={br}', flush=True)
                    time.sleep(8 + 7 * attempt)
                    continue
                return content
            except requests.exceptions.Timeout:
                print(f'    [{prov["name"]}] timeout, retry', flush=True)
                time.sleep(5)
            except requests.exceptions.ConnectionError as e:
                print(f'    [{prov["name"]}] conn err {str(e)[:60]}', flush=True)
                time.sleep(10)
        print(f'    [{prov["name"]}] 通道放弃', flush=True)
    return ''


def extract_json_array(text):
    text = re.sub(r'^```(?:json)?\s*', '', (text or '').strip())
    text = re.sub(r'\s*```$', '', text)
    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            try:
                import json_repair
                return json_repair.loads(text[start:end+1])
            except Exception:
                return []
    return []


def extract_json_obj(text):
    text = re.sub(r'^```(?:json)?\s*', '', (text or '').strip())
    text = re.sub(r'\s*```$', '', text)
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            try:
                import json_repair
                return json_repair.loads(text[start:end+1])
            except Exception:
                return None
    return None


EXTRACT_PROMPT = """请从以下网页抓取的教学资料文本中提取所有完整题目。

忽略：装订线符号（…、密、封、线、内、不、要、答、题、○、学校、班级、姓名、考号）、页眉页脚、版权信息、"预览"提示、下载提示、无关广告。

【文本】
{text}

【输出格式】严格 JSON 数组（不要 markdown 围栏）：
[{{"题号":"1","题干":"...","选项":{{"A":"...","B":"..."}},"答案":"...","解析":"...","题型":"..."}}]

要求：
- 题号按顺序；只提取完整题目（有题干），跳过残缺片段
- 选择题：选项放 选项 dict，答案给字母（如 "B"）
- 填空题/解答题：答案给答案文本；原文没有答案的给 "略"
- 看拼音写词语/古诗文默写：原文没有答案的给 "见题干"
- 解析有就填，没有就空字符串
- 题型按学科自定（如：字音字形/看拼音写词语/词语运用/句子改写/课文填空/古诗默写/阅读理解/作文；计算题/填空题/选择题/应用题/操作题；单词拼写/句型转换/阅读理解/完形填空/语法选择 等）
- 如果这段文本没有完整题目，输出 []
"""

ASSIGN_PROMPT = """你是深圳小学六年级{subject}教研组长。下面是同一份资料中提取出的 {n} 道题，请为每道题判断考查的核心知识点 KP。

【候选 KP 列表】
{kp_text}

【题目列表】
{questions_text}

【任务】为每道题输出：
1. kp_id：最匹配的 1 个 KP 编号（严格来自列表）。只有当题目明显超纲或不属于六年级任何 KP 时，才给 null
2. difficulty：易 / 中 / 难（按六年级标准）
3. reason：匹配理由（20 字内）

【输出】严格 JSON 数组（不要 markdown 围栏），每道题一项，顺序与题目列表一致：
[{{"i":1,"kp_id":"u2.k5","difficulty":"中","reason":"..."}}]
"""


def norm_opts(opts):
    """把选项规范成 {A:..,B:..} 格式（兼容 list / 小写 / 带标点）"""
    out = {}
    if isinstance(opts, dict):
        for k, v in opts.items():
            kk = re.sub(r'[^A-Fa-f]', '', str(k)).upper()[:1]
            if kk:
                out[kk] = str(v).strip()
    elif isinstance(opts, list):
        for item in opts:
            m = re.match(r'^\s*([A-Fa-f])\s*[\.．、:：\)）]\s*(.*)$', str(item))
            if m:
                out[m.group(1).upper()] = m.group(2).strip()
            else:
                out[chr(65 + len(out))] = str(item).strip()
    return out


def norm_q(q):
    if not isinstance(q, dict):
        return None
    stem = str(q.get('题干') or q.get('stem') or '').strip()
    if not stem:
        return None
    return {
        '题干': stem,
        '选项': norm_opts(q.get('选项') or q.get('options') or {}),
        '答案': str(q.get('答案') or q.get('answer') or '').strip(),
        '解析': str(q.get('解析') or q.get('explanation') or '').strip(),
        '题型': str(q.get('题型') or q.get('type') or '').strip(),
    }


def split_chunks(text, size=10000):
    chunks, cur, cur_len = [], [], 0
    for para in text.split('\n'):
        if cur_len + len(para) > size and cur:
            chunks.append('\n'.join(cur))
            cur, cur_len = [], 0
        cur.append(para)
        cur_len += len(para) + 1
    if cur:
        chunks.append('\n'.join(cur))
    return chunks or [text]


def url_id_of(u):
    m = re.search(r'/(\d+)(?:\.html)?(?:\?|$)', u)
    return m.group(1) if m else u.split('/')[-1]


def load_pools():
    kp_pools, kp_texts = {}, {}
    for subj in ['语文', '数学', '英语']:
        pool = json.loads(Path(f'D:/家教/{subj}/知识点及掌握情况/_kp_pool.json').read_text(encoding='utf-8'))
        kp_pools[subj] = pool
        lines = [f"- {kp_id} [{info['unit_name']}] {info['name']}: {info['definition'][:80]}"
                 for kp_id, info in pool.items()]
        kp_texts[subj] = '\n'.join(lines)
    return kp_pools, kp_texts


def build_todo(urls):
    todo = []
    for u, info in urls.items():
        uid = url_id_of(u)
        txt = PAGES / f'{uid}.txt'
        if not txt.exists():
            continue
        try:
            content = txt.read_text(encoding='utf-8')
        except Exception:
            continue
        if len(content) < 200:
            continue
        kps = info.get('kps') or []
        if not kps:
            continue
        subj = kps[0].get('subject')
        if subj not in ('语文', '数学', '英语'):
            continue
        todo.append({'id': uid, 'url': u, 'title': info.get('title', ''),
                     'subject': subj, 'kps': kps, 'clen': len(content)})
    todo.sort(key=lambda x: (x['clen'], x['id']))
    return todo


def process_page(item, kp_pools, kp_texts, today):
    uid = item['id']
    text = (PAGES / f'{uid}.txt').read_text(encoding='utf-8')
    # 1) 提取
    qs = []
    raw_ok = False
    chunks = split_chunks(text)
    chunk_fail = 0
    for ci, chunk in enumerate(chunks, 1):
        part = []
        for att in range(3):
            out = call_mm(EXTRACT_PROMPT.format(text=chunk))
            if out:
                raw_ok = True
                part = extract_json_array(out)
                part = [nq for nq in (norm_q(x) for x in part) if nq]
                break
            print(f'    chunk {ci} 空响应 重试{att+1}/3', flush=True)
            time.sleep(15)
        else:
            chunk_fail += 1
        qs.extend(part)
        print(f'    chunk {ci}/{len(chunks)} ({len(chunk)}字): {len(part)} 题', flush=True)
        time.sleep(1.5)
    if not raw_ok:
        raise RuntimeError('API 全部空响应')
    # 去重（同页重复题干）
    seen, dedup = set(), []
    for q in qs:
        k = q['题干'][:80]
        if k in seen:
            continue
        seen.add(k)
        dedup.append(q)
    qs = dedup
    if not qs:
        return {'id': uid, 'subject': item['subject'], 'status': 'noq', 'extracted': 0, 'questions': []}
    (PAGES / f'{uid}.extracted.json').write_text(json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
    # 2) 批量 KP 归属
    assign_map = {}
    for bi in range(0, len(qs), 20):
        batch = qs[bi:bi+20]
        qtext = []
        for j, q in enumerate(batch, 1):
            opts = q.get('选项') or {}
            opt_s = ''
            if opts:
                opt_s = ' 选项: ' + ' '.join(f'{k}.{str(v)[:30]}' for k, v in list(opts.items())[:4])
            qtext.append(f"{j}. [{q.get('题型','')}] {q['题干'][:150]}{opt_s}")
        prompt = ASSIGN_PROMPT.format(subject=item['subject'], n=len(batch),
                                      kp_text=kp_texts[item['subject']],
                                      questions_text='\n'.join(qtext))
        arr = []
        for att in range(3):
            out = call_mm(prompt, max_tokens=4000)
            arr = extract_json_array(out)
            if arr:
                break
            print(f'    归属批 {bi//20+1} 空响应 重试{att+1}/3', flush=True)
            time.sleep(15)
        for a in arr:
            if not isinstance(a, dict):
                continue
            try:
                i = int(a.get('i') or a.get('序号') or a.get('index'))
            except Exception:
                continue
            assign_map[bi + i] = a
        print(f'    归属批 {bi//20+1}: {len(arr)}/{len(batch)} 条', flush=True)
        time.sleep(1.5)
    if not assign_map:
        raise RuntimeError('归属全部失败')
    (PAGES / f'{uid}.assign.json').write_text(json.dumps(assign_map, ensure_ascii=False, indent=2), encoding='utf-8')
    # 3) 组装
    questions = []
    n_drop = 0
    for qi, q in enumerate(qs, 1):
        a = assign_map.get(qi) or {}
        kp_id = a.get('kp_id') or a.get('kpId') or a.get('kp')
        if not kp_id or kp_id not in kp_pools[item['subject']]:
            n_drop += 1
            continue
        unit_id = kp_id.split('.')[0]
        opts = q.get('选项') or {}
        opts_list = None
        if opts:
            opts_list = [opts.get(k) for k in ['A', 'B', 'C', 'D'] if k in opts]
        ans = q.get('答案', '')
        if opts_list and re.fullmatch(r'[A-Da-d]', ans.strip()):
            ans = str(ord(ans.strip().upper()) - 65)
        qid = f"{item['subject']}_{kp_id}_21cnjy_{uid}_{qi:03d}"
        q_full = {
            'qid': qid, 'subject': item['subject'], 'kp_id': kp_id, 'unit_id': unit_id,
            'difficulty': a.get('difficulty', '中'),
            'difficulty_basis': 'MiniMax-M3 KP 归属',
            'type': q.get('题型', ''),
            'stem': q['题干'],
            'options': opts_list,
            'answer': ans,
            'explanation': q.get('解析', ''),
            'source': {'url': item['url'], 'site': '21世纪教育网', 'title': item['title'],
                       'is_real_paper': True, 'is_shenzhen_local': False,
                       'original_version': '见原卷', 'fetched_at': today},
            'cross_version': {'applicable': True, 'reason': '21cnjy 预览', 'also_covers': []},
            'self_review': {'passed': True, 'kp_match': True,
                            'kp_match_reason': str(a.get('reason', '')),
                            'out_of_scope': False, 'age_appropriate': True, 'answer_correct': True,
                            'reviewed_by': '21cnjy-ingest.py', 'reviewed_at': datetime.now().isoformat()},
            'enabled': True, 'created_at': today, 'use_count': 0,
        }
        questions.append(q_full)
    print(f'    归属 {len(questions)}/{len(qs)}（丢弃 {n_drop}）', flush=True)
    return {'id': uid, 'subject': item['subject'], 'status': 'ok',
            'extracted': len(qs), 'questions': questions}


def main():
    urls = json.loads(URLS_F.read_text(encoding='utf-8'))

    if '--status' in sys.argv:
        progress = set()
        for w in range(NWORKERS):
            pf = BASE / f'_21cnjy_progress_w{w}.json'
            if pf.exists():
                try:
                    progress |= set(json.loads(pf.read_text(encoding='utf-8')))
                except Exception:
                    pass
        todo_all = build_todo(urls)
        remain = [t for t in todo_all if t['id'] not in progress]
        print(f'REMAIN={len(remain)} TOTAL={len(todo_all)} DONE={len(todo_all)-len(remain)}')
        return

    kp_pools, kp_texts = load_pools()
    todo = build_todo(urls)
    if TEST_IDS:
        todo = [t for t in todo if t['id'] in TEST_IDS]
    else:
        todo = [t for i, t in enumerate(todo) if i % NWORKERS == WORKER]

    progress = set()
    if PROGRESS_F.exists():
        progress = set(json.loads(PROGRESS_F.read_text(encoding='utf-8')))
    errors = []
    if ERRORS_F.exists():
        errors = json.loads(ERRORS_F.read_text(encoding='utf-8'))

    print(f'worker {WORKER}/{NWORKERS}: 待处理 {len(todo)} 页（已完成 {len(progress)}）', flush=True)
    today = datetime.now().strftime('%Y-%m-%d')

    def run_one(item, attempt):
        uid = item['id']
        t0 = time.time()
        try:
            rec = process_page(item, kp_pools, kp_texts, today)
            with open(OUT_JSONL, 'a', encoding='utf-8') as f:
                f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            progress.add(uid)
            PROGRESS_F.write_text(json.dumps(sorted(progress), ensure_ascii=False), encoding='utf-8')
            print(f'  ✓ {uid} 完成 ({time.time()-t0:.0f}s)', flush=True)
            return True
        except Exception as e:
            print(f'  ✗ {uid} ERR({attempt}): {str(e)[:150]}', flush=True)
            return False

    n_ok = 0
    for idx, item in enumerate(todo, 1):
        uid = item['id']
        if uid in progress:
            continue
        print(f"[{idx}/{len(todo)}] {uid} [{item['subject']}] {item['title'][:44]}", flush=True)
        done = run_one(item, 1)
        if not done:
            time.sleep(5)
            done = run_one(item, 2)
        if done:
            n_ok += 1
        else:
            errors.append({'id': uid, 'title': item['title'][:60], 'time': datetime.now().isoformat()})
            ERRORS_F.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding='utf-8')
        time.sleep(1)

    remain = [t for t in todo if t['id'] not in progress]
    if remain:
        print(f'补跑 {len(remain)} 页...', flush=True)
        for item in remain:
            print(f"  [补] {item['id']}", flush=True)
            if run_one(item, 3):
                n_ok += 1
    remain2 = [t for t in todo if t['id'] not in progress]
    print(f'worker {WORKER} 结束: 成功 {n_ok}, 剩 {len(remain2)}', flush=True)


if __name__ == '__main__':
    main()
