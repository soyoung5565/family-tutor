#!/usr/bin/env python3
"""
Knowledge Point Extractor

Extracts all knowledge points from a complete textbook PDF, organized by
chapter, into structured JSON files.

Pipeline:
  1. Render PDF pages to PNG (pypdfium2)
  2. Locate chapter boundaries via vision (look for "第X单元" or similar)
  3. For each chapter, batch vision-extract all knowledge points in one
     LLM call (avoids LLM forgetting early content within a chapter)
  4. Validate: ensure no obvious gaps, dedup across chapters
  5. Write one JSON per knowledge point, plus a chapter overview markdown

Output structure:
  D:/家教/{subject}/知识点及掌握情况/
    overview.md                 (chapter list + KP counts for parent review)
    math_day1_kp1.json
    math_day1_kp2.json
    ...

Usage:
  python extract-knowledge-points.py --pdf textbook.pdf --subject math
  python extract-knowledge-points.py --dry-run --pdf textbook.pdf --subject math
        (renders pages + lists chapter boundaries, no LLM calls)
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_TUTOR_ROOT = Path("D:/家教")
RENDER_SCALE = 1.4  # ~100dpi


def render_pdf_pages(pdf_path: Path, out_dir: Path, scale: float = RENDER_SCALE) -> list:
    """Render each PDF page to PNG. Returns list of PNG paths."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print("[error] pypdfium2 not installed. pip install pypdfium2", file=sys.stderr)
        sys.exit(2)

    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = pdfium.PdfDocument(str(pdf_path))
    paths = []
    for i in range(len(pdf)):
        page = pdf[i]
        bitmap = page.render(scale=scale)
        pil_img = bitmap.to_pil()
        p = out_dir / f"page_{i+1:03d}.png"
        pil_img.save(str(p))
        paths.append(p)
    print(f"[render] {len(paths)} pages -> {out_dir}")
    return paths


def locate_chapter_boundaries(pdf_path: Path, page_paths: list, subject: str) -> list:
    """Find page indices where each chapter starts.

    Returns: [{"chapter": "第X单元 Y名称", "start_page": int, "end_page": int}, ...]

    Implementation note: vision-based detection of "第X单元" headers.
    The actual LLM call happens via the parent hermes agent (this script
    provides the prompt template).
    """
    raise NotImplementedError(
        "vision-locate chapters via your multimodal model. "
        "Use the prompt template in locate_chapter_prompt() below."
    )


def locate_chapter_prompt(subject: str) -> str:
    """Return the prompt that asks the vision model to locate chapters."""
    return f"""You are looking at pages from a Chinese {subject} textbook.

Task: identify the page index where each chapter starts.
A chapter usually begins with a header like "第X单元" or "Unit X" followed by a title.

Output JSON:
{{
  "chapters": [
    {{"index": <0-based page index>, "title": "第X单元 Y名称", "grade": "..."}}
  ]
}}
"""


def extract_kps_from_chapter(chapter_title: str, page_indices: list,
                              page_paths: list) -> list:
    """For one chapter, batch-extract all knowledge points in a single LLM call.

    Returns: list of {"id": str, "name": str, "definition": str, "example": str,
                      "difficulty": "easy|medium|hard", "common_mistakes": [str]}
    """
    raise NotImplementedError(
        "vision-extract KPs for one chapter via your multimodal model. "
        "Use the prompt template in kp_extraction_prompt() below."
    )


def kp_extraction_prompt(chapter_title: str, subject: str, grade: str) -> str:
    return f"""You are extracting knowledge points from a Chinese {subject}
textbook chapter: "{chapter_title}" (grade: {grade}).

For each knowledge point, output:
{{
  "id": "<subject>_day<N>_kp<M>",   // unique id
  "name": "<concept name>",
  "definition": "<1-2 sentence definition in student-friendly language>",
  "example": "<one worked example with steps>",
  "difficulty": "easy|medium|hard",
  "common_mistakes": ["<typical error 1>", "<typical error 2>"]
}}

Rules:
1. Cover EVERY concept in this chapter, no omissions
2. Stay within this grade level — do NOT borrow from higher grades
3. Order KPs in teaching order (intro → simple → complex)
4. Use only language appropriate for {grade}

Output a JSON array of knowledge points.
"""


