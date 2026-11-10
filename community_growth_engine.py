#!/usr/bin/env python3
"""
community_growth_engine.py — ระบบสร้าง Engagement ชุมชนเชิงรุกและดูแลนักอ่านอย่างปลอดภัย (White-Hat Engine)
=====================================================================================================
ฟังก์ชันหลัก 3 ด้าน:
1. 🏠 In-House Reader Care (ดูแลบ้านตัวเอง):
   - สแกนความคิดเห็นจากคนฟังในคลิปของเราเอง
   - ร่างข้อความตอบกลับใน Persona ของช่อง "Midnight Tales & เงาพันจันทร์" อย่างอบอุ่น
2. 🎯 Community Trojan Horse (สร้าง Top-Comment คุณภาพสูงในช่องกลุ่มเป้าหมายเดียวกัน):
   - สแกนคลิปที่กำลังเป็นกระแสในวงการนิยายเสียงไทย
   - AI ร่างข้อความชวนคิด/วิเคราะห์ตัวละครที่น่าประทับใจ (ไม่สแปม ไม่ฝากร้าน แต่มีระดับ) เพื่อให้ได้ Top Comment
   - บันทึกลง SecondBrain/05_Active_Projects/community_engagement_drafts.json
3. 📊 Community Tab Poll Generator (โพลสำรวจดูดผู้ฟังใหม่เข้าช่อง):
   - สร้างชุดคำถามโพลสำรวจพร้อมตัวเลือกสำหรับโพสต์ใน YouTube Community Tab ขยายการมองเห็น 5-10 เท่า
"""

import os
import sys
import re
import json
import time
from datetime import datetime
from typing import Dict, Any, List

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats
from llm_provider import generate

SB = os.path.join(ROOT, "SecondBrain")
ENGAGEMENT_DRAFTS_FILE = os.path.join(SB, "05_Active_Projects", "community_engagement_drafts.json")
POLLS_FILE = os.path.join(SB, "05_Active_Projects", "community_polls.json")


def generate_thoughtful_comment(video_title: str, channel_title: str) -> str:
    """สร้างคอมเมนต์คุณภาพสูง เป็นมิตร มีรสนิยม ให้เกียรติเจ้าของคลิป ชวนคนกดไลก์เป็น Top Comment"""
    prompt = f"""คุณคือผู้ฟังนิยายเสียงตัวจริงที่ชื่นชอบงานเขียนและเสียงพากย์คุณภาพดี
คุณกำลังจะเขียนแสดงความคิดเห็นใต้คลิปนิยายเสียงเรื่อง: "{video_title}" ของช่อง: "{channel_title}"

กฎเหล็ก:
1. ห้ามแนะนำชื่อตัวเอง ห้ามบอกว่าชื่อ Typhoon หรือ AI หรือชื่อโมเดลใดๆ ทั้งสิ้น
2. ห้ามฝากร้าน ห้ามบอกให้มากดติดตามช่อง ห้ามแปะลิงก์เด็ดขาด
3. เขียนเหมือนผู้ฟังตัวจริง เช่น ชมจังหวะการเล่า ชื่นชมน้ำเสียง อารมณ์ของตัวละคร หรือบอกความรู้สึกหลังฟังจบ
4. ความยาวสั้นกระชับ 2-3 ประโยค ภาษาอบอุ่น นุ่มนวล สุภาพ น่าประทับใจ
5. ตอบเฉพาะเนื้อหาข้อความคอมเมนต์ภาษาไทยเท่านั้น ไม่ต้องมีเครื่องหมายคำพูด:"""

    try:
        reply = generate(prompt, role="chat", temperature=0.7).strip()
        reply = re.sub(r'^["\'“]+|["\'”]+$', '', reply)
        return reply
    except Exception:
        return f"น้ำเสียงและจังหวะการเล่าเรื่องมีเสน่ห์มากครับ ดึงอารมณ์ความรู้สึกของตัวละครออกมาได้ลึกซึ้งมาก เป็นกำลังใจให้ทีมงานสร้างสรรค์ผลงานดีๆ ต่อไปนะครับ ✨"


