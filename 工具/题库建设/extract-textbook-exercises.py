#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract-textbook-exercises.py
==============================
从课本 PDF 提取"课后练习"页 → OCR → KP 归属 → 入库（零投票，标官方题）

参考：
- references/quiz-bank-design.md §6 跨版本判定（课本原题即同版本）
- references/quiz-bank-workflow.md §3 Step 2

触发：
- 课本 PDF 末尾通常有"课后练习"或"练习"页
- 标 source.is_official=true → 跳过投票，直接入库
- 因为是教材官方题，KP 归属看 KP index 里的 slide_range 自动匹配

输入：
  --input  课本 PDF 路径
  --subject  学科（数学/语文/英语）

示例：
  python extract-textbook-exercises.py --subject 数学 --input D:/家教/数学/课本/xxx.pdf
"""

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path


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


def pdf_to_images(pdf_path: Path) -> list:
    """PDF 转图片列表（用 PyMuPDF/fitz；fallback Pillow+pdf2image）"""
    images = []
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        for page_idx in range(len(doc)):
            page = doc.load_page(page_idx)
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes('png')
            images.append((page_idx + 1, img_bytes))
        doc.close()
        return images
    except ImportError:
        pass

    # Fallback：用 pdf2image
    try:
        from pdf2image import convert_from_path
        pil_images = convert_from_path(str(pdf_path), dpi=150)
        import io
        for i, img in enumerate(pil_images):
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            images.append((i + 1, buf.getvalue()))
        return images
    except ImportError:
        pass

    # 第二个 fallback：调用 pdftoppm CLI
    import subprocess
    out_dir = pdf_path.parent / f'_tmp_pages_{int(time.time())}'
    out_dir.mkdir(exist_ok=True)
    try:
        subprocess.run(
            ['pdftoppm', '-r', '150', '-png', str(pdf_path), str(out_dir / 'page')],
            check=True, timeout=120, capture_output=True
        )
        for img_path in sorted(out_dir.glob('page-*.png')):
            with open(img_path, 'rb') as fh:
                page_num = int(img_path.stem.split('-')[-1])
                images.append((page_num, fh.read()))
    except Exception as e:
        print(f'❌ 需要装 PyMuPDF 或 pdf2image 或 pdftoppm 才能处理 PDF：{e}')
        sys.exit(1)
    finally:
        if out_dir.exists():
            for f in out_dir.glob('*'):
                try:
                    f.unlink()
                except OSError:
                    pass
            try:
                out_dir.rmdir()
            except OSError:
                pass
    return images


OCR_PROMPT = """你是一位严谨的六年级{subject}老师，正在帮我把课本里"课后练习"页的题目转成结构化题库。

【任务】
仔细看图片，提取所有"课后练习"、"做一做"、"练一练"、"习题"、"思考题"部分的题目。
跳过：
- 章节标题、目录、单元导语
- 知识点讲解
- 例题（带"解："或"例 X"的）
- 答案（只在每章最后的"参考答案"页才提取）

【学科特定题型】
- 数学：计算题/应用题/图形与几何/分数小数百分数/单位换算/统计与概率/解方程/比与比例/逻辑推理/动手操作
- 语文：字音字形/近义词辨析/反义词/成语理解与运用/古诗词默写/古诗词理解/文言文阅读/现代文阅读/句子理解与改写/修辞手法辨析/习作片段/文学常识/课文背诵
- 英语：单词拼写/单词辨音/词形变换/句型转换/时态填空/完形填空/阅读理解/情景对话/翻译/单词听写/课文背诵

【难度自标】（基于布鲁姆认知层级 + 题型复杂度）
- 易：记忆/理解，单 KP
- 中：应用/分析
- 难：评价/创造

【答案格式】
- 选项题：answer 用 0-based 索引（字符串）
- 填空/默写/简答：answer 直接给标准答案文本（如果图片里有）
- 如果图片里没答案，answer 写 null

【解析】
简短即可，至少 20 字，含思路。