def write_kp_files(kps: list, out_dir: Path, subject: str) -> int:
    """Write one .json per KP plus an overview markdown."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for kp in kps:
        path = out_dir / f"{kp['id']}.json"
        path.write_text(json.dumps(kp, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(kps)


def write_overview_md(chapters: list, kp_count_by_chapter: dict, out_dir: Path,
                      subject: str, grade: str) -> Path:
    """Generate a markdown overview for parent review (catch omissions fast)."""
    lines = [
        f"# {subject} 知识点总览 ({grade})",
        "",
        f"提取时间：{Path(__file__).name}",
        "",
        f"共 {len(chapters)} 个章节，{sum(kp_count_by_chapter.values())} 个知识点",
        "",
        "## 章节列表",
        "",
    ]
    for ch in chapters:
        cnt = kp_count_by_chapter.get(ch["title"], 0)
        lines.append(f"### {ch['title']} ({cnt} 个知识点)")
        lines.append(f"- 起页：第 {ch['start_page']+1} 页")
        lines.append(f"- 止页：第 {ch['end_page']+1} 页")
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("家长请扫一眼章节列表，确认：")
    lines.append("1. 是否漏章节（章节数对得上教材目录？）")
    lines.append("2. 每个章节的页码范围是否合理（没有覆盖到下个章节？）")
    lines.append("3. 知识点数量是否合理（六年级数学每单元 3-8 个 KP 比较常见）")
    path = out_dir / "overview.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description="Extract knowledge points from textbook PDF")
    parser.add_argument("--pdf", required=True, help="Path to textbook PDF")
    parser.add_argument("--subject", required=True, help="math / chinese / english")
    parser.add_argument("--grade", default="六年级上册", help="e.g. 六年级上册")
    parser.add_argument("--tutor-root", default=str(DEFAULT_TUTOR_ROOT))
    parser.add_argument("--dry-run", action="store_true",
                        help="Render pages + show prompts, no LLM calls / writes")
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"[error] PDF not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    tutor_root = Path(args.tutor_root)
    render_dir = tutor_root / args.subject / "课本" / "_rendered_pages"
    kp_dir = tutor_root / args.subject / "知识点及掌握情况"

    page_paths = render_pdf_pages(pdf_path, render_dir)
    print(f"[info] rendered {len(page_paths)} pages")

    if args.dry_run:
        print(f"\n[dry-run] Prompt for chapter boundary detection:")
        print(locate_chapter_prompt(args.subject))
        print(f"\n[dry-run] Prompt template for KP extraction (per chapter):")
        print(kp_extraction_prompt("<chapter title>", args.subject, args.grade))
        print(f"\n[dry-run] Output directory: {kp_dir}")
        return

    print("[info] To run the full pipeline, wire the LLM calls in")
    print("       locate_chapter_boundaries() and extract_kps_from_chapter()")
    print("       to your multimodal model (e.g. opencode-go + ox-alpha-free).")
    print("       Then call write_kp_files() and write_overview_md() with the")
    print("       returned data.")
    print()
    print("       Example wiring pattern:")
    print("         chapters = vision_locate(pdf_path, locate_chapter_prompt(...))")
    print("         for ch in chapters:")
    print("             kps = vision_extract(pages[ch.start_page:ch.end_page+1],")
    print("                                  kp_extraction_prompt(...))")
    print("             write_kp_files(kps, kp_dir, subject)")
    print("             counts[ch.title] = len(kps)")
    print("         write_overview_md(chapters, counts, kp_dir, subject, grade)")


if __name__ == "__main__":
    main()
