#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""round3-pipeline.py — 扩搜全流程：等搜索 → 合并 → 抓取 → 提取 → 入库"""
import json, subprocess, time
from pathlib import Path

BASE = Path(r'D:\家教\系统\scripts')
PY = r'D:\Python312\python.exe'
SEARCH_PID = 32104


def run(script, timeout=2400):
    print(f"--- {script} ---", flush=True)
    r = subprocess.run([PY, str(BASE / script)], capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=str(BASE), timeout=timeout)
    print((r.stdout or '')[-1200:], flush=True)
    return r.stdout or ''


def alive(p):
    r = subprocess.run(['tasklist', '/FI', f'PID eq {p}'], capture_output=True, text=True, errors='replace')
    return str(p) in (r.stdout or '')


print(f"等扩搜进程 {SEARCH_PID}...", flush=True)
t0 = time.time()
while alive(SEARCH_PID) and time.time() - t0 < 1800:
    time.sleep(20)
print(f"搜索结束（{(time.time()-t0)/60:.1f} 分钟）", flush=True)

# ---- 合并到两站输入 ----
d = json.loads((BASE / '_round3_search.json').read_text(encoding='utf-8'))

uf = BASE / '_21cnjy_urls.json'
urls = json.loads(uf.read_text(encoding='utf-8'))
added_cn = 0
for r in d:
    if '21cnjy' not in r['site']:
        continue
    for u in r['urls']:
        if u['url'] not in urls:
            urls[u['url']] = {'title': u['title'],
                              'kps': [{'kp_id': r['kp_id'], 'subject': r['subj'], 'kp_name': r['name']}]}
            added_cn += 1
uf.write_text(json.dumps(urls, ensure_ascii=False, indent=2), encoding='utf-8')

sf = BASE / '_51jiaoxi_search.json'
s = json.loads(sf.read_text(encoding='utf-8'))
have = set()
for rec in s:
    for u in rec.get('urls', []):
        have.add(u['doc_id'])
by_kp = {}
for r in d:
    if '51jiaoxi' not in r['site']:
        continue
    for u in r['urls']:
        did = u.get('id', '')
        if not did.isdigit() or did in have:
            continue
        by_kp.setdefault((r['kp_id'], r['subj'], r['name']), []).append(
            {'url': u['url'], 'title': u['title'], 'doc_id': did})
added_jx = 0
for (kid, subj, kname), us in by_kp.items():
    s.append({'kp_id': kid, 'name': kname, 'unit_id': kid.split('.')[0], 'current': 0,
              'subject': subj, 'query': f'more {kid}', 'urls': us})
    added_jx += len(us)
sf.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"合并: 21cnjy +{added_cn} / 教习网 +{added_jx}", flush=True)

run('21cnjy-crawl.py')
run('51jiaoxi-crawl.py')

print("--- 启动提取 ---", flush=True)
procs = []
for w in range(4):
    lf = open(BASE / f'_21cnjy_w{w}.log', 'a', encoding='utf-8')
    lf.write(f"\n===== more {time.strftime('%H:%M:%S')} =====\n"); lf.flush()
    procs.append(subprocess.Popen([PY, str(BASE / '21cnjy-ingest.py'), str(w), '4'],
                                  stdout=lf, stderr=subprocess.STDOUT, cwd=str(BASE)))
lf2 = open(BASE / '_51jiaoxi_w0.log', 'a', encoding='utf-8')
lf2.write(f"\n===== more {time.strftime('%H:%M:%S')} =====\n"); lf2.flush()
procs.append(subprocess.Popen([PY, str(BASE / '51jiaoxi-ingest.py'), '0', '1'],
                              stdout=lf2, stderr=subprocess.STDOUT, cwd=str(BASE)))
print(f"worker pids: {[p.pid for p in procs]}", flush=True)
for p in procs:
    p.wait()
print("提取完成", flush=True)

run('51jiaoxi-merge.py')
run('21cnjy-merge.py')

tot = {}
for subj in ['数学', '语文', '英语']:
    n = 0
    for p in Path(f'D:/家教/{subj}/测验').rglob('*.json'):
        if p.parent.name.startswith(('u', 'sp', 'r')) and p.stem.count('.') == 1:
            try: n += len(json.loads(p.read_text(encoding='utf-8')))
            except Exception: pass
    tot[subj] = n
print(f"\n[结果] 题库: {tot} = {sum(tot.values())}", flush=True)
