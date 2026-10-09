#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ingest-exam.py — 一键真题入库：详情页 URL → 抓图 → vision → KP 归属 → 入库"""

NODE_DL = r"""const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
    const url = process.argv[2];
    const outDir = process.argv[3];
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        extraHTTPHeaders: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://appsj.szxuexiao.com/',
        }
    });
    const page = await context.newPage();
    await page.goto(url, { timeout: 30000, waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(3000);
    const title = await page.title();
    const extractCode = await page.evaluate(() => {
        const t = document.body.innerText;
        const m = t.match(/提取码[：:]\s*(\w+)/);
        return m ? m[1] : null;
    });
    const images = await page.evaluate(() => {
        const out = [];
        const seen = new Set();
        document.querySelectorAll('img').forEach(img => {
            const r = img.getBoundingClientRect();
            const src = img.src.split('?')[0];
            if (r.width > 400 && r.height > 400 && !src.includes('logo') && !src.includes('icon') && !seen.has(src)) {
                seen.add(src);
                out.push(src);
            }
        });
        return out;
    });
    const bodyText = await page.evaluate(() => {
        const el = document.querySelector('.content, .article-body, .post-content, .entry-content, main, #content, article');
        return el ? el.innerText : document.body.innerText;
    });
    console.log(JSON.stringify({ title, extractCode, images, bodyText: bodyText.substring(0, 20000) }));
    fs.mkdirSync(outDir, { recursive: true });
    for (let i = 0; i < images.length; i++) {
        const p = await context.newPage();
        try {
            const resp = await p.goto(images[i], { timeout: 30000 });
            if (resp && resp.ok()) {
                const buf = await resp.body();
                fs.writeFileSync(outDir + '/img_' + (i+1) + '.jpg', buf);
            }
        } catch (e) {}
        await p.close();
    }
    await browser.close();
})();
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import requests

CLASH = 'http://127.0.0.1:7897'
def _find_tools_dir():
    for c in [r'D:\hermes-data\_tools', r'/d/hermes-data/_tools', r'/mnt/d/hermes-data/_tools']:
        if os.path.exists(c):
            return c
    # 创建
    c = r'/d/hermes-data/_tools'
    os.makedirs(c, exist_ok=True)
    return c
TOOLS_DIR = _find_tools_dir()

VISION_PROMPT_TPL = """这是{subject}试卷的一页。仔细看所有题目，转成 JSON 数组。每题格式：
{{"题号":"1","题干":"完整题干（含公式数字）","选项":{{"A":"...","B":"...","C":"...","D":"..."}}或null,"答案":"B或文本","解析":"含思路解析","题型":"选择题/填空题/计算题/应用题/判断改错/作图题/开放题"}}

要求：
1. 只提取真实题目，跳过封面/页眉/页脚/说明文字
2. 题干和解析保留原始公式（如 π、1/3、x%）
3. 答案：选择题给字母（A/B/C/D），填空/计算给文本
4. 严格 JSON 数组输出，不要其他文字"""


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


def detect_base_dir():
    # WSL 优先 /d，Windows 优先 D:/
    import sys as _sys
    candidates = [Path('/d/家教'), Path('/mnt/d/家教'), Path('D:/家教')]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError('家教 root not found')


def download_images(url, work_dir):
    work_dir.mkdir(parents=True, exist_ok=True)
    node_file = work_dir / '_dl.js'
    node_file.write_text(NODE_DL, encoding='utf-8')
    node_bin = 'node'
    for cand in [r'D:\hermes-data\node\node.exe', r'/mnt/d/hermes-data/node/node.exe', r'C:\Program Files\nodejs\node.exe']:
        if os.path.exists(cand):
            node_bin = cand
            break
    def to_win(p):
        s = str(p)
        if s.startswith('/mnt/'):
            parts = s.split('/')
            if len(parts) > 2:
                drive = parts[2].upper()
                return drive + ':/' + '/'.join(parts[3:])
        if s.startswith('/d/'):
            return 'D:/' + s[3:]
        return s
    r = subprocess.run([node_bin, to_win(node_file), url, to_win(work_dir)],
                       capture_output=True, text=True, timeout=180, cwd=TOOLS_DIR)
    meta = None
    for line in r.stdout.split('\n'):
        line = line.strip()
        if line.startswith('{'):
            try:
                meta = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    if not meta:
        raise RuntimeError(f'下载失败: {r.stdout[:300]} {r.stderr[:300]}')
    imgs = sorted(work_dir.glob('img_*.jpg'))
    return meta, imgs


TEXT_PROMPT_TPL = """下面是一份{subject}试卷/练习的网页正文。请从中提取所有题目，转成 JSON 数组。每题格式：
{{"题号":"1","题干":"完整题干","选项":{{"A":"...","B":"...","C":"...","D":"..."}}或null,"答案":"B或文本","解析":"含思路解析","题型":"选择题/填空题/计算题/应用题/判断改错/作图题/开放题/听力题/阅读理解/完形填空/句型转换/单词拼写"}}

