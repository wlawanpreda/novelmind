#!/usr/bin/env python3
"""
auto_refill_schedule_plan.py — ระบบเติมสต็อกตารางปล่อยคลิปสั้นอัตโนมัติ (Dynamic Rolling Schedule)
=============================================================================================
รักษาคิวสต็อกคลิปสั้นรอปล่อยล่วงหน้าให้ครอบคลุม 14-30 วันเสมอ:
- สแกน schedule_plan_14days.json
- ตรวจสอบจำนวนวันที่เหลือในแผน (ถ้าสต็อกที่ยังไม่ปล่อยเหลือน้อยกว่า MIN_BUFFER_DAYS วัน จะเติมเพิ่มทันที)
- ดึง Teaser วิดีโอ 9:16 ที่มีอยู่ใน Teaser_Output และมี Full Video URL จาก channel_wide_funnel_syncer
- ป้องกันการใส่คลิปหรือเรื่องซ้ำในระยะสั้น
- บันทึกขยายแผนต่อเนื่องอัตโนมัติ
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List, Set

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from channel_wide_funnel_syncer import STORY_TO_FULL_URL
import story_normalizer as sn

SB = os.path.join(ROOT, "SecondBrain")
PROJ = os.path.join(SB, "05_Active_Projects")
PLAN_FILE = os.path.join(PROJ, "schedule_plan_14days.json")
TEASER_DIR = os.path.join(PROJ, "Teaser_Output")

MIN_BUFFER_DAYS = 7  # ถ้าเหลือคลิปรอปล่อยน้อยกว่า 7 วัน ให้เติม
DEFAULT_TARGET_DAYS = 30  # ขยายแผนให้ครอบคลุม 30 วัน


def load_plan() -> Dict[str, Any]:
    if os.path.exists(PLAN_FILE):
        try:
            with open(PLAN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"schedule": []}


def save_plan(plan_data: Dict[str, Any]):
    os.makedirs(os.path.dirname(PLAN_FILE), exist_ok=True)
    plan_data["total_days"] = len(plan_data.get("schedule", []))
    plan_data["updated_at"] = datetime.now().isoformat()
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_data, f, ensure_ascii=False, indent=2)


def get_available_teasers(scheduled_videos: Set[str]) -> List[Dict[str, Any]]:
    """ค้นหาคลิป Teaser ที่มี Full Audiobook รองรับ และยังไม่ได้ถูกจัดลงในตาราง"""
    teasers = glob.glob(os.path.join(TEASER_DIR, "*.mp4"))
    candidates = []

    for t_path in sorted(teasers):
        filename = os.path.basename(t_path)
        if filename in scheduled_videos:
            continue
        
        # ค้นหา Full Video URL ที่ตรงกับเรื่อง
        base_name = filename.replace(".mp4", "")
        story_guess = base_name.rsplit("_Teaser_", 1)[0]
        
        matched_url = None
        for key, url in STORY_TO_FULL_URL.items():
            if sn.is_same_story(key, story_guess):
                matched_url = url
                break
                
        if not matched_url:
            continue
            
        # แยกตอน (ถ้ามี)
        ep_match = re.search(r"_Teaser_(\d+)", base_name)
        ep_num = int(ep_match.group(1)) if ep_match else 1
        clean_title = sn.get_canonical_title(story_guess)

        candidates.append({
            "story_title": clean_title,
            "raw_story": story_guess,
            "filename": filename,
            "video_path": t_path,
            "full_video_url": matched_url,
            "episode": ep_num,
            "hook_title": f"{clean_title} ตอนที่ {ep_num} | ฟังตัวอย่างนิยายเสียงก่อนนอน #Shorts",
            "synopsis": f"ไฮไลต์เนื้อเรื่องสุดเข้มข้นจาก {clean_title} ฟังฉบับเต็มได้ที่ลิงก์ในคอมเมนต์ปักหมุด",
            "trope": "Immersive Audiobook Highlight"
        })

    return candidates


def refill_plan(target_total_days: int = DEFAULT_TARGET_DAYS, dry_run: bool = False) -> Dict[str, Any]:
    plan = load_plan()
    schedule = plan.get("schedule", [])
    
    # นับจำนวนคลิปที่ยังรอปล่อย (ready_to_schedule หรือ scheduled_on_youtube)
    unreleased = [item for item in schedule if item.get("status") in ("ready_to_schedule", "scheduled_on_youtube")]
    print(f"[*] สถานะปัจจุบัน: แผนมีทั้งหมด {len(schedule)} วัน | กำลังรอปล่อย {len(unreleased)} วัน")
    
    if len(schedule) >= target_total_days and len(unreleased) >= MIN_BUFFER_DAYS:
        print(f"[✓] สต็อกเพียงพอแล้ว (รอปล่อย {len(unreleased)} วัน >= เกณฑ์ {MIN_BUFFER_DAYS} วัน)")
        return {"added": 0, "total": len(schedule)}

    # ดึงรายชื่อไฟล์วิดีโอที่ถูกจัดคิวไปแล้ว
    scheduled_files = {os.path.basename(item.get("video_path", "")) for item in schedule}
    candidates = get_available_teasers(scheduled_files)
    
    if not candidates:
        print("[!] ไม่มีคลิป Teaser ใหม่ที่พร้อมต่อ Funnel เหลือในคลัง")
        return {"added": 0, "total": len(schedule)}

    # คำนวณวันเริ่มต้นของคลิปที่จะเติมต่อ
    if schedule:
        last_item = schedule[-1]
        last_date = datetime.strptime(last_item["date"], "%Y-%m-%d")
        current_day = last_item.get("day", len(schedule))
    else:
        last_date = datetime.now()
        current_day = 0

    added_count = 0
    needed = target_total_days - len(schedule)
    if needed <= 0:
        needed = MIN_BUFFER_DAYS - len(unreleased)

    for cand in candidates:
        if added_count >= needed:
            break
            
        current_day += 1
        release_date = last_date + timedelta(days=added_count + 1)
        date_str = release_date.strftime("%Y-%m-%d")
        utc_iso = f"{date_str}T11:30:00Z"  # 18:30 น. เวลาไทย
        
        new_entry = {
            "day": current_day,
            "date": date_str,
            "thai_time": "18:30 น.",
            "utc_publish_at": utc_iso,
            "story_title": cand["story_title"],
            "trope": cand["trope"],
            "video_path": cand["video_path"],
            "video_exists": True,
            "full_video_url": cand["full_video_url"],
            "hook_title": cand["hook_title"],
            "synopsis": cand["synopsis"],
            "status": "ready_to_schedule"
        }
        
        schedule.append(new_entry)
        added_count += 1
        print(f"   + เพิ่ม Day {current_day} ({date_str}): {cand['story_title']} ({cand['filename']})")

    if not dry_run and added_count > 0:
        plan["schedule"] = schedule
        save_plan(plan)
        print(f"\n✅ ขยายตารางปล่อยงานเพิ่ม +{added_count} วัน (รวมเป็น {len(schedule)} วัน) เรียบร้อยแล้ว!")
    elif dry_run:
        print(f"\n[dry-run] จะเพิ่มทั้งหมด {added_count} วัน")

    return {"added": added_count, "total": len(schedule)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Auto-refill schedule plan up to N days")
    parser.add_argument("--days", type=int, default=DEFAULT_TARGET_DAYS, help="เป้าหมายจำนวนวันรวมในแผน (ค่าเริ่ม 30 วัน)")
    parser.add_argument("--dry-run", action="store_true", help="ทดสอบโดยไม่บันทึกจริง")
    args = parser.parse_args()
    
    refill_plan(target_total_days=args.days, dry_run=args.dry_run)
