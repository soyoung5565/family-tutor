#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract-real-exam.py
====================
真题图片/PDF → MiniMax-M3 vision OCR → 3 模型投票 → 入库

参考：
- references/quiz-bank-design.md §2 (题 schema)
- references/quiz-bank-workflow.md §3-§4 (搜索 + 自审 SOP)

流程：
  [1] MiniMax-M3 vision 读图（图片/PDF 转 base64）
  [2] 让 MiniMax 把图片里的题目按 schema 转成 JSON 数组
  [3] 对每道题调 vote-judge.py 走 3 模型投票
  [4] 通过的题入库到 测验/{unit}/{kp_id}.json
  [5] 更新 index.json + extraction-log.md

输入：
  --input  试卷图片或 PDF 路径（可多个，逗号分隔）
  --subject  学科（数学/语文/英语）
  --kp-mapping  题目→KP 的映射 JSON（可选；不指定则走 LLM 自动归属）
  --output-dir  题库目录（默认 D:/家教/{subject}/测验）

示例：
  python extract-real-exam.py --subject 数学 --input shenzhen_real_exam.pdf
  python extract-real-exam.py --subject 语文 --input page1.jpg,page2.jpg
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


VISION_PROMPT = """你是一位经验丰富的深圳六年级{subject}老师，正在帮我把试卷图片转成结构化题库。

【任务】
仔细看图片里的每一道题（包括题干、选项、答案、解析）。把所有题目按下面 JSON schema 转成数组。

【学科特定】
- 数学：标注题型（计算题/应用题/图形与几何/分数小数百分数/单位换算/统计与概率/解方程/比与比例/逻辑推理/动手操作）
- 语文：标注题型（字音字形/近义词辨析/反义词/成语理解与运用/古诗词默写/古诗词理解/文言文阅读/现代文阅读/句子理解与改写/修辞手法辨析/习作片段/文学常识/课文背诵）
- 英语：标注题型（单词拼写/单词辨音/词形变换/句型转换/时态填空/完形填空/阅读理解/情景对话/翻译/单词听写/课文背诵）

【难度自标】（基于布鲁姆认知层级 + 题型复杂度 + 信息密度）
- 易：记忆/理解，单 KP
- 中：应用/分析，2-3 KP 组合
- 难：评价/创造，4+ KP 跨单元

【答案格式】
- 选项题：answer 用 0-based 索引（字符串如 "0"，不要用 "A"）
- 填空/默写/简答：answer 直接给标准答案文本
- 多选题：answer 用数组 ["0", "2"]

【解析要求】
必须含思路（考点 + 关键步骤 + 易错点），不只给答案。

【输出格式】（严格 JSON 数组，不要任何额外文字）
[
  {{
    "stem": "题干文字（保留原文，包括公式、空格）",
    "type": "题型（从学科特定列表选）",
    "options": ["A", "B", "C", "D"] | null,
    "answer": "0" | "标准答案文本",
    "explanation": "含思路的解析，至少 30 字",
    "difficulty": "易" | "中" | "难",
    "kp_hint": "你判断这道题考的 KP 关键词（如：分数除法、圆的面积、be able to），用于后续自动归属"
  }}
]

如果图片里有非题目内容（如试卷标题、学生信息、分数框），跳过。

【输出示例】
[
  {{
    "stem": "「渚」的正确读音是？",
    "type": "字音字形",
    "options": ["zhǔ", "zhù", "zǔ", "zù"],
    "answer": "0",
    "explanation": "渚指水中小块陆地。读 zhǔ。常见误读 zhù。本题考的是对生字读音的掌握。",
    "difficulty": "易",
    "kp_hint": "生字读音"
  }}
]
"""


