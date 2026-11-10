#!/usr/bin/env python3
"""
funnel_retention_booster.py
===========================
เครื่องมือเร่งอัตราการแปลงยอดวิว (Funnel Conversion Booster)
- ปรับปรุง Description ของ Shorts ยอดนิยม ให้ชี้ตรงไปยัง "Mega Audiobook" คลิปยาว 1 ชั่วโมง
- เชื่อมต่อ Playlist คลังนิยายจบในตอน
- เพิ่ม Call-To-Action (CTA) กระตุ้นการกดติดตามและคอมเมนต์
"""

import os
import sys
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

FLAGSHIP_PLAYLIST = "https://www.youtube.com/playlist?list=PLW2_EmNnr5Y4"
MEGA_TWINS_URL = "https://youtu.be/4jcEqeFD5wI"
MEGA_SPEEDRUN_URL = "https://youtu.be/AD2u0aohB3E"
MEGA_INSURANCE_URL = "https://youtu.be/nvzsUnWx86E"


def boost_twins_shorts():
    """เชื่อมต่อ Shorts ซีรีส์คุณแม่ลูกแฝดยุค 70 ไปยัง Mega 57 นาที"""
    yt = youtube_stats._yt()
    target_ids = ["l8QZWeP9bnY", "ewmXysxakjQ"]

    for vid in target_ids:
        try:
            resp = yt.videos().list(part="snippet", id=vid).execute()
            if not resp.get("items"):
                continue
            item = resp["items"][0]
            snippet = item["snippet"]

            title = snippet["title"]
            desc = snippet["description"]

            # ถ้ายังไม่มีลิงก์ Mega ให้แทรกไว้ด้านบนสุด
            if "4jcEqeFD5wI" not in desc:
                mega_hook = f"""🎧 ฟังนิยายเสียงฉบับเต็ม "รวมครบ 20 ตอนจบ" (ยาวเกือบ 1 ชม.เต็ม):
👉 {MEGA_TWINS_URL}

📻 รวมนิยายเสียงจบในตอน [ฟังยาวต่อเนื่องก่อนนอน]:
👉 {FLAGSHIP_PLAYLIST}
--------------------------------------------------
"""
                new_desc = mega_hook + desc
                snippet["description"] = new_desc

                update_body = {
                    "id": vid,
                    "snippet": {
                        "title": title,
                        "description": new_desc,
                        "categoryId": snippet.get("categoryId", "24"),
                        "tags": snippet.get("tags", [])
                    }
                }
                yt.videos().update(part="snippet", body=update_body).execute()
                print(f"✅ บูสต์ Funnel สำเร็จสำหรับคลิป {vid}: {title}")
            else:
                print(f"ℹ️ คลิป {vid} มีลิงก์ Mega เชื่อมต่ออยู่แล้ว")

        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดกับคลิป {vid}: {e}")


def main():
    print("=" * 60)
    print("🚀 เริ่มกระบวนการ Funnel & Retention Booster...")
    print("=" * 60)
    boost_twins_shorts()
    print("🎉 ดำเนินการเพิ่มประสิทธิภาพ Funnel เรียบร้อยแล้ว!")


if __name__ == "__main__":
    main()
