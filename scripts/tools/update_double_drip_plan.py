#!/usr/bin/env python3
"""
update_double_drip_plan.py
==========================
อัปเกรดระบบปล่อยงานสู่ "Double Drip 2 Slots/Day"
Slot 1: 12:15 น. (พักเที่ยง)
Slot 2: 19:45 น. (หัวค่ำก่อนนอน)
"""

import os
import sys
import json
from datetime import datetime, timezone
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

SB = os.path.join(ROOT, "SecondBrain")
PLAN_FILE = os.path.join(SB, "05_Active_Projects", "schedule_plan_14days.json")
LEDGER_FILE = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")


def update_plan_structure():
    with open(PLAN_FILE, "r", encoding="utf-8") as f:
        plan = json.load(f)

    plan["strategy"] = "Double Drip (วันละ 2 รอบ: พักเที่ยง 12:15 น. และ หัวค่ำ 19:45 น.)"
    plan["golden_hours_thai"] = ["12:15 น. (พักเที่ยง พักสายตา)", "19:45 น. (ช่วงพีกคนฟังนิยายเสียงก่อนนอน)"]

    # อัปเดต Day 4, Day 5, Day 6 ในไฟล์
    for it in plan["schedule"]:
        if it["day"] == 4:
            it["thai_time"] = "19:45 น."
            it["utc_publish_at"] = "2026-11-10T12:45:00Z"
            it["slot"] = "หัวค่ำก่อนนอน"
        elif it["day"] == 5:
            it["date"] = "2026-11-11"
            it["thai_time"] = "12:15 น."
            it["utc_publish_at"] = "2026-11-11T05:15:00Z"
            it["slot"] = "พักเที่ยง"
        elif it["day"] == 6:
            it["date"] = "2026-11-11"
            it["thai_time"] = "19:45 น."
            it["utc_publish_at"] = "2026-11-11T12:45:00Z"
            it["slot"] = "หัวค่ำก่อนนอน"
        elif it["day"] == 7:
            it["date"] = "2026-11-12"
            it["thai_time"] = "12:15 น."
            it["utc_publish_at"] = "2026-11-12T05:15:00Z"
            it["slot"] = "พักเที่ยง"
        elif it["day"] == 8:
            it["date"] = "2026-11-12"
            it["thai_time"] = "19:45 น."
            it["utc_publish_at"] = "2026-11-12T12:45:00Z"
            it["slot"] = "หัวค่ำก่อนนอน"

    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)

    print("✅ อัปเดตโครงสร้างแผน Double Drip เรียบร้อย")


def schedule_slot(day_num: int):
    with open(PLAN_FILE, "r", encoding="utf-8") as f:
        plan = json.load(f)

    target = None
    for it in plan["schedule"]:
        if it["day"] == day_num:
            target = it
            break

    if not target or target.get("status") == "scheduled_on_youtube":
        print(f"ข้าม Day {day_num} (ตั้งเวลาแล้วหรือไม่พบ)")
        return

    video_path = target["video_path"]
    if not os.path.exists(video_path):
        print(f"❌ ไม่พบไฟล์วิดีโอ: {video_path}")
        return

    print(f"\n🚀 [YouTube Double Drip Upload] กำลังอัปโหลด Day {day_num}: {target['story_title']}")
    print(f"   📅 กำหนดเวลาปล่อย (ไทย): {target['date']} เวลา {target['thai_time']} ({target.get('slot', '-')})")
    print(f"   ⏱️ UTC Publish Time: {target['utc_publish_at']}")

    yt = youtube_stats._yt()
    desc = f"""🎧 {target['story_title']} — ไฮไลต์ตอนที่ 1 (Shorts)
{target['synopsis']}

▶️ ฟังนิยายเสียงฉบับเต็ม รวมครบทุกตอนจบภาค ได้ที่นี่:
👉 {target['full_video_url']}

📻 รวมนิยายเสียงจบในตอน [ฟังยาวต่อเนื่องก่อนนอน]:
👉 https://www.youtube.com/playlist?list=PLW2_EmNnr5Y4

📖 ติดตามอ่านฉบับเต็มบน ReadAWrite (นามปากกา: เงาพันจันทร์)
✨ ช่อง Midnight Tales · มิดไนต์เทล
กดติดตามและกดกระดิ่งแจ้งเตือน เพื่อไม่พลาดนิยายเรื่องใหม่ทุกวัน!

#นิยายเสียง #หนังสือนิยาย #นิยายเสียงก่อนนอน #{target['story_title'].replace(' ', '')} #Shorts #Audiobook"""

    tags = ["นิยายเสียง", "Shorts", "นิยายเสียงก่อนนอน", "Full Audiobook", target['story_title']]
    body = {
        "snippet": {
            "title": target["hook_title"][:95],
            "description": desc,
            "tags": tags,
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": "private",
            "publishAt": target["utc_publish_at"],
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"   ⏳ กำลังส่งข้อมูล: {int(status.progress() * 100)}%")

    vid = resp.get("id")
    yt_url = f"https://youtu.be/{vid}"
    print(f"   ✅ อัปโหลดและตั้งเวลาปล่อยสำเร็จ! ID: {vid}")
    print(f"   🔗 YouTube URL: {yt_url}")

    target["status"] = "scheduled_on_youtube"
    target["youtube_id"] = vid
    target["youtube_url"] = yt_url
    target["scheduled_at_utc"] = target["utc_publish_at"]

    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    update_plan_structure()
    # ส่ง Day 7 (พฤหัส 12 พ.ย. 12:15 น.) ขึ้นตั้งเวลาเพื่อเติมบัฟเฟอร์ล่วงหน้า
    schedule_slot(7)
