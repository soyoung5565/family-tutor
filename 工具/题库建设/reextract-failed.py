#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, requests, time, re
from pathlib import Path

env = dict(l.strip().split('=',1) for l in open('D:/hermes-data/.env', encoding='utf-8')
           if '=' in l and not l.startswith('#') and l.strip())
MM_KEY = env['MINIMAX_CN_API_KEY'].split('#')[0].strip()

def call_mm(prompt, max_tokens=8192):
    for attempt in range(3):
        try:
            r = requests.post('https://api.minimaxi.com/v1/text/chatcompletion_v2',
                headers={'Authorization': f'Bearer {MM_KEY}', 'Content-Type': 'application/json'},
                json={'model': 'MiniMax-M3', 'messages': [
                    {'role': 'system', 'content': '你是小学试卷分析专家。直接给JSON。'},
                    {'role': 'user', 'content': prompt}],
                    'max_tokens': max_tokens, 'temperature': 0.1}, timeout=180)
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

PROMPTS = {
    '数学': """请从以下六年级数学试卷文本中提取所有完整题目。

【文本】
{text}

【任务】提取所有要求学生作答的题目：计算/填空/选择/判断/操作/解决问题/统计

【输出】严格 JSON 数组：
[{{"题号":"1","题干":"...","选项":null,"答案":"...","题型":"计算/填空/选择/判断/操作/解决问题/统计"}}]

要求：
- 大题里的小题要展开
- 题号保持原卷层级
- 计算题答案给具体数字或"略"
- 文本可能因双栏重排乱序，自行判断逻辑
- 忽略装订线、注意事项、版权""",

    '语文': """请从以下六年级语文试卷文本中提取所有完整题目。

【文本】
{text}

【任务】提取所有要求学生作答的题目：拼音/字词/句子/默写/阅读/口语/习作/选择/判断

【输出】严格 JSON 数组：
[{{"题号":"1","题干":"...","选项":null,"答案":"...","题型":"拼音/字词/句子/默写/阅读/口语/习作/选择/判断"}}]

要求：
- 阅读理解大题里每个小问单独成题
- 默写题 answer 给"见题干"
- 口语交际/习作 answer 给"略"
- 题号保持原卷层级
- 文本可能因双栏重排乱序，自行判断逻辑
- 忽略装订线、注意事项、版权""",

    '英语': """请从以下六年级英语试卷文本中提取所有完整题目。

【文本】
{text}

【任务】提取所有要求学生作答的题目：听力跳过/词汇/单选/完形/句型/交际/阅读/写作

【输出】严格 JSON 数组：
[{{"题号":"1","题干":"...","选项":null,"答案":"...","题型":"词汇/单选/完形/句型/交际/阅读/写作"}}]

要求：
- 听力题跳过
- 阅读理解每个小问单独成题
- 选择题选项放 options dict
- 题号保持原卷层级
- 文本可能因双栏重排乱序，自行判断逻辑
- 忽略装订线、注意事项、版权"""
}

cands = json.loads(Path(r'D:\家教\系统\scripts\_all_candidates_v2.json').read_text(encoding='utf-8'))
sid_to_subject = {}
for c in cands:
    su = c['subjects_units']
    if su:
        sid_to_subject[c['soft_id']] = su[0][0]

failed_sids = ["28796355", "34534128", "40636763", "46717656", "47168194", "47764301", "48882333", "52088804", "53264530", "53706232", "53818187", "53999284", "54180160", "54271436", "54284625", "54422940", "54480137", "54547381", "54567444", "54567501", "55130627", "55201639", "55326374", "55392451", "55456045", "55456048", "55465861", "55539155", "55837852", "58440157", "58686042", "58865982", "58916576", "59087292", "59106549", "59132161", "59136629", "59332293", "59417269", "59434251", "59453910", "59461819", "59556693", "59575601", "59578799", "59582514", "59589727", "59600777", "59625068"]

v3 = Path(r'D:\家教\系统\scripts\_zxxk_v3')
PROGRESS = Path(r'D:\家教\系统\scripts\_reextract_progress.json')
done = set()
if PROGRESS.exists():
    done = set(json.loads(PROGRESS.read_text(encoding='utf-8')))

print(f"待重提: {len(failed_sids)} 份", flush=True)

for i, sid in enumerate(failed_sids, 1):
    if sid in done:
        print(f"  [{i}] {sid} SKIP", flush=True)
        continue
    full_f = v3 / sid / 'full.txt'
    if not full_f.exists():
        continue
    text = full_f.read_text(encoding='utf-8')
    if len(text) < 300:
        continue
    
    subject = sid_to_subject.get(sid, '数学')
    prompt = PROMPTS[subject].format(text=text)
    print(f"  [{i}/{len(failed_sids)}] {sid} [{subject}] {len(text)}字符", flush=True)
    
    out = call_mm(prompt)
    qs = extract_json_array(out)
    print(f"    -> {len(qs)} 题", flush=True)
    
    if qs:
        (v3 / sid / 'extracted.json').write_text(
            json.dumps(qs, ensure_ascii=False, indent=2), encoding='utf-8')
    
    done.add(sid)
    PROGRESS.write_text(json.dumps(list(done)), encoding='utf-8')
    time.sleep(3)

print(f"\n完成", flush=True)
