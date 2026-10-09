#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微课堂课件剪裁工具（edit-micro-lesson.py）  2026-09-25 新增。

用途：对已生成的微课堂课件做“小题级剪裁”——某大题多个小题合并生成了一课，
学生后来订正对了其中 1 个小题，需要把该小题对应内容（知识点页/回到小题页）删掉时用。

用法：
  D:\\Python312\\python.exe edit-micro-lesson.py --classroom <课件id> --list
  D:\\Python312\\python.exe edit-micro-lesson.py --classroom <课件id> --subs-preview 2
  D:\\Python312\\python.exe edit-micro-lesson.py --classroom <课件id> --remove-scenes 4,5
  D:\\Python312\\python.exe edit-micro-lesson.py --classroom <课件id> --restore-latest

安全特性：改前自动备份 JSON；被删场景音频移到 audio/_removed/（可恢复）；order 重排。
"""
import argparse, json, re, shutil, sys, time
from pathlib import Path

ROOT = Path("D:/projects/OpenMAIC/data/classrooms")
CN_NUM = {1: "一", 2: "二", 3: "三", 4: "四", 5: "五", 6: "六", 7: "七", 8: "八", 9: "九", 10: "十"}


def load(cid):
    f = ROOT / f"{cid}.json"
    if not f.exists():
        sys.exit(f"[x] 课件不存在: {f}")
    return f, json.loads(f.read_text(encoding="utf-8"))


def scene_audio_ids(sc):
    return [a["audioId"] for a in (sc.get("actions") or []) if a.get("audioId")]


def cmd_list(cid):
    f, d = load(cid)
    scenes = d.get("scenes") or []
    print(f"课件 {cid}: {len(scenes)} 个场景 | {d.get('stage', {}).get('name', '')}")
    ad = ROOT / cid / "audio"
    for i, sc in enumerate(scenes, 1):
        aids = scene_audio_ids(sc)
        n = sum(1 for aid in aids for _ in ad.glob(f"{aid}.*")) if ad.exists() else 0
        print(f"  {i:>2}. {sc.get('title', '?')}  [order={sc.get('order')}, 语音={len(aids)}, 音频={n}]")


def match_sub(title, n):
    pats = [
        rf"回到\s*小题\s*[（(]?{n}[)）]?",
        rf"订正\s*小题\s*[（(]?{n}[)）]?",
        rf"小题\s*[（(]{n}[)）]",
        rf"[（(]{n}[)）]",
    ]
    if n <= 10:
        cnn = CN_NUM[n]
        pats += [rf"回到\s*小题\s*{cnn}", rf"小题\s*{cnn}(?!十)"]
    return any(re.search(p, title) for p in pats)


def cmd_subs_preview(cid, n):
    f, d = load(cid)
    print(f"课件 {cid} —— 预览：与“小题 {n}”相关的场景（只读）")
    for i, sc in enumerate(d.get("scenes") or [], 1):
        t = sc.get("title") or ""
        if match_sub(t, n):
            print(f"  -> #{i} [{t}]  (order={sc.get('order')}, 语音={len(scene_audio_ids(sc))})")
    print()
    print("提示：如要连同该小题‘知识点页’一起删，把知识点页序号也加进 --remove-scenes。")
    print("      典型删法 = 知识点页序号 + 回到小题页序号，逗号分隔。")


def cmd_remove(cid, nums, keep_audio):
    f, d = load(cid)
    scenes = d.get("scenes") or []
    bad = [n for n in nums if n < 1 or n > len(scenes)]
    if bad:
        sys.exit(f"[x] 序号越界: {bad}（当前共 {len(scenes)} 个场景）")
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = f.with_name(f"{f.stem}.json.bak-edit-{ts}")
    shutil.copyfile(f, bak)
    print(f"[备份] {bak.name}")
    removed, kept = [], []
    for i, sc in enumerate(scenes, 1):
        (removed if i in nums else kept).append((i, sc))
    moved = 0
    ad = ROOT / cid / "audio"
    rmdir = ad / "_removed"
    if not keep_audio and ad.exists():
        for _, sc in removed:
            names = set()
            for aid in scene_audio_ids(sc):
                names |= set(ad.glob(f"{aid}.*"))
            names |= set(ad.glob(f"tts_s{sc.get('order')}_*"))
            if names:
                rmdir.mkdir(parents=True, exist_ok=True)
            for fp in names:
                if fp.is_file():
                    shutil.move(str(fp), str(rmdir / fp.name))
                    moved += 1
    now = int(time.time() * 1000)
    for idx, (_, sc) in enumerate(kept, 1):
        sc["order"] = idx
        sc["updatedAt"] = now
    d["scenes"] = [sc for _, sc in kept]
    f.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[完成] 删 {len(removed)} 场景，移音频 {moved} 个 -> audio/_removed/")
    for i, sc in removed:
        print(f"   - 已删 #{i} {sc.get('title')}")
    print(f"[结果] {len(kept)} 个场景（序号重排）：")
    for idx, (_, sc) in enumerate(kept, 1):
        print(f"   {idx}. {sc.get('title')}")


def cmd_restore(cid):
    f, _ = load(cid)
    baks = sorted(f.parent.glob(f"{f.stem}.json.bak-edit-*"))
    if not baks:
        sys.exit("[x] 没有备份")
    shutil.copyfile(baks[-1], f)
    print(f"[恢复] 已用 {baks[-1].name} 覆盖 {f.name}（音频如需恢复请到 audio/_removed/ 手工移回）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classroom", required=True)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--subs-preview", type=int, metavar="N")
    ap.add_argument("--remove-scenes", type=str, metavar="1,2,3")
    ap.add_argument("--keep-audio", action="store_true")
    ap.add_argument("--restore-latest", action="store_true")
    a = ap.parse_args()
    if a.list:
        cmd_list(a.classroom)
    elif a.subs_preview:
        cmd_subs_preview(a.classroom, a.subs_preview)
    elif a.remove_scenes:
        cmd_remove(a.classroom, {int(x) for x in re.split(r"[,\s]+", a.remove_scenes.strip()) if x}, a.keep_audio)
    elif a.restore_latest:
        cmd_restore(a.classroom)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
