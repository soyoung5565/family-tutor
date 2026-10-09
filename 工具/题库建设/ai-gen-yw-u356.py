#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AI 生成语文 u3/u5/u6 题目"""
import json, requests, time, re
from pathlib import Path
from datetime import datetime

env = dict(l.strip().split('=',1) for l in open('D:/hermes-data/.env', encoding='utf-8')
           if '=' in l and not l.startswith('#') and l.strip())
MM_KEY = env['MINIMAX_CN_API_KEY'].split('#')[0].strip()

def call_mm(prompt, max_tokens=8192):
    for attempt in range(3):
        try:
            r = requests.post('https://api.minimaxi.com/v1/text/chatcompletion_v2',
                headers={'Authorization': f'Bearer {MM_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'MiniMax-M3', 'messages': [
                    {'role': 'system', 'content': '你是深圳小学六年级语文教研组长。直接出题，不要冗长推理。'},
                    {'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens, 'temperature': 0.7}, timeout=180)
            if r.status_code == 429:
                time.sleep(15*(attempt+1)); continue
            j = r.json()
            ch = j.get('choices') or []
            if not ch: continue
            return ch[0].get('message',{}).get('content','')
        except Exception as e:
            time.sleep(5)
    return ''

def extract_json_array(text):
    text = re.sub(r'^```(?:json)?\s*', '', text.strip())
    text = re.sub(r'\s*```$', '', text)
    s = text.find('['); e = text.rfind(']')
    if s >= 0 and e > s:
        try: return json.loads(text[s:e+1])
        except:
            try:
                import json_repair
                return json_repair.loads(text[s:e+1])
            except: return []
    return []

UNIT_PROMPTS = {
    'u3': {
        'unit_name': '第三单元：阅读策略',
        'topic': '根据阅读目的选用恰当的阅读方法',
        'kps': [
            ('u3.k2', '课文《竹节人》范锡林', '叙事散文，传统玩具与师生情谊'),
            ('u3.k3', '课文《宇宙生命之谜》', '科学说明文，火星生命探索'),
            ('u3.k4', '课文《故宫博物院》', '群文阅读，故宫多角度介绍'),
            ('u3.k6', '语文园地', '阅读策略梳理、《观书有感》'),
        ],
    },
    'u5': {
        'unit_name': '第五单元：围绕中心意思写',
        'topic': '体会并实践围绕中心意思写作',
        'kps': [
            ('u5.k2', '课文《灯光》王愿坚', '革命先烈献身精神'),
            ('u5.k3', '课文《盼》铁凝', '儿童盼雨天穿新雨衣'),
            ('u5.k4', '梳理与交流：围绕中心意思写', '选材、详略'),
            ('u5.k6', '例文《小站》袁鹰', '山区小站的温暖春意'),
        ],
    },
    'u6': {
        'unit_name': '第六单元：保护地球',
        'topic': '人与自然和谐共生，环保主题',
        'kps': [
            ('u6.k2', '课文《只有一个地球》', '说明文，保护地球'),
            ('u6.k3', '课文《青山不老》', '老人植树造林'),
            ('u6.k4', '课文《三黑和土地》', '现代诗，农民热爱土地'),
            ('u6.k5', '古诗三首', '山水田园诗'),
            ('u6.k7', '习作：学写倡议书', '环保倡议书'),
        ],
    },
}

GEN_PROMPT_TMPL = """你是深圳小学六年级语文教研组长。请针对下面 KP 出 **6 道测试题**，覆盖：字词基础(2题)、课文内容理解(2题)、方法迁移/拓展(2题)。

【KP】{kp_id} {kp_name}
【课文/内容】{kp_def}
【单元主题】{unit_name}：{unit_topic}

【出题要求】
1. 题型混合：选择题(2-3道)、填空题(2-3道)、简答题(1-2道)
2. 难度梯度：2 易 + 3 中 + 1 难
3. 题干严谨、表述符合六年级学生认知
4. 涉及课文内容的题目必须忠于原文，不杜撰
5. 选择题 4 个选项（A/B/C/D），其他题型"答案"给"略"或具体内容
6. 不超纲（不超六年级上册范围）

【输出】严格 JSON 数组（不要 markdown 围栏）：
[{{"题号":"1","题干":"...","选项":{{"A":"...","B":"...","C":"...","D":"..."}},"答案":"B","题型":"选择","难度":"易"}},
 {{"题号":"2","题干":"看拼音写词语：jùn mǎ (    )","答案":"骏马","题型":"填空","难度":"易"}}]

直接给 JSON，不要其他解释。"""

# 断点续跑
PROGRESS = Path(r'D:\家教\系统\scripts\_ai_gen_progress.json')
done_kps = set()
if PROGRESS.exists():
    done_kps = set(json.loads(PROGRESS.read_text(encoding='utf-8')))

all_new = []
OUT = Path(r'D:\家教\系统\scripts\_ai_generated_yw_u356.json')
if OUT.exists():
    all_new = json.loads(OUT.read_text(encoding='utf-8'))
    print(f"已有 {len(all_new)} 题，继续生成", flush=True)

for unit_id, uinfo in UNIT_PROMPTS.items():
    print(f"\n===== {unit_id} {uinfo['unit_name']} =====", flush=True)
    for kp_id, kp_name, kp_def in uinfo['kps']:
        if kp_id in done_kps:
            print(f"  SKIP {kp_id}", flush=True)
            continue
        print(f"  {kp_id} {kp_name}...", flush=True)
        prompt = GEN_PROMPT_TMPL.format(
            kp_id=kp_id, kp_name=kp_name, kp_def=kp_def,
            unit_name=uinfo['unit_name'], unit_topic=uinfo['topic'])
        out = call_mm(prompt)
        qs = extract_json_array(out)
        print(f"    -> {len(qs)} 题", flush=True)
        for q in qs:
            q['_kp_id'] = kp_id
            q['_unit_id'] = unit_id
            all_new.append(q)
        done_kps.add(kp_id)
        PROGRESS.write_text(json.dumps(list(done_kps)), encoding='utf-8')
        OUT.write_text(json.dumps(all_new, ensure_ascii=False, indent=2), encoding='utf-8')
        time.sleep(3)

print(f"\n=== 总 {len(all_new)} 题 -> {OUT} ===", flush=True)
