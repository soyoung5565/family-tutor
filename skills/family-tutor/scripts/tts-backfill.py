#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tts-backfill.py — 给已生成的 OpenMAIC 课件补录语音（MIMO TTS 代理版）

场景：生成时 TTS 代理(127.0.0.1:8787)没跑 -> generateTTSForClassroom 全部 fetch failed
      -> 课件 speech action 缺 audioId/audioUrl -> 播放无声。
本脚本按其生成管线同款规则补录（幂等，可反复跑）：
  - 每条 speech -> POST 代理 /v1/audio/speech (voice=alloy -> 冰糖, mp3)
  - 落盘 data/classrooms/{id}/audio/tts_s{场景序}_{actionId}.mp3
  - 回写 audioId + audioUrl=http://localhost:3000/api/classroom-media/{id}/audio/{fn}
  - 重写课件 JSON（保留其余字段）

前置：TTS 代理在跑（schtasks /Run /TN FamTutorTTS）
用法：D:/Python312/python.exe tts-backfill.py --classrooms ID1 ID2 ...
      [--base http://localhost:3000] [--proxy http://127.0.0.1:8787] [--concurrency 4]
"""
import argparse
import json
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

TMP = Path("D:/hermes-data/tmp")
CLASSROOMS = Path("D:/projects/OpenMAIC/data/classrooms")


def valid_mp3(fp):
    try:
        if fp.stat().st_size <= 1000:
            return False
        h = fp.read_bytes()[:3]
        return h[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2") or h == b"ID3"
    except Exception:
        return False


def tts_bytes(text, proxy, tries=3):
    uid = uuid.uuid4().hex[:8]
    reqf = TMP / f"_tts_req_{uid}.json"
    outf = TMP / f"_tts_out_{uid}.mp3"
    reqf.write_bytes(json.dumps({"input": text, "voice": "alloy", "response_format": "mp3"}).encode("utf-8"))
    try:
        for i in range(tries):
            r = subprocess.run(["curl.exe", "-s", "-X", "POST", proxy + "/v1/audio/speech",
                                "-H", "Content-Type: application/json",
                                "--data-binary", f"@{reqf}", "-o", str(outf),
                                "-w", "%{http_code}", "--max-time", "150"], capture_output=True)
            if r.stdout.decode().strip() == "200" and valid_mp3(outf):
                return outf.read_bytes()
            time.sleep(2 + 2 * i)
        return None
    finally:
        reqf.unlink(missing_ok=True)
        outf.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--classrooms", nargs="+", required=True)
    ap.add_argument("--base", default="http://localhost:3000")
    ap.add_argument("--proxy", default="http://127.0.0.1:8787")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    for cid in args.classrooms:
        cf = CLASSROOMS / f"{cid}.json"
        if not cf.exists():
            print(f"[{cid}] 课件不存在，跳过")
            continue
        doc = json.loads(cf.read_text(encoding="utf-8"))
        adir = CLASSROOMS / cid / "audio"
        adir.mkdir(parents=True, exist_ok=True)
        todo = []
        for scene in doc.get("scenes", []):
            order = scene.get("order")
            for a in scene.get("actions", []):
                if a.get("type") != "speech" or not a.get("text"):
                    continue
                fn = f"tts_s{order}_{a['id']}.mp3"
                fp = adir / fn
                if a.get("audioUrl") and fp.exists():
                    continue
                todo.append((a, fn, fp))
        gen, failed = 0, []
        if todo:
            with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                futs = {ex.submit(tts_bytes, a["text"], args.proxy): (a, fn, fp) for a, fn, fp in todo}
                for fut in as_completed(futs):
                    a, fn, fp = futs[fut]
                    b = fp.read_bytes() if (fp.exists() and valid_mp3(fp)) else fut.result()
                    if b:
                        fp.write_bytes(b)
                        a["audioId"] = fn[:-4]
                        a["audioUrl"] = f"{args.base}/api/classroom-media/{cid}/audio/{fn}"
                        gen += 1
                    else:
                        failed.append(a["id"])
        cf.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        stamped = sum(1 for s in doc.get("scenes", []) for a in s.get("actions", [])
                      if a.get("type") == "speech" and a.get("audioUrl"))
        total = sum(1 for s in doc.get("scenes", []) for a in s.get("actions", []) if a.get("type") == "speech")
        print(f"[{cid}] 本次生成 {gen} | 失败 {len(failed)} {failed[:6]} | stamp {stamped}/{total}")


if __name__ == "__main__":
    main()
