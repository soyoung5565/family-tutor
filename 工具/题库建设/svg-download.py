#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""批量抓 zxxk SVG → 双栏重排 → full.txt
v4: 2026-09-17, 接收 _extract_todo_v3.json，输出 _zxxk_v3/{soft_id}/full.txt
"""
import json, re, ssl, time, sys, urllib.request
from pathlib import Path

TODO = Path(r'D:/家教/系统/scripts/_extract_todo_v3.json')
OUT_BASE = Path(r'D:/家教/系统/scripts/_zxxk_v3')
PROGRESS = Path(r'D:/家教/系统/scripts/_svg_progress.json')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def read_svg_bytes(raw):
    if raw.startswith(b'\xff\xfe'): return raw.decode('utf-16-le', errors='ignore')
    if raw.startswith(b'\xfe\xff'): return raw.decode('utf-16-be', errors='ignore')
    if raw.startswith(b'\xef\xbb\xbf'): return raw.decode('utf-8-sig', errors='ignore')
    return raw.decode('utf-8', errors='ignore')

def parse_svg_columns(content, gutter_x=650, binding_x=1200):
    items = []
    for m in re.finditer(r'<text\s+([^>]*)>(.*?)</text>', content, re.DOTALL):
        attrs, inner = m.group(1), m.group(2)
        x_m = re.search(r'\bx="([^"]+)"', attrs)
        y_m = re.search(r'\by="([^"]+)"', attrs)
        if not x_m or not y_m: continue
        try:
            xs = [float(v) for v in x_m.group(1).strip().split()]
            y = float(y_m.group(1))
        except ValueError: continue
        text = re.sub(r'<[^>]+>', '', inner).strip()
        if not text: continue
        items.append((y, xs[0], text))
    left = [(y,x,t) for y,x,t in items if x < gutter_x]
    right = [(y,x,t) for y,x,t in items if gutter_x <= x < binding_x]
    def to_lines(column):
        column.sort(key=lambda z: (z[0], z[1]))
        lines, cur_y, cur_line = [], -1000, []
        for y, x, t in column:
            if abs(y - cur_y) > 6:
                if cur_line:
                    cur_line.sort(key=lambda z: z[0])
                    lines.append(''.join(tt for _, tt in cur_line))
                cur_y, cur_line = y, [(x, t)]
            else:
                cur_line.append((x, t))
        if cur_line:
            cur_line.sort(key=lambda z: z[0])
            lines.append(''.join(tt for _, tt in cur_line))
        return lines
    skip = set('…密封线内不要答题○：: ')
    skip_w = {'学校','班级','姓名','考号','学科网（北京）股份有限公司'}
    def clean(lines):
        out = []
        for ln in lines:
            s = ln.strip()
            if not s or all(c in skip for c in s) or s in skip_w: continue
            out.append(s)
        return out
    return clean(to_lines(left)), clean(to_lines(right))

def download_and_parse(sid, svg_urls):
    out_dir = OUT_BASE / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    all_lines = []
    for i, src in enumerate(svg_urls, 1):
        try:
            req = urllib.request.Request(src, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=15, context=ctx).read()
            (out_dir / f'page_{i}.svg').write_bytes(data)
            content = read_svg_bytes(data)
            left, right = parse_svg_columns(content)
            all_lines.extend(left)
            all_lines.extend(right)
            all_lines.append('')  # 页间空行
        except Exception as e:
            print(f'    page {i} 下载失败: {e}', flush=True)
    full_text = '\n'.join(all_lines)
    (out_dir / 'full.txt').write_text(full_text, encoding='utf-8')
    return len(all_lines), len(full_text)

# 这个脚本只负责"已经拿到 SVG URL 后的下载+解析"
# SVG URL 列表由 browser_exec 那边单独抓
if __name__ == '__main__':
    # 读 svg_urls 清单: _svg_urls.json  {soft_id: [url1, url2, ...]}
    urls_file = Path(r'D:/家教/系统/scripts/_svg_urls.json')
    if not urls_file.exists():
        print('需要 _svg_urls.json，先跑 browser_exec 抓 URL')
        sys.exit(1)
    svg_urls = json.loads(urls_file.read_text(encoding='utf-8'))
    
    progress = set()
    if PROGRESS.exists():
        progress = set(json.loads(PROGRESS.read_text(encoding='utf-8')))
    
    for sid, urls in svg_urls.items():
        if sid in progress:
            print(f'SKIP {sid}')
            continue
        if not urls:
            print(f'[x] {sid} 无 SVG URL')
            continue
        print(f'[+] {sid}  {len(urls)} 页')
        n_lines, n_chars = download_and_parse(sid, urls)
        print(f'    → {n_lines} 行, {n_chars} 字符')
        progress.add(sid)
        PROGRESS.write_text(json.dumps(list(progress)), encoding='utf-8')
        time.sleep(1)
    
    print(f'\n完成: {len(progress)} 份')
