import json, urllib.request

BASE = r'D:\projects\family-tutor\quiz-data'

def gen(parse_file, requirement, name):
    d = json.load(open(parse_file, encoding='utf-8'))
    body = json.dumps({
        'requirement': requirement,
        'pdfContent': d['data'],
        'enableWebSearch': True,
        'webSearchProviderId': 'baidu',
        'enableTTS': True,
        'enableImageGeneration': False,
        'agentMode': 'default'
    }).encode('utf-8')
    req = urllib.request.Request('http://localhost:3000/api/generate-classroom', data=body, headers={'Content-Type': 'application/json'})
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print(f'{name}: jobId={resp["jobId"]}')
    return resp['jobId']

jobs = []
jobs.append(gen(f'{BASE}/parse_math_day1.json', '六年级上册数学《分数的应用（一）》', '数学Day1'))
jobs.append(gen(f'{BASE}/parse_math_day2.json', '六年级上册数学《分数的应用（二）》', '数学Day2'))
jobs.append(gen(f'{BASE}/parse_math_day3.json', '六年级上册数学《数据的表示和分析（三）》', '数学Day3'))
jobs.append(gen(f'{BASE}/parse_math_day4.json', '六年级上册数学《数据的分段整理与分析》', '数学Day4'))
jobs.append(gen(f'{BASE}/parse_english_unit1.json', '六年级上册英语《代词与可数名词》', '英语Day1'))

print(f'\n全部提交完成！Job IDs: {", ".join(jobs)}')
with open(f'{BASE}/courseware-jobs.json', 'w') as f:
    json.dump({'jobs': jobs}, f)
