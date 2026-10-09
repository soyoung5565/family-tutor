#!/usr/bin/env python3
"""
家庭教师 - 动态生成补强练习（正确版）
根据薄弱知识点，从课本中提取多个相关题目
每次生成的题都不同，但考点一致
答案随机分布，不会全是A
"""

import json
import os
import random
from datetime import datetime

# 课本知识点库（从课本中提取）
KNOWLEDGE_BASE = {
    "生字拼音": [
        {"char": "渚", "pinyin": "zhǔ", "options": ["zhǔ", "zhù", "zǔ", "zù"]},
        {"char": "暮", "pinyin": "mù", "options": ["mù", "mò", "mó", "mǔ"]},
        {"char": "旷", "pinyin": "kuàng", "options": ["kuàng", "kuāng", "guǎng", "guàng"]},
        {"char": "鹊", "pinyin": "què", "options": ["què", "qué", "qū", "qù"]},
        {"char": "蝉", "pinyin": "chán", "options": ["chán", "chǎn", "chàn", "chān"]},
        {"char": "稻", "pinyin": "dào", "options": ["dào", "dǎo", "dāo", "dáo"]},
        {"char": "泊", "pinyin": "bó", "options": ["bó", "bò", "bō", "bǒ"]},
        {"char": "轼", "pinyin": "shì", "options": ["shì", "shí", "shī", "shǐ"]},
    ],
    "字词解释": [
        {"word": "渚", "meaning": "水中间的小块陆地", "options": ["水中间的小块陆地", "河流的岸边", "大海中的岛屿", "湖泊的中心"]},
        {"word": "别枝", "meaning": "横斜的树枝", "options": ["横斜的树枝", "离开树枝", "另一根树枝", "独特的树枝"]},
        {"word": "茅店", "meaning": "用茅草盖的旅舍", "options": ["用茅草盖的旅舍", "用木头盖的房子", "用石头盖的城堡", "用竹子盖的凉亭"]},
        {"word": "社林", "meaning": "社庙丛林", "options": ["社庙丛林", "树林", "竹林", "果园"]},
        {"word": "见", "meaning": "同'现'，出现、显现", "options": ["同'现'，出现、显现", "看见", "遇见", "见面"]},
        {"word": "泊", "meaning": "停船靠岸", "options": ["停船靠岸", "漂浮", "划船", "游泳"]},
        {"word": "旷", "meaning": "空旷、广阔", "options": ["空旷、广阔", "黑暗", "明亮", "寒冷"]},
    ],
    "诗词对比": [
        {
            "angle": "情感",
            "question": "《宿建德江》和《西江月·夜行黄沙道中》都写了月夜的景色，但表达的情感却不同。请结合具体诗句，简要说明两首诗词在情感上的主要差异。",
            "answer": "《宿建德江》通过「野旷天低树，江清月近人」等景物描写，抒发了诗人羁旅在外、孤寂愁闷的情感。《西江月·夜行黄沙道中》通过描绘「稻花香里说丰年，听取蛙声一片」以及「路转溪桥忽见」的惊喜，表达了作者对田园生活的热爱、对丰收在望的喜悦以及轻松愉快的心情。",
            "keywords": ["羁旅", "孤寂", "愁闷", "田园", "喜悦", "丰收", "野旷", "稻花"]
        },
        {
            "angle": "意象",
            "question": "《宿建德江》和《西江月·夜行黄沙道中》都描写了自然景物，但使用的意象有何不同？请举例说明。",
            "answer": "《宿建德江》的意象较为静态、孤寂：烟渚、野旷、天低树、江清、月近人，营造出一种空旷、寂寥的氛围。《西江月·夜行黄沙道中》的意象较为动态、热闹：明月、惊鹊、清风、鸣蝉、稻花、蛙声，充满了生机和活力。",
            "keywords": ["意象", "静态", "动态", "孤寂", "热闹", "生机"]
        },
        {
            "angle": "写作手法",
            "question": "《宿建德江》和《西江月·夜行黄沙道中》在写作手法上有何异同？请简要分析。",
            "answer": "相同点：两首诗词都运用了借景抒情的手法，通过描写自然景物来表达情感。不同点：《宿建德江》主要运用静态描写，如「野旷天低树，江清月近人」，营造出一种空旷、寂寥的氛围，抒发了诗人的羁旅之愁。《西江月·夜行黄沙道中》则运用了动静结合的手法，如「明月别枝惊鹊，清风半夜鸣蝉」，既有动态的「惊鹊」「鸣蝉」，又有静态的「明月」「清风」，描绘出一幅充满生机的夏夜田园风光图。",
            "keywords": ["借景抒情", "静态描写", "动静结合", "羁旅之愁", "田园风光"]
        },
        {
            "angle": "时代背景",
            "question": "《宿建德江》和《西江月·夜行黄沙道中》的作者分别生活在哪个时代？他们的生活经历如何影响了作品的风格？",
            "answer": "《宿建德江》的作者孟浩然是唐代诗人，他一生未曾入仕，长期隐居山林，但内心仍有入世的渴望。这种矛盾心理在他的诗中有所体现，如「移舟泊烟渚，日暮客愁新」就流露出一种淡淡的羁旅之愁。《西江月·夜行黄沙道中》的作者辛弃疾是南宋词人，他一生致力于抗金复国，但屡遭排挤。这首词是他闲居江西上饶时所作，词中描绘的田园风光和丰收景象，表达了他对田园生活的热爱和对和平生活的向往。",
            "keywords": ["唐代", "南宋", "孟浩然", "辛弃疾", "隐居", "抗金", "田园生活"]
        },
    ]
}