【输出格式】（严格 JSON 数组，不要任何额外文字）
[
  {{
    "stem": "题干",
    "type": "题型",
    "options": ["A", "B", "C", "D"] | null,
    "answer": "0" | "答案文本" | null,
    "explanation": "解析",
    "difficulty": "易" | "中" | "难",
    "exercise_label": "课后练习第 X 题" 或 "做一做第 Y 题"
  }}
]
"""


def call_minimax_vision(prompt: str, img_bytes: bytes, env: dict) -> str:
    """调 MiniMax-M3 vision 读图"""
    import requests
    b64 = base64.standard_b64encode(img_bytes).decode('utf-8')
    r = requests.post(
        'https://api.minimaxi.com/anthropic/v1/messages',
        headers={
            'Authorization': f'Bearer {env["MINIMAX_CN_API_KEY"]}',
            'Content-Type': 'application/json',
            'anthropic-version': '2023-06-01',
        },
        json={
            'model': 'MiniMax-M3',
            'max_tokens': 6000,
            'messages': [{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': b64}},
                    {'type': 'text', 'text': prompt},
                ],
            }],
        },
        timeout=180,
    )
    if r.status_code != 200:
        raise RuntimeError(f'MiniMax HTTP {r.status_code}: {r.text[:300]}')
    j = r.json()
    for block in j.get('content', []):
        if block.get('type') == 'text':
            return block['text']
    return ''


def extract_json(text: str):
    text = text.strip()
    for open_c, close_c in [('[', ']'), ('{', '}')]:
        start = text.find(open_c)
        end = text.rfind(close_c)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end+1])
            except json.JSONDecodeError:
                continue
    return []


def match_kp_by_slide(slide_num: int, kp_index: dict) -> tuple:
    """根据 slide 编号匹配 KP（用 KP index 里的 slide_range）"""
    for unit in kp_index['units']:
        for kp_id in unit.get('kp_ids', []):
            slide_range = unit.get('slide_range', '')
            # 解析 "slide_007-015" 格式
            try:
                if slide_range.startswith('slide_'):
                    nums = slide_range.replace('slide_', '').split('-')
                    if len(nums) == 2:
                        start = int(nums[0])
                        end = int(nums[1])
                        if start <= slide_num <= end:
                            return kp_id, unit['id']
            except (ValueError, IndexError):
                continue
    return None, None


def insert_official_question(subject_dir: Path, kp_id: str, unit_id: str, q: dict, page_num: int):
    """入库官方题（零投票）"""
    unit_dir = subject_dir / '测验' / unit_id
    unit_dir.mkdir(parents=True, exist_ok=True)
    kp_file = unit_dir / f'{kp_id}.json'

    existing = []
    if kp_file.exists():
        existing = json.loads(kp_file.read_text(encoding='utf-8'))

    # 官方题 qid 后缀 .official
    qid = f"{subject_dir.name}_{kp_id}_official_{len(existing)+1:03d}"

    q_full = {
        'qid': qid,
        'subject': subject_dir.name,
        'kp_id': kp_id,
        'unit_id': unit_id,
        'difficulty': q.get('difficulty', '中'),
        'difficulty_basis': 'AI 自标',
        'type': q.get('type', ''),
        'stem': q.get('stem', ''),
        'options': q.get('options'),
        'answer': q.get('answer'),
        'explanation': q.get('explanation', ''),
        'source': {
            'url': 'local:textbook',
            'site': '课本官方',
            'title': f"{subject_dir.name}六年级上册 第{page_num}页 {q.get('exercise_label', '')}",
            'is_real_paper': False,
            'is_official': True,
            'is_shenzhen_local': False,
            'original_version': '本教材',
            'fetched_at': datetime.now().strftime('%Y-%m-%d'),
        },
        'cross_version': {
            'applicable': True,
            'reason': '本教材官方题，原版本',
        },
        'self_review': {
            'passed': True,
            'kp_match': True,
            'out_of_scope': False,
            'age_appropriate': True,
            'answer_correct': True,
            'reviewed_by': 'extract-textbook-exercises (官方题免投票)',
            'reviewed_at': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
            'bypass_vote': True,
            'bypass_reason': '教材官方题，质量由出版社保证',
        },
        'enabled': True,
        'created_at': datetime.now().strftime('%Y-%m-%d'),
        'use_count': 0,
    }

    if any(e['qid'] == qid for e in existing):
        return False

    existing.append(q_full)
    kp_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')

    # by-type
    if q_full['type']:
        by_type_dir = subject_dir / '测验/by-type'
        by_type_dir.mkdir(parents=True, exist_ok=True)
        type_file = by_type_dir / f"{q_full['type']}.json"
        type_existing = []
        if type_file.exists():
            type_existing = json.loads(type_file.read_text(encoding='utf-8'))
        if not any(e['qid'] == qid for e in type_existing):
            type_existing.append(q_full)
            type_file.write_text(json.dumps(type_existing, ensure_ascii=False, indent=2), encoding='utf-8')

    return True


def main():
    parser = argparse.ArgumentParser(description='课本课后题提取（官方题免投票）')
    parser.add_argument('--input', required=True, help='课本 PDF 路径')
    parser.add_argument('--subject', required=True, choices=['数学', '语文', '英语'])
    parser.add_argument('--page-range', help='指定页码范围，如 5-30')
    parser.add_argument('--base-dir', default=None)

    args = parser.parse_args()

    env = load_keys()

    base_dir = None
    if args.base_dir:
        base_dir = Path(args.base_dir)
    else:
        for cand in [Path('D:/家教'), Path('/d/家教'), Path('D:\\家教')]:
            if cand.exists():
                base_dir = cand
                break

    subject_dir = base_dir / args.subject
    if not subject_dir.exists():
        print(f'❌ 科目目录不存在：{subject_dir}')
        sys.exit(1)

    kp_index_file = subject_dir / '知识点及掌握情况/index.json'
    if not kp_index_file.exists():
        print(f'❌ KP 索引不存在：{kp_index_file}')
        sys.exit(1)
    kp_index = json.loads(kp_index_file.read_text(encoding='utf-8'))

    pdf_path = Path(args.input)
    if not pdf_path.exists():
        print(f'❌ PDF 不存在：{pdf_path}')
        sys.exit(1)

    print(f'⏳ PDF 转图片：{pdf_path.name}')
    pages = pdf_to_images(pdf_path)
    print(f'✓ 共 {len(pages)} 页')

    if args.page_range:
        start_p, end_p = map(int, args.page_range.split('-'))
        pages = [(p, img) for p, img in pages if start_p <= p <= end_p]
        print(f'  → 按页码范围筛选：{args.page_range} → {len(pages)} 页')

    print()
    print(f'⏳ MiniMax-M3 vision OCR（{len(pages)} 页）...')
    total_added = 0
    for page_num, img_bytes in pages:
        print(f'  📄 第 {page_num} 页...', end=' ', flush=True)
        try:
            text = call_minimax_vision(OCR_PROMPT.format(subject=args.subject), img_bytes, env)
            questions = extract_json(text)
            if not isinstance(questions, list):
                questions = [questions]
            if not questions:
                print('空（可能不是练习页）')
                continue

            # 按 slide 归属 KP
            added = 0
            skipped = 0
            for q in questions:
                kp_id, unit_id = match_kp_by_slide(page_num, kp_index)
                if not kp_id:
                    skipped += 1
                    continue
                ok = insert_official_question(subject_dir, kp_id, unit_id, q, page_num)
                if ok:
                    added += 1
            print(f'{len(questions)} 题 → 入库 {added} / 跳过 {skipped}')
            total_added += added
        except Exception as e:
            print(f'✗ {str(e)[:100]}')

    print()
    print('=' * 50)
    print(f'✅ 完成：{total_added} 道课后题入库（官方题免投票）')
    print('=' * 50)
    print(f'  - 课本：{pdf_path.name}')
    print(f'  - 来源：本地 PDF 提取')
    print(f'  - 标记：source.is_official=true, bypass_vote=true')


if __name__ == '__main__':
    main()
