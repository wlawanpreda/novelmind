#!/usr/bin/env python3
"""
scheduled_drip_publisher.py
===========================
ระบบจัดการและส่งคลิปขึ้น YouTube แบบตั้งเวลาล่วงหน้าอัตโนมัติ (Automated Scheduled Drip Publisher)
- ดึงข้อมูลจาก SecondBrain/05_Active_Projects/schedule_plan_14days.json
- อัปโหลดคลิปขึ้น YouTube ในโหมด Private พร้อมกำหนด publishAt (UTC)
- YouTube จะทำการ Publish คลิปสู่สาธารณะอัตโนมัติตามเวลาที่กำหนด (แม้เครื่องจะปิดอยู่)
- อัปเดตสถานะและ YouTube Video ID กลับลงในแผนผังและ publish_ledger.json
"""

import os
import sys
import json
import time
from datetime import datetime, timezone
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

SB = os.path.join(ROOT, "SecondBrain")
PLAN_FILE = os.path.join(SB, "05_Active_Projects", "schedule_plan_14days.json")
LEDGER_FILE = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")


def load_plan():
    if not os.path.exists(PLAN_FILE):
        return None
    with open(PLAN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_plan(plan):
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=2)


def load_ledger():
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_ledger(data):
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def show_schedule_status():
    plan = load_plan()
    if not plan:
        print("❌ ไม่พบไฟล์ schedule_plan_14days.json")
        return

    print("\n" + "=" * 70)
    print(" 📅 แผนผังคลังสต็อกและการปล่อยผลงาน 14 วัน (Midnight Tales)")
    print(f" ⏰ ช่วงเวลาทองประจำวัน: {plan.get('golden_hour_thai')}")
    print("=" * 70)

    for item in plan.get("schedule", []):
        day = item["day"]
        date = item["date"]
        time_th = item["thai_time"]
        story = item["story_title"]
        status = item["status"]
        vid = item.get("youtube_id", "-")

        icon = "⏳"
        if status == "scheduled_on_youtube":
            icon = "🚀 [ตั้งเวลาบน YouTube แล้ว]"
        elif status == "published":
            icon = "✅ [ออนแอร์แล้ว]"
        else:
            icon = "📦 [สต็อกพร้อมส่ง]"

        print(f" Day {day:02d} ({date} @ {time_th}) | {icon}")
        print(f"   • เรื่อง: {story}")
        print(f"   • Hook Title: {item['hook_title']}")
        if vid != "-":
            print(f"   • YouTube URL: https://youtu.be/{vid}")
        print("-" * 70)