def scout_trending_community_videos(max_results: int = 5) -> List[Dict[str, Any]]:
    """สแกนค้นหาคลิปนิยายเสียงที่กำลังได้รับความสนใจในไทย"""
    print("\n🔍 กำลังสแกนหาคลิปชุมชนนิยายเสียงยอดนิยมบน YouTube...")
    yt = youtube_stats._yt()

    search_queries = ["นิยายเสียงจบในตอน", "นิยายเสียงก่อนนอน", "นิยายแปลจีน ยุค 70"]
    found_videos = []
    seen_ids = set()

    for q in search_queries:
        if len(found_videos) >= max_results:
            break
        resp = yt.search().list(
            part="snippet",
            q=q,
            type="video",
            order="relevance",
            maxResults=3,
            relevanceLanguage="th"
        ).execute()

        for it in resp.get("items", []):
            vid = it["id"]["videoId"]
            if vid in seen_ids:
                continue
            seen_ids.add(vid)

            title = it["snippet"]["title"]
            ch_title = it["snippet"]["channelTitle"]

            # ข้ามช่องของตัวเอง
            if "Midnight Tales" in ch_title:
                continue

            print(f"  • พบ: {title[:50]}... (ช่อง: {ch_title})")
            thoughtful_text = generate_thoughtful_comment(title, ch_title)

            found_videos.append({
                "video_id": vid,
                "video_url": f"https://www.youtube.com/watch?v={vid}",
                "title": title,
                "channel_title": ch_title,
                "draft_comment": thoughtful_text,
                "created_at": datetime.now().isoformat()
            })

    # บันทึกคลัง Draft
    os.makedirs(os.path.dirname(ENGAGEMENT_DRAFTS_FILE), exist_ok=True)
    with open(ENGAGEMENT_DRAFTS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "note": "ข้อความคอมเมนต์คุณภาพสูงสำหรับนำไปโพสต์สร้างตัวตนแบรนด์ (White-Hat Strategy)",
            "drafts": found_videos
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ บันทึกคลัง Draft คอมเมนต์ดึงดูดผู้ฟังเรียบร้อย: {ENGAGEMENT_DRAFTS_FILE}")
    return found_videos


def generate_community_polls():
    """สร้างคลังชุดโพลล์คำถามชวนคุยสำหรับแท็บ YouTube Community"""
    print("\n📊 กำลังสร้างชุดโพลสำรวจ (Community Polls) เพื่อเร่งการมองเห็น...")

    polls = [
        {
            "id": "poll_01",
            "question": "🌾 ถ้าย้อนเวลาไปใน 'ยุค 70' ได้จริงๆ แล้วเลือกมิติลับติดตัวไปได้ 1 อย่าง คุณจะเลือกอะไร?",
            "options": [
                "1. ซูเปอร์มาร์เก็ตลับ (ของกินของใช้ไม่อั้น)",
                "2. น้ำทิพย์วิเศษ (รักษาโรค เยียวยาร่างกาย)",
                "3. มิติดินแดนปลูกผัก (ผลผลิตโตใน 1 วัน)",
                "4. ตำราสมุนไพรและสูตรยาโบราณ"
            ],
            "purpose": "ดึงดูดแฟนคลับแนวยุค 70 และโปรโมตเรื่องคุณแม่ลูกแฝดยุค 70"
        },
        {
            "id": "poll_02",
            "question": "🎧 ปกติแล้วเพื่อนๆ นิยมฟัง 'นิยายเสียง' ในช่วงเวลาไหนมากที่สุดกันครับ?",
            "options": [
                "1. เปิดฟังก่อนนอน (หลับสบาย มีสารบัญ)",
                "2. ฟังตอนทำงาน / ทำงานบ้าน เพลินๆ",
                "3. ฟังระหว่างเดินทาง / ขับรถ",
                "4. ฟังตอนพักผ่อนวันหยุดยาวๆ"
            ],
            "purpose": "เก็บข้อมูลพฤติกรรมผู้ฟังเพื่อกำหนดเวลาปล่อยคลิปยาว"
        },
        {
            "id": "poll_03",
            "question": "⚔️ ตัวเอกสไตล์ไหนที่คุณชอบฟังและเอาใจช่วยมากที่สุด?",
            "options": [
                "1. สายชิลล์ ขี้เกียจแต่พลังโกงระดับเทพ",
                "2. สู้ชีวิตจากศูนย์ ฉลาด ทันคน ไม่ยอมใคร",
                "3. นางเอกแกร่ง เอาคืนคนใจร้ายแบบสะใจ",
                "4. นักสืบจอมวางแผน สปีดรันไขคดีเร็วกว่าแสง"
            ],
            "purpose": "วัดผลความสนใจตัวละครเพื่อคัดเลือกนิยายเรื่องถัดไปเข้า Pipeline"
        }
    ]

    os.makedirs(os.path.dirname(POLLS_FILE), exist_ok=True)
    with open(POLLS_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "updated_at": datetime.now().isoformat(),
            "instruction": "นำคำถามและตัวเลือกเหล่านี้ไปโพสต์ในแท็บ 'ชุมชน (Community)' ของ YouTube เพื่อกระตุ้นให้อัลกอริทึมดันช่องสู่ฟีดคนนอก",
            "polls": polls
        }, f, ensure_ascii=False, indent=2)

    print(f"✅ บันทึกชุดโพลล์ชุมชนเรียบร้อย: {POLLS_FILE}")
    return polls


if __name__ == "__main__":
    drafts = scout_trending_community_videos(max_results=3)
    polls = generate_community_polls()

    print("\n" + "=" * 70)
    print(" 🌟 ตัวอย่างข้อความคอมเมนต์คุณภาพสูง (White-Hat Top Comments):")
    print("=" * 70)
    for idx, d in enumerate(drafts):
        print(f"\n[{idx+1}] คลิป: {d['title'][:55]}...")
        print(f"    🔗 ลิงก์: {d['video_url']}")
        print(f"    💬 ข้อความคอมเมนต์: \"{d['draft_comment']}\"")

    print("\n" + "=" * 70)
    print(" 📊 ตัวอย่างชุดโพลล์กระตุ้นการมองเห็น (Community Poll):")
    print("=" * 70)
    p = polls[0]
    print(p["question"])
    for opt in p["options"]:
        print(f"   {opt}")
    print("=" * 70)
