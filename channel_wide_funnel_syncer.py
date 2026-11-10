#!/usr/bin/env python3
"""
channel_wide_funnel_syncer.py — ระบบเชื่อมโยง Funnel คลิปสั้นทั้งช่องเข้าสู่ Mega & Full Audiobook
==================================================================================================
สแกนคลิปสั้น (Shorts) ที่มียอดวิวสูงสุดในช่อง แล้วแทรกสะพานเชื่อม (Funnel Block) ไว้บรรทัดบนสุดของ Description
เพื่อเปลี่ยนทราฟฟิกคนดู Shorts ให้ไหลเข้าสู่คลิปยาว (สะสม Watch Time 4,000 ชั่วโมง) อัตโนมัติ
"""

import os
import sys
import json
import argparse
from typing import Dict, Optional, List

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

FLAGSHIP_PLAYLIST = "https://www.youtube.com/playlist?list=PLW2_EmNnr5Y4"

# ตารางจับคู่คีย์เวิร์ดชื่อเรื่อง -> ลิงก์ฟังฉบับเต็ม (Mega / Full Audiobook)
STORY_TO_FULL_URL: Dict[str, str] = {
    "คุณแม่ลูกแฝด": "https://youtu.be/4jcEqeFD5wI",
    "วีรบุรุษสุดขี้เกียจ": "https://youtu.be/Bh6YtuWNZcE",
    "ตื่นตามฝันนางพยากรณ์": "https://youtu.be/3BPqQLhCgaE",
    "กระจกเงาคนตาย": "https://youtu.be/Jv0yZKuUZjk",
    "ร้านค้าเหนือโลก": "https://youtu.be/Jv0yZKuUZjk",
    "รหัสลับใต้เงา": "https://youtu.be/xWqlc-Bo_kw",
    "ยอดนักสืบสปีดรัน": "https://youtu.be/AD2u0aohB3E",
    "สมาคมประกันภัยลี้ลับ": "https://youtu.be/-KdOEn051j4",
    "กลิ่นหอมกู้วิกฤต": "https://youtu.be/ZXCYRB_2tsM",
    "กอธาม": "https://youtu.be/1P583lKnKWw",
    "หมอฟันยุคเหนือธรรมชาติ": "https://youtu.be/GqyIRz5cW8I",
    "สาวอภินิหารหัวใจเหล็ก": "https://youtu.be/Mp2zzJEyI9w",
    "ภารกิจสร้างตัว": "https://youtu.be/sXRcrilfnCg",
    "ภารกิจร้างตัว": "https://youtu.be/sXRcrilfnCg",
    "แสงอัศวินในความมืด": "https://youtu.be/WXxptSQWiuA",
    "ราชอาณาจักรสองร้อยส่วน": "https://youtu.be/nA2nRHgOxfI",
    "หนุ่มน้อยชิงบัลลังก์": "https://youtu.be/nA2nRHgOxfI",
    "เทพส่งเสริมความบันเทิง": "https://youtu.be/5pAlRn6vogM",
    "ปรมาจารย์สมาคมคนเดียว": "https://youtu.be/nDoWGwzwaiw",
    "นิมิตดวงดาวว่านหางแมว": "https://youtu.be/00xVUDjrilw",
    "หายใจในช่องว่าง": "https://youtu.be/EgNWhT7YR9A",
    "จากน้องสาวสู่พี่ใหญ่": "https://youtu.be/AwrE4AMQS4k",
    "เจ้าชายหิมะน้ำแข็ง": "https://youtu.be/j2g99CpZUEo",
    "มาร์ชั่นผู้พิชิต": "https://youtu.be/RGw0KYqBanY",
    "Succubus": "https://youtu.be/RGw0KYqBanY",
    "ดาบไร้พระเจ้า": "https://youtu.be/pB74ZaKV4tU",
    "นักรบแสงผู้ล่วงลับ": "https://youtu.be/nFyn6AApLT4",
    "ผู้สาปแช่ง": "https://youtu.be/0Vk2UGQ9QX4",
    "มหาเศรษฐียุค 90": "https://youtu.be/crSeM2ZpRpY",
    "สมาคมภูติ์ผีกวนประสาท": "https://youtu.be/XC93Gu6j8I4",
    "โลกแฟนตาซีอันเหนือจริง": "https://youtu.be/bsRVi9VyNpc",
    "แดนศรัทธา": "https://youtu.be/bsRVi9VyNpc",
    "เหล่ามือกระบี่": "https://youtu.be/bgBF3F3FNB8",
    "ดวงจันทร์แห่งเวทมนตร์": "https://youtu.be/Emd4CPU3ePQ",
    "ฟาร์มสาวปีศาจรัก": "https://youtu.be/8QBP8Me7zaI",
    "วนเกิดมาเป็นตัวเอก": "https://youtu.be/YpMdjON184w",
    "สถานีตำรวจกาววิญญาณ": "https://youtu.be/NQjROjc1hb8",
    "เมื่อนางร้ายหมดรัก": "https://youtu.be/4cM5iELFUso",
}