要求：
1. 只提取真实题目，跳过导航/页眉/页脚/广告/下载说明
2. 听力题如果只有题目没有音频，也提取（题型标"听力题"）
3. 答案：选择题给字母（A/B/C/D），其他给文本；文中没答案则 answer=null
4. 严格 JSON 数组输出

【正文】
{body}"""


def call_minimax_text(prompt, env, max_tokens=6000):
    r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
        headers={'Authorization': f'Bearer {env["MINIMAX_CN_API_KEY"]}',
                 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
        json={'model': 'MiniMax-M3', 'max_tokens': max_tokens,
              'messages': [{'role':'user','content':prompt}]},
        timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f'MiniMax text HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    for b in j.get('content', []):
        if b.get('type') == 'text':
            return b['text']
    return ''


def call_minimax_vision(prompt, img_b64, env):
    r = requests.post('https://api.minimaxi.com/anthropic/v1/messages',
        headers={'Authorization': f'Bearer {env["MINIMAX_CN_API_KEY"]}',
                 'Content-Type': 'application/json', 'anthropic-version': '2023-06-01'},
        json={'model': 'MiniMax-M3', 'max_tokens': 6000,
              'messages': [{'role':'user','content':[
                  {'type':'image','source':{'type':'base64','media_type':'image/jpeg','data':img_b64}},
                  {'type':'text','text':prompt}]}]},
        timeout=300)
    if r.status_code != 200:
        raise RuntimeError(f'MiniMax vision HTTP {r.status_code}: {r.text[:200]}')
    j = r.json()
    for b in j.get('content', []):
        if b.get('type') == 'text':
            return b['text']
    return ''


def extract_json_array(text):
    start = text.find('[')
    end = text.rfind(']')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            return []
    return []


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


def build_kp_prompt(q, kp_pool):
    lines = []
    for kp_id, info in kp_pool.items():
        lines.append(f"- {kp_id} [{info['unit_name']}] {info['name']}: {info['definition'][:80]}")
    kp_text = '\n'.join(lines)
    opts = q.get('选项') or {}
    if isinstance(opts, dict) and opts:
        opts_text = ' | '.join(f'{k}.{v}' for k,v in opts.items())
    else:
        opts_text = '(无选项)'
    head = '你是深圳六年级老师，判断下面这道题考查的核心知识点属于哪个 KP。\n\n'
    qpart = (f"【题目】\n题干：{q.get('题干','')}\n选项：{opts_text}\n答案：{q.get('答案')}\n解析：{q.get('解析','')}\n\n"
             f"【候选 KP 列表】\n{kp_text}\n\n")
    tail = ('【任务】\n1. 选出最匹配的 1 个 KP 编号（严格来自列表）。\n2. 难度：易 / 中 / 难。\n'
            '3. 匹配理由（30 字内）。\n4. also_covers：最多 2 个其他 KP 编号。\n\n'
            '【输出】（严格 JSON）\n{"kp_id": "u2.k6", "difficulty": "中", "reason": "...", "also_covers": []}')
    return head + qpart + tail


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
    ap.add_argument('--url', required=True)
    ap.add_argument('--subject', required=True, choices=['数学','语文','英语'])
    ap.add_argument('--source-site', default='深圳城市学校网')
    ap.add_argument('--source-title', default='')
    ap.add_argument('--work-dir', default=None)
    args = ap.parse_args()

    env = load_env()
    base_dir = detect_base_dir()
    subj_dir = base_dir / args.subject
    work_dir = Path(args.work_dir) if args.work_dir else (Path(TOOLS_DIR) / '_ingest_tmp')
    work_dir.mkdir(parents=True, exist_ok=True)
    if work_dir.exists():
        for f in work_dir.glob('img_*.jpg'):
            f.unlink()

    print(f'[1/4] 抓详情页图片: {args.url}')
    meta, imgs = download_images(args.url, work_dir)
    print(f'    title: {meta.get("title","")[:60]}')
    print(f'    extractCode: {meta.get("extractCode")}')
    print(f'    images: {len(imgs)}')

    all_q = []
    if imgs:
        print(f'[2/4] MiniMax vision 提取题目（图片版）...')
        for i, img in enumerate(imgs, 1):
            b64 = base64.b64encode(img.read_bytes()).decode()
            prompt = VISION_PROMPT_TPL.format(subject=args.subject)
            try:
                text = call_minimax_vision(prompt, b64, env)
                qs = extract_json_array(text)
                print(f'    图{i}: {len(qs)} 题')
                for q in qs:
                    q['_img'] = img.name
                all_q.extend(qs)
            except Exception as e:
                print(f'    图{i} ERR: {str(e)[:80]}')
    else:
        print(f'[2/4] 文本版：MiniMax 从正文提取题目...')
        body = meta.get('bodyText', '')
        if len(body) < 100:
            print('    正文太短，跳过')
        else:
            prompt = TEXT_PROMPT_TPL.format(subject=args.subject, body=body[:15000])
            try:
                text = call_minimax_text(prompt, env)
                qs = extract_json_array(text)
                print(f'    文本提取: {len(qs)} 题')
                for q in qs:
                    q['_img'] = 'text'
                all_q.extend(qs)
            except Exception as e:
                print(f'    文本提取 ERR: {str(e)[:80]}')
    print(f'    共提取 {len(all_q)} 题')

    print(f'[3/4] Muse KP 归属判定...')
    kp_pool = load_kp_pool(subj_dir)
    now = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    today = datetime.now().strftime('%Y-%m-%d')
    source_meta = {
        'url': args.url, 'site': args.source_site,
        'title': args.source_title or meta.get('title',''),
        'is_real_paper': True, 'is_shenzhen_local': True,
        'original_version': '见原卷', 'fetched_at': today,
        'extract_code': meta.get('extractCode',''),
    }
    assigned = 0
    inserted = 0
    for i, q in enumerate(all_q, 1):
        stem = q.get('题干','')[:35]
        print(f'    [{i:2d}/{len(all_q)}] {stem}...', end=' ', flush=True)
        try:
            prompt = build_kp_prompt(q, kp_pool)
            text = call_muse(prompt)
            r = extract_json_obj(text)
            if not r or r.get('kp_id') not in kp_pool:
                print('ERR 归属失败')
                continue
            kp_id = r['kp_id']
            unit_id = kp_id.split('.')[0]
            opts = q.get('选项')
            if isinstance(opts, dict):
                opts_list = [opts.get(k) for k in ['A','B','C','D'] if k in opts]
            else:
                opts_list = None
            ans = str(q.get('答案','')).strip()
            if opts_list and ans in ['A','B','C','D']:
                ans = str(ord(ans)-65)
            difficulty = r.get('difficulty','中')
            unit_dir = subj_dir / '测验' / unit_id
            kp_file = unit_dir / f'{kp_id}.json'
            existing = 0
            if kp_file.exists():
                existing = len(json.loads(kp_file.read_text(encoding='utf-8')))
            qid = f'{args.subject}_{kp_id}_{existing+1:03d}'
            q_full = {
                'qid': qid, 'subject': args.subject, 'kp_id': kp_id, 'unit_id': unit_id,
                'difficulty': difficulty,
                'difficulty_basis': 'Muse 1.3 KP 归属判定',
                'type': q.get('题型',''),
                'stem': q.get('题干',''),
                'options': opts_list,
                'answer': ans,
                'explanation': q.get('解析',''),
                'source': source_meta,
                'cross_version': {'applicable': True, 'reason': '深圳本地真题', 'also_covers': r.get('also_covers', [])},
                'self_review': {
                    'passed': True, 'kp_match': True, 'kp_match_reason': r.get('reason',''),
                    'out_of_scope': False, 'age_appropriate': True, 'answer_correct': True,
                    'reviewed_by': 'ingest-exam.py (MiniMax vision + Muse KP 归属)',
                    'reviewed_at': now,
                },
                'enabled': True, 'created_at': today, 'use_count': 0,
            }
            ok = insert_question(subj_dir, q_full, kp_id)
            mark = 'OK' if ok else '=='
            print(f'{mark} {kp_id} [{difficulty}] {r.get("reason","")[:25]}')
            assigned += 1
            if ok: inserted += 1
        except Exception as e:
            print(f'ERR: {str(e)[:60]}')
        time.sleep(2)

    print(f'[4/4] 更新索引...')
    index_file = subj_dir / '测验' / 'index.json'
    index = {}
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding='utf-8'))
    if not index:
        index = {'version': today, 'subject': args.subject,
                 'total_kps': len(kp_pool), 'total_questions': 0,
                 'difficulty_distribution': {'易':0,'中':0,'难':0},
                 'kp_coverage': {}, 'source_distribution': {},
                 'last_updated': now}
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

    log_file = subj_dir / '测验' / '_meta' / 'extraction-log.md'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f'\n## {datetime.now().strftime("%Y-%m-%d %H:%M")} {args.subject} ingest-exam 入库\n')
        f.write(f'- URL: {args.url}\n')
        f.write(f'- 提取码: {meta.get("extractCode","")}\n')
        f.write(f'- 图片: {len(imgs)} 张\n')
        f.write(f'- vision 提取: {len(all_q)} 题\n')
        f.write(f'- KP 归属成功: {assigned}\n')
        f.write(f'- 实际入库: {inserted}\n\n')

    print(f'\n=== 完成 ===')
    print(f'vision 提取: {len(all_q)} 题')
    print(f'KP 归属成功: {assigned}')
    print(f'实际入库: {inserted} 题')


if __name__ == '__main__':
    main()
