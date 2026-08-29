"""
update_privacy.py — สลับสถานะวิดีโอ YouTube จาก unlisted -> public
===================================================================

ใช้สำหรับเปิดการมองเห็นสาธารณะให้คลิปใน YouTube เพื่อเริ่มรับ Organic Views

CLI:
  python update_privacy.py --status           # ตรวจสอบสถานะ privacy ปัจจุบันของทุกคลิป
  python update_privacy.py --public --limit 3 # ปรับเป็น public วันละ 3 คลิป (ป้องกัน spam)
  python update_privacy.py --public --all     # ปรับเป็น public ทั้งหมดทันที
"""
from __future__ import annotations

import os
import re
import sys
import argparse
import youtube_stats

def update_privacy(mode: str = "status", limit: int = 3, target_privacy: str = "public"):
    try:
        yt = youtube_stats._yt()
    except Exception as e:
        print(f"❌ ไม่สามารถเชื่อมต่อ YouTube API: {e}")
        return

    rows = youtube_stats.collect()
    print(f"[*] ตรวจพบ {len(rows)} วิดีโอในระบบ...")
    stats = youtube_stats.fetch_stats(rows)

    unlisted_vids = [s for s in stats if s["privacy"] == "unlisted"]
    public_vids = [s for s in stats if s["privacy"] == "public"]
    private_vids = [s for s in stats if s["privacy"] == "private"]

    print(f"\n📊 สรุปสถานะปัจจุบัน:")
    print(f"  • สาธารณะ (Public):  {len(public_vids)} คลิป")
    print(f"  • ซ่อนไว้ (Unlisted): {len(unlisted_vids)} คลิป")
    print(f"  • ส่วนตัว (Private):  {len(private_vids)} คลิป")

    if mode == "status":
        print("\n💡 คำแนะนำ: รัน 'python update_privacy.py --public --limit 3' เพื่อเริ่มปล่อยคลิปเป็นสาธารณะวันละ 3 คลิป")
        return

    if mode == "update":
        targets = unlisted_vids[:limit] if limit > 0 else unlisted_vids
        if not targets:
            print("\n✅ ไม่มีคลิป unlisted ที่ต้องปรับแล้ว ทุกคลิปเป็นสาธารณะแล้ว!")
            return

        print(f"\n🚀 กำลังปรับสถานะ {len(targets)} คลิปเป็น '{target_privacy}'...")
        updated_count = 0
        for item in targets:
            vid = item["vid"]
            title = item["title"]
            try:
                yt.videos().update(
                    part="status",
                    body={
                        "id": vid,
                        "status": {
                            "privacyStatus": target_privacy
                        }
                    }
                ).execute()
                print(f"  ✅ [สำเร็จ] {vid} -> {target_privacy} : {title[:50]}")
                updated_count += 1
            except Exception as e:
                print(f"  ❌ [ล้มเหลว] {vid} : {e}")

        print(f"\n🎉 ปรับสถานะสำเร็จทั้งหมด {updated_count}/{len(targets)} คลิป!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Privacy Manager")
    parser.add_argument("--status", action="store_true", help="ดูสถานะคลิปทั้งหมด")
    parser.add_argument("--public", action="store_true", help="ปรับเป็น Public")
    parser.add_argument("--unlisted", action="store_true", help="ปรับเป็น Unlisted")
    parser.add_argument("--limit", type=int, default=3, help="จำนวนคลิปที่จะปรับ (default: 3)")
    parser.add_argument("--all", action="store_true", help="ปรับทั้งหมดโดยไม่จำกัดจำนวน")

    args = parser.parse_args()

    if args.public:
        lim = 0 if args.all else args.limit
        update_privacy(mode="update", limit=lim, target_privacy="public")
    elif args.unlisted:
        lim = 0 if args.all else args.limit
        update_privacy(mode="update", limit=lim, target_privacy="unlisted")
    else:
        update_privacy(mode="status")
