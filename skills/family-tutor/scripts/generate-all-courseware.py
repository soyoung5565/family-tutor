"""
批量生成 OpenMAIC 课件
适用场景：一科多课（数学 4 天、英语 1 天），一次性提交所有 job 并保存 IDs

Prereqs:
  - 已用 parse-pdf API 解析每个 PDF，把结果 JSON 放到 quiz-data/parse_<name>.json
  - OpenMAIC 在 localhost:3000 运行
  - .env.local 的 DEFAULT_MODEL 指向当前使用的 LLM
"""
import json, urllib.request, os

BASE = r'D:\projects\family-tutor\quiz-data'

JOBS = [
    (f'{BASE}/parse_math_day1.json',   '六年级上册数学《分数的应用（一）》',         '数学Day1'),
    (f'{BASE}/parse_math_day2.json',   '六年级上册数学《分数的应用（二）》',         '数学Day2'),
    (f'{BASE}/parse_math_day3.json',   '六年级上册数学《数据的表示和分析（三）》', '数学Day3'),
    (f'{BASE}/parse_math_day4.json',   '六年级上册数学《数据的分段整理与分析》',   '数学Day4'),
    (f'{BASE}/parse_english_unit1.json', '六年级上册英语《代词与可数名词》',        '英语Day1'),
]

PARAMS = {
    'enableWebSearch': True,
    'webSearchProviderId': 'baidu',
    'enableTTS': True,
    'enableImageGeneration': False,
    'agentMode': 'fast',
}


def gen(parse_file, requirement, name):
    d = json.load(open(parse_file, encoding='utf-8'))
    body = json.dumps({
        'requirement': requirement,
        'pdfContent': d['data'],
        **PARAMS,
    }).encode('utf-8')
    req = urllib.request.Request(
        'http://localhost:3000/api/generate-classroom',
        data=body,
        headers={'Content-Type': 'application/json'},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print(f'{name}: jobId={resp["jobId"]}')
    return resp['jobId']


def main():
    jobs = []
    for parse_file, requirement, name in JOBS:
        if not os.path.exists(parse_file):
            print(f'❌ 跳过 {name}: {parse_file} 不存在')
            continue
        jobs.append(gen(parse_file, requirement, name))

    print(f'\n全部提交完成！Job IDs: {", ".join(jobs)}')

    out = f'{BASE}/courseware-jobs.json'
    with open(out, 'w') as f:
        json.dump({'jobs': jobs}, f)
    print(f'Job IDs 已保存到 {out}')


if __name__ == '__main__':
    main()