def load_keys():
    candidates = [
        r'D:\hermes-data\.env',
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
    raise FileNotFoundError('.env not found')


def file_to_base64(path: Path) -> tuple:
    """文件转 base64，返回 (media_type, base64_str)"""
    suffix = path.suffix.lower()
    if suffix in ('.jpg', '.jpeg'):
        media_type = 'image/jpeg'
    elif suffix == '.png':
        media_type = 'image/png'
    elif suffix == '.webp':
        media_type = 'image/webp'
    elif suffix == '.gif':
        media_type = 'image/gif'
    elif suffix == '.pdf':
        media_type = 'application/pdf'
    else:
        raise ValueError(f'不支持的文件格式：{suffix}')
    with open(path, 'rb') as f:
        data = f.read()
    return media_type, base64.standard_b64encode(data).decode('utf-8')


def call_minimax_vision(prompt: str, media_type: str, b64_data: str, env: dict) -> str:
    """调 MiniMax-M3 vision 读图（anthropic 协议）"""
    import requests
    key = env['MINIMAX_CN_API_KEY']
    r = requests.post(
        'https://api.minimaxi.com/anthropic/v1/messages',
        headers={
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
        },
        json={
            'model': 'MiniMax-M3',
            'max_tokens': 8000,
            'messages': [{
                'role': 'user',
                'content': [
                    {
                        'type': 'image',
                        'source': {
                            'type': 'base64',
                            'media_type': media_type,
                            'data': b64_data,
                        },
                    },
                    {'type': 'text', 'text': prompt},
                ],
            }],
        },
        timeout=180,  # vision 大图需要更久
    )
    if r.status_code != 200:
        raise RuntimeError(f'MiniMax vision HTTP {r.status_code}: {r.text[:300]}')
    j = r.json()
    # 提取 text 块
    for block in j.get('content', []):
        if block.get('type') == 'text':
            return block['text']
    return ''


def extract_json(text: str) -> list | dict:
    """从模型输出提取 JSON（容错）"""
    text = text.strip()
    # 找第一个 [ 或 { 和最后一个 ] 或 }
    for open_c, close_c in [('[', ']'), ('{', '}')]:
        start = text.find(open_c)
        end = text.rfind(close_c)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f'未找到有效 JSON：{text[:300]}')


def match_kp(kp_hint: str, kp_index: dict) -> str:
    """根据 kp_hint 关键词匹配最佳 KP"""
    if not kp_hint:
        return None
    hint_lower = kp_hint.lower()
    best = None
    best_score = 0
    for unit in kp_index['units']:
        for kp_id in unit.get('kp_ids', []):
            kp_file = Path(kp_index.get('kp_index_path', '')).parent / f'{kp_id}.json'
            # 简化：直接在 kp_id 名称上搜
            unit_name = unit.get('name', '').lower()
            if any(word in hint_lower for word in unit_name.split() if len(word) > 2):
                score = 1
            else:
                score = 0
            if score > best_score:
                best_score = score
                best = kp_id
    return best


def load_kp_index(subject_dir: Path) -> dict:
    return json.loads((subject_dir / '知识点及掌握情况/index.json').read_text(encoding='utf-8'))


