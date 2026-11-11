#!/usr/bin/env python3
"""
backfill_audioscripts.py — เติม AudioScript ให้ตอนที่มีนิยายแล้วแต่ยังไม่มีบทเสียง
=================================================================================
ช่องว่างที่พบ: บางตอนมี Chapter แต่ไม่มี AudioScript → audio_engine ไม่ผลิตเสียง → ไม่ครบเกณฑ์ทำ Mega
สคริปต์นี้เติมให้ทีละน้อย/รอบ (ใช้ LLM ผ่าน run_stage_6_audio_script — มีค่า token) โดยเรียงลำดับ:
เรื่องที่ "ใกล้ครบเกณฑ์ Mega" ก่อน (มีเสียงมากแต่ยังไม่ถึง) แล้วค่อยเรื่องอื่น

    python backfill_audioscripts.py --dry-run
    python backfill_audioscripts.py --max 2        # เติมสูงสุด 2 ตอน/รอบ (ค่าเริ่ม ANSRE_AUDIOSCRIPT_BACKFILL_PER_RUN=2)
"""
from __future__ import annotations

import os
import re
import sys
import glob
import argparse
from collections import defaultdict

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
PROJ = os.path.join(ROOT, "SecondBrain", "05_Active_Projects")
CH_DIR = os.path.join(PROJ, "Chapters")
AS_DIR = os.path.join(PROJ, "Audio_Scripts")
MEGA_MIN = int(os.environ.get("ANSRE_MEGA_MIN_CHAPTERS", "15"))
MIN_CHARS = int(os.environ.get("ANSRE_MIN_CHAPTER_CHARS", "1500"))


def find_missing():
    """คืน list ของ (priority, title, n, chapter_path) ตอนที่ขาด AudioScript"""
    chapters = defaultdict(dict)
    scripts = defaultdict(set)
    for p in glob.glob(os.path.join(CH_DIR, "*_Chapter_*.md")):
        m = re.match(r"^(.*)_Chapter_(\d+)\.md$", os.path.basename(p))
        if m:
            chapters[m[1]][int(m[2])] = p
    for p in glob.glob(os.path.join(AS_DIR, "*_AudioScript_*.md")):
        m = re.match(r"^(.*)_AudioScript_(\d+)\.md$", os.path.basename(p))
        if m and os.path.getsize(p) > 200:
            scripts[m[1]].add(int(m[2]))

    # เรื่องที่ทำ Mega ไปแล้วไม่เร่งเติม (ผลตอบแทนต่ำกว่า) — ใช้ตัวตรวจเดียวกับ auto_mega
    try:
        import auto_mega
        built = auto_mega.built_story_names(auto_mega.load_ledger())
        pub = auto_mega.published_mega_keys()
        has_mega = lambda t: auto_mega._already_built(t, built, pub)
    except Exception:
        has_mega = lambda t: False

    out = []
    for title, chs in chapters.items():
        mega_done = has_mega(title)
        have = len(scripts[title])
        total = len(chs)
        for n, path in sorted(chs.items()):
            if n in scripts[title]:
                continue
            # priority: (กลุ่ม: ยังไม่มี Mega & ตอนพอ → ยังไม่มี Mega → มี Mega แล้ว), ขาดน้อยสุดก่อน
            reachable = total >= MEGA_MIN
            shortfall = max(0, MEGA_MIN - have)
            group = 2 if mega_done else (0 if reachable else 1)
            out.append(((group, shortfall, -have, n), title, n, path))
    out.sort(key=lambda x: x[0])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=int(os.environ.get("ANSRE_AUDIOSCRIPT_BACKFILL_PER_RUN", "2")))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    missing = find_missing()
    print(f"[backfill] ขาด AudioScript {len(missing)} ตอน")
    if not missing:
        return 0
    batch = missing[: args.max]
    for _, title, n, _p in batch:
        print(f"   → {title} ตอน {n}")
    if args.dry_run:
        return 0

    from agent_writer import run_stage_6_audio_script
    from run_log import log_event
    os.makedirs(AS_DIR, exist_ok=True)
    done = 0
    for _, title, n, path in batch:
        try:
            with open(path, "r", encoding="utf-8") as f:
                chapter = f.read()
            if len(chapter) < MIN_CHARS:
                print(f"[backfill] ข้าม {title} ตอน {n}: เนื้อหาสั้นเกิน ({len(chapter)})")
                continue
            script = run_stage_6_audio_script(f"{title} ตอนที่ {n}", chapter)
            try:
                from agent_auditor import sanitize_meta_talk
                script = sanitize_meta_talk(script)
            except Exception:
                pass
            if not script or len(script) < 300:
                print(f"[backfill] ข้าม {title} ตอน {n}: บทเสียงที่ได้สั้นผิดปกติ (LLM ล่ม?)")
                continue
            with open(os.path.join(AS_DIR, f"{title}_AudioScript_{n:02d}.md"), "w", encoding="utf-8") as f:
                f.write(script)
            done += 1
            log_event("audioscript_backfill", title=title, chapter=n, chars=len(script))
            print(f"[backfill] ✓ {title} ตอน {n} ({len(script)} ตัวอักษร)")
        except Exception as e:
            print(f"[backfill] ✗ {title} ตอน {n}: {e}")
            log_event("audioscript_backfill_error", title=title, chapter=n, error=str(e))
    print(f"[backfill] เติมสำเร็จ {done}/{len(batch)} ตอน • คงเหลือ {len(missing) - done}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
