#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
grade-batch.py — 多页作业并行批改壳（无损提速，2026-09-29）

把 N 张作业图分发给 N 个 grade-mistake.py 子进程并行跑（每页内部再带自己的并发），
页面之间完全独立，质量与单页跑完全相同（无损）；只是把"一页一页排"改成"一起跑"。

用法：
  D:/Python312/python.exe grade-batch.py --images a.jpg b.jpg c.jpg --subject 语文
  D:/Python312/python.exe grade-batch.py --images a.jpg b.jpg --subject 数学 --pages 2 --inner 4 --outdir D:/家教/_batch_out/数学_01

参数：
  --images   一个或多个作业图（必填）
  --subject  科目（默认 数学）
  --pages    并行页数（默认 2；建议 2-3，避免 API 过载）
  --inner    每页内部判卷并发（默认 4，透传给 grade-mistake.py --concurrency）
  --outdir   输出目录（默认 脚本上级/_batch_out/时间戳/）
  --no-typo-check  跳过错字/拼写专项

输出：
  每页 <图片名>.graded.json + <图片名>.log；外加 batch_summary.json（含每页耗时与总数）
"""
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
GM = HERE / "grade-mistake.py"


def run_one(img: Path, subject: str, inner: int, outdir: Path, extra: list) -> dict:
    t0 = time.time()
    out_json = outdir / (img.stem + ".graded.json")
    logf = outdir / (img.stem + ".log")
    cmd = [sys.executable, str(GM), "--image", str(img), "--subject", subject,
           "--concurrency", str(inner), "--out", str(out_json)] + extra
    with open(logf, "w", encoding="utf-8") as lf:
        p = subprocess.run(cmd, stdout=lf, stderr=lf, cwd=str(HERE))
    secs = round(time.time() - t0, 1)
    ok = (p.returncode == 0 and out_json.exists())
    n_q = n_typo = -1
    if ok:
        try:
            d = json.loads(out_json.read_text(encoding="utf-8"))
            n_q = len(d.get("mistakes", []))
            tc = d.get("typo_check") or {}
            n_typo = len(tc.get("errors") or []) if tc.get("checked") else -1
        except Exception:
            ok = False
    return {"image": str(img), "out": str(out_json), "log": str(logf), "rc": p.returncode,
            "seconds": secs, "ok": ok, "questions": n_q, "typo_errors": n_typo}


def main():
    ap = argparse.ArgumentParser(description="Batch parallel homework grading")
    ap.add_argument("--images", nargs="+", required=True)
    ap.add_argument("--subject", default="数学")
    ap.add_argument("--pages", type=int, default=2, help="并行页数（默认2；建议2-3）")
    ap.add_argument("--inner", type=int, default=4, help="每页内部并发（默认4）")
    ap.add_argument("--outdir", default=None)
    ap.add_argument("--no-typo-check", action="store_true")
    args = ap.parse_args()

    imgs = [Path(p) for p in args.images]
    for im in imgs:
        if not im.exists():
            sys.exit("[x] 图片不存在：%s" % im)
    outdir = Path(args.outdir) if args.outdir else (
        HERE.parent / "_batch_out" / datetime.now().strftime("%Y%m%d_%H%M%S"))
    outdir.mkdir(parents=True, exist_ok=True)
    extra = ["--no-typo-check"] if args.no_typo_check else []

    print("[batch] %d 页｜并行页数 %d｜每页内并发 %d｜输出 %s" % (len(imgs), args.pages, args.inner, outdir))
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.pages)) as pool:
        futs = [pool.submit(run_one, im, args.subject, args.inner, outdir, extra) for im in imgs]
        rows = [f.result() for f in futs]
    total = round(time.time() - t0, 1)

    (outdir / "batch_summary.json").write_text(
        json.dumps({"total_seconds": total, "pages": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[batch] 全部完成，总耗时 %ss" % total)
    for r in rows:
        print("  - %-36s %7.1fs  %-4s  题=%s 错字=%s" % (
            Path(r["image"]).name, r["seconds"], "OK" if r["ok"] else "FAIL", r["questions"], r["typo_errors"]))
    print("[batch] 明细目录：%s" % outdir)


if __name__ == "__main__":
    main()