def shuffle_options(item, correct_key):
    """随机打乱选项顺序，返回新的选项列表和正确答案索引"""
    options = item['options'].copy()
    correct_answer = item[correct_key]
    
    # 找到正确答案的原始位置
    correct_idx = options.index(correct_answer)
    
    # 创建 (选项, 是否正确) 的配对
    paired = list(enumerate(options))
    
    # 随机打乱
    random.shuffle(paired)
    
    # 提取打乱后的选项和正确答案的新位置
    new_options = [opt for _, opt in paired]
    new_correct_idx = next(i for i, (orig_idx, _) in enumerate(paired) if orig_idx == correct_idx)
    
    return new_options, new_correct_idx

def generate_remedial_quiz(weak_points, has_choice_errors, has_essay_errors):
    """根据薄弱知识点生成补强练习题"""
    questions = []
    
    # 根据薄弱知识点生成题目
    for point in weak_points:
        if '生字拼音' in point or '渚的读音' in point or '见的读音' in point:
            # 从生字拼音库中随机选择几个（不重复原题）
            available = [c for c in KNOWLEDGE_BASE['生字拼音'] if c['char'] not in ['渚', '见']]
            if available:
                selected = random.sample(available, min(3, len(available)))
                for item in selected:
                    # 随机打乱选项
                    new_options, new_correct_idx = shuffle_options(item, 'pinyin')
                    questions.append({
                        "type": "choice",
                        "topic": "生字拼音",
                        "text": f"「{item['char']}」的正确读音是？",
                        "options": new_options,
                        "answer": new_correct_idx,
                        "keywords": []
                    })
        
        if '字词解释' in point or '渚的意思' in point:
            # 从字词解释库中随机选择几个（不重复原题）
            available = [w for w in KNOWLEDGE_BASE['字词解释'] if w['word'] not in ['渚']]
            if available:
                selected = random.sample(available, min(2, len(available)))
                for item in selected:
                    # 随机打乱选项
                    new_options, new_correct_idx = shuffle_options(item, 'meaning')
                    questions.append({
                        "type": "choice",
                        "topic": "字词解释",
                        "text": f"「{item['word']}」的意思是？",
                        "options": new_options,
                        "answer": new_correct_idx,
                        "keywords": []
                    })
        
        if '诗词对比' in point:
            # 从诗词对比库中随机选择一个角度
            available = KNOWLEDGE_BASE['诗词对比']
            if available:
                item = random.choice(available)
                questions.append({
                    "type": "text",
                    "topic": "诗词对比",
                    "text": item['question'],
                    "answer": item['answer'],
                    "keywords": item['keywords']
                })
    
    # 如果没有匹配的题目，生成通用题目
    if not questions:
        if has_choice_errors:
            # 随机选择几个生字
            selected = random.sample(KNOWLEDGE_BASE['生字拼音'], 3)
            for item in selected:
                # 随机打乱选项
                new_options, new_correct_idx = shuffle_options(item, 'pinyin')
                questions.append({
                    "type": "choice",
                    "topic": "生字拼音",
                    "text": f"「{item['char']}」的正确读音是？",
                    "options": new_options,
                    "answer": new_correct_idx,
                    "keywords": []
                })
        
        if has_essay_errors:
            # 随机选择一个诗词对比角度
            item = random.choice(KNOWLEDGE_BASE['诗词对比'])
            questions.append({
                "type": "text",
                "topic": "诗词对比",
                "text": item['question'],
                "answer": item['answer'],
                "keywords": item['keywords']
            })
    
    return questions

