#!/usr/bin/env python3
"""
ypp_velocity_tracker.py — ระบบติดตามความเร็วสู่เป้าหมาย YouTube Partner Program (1,000 Subs & 4,000 Watch Hours)
=================================================================================================================
บันทึกสถิติรายวัน คำนวณอัตราการเติบโตของคลิปยาว (Mega/Full Audiobooks) และตรวจสอบสุขภาพคิวปล่อยงานอัตโนมัติ
"""

import os
import sys
import json
from datetime import datetime
from typing import Dict, Any

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

SB = os.path.join(ROOT, "SecondBrain")
HISTORY_FILE = os.path.join(SB, "05_Active_Projects", "ypp_velocity_history.json")
PLAN_FILE = os.path.join(SB, "05_Active_Projects", "schedule_plan_14days.json")


def load_history() -> Dict[str, Any]:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"snapshots": []}


def save_history(data: Dict[str, Any]):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_velocity_report():
    overview = youtube_stats.get_channel_overview()
    all_videos = overview.get("all_videos", [])

    # แยกประเภทคลิป
    shorts_public = [v for v in all_videos if "#Shorts" in v.get("title", "") and v.get("privacy") == "public"]
    longform_public = [v for v in all_videos if "#Shorts" not in v.get("title", "") and v.get("privacy") == "public"]
    scheduled_private = [v for v in all_videos if v.get("privacy") == "private"]

    shorts_views = sum(int(v.get("views", 0)) for v in shorts_public)
    longform_views = sum(int(v.get("views", 0)) for v in longform_public)
    total_views = shorts_views + longform_views

    # บันทึก Snapshot
    hist = load_history()
    today_str = datetime.now().strftime("%Y-%m-%d")

    prev_total = total_views
    prev_long = longform_views
    if hist["snapshots"]:
        last = hist["snapshots"][-1]
        prev_total = last.get("total_views", total_views)
        prev_long = last.get("longform_views", longform_views)

    delta_total = total_views - prev_total
    delta_long = longform_views - prev_long

    snapshot = {
        "timestamp": datetime.now().isoformat(),
        "date": today_str,
        "total_views": total_views,
        "shorts_views": shorts_views,
        "longform_views": longform_views,
        "shorts_count": len(shorts_public),
        "longform_count": len(longform_public),
        "scheduled_queue_count": len(scheduled_private),
        "delta_total_views": delta_total,
        "delta_longform_views": delta_long
    }
    hist["snapshots"].append(snapshot)
    hist["snapshots"] = hist["snapshots"][-60:]  # เก็บย้อนหลัง 60 วัน
    save_history(hist)

    print("\n" + "=" * 72)
    print(" 📈 รายงานความเร็วสู่เป้าหมาย YPP (Midnight Tales Velocity Tracker)")
    print("=" * 72)
    print(f" • ยอดวิวรวมคลิปที่ออนแอร์: {total_views:,} วิว (เปลี่ยนแปลง: {delta_total:+d} วิว)")
    print(f" • ยอดวิวฝั่งคลิปยาว (สะสมชั่วโมงหลัก): {longform_views:,} วิว ({len(longform_public)} เรื่อง | {delta_long:+d} วิว)")
    print(f" • ยอดวิวฝั่งคลิปสั้น (ดึงคนดูใหม่): {shorts_views:,} วิว ({len(shorts_public)} คลิป)")
    print(f" • คลิปที่ตั้งเวลารอปล่อยบนคลาวด์ YouTube: {len(scheduled_private)} คลิป")
    print("-" * 72)
    print(" 🏆 Top 5 คลิปยาวขับเคลื่อน Watch Time สูงสุด:")
    longform_public.sort(key=lambda x: int(x.get("views", 0)), reverse=True)
    for idx, lv in enumerate(longform_public[:5], 1):
        print(f"   {idx}. [{lv['views']} วิว] {lv['title'][:58]} ({lv['vid']})")
    print("=" * 72)

    # ส่งสรุปเข้า Discord (ไม่ทำให้ stage ล้มถ้าส่งไม่ได้)
    try:
        from discord_reporter import send_ypp_velocity_to_discord
        send_ypp_velocity_to_discord(snapshot, longform_public[:5])
    except Exception as e:
        print(f"[ypp] discord report skipped: {e}")


if __name__ == "__main__":
    run_velocity_report()
