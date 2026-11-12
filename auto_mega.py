#!/usr/bin/env python3
"""
auto_mega.py — เลือกเรื่อง + กำหนดเวลาปล่อย Mega Audiobook อัตโนมัติ
====================================================================
เลือกนิยายที่มีไฟล์เสียงครบตามเกณฑ์ (ANSRE_MEGA_MIN_CHAPTERS, ค่าเริ่ม 15) และยังไม่เคยทำ Mega
แล้วเรียก mega_audiobook_pipeline.build_mega_audiobook พร้อมตั้งเวลา Golden Hour ว่างถัดไป

    python auto_mega.py --plan        # แสดงว่าจะเลือกเรื่องไหน/เวลาไหน (ไม่ทำจริง)
    python auto_mega.py               # ผลิต+อัปโหลด 1 เรื่อง (ถ้าครบ cooldown)
    python auto_mega.py --no-upload   # ผลิตไฟล์อย่างเดียว ไม่ขึ้น YouTube

ปลอดภัย/idempotent: บันทึกใน mega_ledger.json, ทำสูงสุด 1 เรื่องต่อรอบ,
เว้นระยะอย่างน้อย ANSRE_MEGA_EVERY_DAYS (ค่าเริ่ม 3) วัน, ไม่ชนช่องเวลาในแผน 14 วัน
"""
from __future__ import annotations

import os
import re
import sys
import json
import glob
import argparse
from datetime import datetime, timedelta, timezone
from typing import Optional, Set

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

SB = os.path.join(ROOT, "SecondBrain")
PROJ = os.path.join(SB, "05_Active_Projects")
LEDGER = os.path.join(PROJ, "mega_ledger.json")
PLAN = os.path.join(PROJ, "schedule_plan_14days.json")
MEGA_EXPORTS = os.path.join(PROJ, "Exports", "Mega_Audiobooks")

TZ_TH = timezone(timedelta(hours=7))
GOLDEN_HOURS = [(7, 30), (12, 0), (17, 30), (20, 30)]  # เวลาไทย ตรงกับ auto_release_scheduler
MIN_LEAD_HOURS = 36
PUBLISH_LEDGER = os.path.join(PROJ, "publish_ledger.json")


import story_normalizer as sn

def published_mega_keys() -> Set[str]:
    """Mega ที่ผลิต/ตั้งเวลาไว้แล้วในอดีตผ่าน publish_ledger (type=mega_audiobook) → ชื่อเรื่อง normalize"""
    keys: Set[str] = set()
    try:
        with open(PUBLISH_LEDGER, "r", encoding="utf-8") as f:
            for fname, v in json.load(f).items():
                if isinstance(v, dict) and v.get("type") == "mega_audiobook":
                    base = fname.split("_Mega", 1)[0]
                    keys.add(sn.normalize_key(base))
    except Exception:
        pass
    return keys


def _already_built(story: str, built: Set[str], pub_keys: Set[str]) -> bool:
    if story in built:
        return True
    return any(sn.is_same_story(story, k) for k in pub_keys)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def load_ledger() -> dict:
    try:
        with open(LEDGER, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"items": []}