def main():
    # 读取薄弱知识点分析结果
    weak_points_file = 'D:/projects/family-tutor/quiz-data/weak-points-analysis.json'
    if not os.path.exists(weak_points_file):
        print("❌ 没有找到薄弱知识点分析结果")
        print("请先运行 python analyze-weak-points.py")
        return
    
    with open(weak_points_file, 'r', encoding='utf-8') as f:
        weak_analysis = json.load(f)
    
    weak_points = weak_analysis.get('weak_points', [])
    has_choice_errors = weak_analysis.get('has_choice_errors', False)
    has_essay_errors = weak_analysis.get('has_essay_errors', False)
    
    print("=== 薄弱知识点 ===")
    for point in weak_points:
        print(f"  - {point}")
    print(f"需要选择题: {has_choice_errors}")
    print(f"需要简答题: {has_essay_errors}")
    print()
    
    # 生成补强练习
    print("正在生成补强练习题...")
    questions = generate_remedial_quiz(weak_points, has_choice_errors, has_essay_errors)
    
    # 构建补强练习数据
    remedial_quiz = {
        "title": f"查漏补缺练习 - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "questions": questions,
        "generated_from": "knowledge_base",
        "weak_points": weak_points,
        "generated_at": datetime.now().isoformat()
    }
    
    # 保存补强练习
    output_file = 'D:/projects/family-tutor/quiz-data/quiz-data-remedial.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(remedial_quiz, f, ensure_ascii=False, indent=2)
    
    balance_answer_distribution(remedial_quiz['questions'])
    inject_into_loader(remedial_quiz)
    
    print(f"\n✅ 补强练习已生成: {output_file}")
    print(f"题目数量: {len(questions)}")
    print(f"题型分布:")
    for q in questions:
        print(f"  - {q['type']}: {q.get('topic', '未知')} - {q['text'][:40]}...")
        if q['type'] == 'choice':
            print(f"    答案位置: {chr(65 + q['answer'])} ({q['options'][q['answer']]})")


def reshuffle_choice(q):
    """对单道已生成的选择题重新打乱选项，保持正确答案内容不变"""
    correct = q['options'][q['answer']]
    random.shuffle(q['options'])
    q['answer'] = q['options'].index(correct)


def balance_answer_distribution(questions):
    """用户硬性要求：选择题正确答案不能全落在同一位置（pitfall 64/75d）"""
    choice_qs = [q for q in questions if q['type'] == 'choice']
    if len(choice_qs) <= 1:
        return
    for _ in range(50):
        positions = {q['answer'] for q in choice_qs}
        if len(positions) > 1:
            return
        for q in choice_qs:
            reshuffle_choice(q)


def inject_into_loader(remedial_quiz):
    """把补强题注入 load-quiz-remedial.html，并同步薄弱点展示"""
    import re as _re
    html_path = 'D:/projects/family-tutor/load-quiz-remedial.html'
    html = open(html_path, encoding='utf-8').read()

    payload = _re.sub(r'</?script[^>]*>', '', json.dumps(
        {'title': remedial_quiz['title'], 'questions': remedial_quiz['questions']},
        ensure_ascii=False))
    html = _re.sub(
        r'<script type="application/json" id="embedded-quiz-data">.*?</script>',
        '<script type="application/json" id="embedded-quiz-data">' + payload.replace('\\', '\\\\') + '</script>',
        html, flags=_re.DOTALL)

    weak_items = ''.join(f'<li>{_re.sub(r"</?[ulil]+>", "", str(w))}</li>' for w in remedial_quiz.get('weak_points', [])) or '<li>（无）</li>'
    html = _re.sub(r'(<ul id="weak-list">).*?(</ul>)',
                   lambda m: m.group(1) + weak_items + m.group(2), html, flags=_re.DOTALL)

    n_choice = sum(1 for q in remedial_quiz['questions'] if q['type'] == 'choice')
    n_essay = len(remedial_quiz['questions']) - n_choice
    html = _re.sub(r'(<p id="quiz-count">).*?(</p>)',
                   lambda m: m.group(1) + f'{n_choice} 道选择题 + {n_essay} 道简答题（答案随机分布）' + m.group(2), html)

    open(html_path, 'w', encoding='utf-8').write(html)
    print(f'✅ 已注入 load-quiz-remedial.html（{len(remedial_quiz["questions"])} 题）')


if __name__ == '__main__':
    main()