def schedule_video_on_youtube(day_num: int) -> dict:
    plan = load_plan()
    if not plan:
        return {"success": False, "error": "plan_not_found"}

    target = None
    for it in plan["schedule"]:
        if it["day"] == day_num:
            target = it
            break

    if not target:
        return {"success": False, "error": f"day_{day_num}_not_found"}

    video_path = target["video_path"]
    if not os.path.exists(video_path):
        return {"success": False, "error": f"video_file_not_found: {video_path}"}

    print(f"\n🚀 [YouTube Scheduled Upload] กำลังอัปโหลด Day {day_num}: {target['story_title']}")
    print(f"   📅 กำหนดเวลาปล่อย (ไทย): {target['date']} เวลา {target['thai_time']}")
    print(f"   ⏱️ UTC Publish Time: {target['utc_publish_at']}")

    yt = youtube_stats._yt()

    # ประกอบ Description ชวนฟังคลิปเต็ม + ReadAWrite Link
    desc = f"""🎧 {target['story_title']} — ไฮไลต์ตอนที่ 1 (Shorts)
{target['synopsis']}

▶️ ฟังนิยายเสียงฉบับเต็ม รวมครบทุกตอนจบภาค ได้ที่นี่:
👉 {target['full_video_url']}

📖 ติดตามอ่านฉบับเต็มบน ReadAWrite (นามปากกา: เงาพันจันทร์)
✨ ช่อง Midnight Tales · มิดไนต์เทล
กดติดตามและกดกระดิ่งแจ้งเตือน เพื่อไม่พลาดนิยายเรื่องใหม่ทุกวัน!

#นิยายเสียง #หนังสือนิยาย #นิยายเสียงก่อนนอน #{target['story_title'].replace(' ', '')} #Shorts #Audiobook"""

    tags = ["นิยายเสียง", "Shorts", "นิยายเสียงก่อนนอน", "Full Audiobook", target['story_title']]

    body = {
        "snippet": {
            "title": target["hook_title"][:99],
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

    try:
        media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = req.next_chunk()
            if status:
                print(f"   ⏳ กำลังส่งข้อมูล: {int(status.progress() * 100)}%")

        vid = resp.get("id")
        yt_url = f"https://youtu.be/{vid}"
        print(f"   ✅ อัปโหลดและตั้งเวลาปล่อยสำเร็จ!")
        print(f"   🔗 YouTube URL: {yt_url}")
        print(f"   ⏰ ระบบ YouTube จะเปิดเป็น Public อัตโนมัติวันที่ {target['date']} เวลา {target['thai_time']}")

        # อัปเดตแผนและ ledger
        target["status"] = "scheduled_on_youtube"
        target["youtube_id"] = vid
        target["youtube_url"] = yt_url
        target["scheduled_at_utc"] = target["utc_publish_at"]
        save_plan(plan)

        ledger = load_ledger()
        v_name = os.path.basename(video_path)
        ledger[v_name] = {
            "youtube": yt_url,
            "scheduled": target["utc_publish_at"],
            "type": "shorts_teaser",
            "day": day_num
        }
        save_ledger(ledger)

        return {"success": True, "vid": vid, "url": yt_url}
    except Exception as e:
        print(f"   ❌ ข้อผิดพลาด: {e}")
        return {"success": False, "error": str(e)}


def sync_and_refresh_statuses():
    """ซิงค์สถานะคลิปที่ถึงเวลาเผยแพร่แล้วให้เป็น 'published' อัตโนมัติ"""
    plan = load_plan()
    if not plan:
        return 0
    now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = False
    for it in plan.get("schedule", []):
        if it.get("status") == "scheduled_on_youtube":
            if it.get("utc_publish_at", "") <= now_utc_str:
                it["status"] = "published"
                updated = True
                print(f"   ✨ ซิงค์สถานะ: Day {it['day']} ({it['story_title']}) ถึงเวลาเผยแพร่แล้ว -> ปรับเป็น 'published'")
    if updated:
        save_plan(plan)
    return plan


def cron_tick():
    """ตรวจสอบและส่งคิวคลิปถัดไปขึ้น YouTube อัตโนมัติ (คงสต็อกล่วงหน้า 3 วันเสมอ)"""
    plan = sync_and_refresh_statuses()
    if not plan:
        return

    scheduled_items = [it for it in plan.get("schedule", []) if it["status"] == "scheduled_on_youtube"]
    scheduled_count = len(scheduled_items)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏳ Cron tick: มีคลิปรอคิวปล่อยบน YouTube อยู่ {scheduled_count} คลิป")

    # รักษาบัฟเฟอร์ล่วงหน้า 3 คลิปเสมอ
    while scheduled_count < 3:
        found_next = False
        for it in plan.get("schedule", []):
            if it["status"] == "ready_to_schedule":
                print(f"   🚀 บัฟเฟอร์เหลือน้อย ({scheduled_count}/3): พบสต็อกพร้อมส่ง Day {it['day']} ({it['story_title']}) -> ดำเนินการตั้งเวลาล่วงหน้า...")
                res = schedule_video_on_youtube(it["day"])
                if res.get("success"):
                    scheduled_count += 1
                    found_next = True
                    plan = load_plan()  # reload
                break
        if not found_next:
            break



if __name__ == "__main__":
    args = sys.argv[1:]
    if "--status" in args or not args:
        show_schedule_status()
    elif "--schedule" in args:
        d_idx = args.index("--schedule")
        day_val = int(args[d_idx + 1]) if len(args) > d_idx + 1 else 1
        schedule_video_on_youtube(day_val)
    elif "--cron-tick" in args:
        cron_tick()