def save_ledger(data: dict) -> None:
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with open(LEDGER, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def built_story_names(ledger: dict) -> Set[str]:
    """เรื่องที่เคยทำ Mega แล้ว: จาก ledger + Metadata ที่ผลิตด้วยมือก่อนหน้านี้"""
    names = {it["story_name"] for it in ledger.get("items", []) if it.get("story_name")}
    for p in glob.glob(os.path.join(MEGA_EXPORTS, "*_Mega_Metadata.json")):
        try:
            with open(p, "r", encoding="utf-8") as f:
                n = json.load(f).get("story_name")
            if n:
                names.add(n)
        except Exception:
            pass
    return names


def _is_contiguous(files) -> bool:
    """ตอนต้องเรียงต่อเนื่อง 1..N ไม่ขาดกลางเรื่อง (Mega ที่ข้ามตอนจะเนื้อเรื่องกระโดด)"""
    nums = sorted(int(m.group(1)) for f in files
                  if (m := re.search(r"_Audiobook_(\d+)\.mp3$", f)))
    return bool(nums) and nums == list(range(1, len(nums) + 1))


def pick_story(min_chapters: int, built: Set[str]) -> Optional[str]:
    from mega_audiobook_pipeline import scan_available_series
    series = scan_available_series()
    pub_keys = published_mega_keys()
    cands = [(len(files), name) for name, files in series.items()
             if len(files) >= min_chapters and name != "Mock"
             and _is_contiguous(files)
             and not _already_built(name, built, pub_keys)]
    if not cands:
        return None
    cands.sort(key=lambda x: (-x[0], x[1]))
    return cands[0][1]


def _taken_slots(ledger: dict) -> Set[str]:
    taken = {it.get("publish_at") for it in ledger.get("items", [])}
    try:
        with open(PLAN, "r", encoding="utf-8") as f:
            taken |= {it.get("utc_publish_at") for it in json.load(f).get("schedule", [])}
    except Exception:
        pass
    try:
        with open(PUBLISH_LEDGER, "r", encoding="utf-8") as f:
            for v in json.load(f).values():
                if isinstance(v, dict):
                    taken |= {v.get("scheduled"), v.get("publish_at")}
    except Exception:
        pass
    return {t for t in taken if t}


def next_free_slot(ledger: dict, now: Optional[datetime] = None) -> str:
    """Golden Hour ว่างถัดไป (>= MIN_LEAD_HOURS จากตอนนี้) คืนค่า UTC ISO แบบ ...Z"""
    now = now or datetime.now(TZ_TH)
    taken = _taken_slots(ledger)
    earliest = now + timedelta(hours=MIN_LEAD_HOURS)
    for d in range(0, 60):
        day = (earliest + timedelta(days=d)).date()
        for h, m in GOLDEN_HOURS:
            local = datetime(day.year, day.month, day.day, h, m, tzinfo=TZ_TH)
            if local < earliest:
                continue
            iso = local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if iso not in taken:
                return iso
    raise RuntimeError("ไม่พบช่องเวลาว่างใน 60 วัน")


def cooldown_ok(ledger: dict, every_days: int) -> bool:
    items = ledger.get("items", [])
    if not items:
        return True
    try:
        last = datetime.fromisoformat(items[-1]["created_at"])
    except Exception:
        return True
    return datetime.now() - last >= timedelta(days=every_days)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="แสดงแผนอย่างเดียว ไม่ผลิต")
    ap.add_argument("--no-upload", action="store_true", help="ผลิตไฟล์ แต่ไม่อัปโหลด YouTube")
    ap.add_argument("--force", action="store_true", help="ข้าม cooldown")
    args = ap.parse_args()

    min_ch = _int_env("ANSRE_MEGA_MIN_CHAPTERS", 15)
    every = _int_env("ANSRE_MEGA_EVERY_DAYS", 3)
    ledger = load_ledger()

    if not args.plan and not args.force and not cooldown_ok(ledger, every):
        print(f"[auto_mega] ข้าม — ยังไม่ครบ cooldown {every} วัน")
        return 0

    story = pick_story(min_ch, built_story_names(ledger))
    if not story:
        print(f"[auto_mega] ไม่มีเรื่องที่ครบเกณฑ์ (>= {min_ch} ตอน และยังไม่เคยทำ Mega)")
        return 0
    slot = None if args.no_upload else next_free_slot(ledger)

    if args.plan:
        print(f"[auto_mega] แผน: เรื่อง='{story}' เวลาปล่อย(UTC)={slot or '(ไม่อัปโหลด)'}")
        return 0

    from mega_audiobook_pipeline import build_mega_audiobook
    from run_log import log_event
    log_event("mega_start", story=story, publish_at=slot)
    meta = build_mega_audiobook(story, schedule_utc=slot)
    yt = meta.get("youtube_result", {})
    ledger.setdefault("items", []).append({
        "story_name": story,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "publish_at": slot,
        "youtube_id": yt.get("youtube_id"),
        "url": yt.get("url"),
        "title": meta.get("youtube_title"),
    })
    save_ledger(ledger)
    log_event("mega_done", story=story, publish_at=slot, youtube_id=yt.get("youtube_id"))
    try:
        from discord_reporter import send_discord_message
        send_discord_message({"embeds": [{
            "title": "🎬 Mega Audiobook ใหม่",
            "description": f"**{meta.get('youtube_title', story)}**\n{yt.get('url', '(ยังไม่อัปโหลด)')}",
            "color": 0xF59E0B,
            "fields": [{"name": "⏰ ปล่อย (UTC)", "value": f"`{slot or '-'}`", "inline": True}],
            "footer": {"text": "ANSRE Auto Mega"}}]})
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
