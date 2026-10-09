#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""search-gap3.py — 针对 9 个仍偏少的 KP 做专项补搜（多关键词变体）"""
import json, requests, time, re
from pathlib import Path

TAVILY_KEY = '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'
BASE = Path(r'D:\家教\系统\scripts')
OUT = BASE / '_gap3_search.json'

GAP_KPS = [
    ('语文', 'u5.k6', '例文《小站》袁鹰', ['小站 袁鹰 六年级 阅读短文', '小站 六年级语文 阅读练习题', '统编版 六年级上册 小站 练习']),
    ('语文', 'u4.k8', '古诗《送元二使安西》王维', ['送元二使安西 六年级 古诗练习', '送元二使安西 王维 测试题', '小学古诗 送元二使安西 练习卷']),
    ('数学', 'u3.k7', '探索规律（n张桌子坐的人数）', ['数学 探索规律 六年级 测试', '找规律 六年级数学 练习卷', '图形规律 六年级 专项']),
    ('数学', 'u8.k2', '三视图', ['三视图 六年级数学 练习', '观察物体 六年级 测试卷', '从三个方向看物体 六年级 练习']),
    ('英语', 'u1.k6', 'Project: Make a poster about my growth', ['六年级英语 Project 单元测试', '六年级上册英语 综合练习 单元检测', '英语六年级 单元检测卷 上册']),
    ('英语', 'u5.k4', 'Lesson 3 Is technology our friend?', ['六年级英语 科技 单元测试', '英语六年级上册 单元检测 科技', '六年级英语 单元测试卷 上册']),
    ('英语', 'u5.k3', 'Lesson 2 My inventions', ['六年级英语 inventions 练习', '六年级英语 发明 单元测试', '英语六年级上册 单元训练']),
    ('英语', 'u4.k4', 'Lesson 3 What shall I do to be great?', ['六年级英语 单元测试卷 上册', '六年级英语 famous people 练习', '英语六年级 人物 单元检测']),
    ('英语', 'u4.k1', 'Unit 4 Learning Goals', ['六年级英语 上册 期中测试卷', '英语六年级上册 单元检测卷', '六年级英语 上册 期末测试卷']),
]

EXCLUDE = ['下册', '下学期', '五年级', '四年级', '三年级', '二年级', '一年级',
           '七年级', '八年级', '九年级', '初一', '初二', '初三', '中考', '高考', '高中',
           '教案', '课件', 'ppt', '教学设计', '教学计划', '学案', '导学案', '说课']
INCLUDE = ['试卷', '测试', '练习', '检测', '真题', '单元', '期中', '期末', '达标', '训练', '题']

queries = []
for subj, kid, kname, kws in GAP_KPS:
    for kw in kws:
        for site in ['51jiaoxi.com', '21cnjy.com']:
            queries.append({'kp_id': kid, 'kp_name': kname, 'subject': subj,
                            'query': kw, 'site': site})
print(f"计划 {len(queries)} 次搜索", flush=True)

results = []
if OUT.exists():
    try:
        results = json.loads(OUT.read_text(encoding='utf-8'))
    except Exception:
        results = []
done = {(r['query'], r['site']) for r in results}

for i, item in enumerate(queries, 1):
    if (item['query'], item['site']) in done:
        continue
    urls = []
    try:
        r = requests.post('https://api.tavily.com/search',
            json={'api_key': TAVILY_KEY, 'query': f"site:{item['site']} {item['query']}", 'max_results': 15},
            timeout=40)
        for x in r.json().get('results', []):
            u, t = x.get('url', ''), x.get('title', '')
            if item['site'] not in u:
                continue
            if any(k.lower() in t.lower() for k in EXCLUDE):
                continue
            if not any(k in t for k in INCLUDE):
                continue
            m = re.search(r'51jiaoxi\.com/(?:doc-)?(\d+)\.html', u) if '51jiaoxi' in u else re.search(r'21cnjy\.com/(?:P/|p/)(\d+)', u)
            urls.append({'url': u, 'title': t[:90], 'id': m.group(1) if m else u[:40]})
        if urls:
            print(f"  [{i}/{len(queries)}] {item['kp_id']}@{item['site'][:9]} -> {len(urls)}", flush=True)
    except Exception as e:
        print(f"  [{i}] err {str(e)[:60]}", flush=True)
    results.append({**item, 'urls': urls})
    time.sleep(0.9)
    if i % 15 == 0:
        OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

OUT.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
tot = sum(len(r['urls']) for r in results)
print(f"\n总命中 {tot}", flush=True)
