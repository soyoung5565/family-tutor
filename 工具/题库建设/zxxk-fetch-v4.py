#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""zxxk-fetch-v4.py — 下载 zxxk 预览页，按魔数分流：
   SVG → 双栏重排 → _zxxk_v4/{sid}/full.txt
   JPG → 存图 → _zxxk_v4_jpg.json（留待 vision 提取）
"""
import json, re, ssl, time, urllib.request
from pathlib import Path

BASE = Path(r'D:/家教/系统/scripts')
OUT_BASE = BASE / '_zxxk_v4'
PROG = BASE / '_zxxk_v4_progress.json'
JPG_LIST = BASE / '_zxxk_v4_jpg.json'
CAND_F = BASE / '_zxxk_candidates_v3_filtered.json'
SVG_URLS_F = BASE / '_svg_urls.json'

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
    left = [(y, x, t) for y, x, t in items if x < gutter_x]
    right = [(y, x, t) for y, x, t in items if gutter_x <= x < binding_x]

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
    skip_w = {'学校', '班级', '姓名', '考号', '学科网（北京）股份有限公司'}

    def clean(lines):
        out = []
        for ln in lines:
            s = ln.strip()
            if not s or all(c in skip for c in s) or s in skip_w: continue
            out.append(s)
        return out
    return clean(to_lines(left)), clean(to_lines(right))


cands = json.loads(CAND_F.read_text(encoding='utf-8'))
svg_urls = json.loads(SVG_URLS_F.read_text(encoding='utf-8'))
prog = {}
if PROG.exists():
    try: prog = json.loads(PROG.read_text(encoding='utf-8'))
    except Exception: prog = {}
jpg_map = {}
if JPG_LIST.exists():
    try: jpg_map = json.loads(JPG_LIST.read_text(encoding='utf-8'))
    except Exception: jpg_map = {}

for ci, c in enumerate(cands, 1):
    sid = c['soft_id']
    urls = svg_urls.get(sid) or []
    if not urls:
        prog[sid] = 'no_urls'
        continue
    if prog.get(sid) == 'done':
        continue
    out_dir = OUT_BASE / sid
    out_dir.mkdir(parents=True, exist_ok=True)
    lines_all, jpgs, n_svg = [], [], 0
    for i, u in enumerate(urls, 1):
        try:
            req = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0'})
            data = urllib.request.urlopen(req, timeout=25, context=ctx).read()
        except Exception as e:
            print(f'    [{sid}] page {i} 下载失败 {str(e)[:50]}', flush=True)
            continue
        if data[:2] == b'\xff\xd8':
            jp = out_dir / f'page_{i}.jpg'
            jp.write_bytes(data)
            jpgs.append(str(jp))
        else:
            head = data.lstrip()[:4].lower()
            if head in (b'<svg', b'<?xm'):
                (out_dir / f'page_{i}.svg').write_bytes(data)
                left, right = parse_svg_columns(read_svg_bytes(data))
                lines_all.extend(left); lines_all.extend(right); lines_all.append('')
                n_svg += 1
            else:
                print(f'    [{sid}] page {i} 未知类型 {data[:12]}', flush=True)
    if lines_all:
        (out_dir / 'full.txt').write_text('\n'.join(lines_all), encoding='utf-8')
    if jpgs:
        jpg_map[sid] = jpgs
    prog[sid] = 'done'
    print(f'  [{ci}/{len(cands)}] {sid}: svg页 {n_svg} / jpg页 {len(jpgs)} / 文本 {sum(len(x) for x in lines_all)} 字', flush=True)
    PROG.write_text(json.dumps(prog, ensure_ascii=False, indent=2), encoding='utf-8')
    JPG_LIST.write_text(json.dumps(jpg_map, ensure_ascii=False, indent=2), encoding='utf-8')
    time.sleep(0.5)

ok_svg = sum(1 for s in prog if (OUT_BASE / s / 'full.txt').exists())
print(f'\n完成: {len(prog)} 份 | 有 SVG 文本 {ok_svg} 份 | 有 JPG 的 {len(jpg_map)} 份', flush=True)