def resolve_full_audiobook_url(title: str) -> Optional[str]:
    for key, url in STORY_TO_FULL_URL.items():
        if key in title:
            return url
    return None


def sync_channel_shorts_funnel(limit: int = 25, dry_run: bool = False):
    print("=" * 70)
    print(f"🔗 กำลังสแกนและเชื่อมโยง Funnel คลิปสั้นยอดนิยมในช่อง (Top {limit} Shorts)...")
    print("=" * 70)

    overview = youtube_stats.get_channel_overview()
    all_videos = overview.get("all_videos", [])

    # คัดเฉพาะคลิปสั้น #Shorts ที่เป็น Public และเรียงตามยอดวิวสูงสุดก่อน
    shorts = [
        v for v in all_videos
        if "#Shorts" in v.get("title", "") and v.get("privacy") == "public"
    ]
    shorts.sort(key=lambda x: int(x.get("views", 0)), reverse=True)

    yt = youtube_stats._yt()
    updated_count = 0

    for s in shorts:
        if updated_count >= limit:
            break

        vid = s["vid"]
        views = s["views"]
        title = s["title"]

        resp = yt.videos().list(part="snippet", id=vid).execute()
        if not resp.get("items"):
            continue

        snippet = resp["items"][0]["snippet"]
        desc = snippet.get("description", "")

        # ข้ามถ้ามีบล็อก Funnel เชื่อม Playlist หลักอยู่แล้ว
        if "PLW2_EmNnr5Y4" in desc:
            continue

        full_url = resolve_full_audiobook_url(title)
        if full_url:
            funnel_header = f"""🎧 ฟังนิยายเสียงเรื่องนี้ฉบับเต็ม (รวมครบทุกตอนจบภาค):
👉 {full_url}

📻 เพลย์ลิสต์รวมนิยายเสียงจบในตอน [ฟังยาวต่อเนื่องก่อนนอน]:
👉 {FLAGSHIP_PLAYLIST}
--------------------------------------------------
"""
        else:
            funnel_header = f"""📻 ฟังนิยายเสียงเรื่องยาวจบในตอน (รวมครบทุกตอน ฟังสบายก่อนนอน):
👉 {FLAGSHIP_PLAYLIST}

🔥 เรื่องยอดฮิตประจำสัปดาห์ (คุณแม่ลูกแฝดยุค 70 รวม 20 ตอนจบ):
👉 https://youtu.be/4jcEqeFD5wI
--------------------------------------------------
"""

        new_desc = funnel_header + desc

        if dry_run:
            print(f"[DRY-RUN] จะอัปเดต {vid} ({views} วิว): {title[:45]}... -> {full_url or 'Flagship Playlist'}")
            updated_count += 1
            continue

        try:
            body = {
                "id": vid,
                "snippet": {
                    "title": snippet["title"],
                    "description": new_desc,
                    "categoryId": snippet.get("categoryId", "24"),
                    "tags": snippet.get("tags", ["นิยายเสียง", "Shorts", "นิยายเสียงก่อนนอน"])
                }
            }
            yt.videos().update(part="snippet", body=body).execute()
            updated_count += 1
            print(f"  ✅ [{updated_count}/{limit}] เชื่อม Funnel สำเร็จ ({views} วิว) | {vid} | {title[:42]}...")
        except Exception as e:
            print(f"  ⚠️ ข้าม {vid} เนื่องจากข้อผิดพลาด: {e}")

    print("=" * 70)
    print(f"🎉 เชื่อมโยง Funnel คลิปสั้นเข้าสู่คลิปยาวสำเร็จรวมทั้งสิ้น {updated_count} คลิป!")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25, help="จำนวนคลิปสูงสุดที่จะอัปเดตในรอบนี้ (ประหยัด Quota)")
    parser.add_argument("--dry-run", action="store_true", help="ทดสอบโดยไม่เขียนจริง")
    args = parser.parse_args()
    sync_channel_shorts_funnel(limit=args.limit, dry_run=args.dry_run)