def insert_question(subject_dir: Path, kp_id: str, unit_id: str, question: dict, source_meta: dict):
    """入库单道题（已通过投票）"""
    unit_dir = subject_dir / '测验' / unit_id
    unit_dir.mkdir(parents=True, exist_ok=True)
    kp_file = unit_dir / f'{kp_id}.json'

    existing = []
    if kp_file.exists():
        existing = json.loads(kp_file.read_text(encoding='utf-8'))

    qid_prefix = f"{subject_dir.name}_{kp_id}"
    qid = f"{qid_prefix}_{len(existing) + 1:03d}"
    # 若 LLM 生成过再加 .g 后缀（这里先全部按真题入库，不加 .g）
    if not source_meta.get('is_real_paper', True):
        qid += '.g'

    q = {
        'qid': qid,
        'subject': subject_dir.name,
        'kp_id': kp_id,
        'unit_id': unit_id,
        'difficulty': question.get('difficulty', '中'),
        'difficulty_basis': 'AI 自标',
        'type': question.get('type', ''),
        'stem': question.get('stem', ''),
        'options': question.get('options'),
        'answer': question.get('answer'),
        'explanation': question.get('explanation', ''),
        'source': source_meta,
        'cross_version': {
            'applicable': True,
            'reason': '已通过 3 模型投票 + KP 归属审核',
        },
        'self_review': {
            'passed': True,
            'kp_match': True,
            'out_of_scope': False,
            'age_appropriate': True,
            'answer_correct': True,
            'reviewed_by': 'vote-judge pipeline',
            'reviewed_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        },
        'enabled': True,
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'use_count': 0,
    }

    # 查重
    if any(e['qid'] == q['qid'] for e in existing):
        print(f'  ⚠ 重复 qid {q["qid"]}，跳过')
        return False

    existing.append(q)
    kp_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')

    # 更新 by-type
    if q['type']:
        by_type_dir = subject_dir / '测验/by-type'
        by_type_dir.mkdir(parents=True, exist_ok=True)
        type_file = by_type_dir / f'{q["type"]}.json'
        type_existing = []
        if type_file.exists():
            type_existing = json.loads(type_file.read_text(encoding='utf-8'))
        if not any(e['qid'] == q['qid'] for e in type_existing):
            type_existing.append(q)
            type_file.write_text(json.dumps(type_existing, ensure_ascii=False, indent=2), encoding='utf-8')

    return True


def update_index(subject_dir: Path, added_questions: list):
    """更新题库 index.json"""
    index_file = subject_dir / '测验/index.json'
    index = {}
    if index_file.exists():
        index = json.loads(index_file.read_text(encoding='utf-8'))

    if not index:
        index = {
            'version': datetime.now().strftime('%Y-%m-%d'),
            'subject': subject_dir.name,
            'total_kps': 0,
            'total_questions': 0,
            'difficulty_distribution': {'易': 0, '中': 0, '难': 0},
            'kp_coverage': {},
            'source_distribution': {},
            'last_updated': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        }

    for q in added_questions:
        kp_id = q['kp_id']
        if kp_id not in index['kp_coverage']:
            index['kp_coverage'][kp_id] = {'total': 0, '易': 0, '中': 0, '难': 0, 'enabled': 0}

        cov = index['kp_coverage'][kp_id]
        cov['total'] += 1
        cov['enabled'] += 1
        diff = q.get('difficulty', '中')
        if diff in cov:
            cov[diff] += 1
        if diff in index['difficulty_distribution']:
            index['difficulty_distribution'][diff] += 1

        site = q.get('source', {}).get('site', 'unknown')
        if site not in index['source_distribution']:
            index['source_distribution'][site] = 0
        index['source_distribution'][site] += 1

        index['total_questions'] = index.get('total_questions', 0) + 1

    index['last_updated'] = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    index_file.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description='真题入库：vision OCR + 3 模型投票')
    parser.add_argument('--input', required=True, help='试卷图片/PDF 路径，逗号分隔支持多张')
    parser.add_argument('--subject', required=True, choices=['数学', '语文', '英语'])
    parser.add_argument('--kp-mapping', help='题目→KP 手动映射 JSON（可选）')
    parser.add_argument('--output-dir', help='题库目录（默认 D:/家教/{subject}/测验）')
    parser.add_argument('--source-url', default='manual_upload', help='题目来源 URL（标 source.url）')
    parser.add_argument('--source-site', default='手动上传', help='来源网站名（标 source.site）')
    parser.add_argument('--source-title', default='', help='来源标题（如"深圳外国语 2023 期中"）')
    parser.add_argument('--is-shenzhen-local', action='store_true', help='是否深圳本地真题')
    parser.add_argument('--base-dir', default=None)

    args = parser.parse_args()

    env = load_keys()

    # 自动探测 base_dir
    base_dir = None
    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        for cand in [Path('D:/家教'), Path('/d/家教'), Path('D:\\家教')]:
            if cand.exists():
                base_dir = cand
                break
    if not base_dir:
        print('❌ 未找到家教根目录')
        sys.exit(1)

    subject_dir = base_dir / args.subject
    if not subject_dir.exists():
        print(f'❌ 科目目录不存在：{subject_dir}')
        sys.exit(1)

    # 输入文件列表
    input_files = [Path(p.strip()) for p in args.input.split(',')]
    for f in input_files:
        if not f.exists():
            print(f'❌ 输入文件不存在：{f}')
            sys.exit(1)

    # 加载 KP 索引
    kp_index = load_kp_index(subject_dir)
    print(f'✓ KP 索引加载：{kp_index["total_kps"]} KP / {len(kp_index["units"])} 单元')

    # Step 1: MiniMax vision 提取题目
    print()
    print(f'⏳ [Step 1] MiniMax-M3 vision 提取题目（{len(input_files)} 张图）...')
    all_questions = []
    for fp in input_files:
        print(f'  📷 处理：{fp.name} ({fp.stat().st_size // 1024} KB)')
        try:
            media_type, b64 = file_to_base64(fp)
            prompt = VISION_PROMPT.format(subject=args.subject)
            text = call_minimax_vision(prompt, media_type, b64, env)
            questions = extract_json(text)
            if not isinstance(questions, list):
                questions = [questions]
            print(f'     → 提取到 {len(questions)} 道题')
            for q in questions:
                q['_source_file'] = str(fp)
            all_questions.extend(questions)
        except Exception as e:
            print(f'  ✗ {fp.name} 失败：{e}')

    if not all_questions:
        print('❌ 未能提取任何题目')
        sys.exit(1)

    print(f'\n✓ 共提取 {len(all_questions)} 道题')

    # Step 2: KP 归属
    print()
    print(f'⏳ [Step 2] KP 归属...')
    for i, q in enumerate(all_questions, 1):
        hint = q.get('kp_hint', '')
        kp_id = match_kp(hint, kp_index)
        if kp_id:
            unit_id = kp_id.split('.')[0]
            q['kp_id'] = kp_id
            q['unit_id'] = unit_id
            print(f'  [{i}] {hint[:30]} → {kp_id}')
        else:
            q['kp_id'] = None
            q['unit_id'] = None
            print(f'  [{i}] {hint[:30]} → ⚠ 无匹配 KP')

    # 过滤有 KP 的
    questions_with_kp = [q for q in all_questions if q.get('kp_id')]
    print(f'\n✓ 有 KP 归属：{len(questions_with_kp)}/{len(all_questions)}')

    # Step 3: 3 模型投票（调 vote-judge.py）
    print()
    print(f'⏳ [Step 3] 3 模型投票（调 vote-judge.py，串行调用）...')

    # 构造 vote-judge 输入
    candidates_for_vote = []
    for q in questions_with_kp:
        candidates_for_vote.append({
            'qid': f"pending_{q.get('kp_id')}_{len(candidates_for_vote)+1:03d}",
            'kp_id': q['kp_id'],
            'stem': q.get('stem', ''),
            'options': q.get('options'),
            'answer': q.get('answer'),
            'explanation': q.get('explanation', ''),
        })

    vote_input = {'candidates': candidates_for_vote}
    vote_input_file = base_dir / '系统/scripts/_tmp_vote_input.json'
    vote_input_file.write_text(json.dumps(vote_input, ensure_ascii=False, indent=2), encoding='utf-8')
    vote_output_file = base_dir / '系统/scripts/_tmp_vote_output.json'

    cmd = [
        sys.executable,
        str(base_dir / '系统/scripts/vote-judge.py'),
        '--subject', args.subject,
        '--input', str(vote_input_file),
        '--output', str(vote_output_file),
        '--base-dir', str(base_dir),
    ]
    print(f'  执行：{" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)  # 30 分钟兜底
    print(result.stdout[-2000:])
    if result.returncode != 0:
        print(f'  ⚠ vote-judge exit {result.returncode}')
        print(f'  stderr: {result.stderr[-1000:]}')

    if not vote_output_file.exists():
        print('❌ vote-judge 未输出结果文件')
        sys.exit(1)

    vote_summary = json.loads(vote_output_file.read_text(encoding='utf-8'))
    passed_qids = set()
    for r in vote_summary.get('results', []):
        if r.get('consensus', {}).get('passed'):
            passed_qids.add(r['qid'])

    print(f'\n✓ 投票通过：{len(passed_qids)}/{len(candidates_for_vote)}')

    # Step 4: 入库
    print()
    print(f'⏳ [Step 4] 入库（仅通过投票的题）...')

    source_meta = {
        'url': args.source_url,
        'site': args.source_site,
        'title': args.source_title,
        'is_real_paper': True,
        'is_shenzhen_local': args.is_shenzhen_local,
        'original_version': '见原卷',
        'fetched_at': datetime.now().strftime('%Y-%m-%d'),
    }

    added = []
    for q in questions_with_kp:
        qid_key = f"pending_{q.get('kp_id')}_{len(added)+1:03d}"
        # 修正 qid_key 匹配方式（vote-judge 用的 qid 格式是 pending_{kp_id}_{idx:03d}）
        # 找 vote_summary 里对应的 qid
        matched_qid = None
        for cand in candidates_for_vote:
            if (cand['kp_id'] == q['kp_id']
                    and cand['stem'] == q.get('stem', '')):
                matched_qid = cand['qid']
                break

        if matched_qid not in passed_qids:
            print(f'  ✗ 跳过（未通过投票）：{q.get("stem", "")[:40]}...')
            continue

        ok = insert_question(subject_dir, q['kp_id'], q['unit_id'], q, source_meta)
        if ok:
            added.append(q)
            print(f'  ✓ 入库：{q["kp_id"]} | {q.get("stem", "")[:40]}...')

    # Step 5: 更新 index
    if added:
        # 构造 q 列表给 update_index
        from dataclasses import dataclass
        added_with_meta = []
        for q in added:
            q_meta = dict(q)
            q_meta['source'] = source_meta
            added_with_meta.append(q_meta)
        update_index(subject_dir, added_with_meta)

    # 写 extraction log
    log_file = subject_dir / '测验/_meta/extraction-log.md'
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f'\n## {datetime.now().strftime("%Y-%m-%d %H:%M")} {args.subject} 真题入库（extract-real-exam.py）\n')
        f.write(f'- 输入文件：{[f.name for f in input_files]}\n')
        f.write(f'- 来源：{args.source_site} | {args.source_title}\n')
        f.write(f'- 深圳本地：{args.is_shenzhen_local}\n')
        f.write(f'- Vision 提取：{len(all_questions)} 道\n')
        f.write(f'- 有 KP 归属：{len(questions_with_kp)}\n')
        f.write(f'- 投票通过：{len(added)}\n')
        f.write(f'- 来源 URL：{args.source_url}\n\n')

    print()
    print('=' * 50)
    print(f'✅ 完成：{len(added)} 道题入库')
    print('=' * 50)

    # 清理临时
    try:
        vote_input_file.unlink()
        vote_output_file.unlink()
    except:
        pass


if __name__ == '__main__':
    main()
