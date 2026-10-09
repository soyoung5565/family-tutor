#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wrong-list.py — 第一阶段反馈：只列出错题，不给答案

用户 2026-09-24 流程调整：
  之前：批改 → 直接给答案 + 微课堂
  现在：批改 → 【只告诉哪些题错了】→ 学生自己订正 → 第二次才给答案 + 微课堂

本脚本把批改结果 mistakes.json 转成"给学生的订正清单"：
  - 保留：题号、题干、学生自己的答案
  - 剔除：correct_answer / correct_solution / common_mistakes（关键！）
  - 输出：Markdown（打印/微信）+ HTML（可视化，可直接打开）

用法:
  python wrong-list.py --mistakes mistakes.json --subject 数学
  python wrong-list.py --mistakes mistakes.json --subject 数学 --html out.html
  python wrong-list.py --demo
"""
import argparse
import json
import html as H
from datetime import datetime
from pathlib import Path

STRIP_FIELDS = ('correct_answer', 'correct_solution', 'common_mistakes',
                'answer', 'solution', 'explanation')

DEMO = [
    {"id": "q1", "question": "摄影小组有12人，是气象小组的1/3，航模小组的人数是摄影小组的3/4，求航模小组的人数。",
     "student_answer": "27", "correct_answer": "9人",
     "correct_solution": "气象小组=12÷(1/3)=36人；航模=12×3/4=9人",
     "knowledge_points": ["u1.k1"]},
    {"id": "q2", "question": "一个圆形花坛的半径是4米，它的面积是多少平方米？(π取3.14)",
     "student_answer": "25.12 平方米", "correct_answer": "50.24 平方米",
     "correct_solution": "S=πr²=3.14×16=50.24", "knowledge_points": ["u2.k6"]},
]


def sanitize(m):
    """剥离一切答案/解法信息"""
    return {k: v for k, v in m.items() if k not in STRIP_FIELDS}


def to_markdown(items, subject, date_str):
    n = len(items)
    out = [f"# {subject} 订正清单（{date_str}）", ""]
    out.append(f"这次一共 **{n} 道题** 需要你重新做一遍。")
    out.append("")
    out.append("> 请**先自己订正**，把新的解答写出来。")
    out.append("> 订正好后拍照发给我，我再给你正确答案和讲解。")
    out.append("")
    out.append("---")
    out.append("")
    for i, m in enumerate(items, 1):
        out.append(f"## {i}. （原题号 {m.get('id','')}）")
        out.append("")
        out.append(f"**题目**：{m.get('question','').strip()}")
        out.append("")
        sa = str(m.get('student_answer', '') or '').strip()
        if sa:
            out.append(f"**你上次写的**：{sa}")
            out.append("")
        out.append("**订正**：")
        out.append("")
        out.append("```")
        out.append("（在这里写你的新解答）")
        out.append("```")
        out.append("")
    return "\n".join(out)


def to_plain(items, subject, date_str):
    """纯文字版：直接复制发微信/对话框，学生看到的就是这个"""
    n = len(items)
    out = [f"这次批改有 {n} 道题做错了，请你重新做一遍。", ""]
    for i, m in enumerate(items, 1):
        out.append(f"{i}. {str(m.get('question','')).strip()}")
        sa = str(m.get('student_answer', '') or '').strip()
        if sa:
            out.append(f"   （你上次写的：{sa}）")
        out.append("")
    out.append("做完后把新的解答拍照发我，我再给你正确答案和讲解。")
    return "\n".join(out)


def to_html(items, subject, date_str):
    n = len(items)
    blocks = []
    for i, m in enumerate(items, 1):
        sa = str(m.get('student_answer', '') or '').strip()
        sa_html = f'<div class="sa">你上次写的：<code>{H.escape(sa)}</code></div>' if sa else ''
        blocks.append(f"""
  <div class="item">
    <div class="no">{i} <span class="oid">原题号 {H.escape(str(m.get('id','')))}</span></div>
    <div class="q">{H.escape(m.get('question','').strip())}</div>
    {sa_html}
    <div class="fix">订正：</div>
    <div class="blank"></div>
  </div>""")
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<title>{subject} 订正清单 {date_str}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: -apple-system, "Microsoft YaHei", sans-serif; max-width: 820px;
         margin: 0 auto; padding: 28px 20px 60px; line-height: 1.75; }}
  h1 {{ font-size: 26px; margin: 0 0 6px; }}
  .sub {{ color: #666; margin-bottom: 22px; }}
  .tip {{ background: #fff8e1; border-left: 4px solid #ffb300; padding: 12px 16px;
          border-radius: 6px; margin-bottom: 28px; }}
  .item {{ border: 1px solid #e0e0e0; border-radius: 10px; padding: 18px 20px; margin-bottom: 22px; }}
  .no {{ font-weight: 700; font-size: 18px; margin-bottom: 10px; }}
  .oid {{ font-weight: 400; font-size: 12px; color: #999; margin-left: 6px; }}
  .q {{ font-size: 17px; margin-bottom: 12px; }}
  .sa {{ font-size: 15px; color: #c62828; margin-bottom: 14px; }}
  .sa code {{ background: #f5f5f5; padding: 2px 8px; border-radius: 4px; }}
  .fix {{ font-weight: 600; margin-bottom: 8px; }}
  .blank {{ height: 110px; border: 1px dashed #bbb; border-radius: 8px; background: #fafafa; }}
</style></head><body>
<h1>{subject} 订正清单</h1>
<div class="sub">{date_str} · 共 {n} 道题</div>
<div class="tip">请<b>先自己订正</b>，把新的解答写在下面的空白处。<br>
订正好后拍照发给我，我再给你<b>正确答案和讲解</b>。</div>
{''.join(blocks)}
</body></html>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mistakes', help='mistakes.json 路径')
    ap.add_argument('--subject', default='数学')
    ap.add_argument('--out', help='输出 Markdown 路径')
    ap.add_argument('--html', help='输出 HTML 路径')
    ap.add_argument('--text-only', action='store_true',
                    help='只输出可直接发微信/对话框的纯文字（默认行为）')
    ap.add_argument('--demo', action='store_true')
    a = ap.parse_args()

    if a.demo:
        items = DEMO
    else:
        if not a.mistakes:
            print('需要 --mistakes 或 --demo'); return
        items = json.loads(Path(a.mistakes).read_text(encoding='utf-8'))
        if isinstance(items, dict):
            items = items.get('mistakes') or items.get('items') or []

    safe = [sanitize(m) for m in items]
    date_str = datetime.now().strftime('%Y-%m-%d')
    md = to_markdown(safe, a.subject, date_str)
    plain = to_plain(safe, a.subject, date_str)
    htm = to_html(safe, a.subject, date_str)

    out_md = Path(a.out) if a.out else Path(f'D:/家教/系统/错题清单_{date_str}.md')
    out_md.write_text(md, encoding='utf-8')

    # 安全检查：确认输出里没有答案泄漏
    leak = [f for f in STRIP_FIELDS if f in md]
    print(f'✓ 错题清单: {out_md}')
    print(f'  题数 {len(safe)} | 答案泄漏检查: {"❌ 发现 " + str(leak) if leak else "✓ 无泄漏"}')

    # --text-only：直接输出一段可直接发给学生的纯文字（微信/对话框粘贴用）
    if a.text_only:
        print('\n' + '=' * 50)
        print(plain)
        print('=' * 50)


if __name__ == '__main__':
    main()
