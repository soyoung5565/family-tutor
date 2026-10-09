#!/usr/bin/env python3
"""
家庭教师 - 分析薄弱知识点
从测验结果中提取薄弱知识点（不是错题）
输出：知识点列表（如"渚的读音"、"见的读音"、"诗词情感对比"）
"""

import json
import os
from datetime import datetime

def _normalize_results(quiz_results):
    """兼容两种批改报告格式，统一为 [{question/text, type, isCorrect, score}] 列表"""
    items = []
    if isinstance(quiz_results.get('details'), list):   # 旧格式（quiz-ai.html 同步批改）
        items = quiz_results['details']
    elif isinstance(quiz_results.get('results'), list): # 新格式（两阶段 Hermes 批改）
        items = quiz_results['results']
    out = []
    for it in items:
        text = it.get('text') or it.get('question') or ''
        qtype = it.get('type', '')
        correct = bool(it.get('isCorrect'))
        score = it.get('score')
        # 简答题低于80分视为未掌握（即使AI判对也计入薄弱）
        if qtype in ('text', 'essay') and isinstance(score, (int, float)) and score < 80:
            correct = False
        out.append({'text': text, 'type': qtype, 'isCorrect': correct,
                    'userAnswer': it.get('userAnswer', ''), 'score': score})
    return out


def analyze_weak_points(quiz_results):
    """分析薄弱知识点，返回知识点列表"""
    details = _normalize_results(quiz_results)
    weak_areas = quiz_results.get('weakAreas', [])

    # 从 weakAreas 提取薄弱主题
    weak_topics = [w['topic'] for w in weak_areas if w.get('rate', 0) < 80]

    # 从错题中提取具体知识点
    weak_points = []

    for item in details:
        if item['isCorrect']:
            continue
        question = item['text']
        user_answer = str(item.get('userAnswer') or '')

        # 作者/朝代等文学常识
        if any(k in question for k in ['作者', '词人', '诗人', '朝代']):
            weak_points.append('诗词作者与文学常识')

        if '渚' in question:
            if '读音' in question or '拼音' in question:
                weak_points.append('渚的读音（zhǔ）')
            elif '意思' in question or '解释' in question:
                weak_points.append('渚的意思（水中间的小块陆地）')

        if '见' in question:
            if '读音' in question or '拼音' in question:
                weak_points.append('见的读音（xiàn，表示出现）')

        if '泊' in question:
            if '意思' in question or '解释' in question:
                weak_points.append('泊的意思（停船靠岸）')

        if '旷' in question:
            if '意思' in question or '解释' in question:
                weak_points.append('旷的意思（空旷、广阔）')

        if '情感' in question or '对比' in question or '异同' in question or '差异' in question:
            weak_points.append('诗词情感对比分析（需要详细分析两首诗的情感差异）')

        if '画面' in question or '描绘' in question or '景象' in question:
            weak_points.append('诗句画面描述（需要详细描述画面和情感）')

        # 兜底：无法归类的选择题错误
        if item['type'] == 'choice' and not any(
                k in question for k in ['作者','词人','诗人','朝代','渚','见','泊','旷','情感','对比']):
            weak_points.append(f'选择题掌握不牢（{question[:20]}…）')

    # 去重
    weak_points = list(set(weak_points))

    return {
        'weak_topics': weak_topics,
        'weak_points': weak_points,
        'has_choice_errors': any(item['type'] == 'choice' and not item['isCorrect'] for item in details),
        'has_essay_errors': any(item['type'] in ('text', 'essay') and not item['isCorrect'] for item in details)
    }


def main():
    # 读取最新的测验结果
    results_file = 'D:/projects/family-tutor/quiz-results/latest.json'
    if not os.path.exists(results_file):
        print("❌ 没有找到测验结果")
        return
    
    with open(results_file, 'r', encoding='utf-8') as f:
        quiz_results = json.load(f)
    
    # 分析薄弱知识点
    weak_analysis = analyze_weak_points(quiz_results)
    
    print("=== 薄弱知识点分析 ===")
    print(f"薄弱主题: {weak_analysis['weak_topics']}")
    print(f"具体知识点:")
    for point in weak_analysis['weak_points']:
        print(f"  - {point}")
    print(f"需要选择题: {weak_analysis['has_choice_errors']}")
    print(f"需要简答题: {weak_analysis['has_essay_errors']}")
    
    # 保存分析结果
    output_file = 'D:/projects/family-tutor/quiz-data/weak-points-analysis.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(weak_analysis, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ 分析结果已保存: {output_file}")

if __name__ == '__main__':
    main()
