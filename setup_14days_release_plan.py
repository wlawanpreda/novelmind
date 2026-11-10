#!/usr/bin/env python3
"""
setup_14days_release_plan.py
===========================
สร้างตารางการปล่อยผลงาน Stock ต่อเนื่อง 14 วัน (2 สัปดาห์)
- ปล่อยคลิป Shorts ทุกวันเวลา 18:30 น. (Golden Hour ประจำวัน)
- ผูกลิงก์คลิปเต็ม Full Audiobook ของแต่ละเรื่อง
- บันทึกตารางลง SecondBrain/05_Active_Projects/schedule_plan_14days.json
"""

import os
import json
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
TEASER_DIR = os.path.join(SB, "05_Active_Projects", "Teaser_Output")
PLAN_FILE = os.path.join(SB, "05_Active_Projects", "schedule_plan_14days.json")

# แผนผังคอนเทนต์ 14 วัน คัดเลือกจาก Winning Tropes และความน่าสนใจสูงสุด
PLAN_DATA = [
    {
        "day": 1,
        "date_offset": 1,  # พรุ่งนี้ 2026-11-07
        "story_title": "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70",
        "trope": "Winning Trope #1: ยุค 70 มิติลับ สู้ชีวิต เลี้ยงลูกแฝด",
        "teaser_file": "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค_70_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/li5uCOYSSpA",
        "hook_title": "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 ตอนที่ 1 | นิยายเสียงก่อนนอน #Shorts",
        "synopsis": "ตื่นขึ้นมาในยุค 70 แร้นแค้น พร้อมลูกแฝดสองคน! แต่โชคดีที่มีซูเปอร์มาร์เก็ตลับติดตัวมาด้วย"
    },
    {
        "day": 2,
        "date_offset": 2,
        "story_title": "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์",
        "trope": "Winning Trope #2: พระเอกเก่งแต่ชิลล์ คอมเมดี้ (ยอดวิวอันดับ 1 ในช่อง)",
        "teaser_file": "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/Bh6YtuWNZcE",
        "hook_title": "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์ ตอนที่ 1 | ขอนอนสบายๆ ได้ไหม #Shorts",
        "synopsis": "ขอแค่อยู่อย่างสงบ แต่พลังเวทมหาศาลกลับปลุกเรื่องวุ่นวายไม่เว้นแต่ละวัน"
    },
    {
        "day": 3,
        "date_offset": 3,
        "story_title": "ตื่นตามฝันนางพยากรณ์",
        "trope": "Winning Trope #3: นิมิตลึกลับ พลิกชะตา (ยอดวิวอันดับ 2 ในช่อง)",
        "teaser_file": "ตื่นตามฝันนางพยากรณ์_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/3BPqQLhCgaE",
        "hook_title": "ตื่นตามฝันนางพยากรณ์ ตอนที่ 1 | นิมิตคำทำนายพลิกชะตา #Shorts",
        "synopsis": "ทุกความฝันคือเรื่องจริงล่วงหน้า เมื่อเห็นจุดจบ จึงต้องลงมือเปลี่ยนชะตาชีวิต"
    },
    {
        "day": 4,
        "date_offset": 4,
        "story_title": "กอธาม ทหารรับจ้างชะตาเปลี่ยน",
        "trope": "Action Fantasy: ดาบ เวทมนตร์ และสมรภูมิชิงอิสรภาพ",
        "teaser_file": "กอธาม_ทหารรับจ้างชะตาเปลี่ยน_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/1P583lKnKWw",
        "hook_title": "กอธาม ทหารรับจ้างชะตาเปลี่ยน ตอนที่ 1 | สมรภูมิที่ไม่มีวันลืม #Shorts",
        "synopsis": "ทหารรับจ้างผู้ถือดาบฝ่าดงศัตรู เพื่ออิสรภาพและโชคชะตาที่ลิขิตด้วยคมดาบ"
    },
    {
        "day": 5,
        "date_offset": 5,
        "story_title": "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง",
        "trope": "Romance Drama: หญิงแกร่งเอาคืน ประธานคลั่งรัก",
        "teaser_file": "เมื่อนางร้ายหมดรัก_ท่านประธานก็เริ่มคลั่ง_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/4cM5iELFUso",
        "hook_title": "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง ตอนที่ 1 | วันที่ฉันไม่สนคุณอีกต่อไป #Shorts",
        "synopsis": "วันที่ฉันตัดสินใจเดินจากมาอย่างเด็ดขาด คือวันที่เขาเพิ่งรู้ตัวว่าขาดฉันไม่ได้"
    },
    {
        "day": 6,
        "date_offset": 6,
        "story_title": "หมอฟันยุคเหนือธรรมชาติ",
        "trope": "Urban Supernatural: คอมเมดี้ลี้ลับ คลินิกรักษาคนและวิญญาณ",
        "teaser_file": "หมอฟันยุคเหนือธรรมชาติ_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/GqyIRz5cW8I",
        "hook_title": "หมอฟันยุคเหนือธรรมชาติ ตอนที่ 1 | คนไข้คนนี้... ไม่ใช่คน! #Shorts",
        "synopsis": "เปิดคลินิกทำฟันธรรมดา แต่ดันมีภูตผีปีศาจมาต่อคิวรักษาทุกค่ำคืน"
    },
    {
        "day": 7,
        "date_offset": 7,
        "story_title": "สาวอภินิหารหัวใจเหล็ก",
        "trope": "Cyberpunk Action: สาวแกร่งไซเบอร์ ต่อสู้เพื่อความถูกต้อง",
        "teaser_file": "สาวอภินิหารหัวใจเหล็ก_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/Mp2zzJEyI9w",
        "hook_title": "สาวอภินิหารหัวใจเหล็ก ตอนที่ 1 | หัวใจเหล็กกล้าที่ไม่มีวันพ่าย #Shorts",
        "synopsis": "ในโลกอนาคตอันเสื่อมทราม หญิงสาวผู้มีหัวใจเหล็กกล้าลุกขึ้นสู้เพื่อกอบกู้ความหวัง"
    },
    {
        "day": 8,
        "date_offset": 8,
        "story_title": "สมาคมประกันภัยลี้ลับ",
        "trope": "Mystery Fantasy: เคลมประกันมิติพิศวง คุ้มครองคำสาป",
        "teaser_file": "สมาคมประกันภัยลี้ลับ_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/-KdOEn051j4",
        "hook_title": "สมาคมประกันภัยลี้ลับ ตอนที่ 1 | ประกันที่คุ้มครองแม้กระทั่งคำสาป #Shorts",
        "synopsis": "บริษัทประกันภัยที่รับเคลมคดีเหนือธรรมชาติ เมื่อเหตุไม่คาดฝันเกิดจากอาถรรพ์"
    },
    {
        "day": 9,
        "date_offset": 9,
        "story_title": "ภารกิจสร้างตัว พลิกชะตากู้ตระกูล",
        "trope": "Self-Made Growth: สู้ชีวิตจากจุดต่ำสุดสู่จุดสูงสุด",
        "teaser_file": "ภารกิจร้างตัว_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/sXRcrilfnCg",
        "hook_title": "ภารกิจสร้างตัว พลิกชะตากู้ตระกูล ตอนที่ 1 | จากศูนย์สู่ความยิ่งใหญ่ #Shorts",
        "synopsis": "เริ่มต้นใหม่จากความว่างเปล่า ใช้สติปัญญาและความมุ่งมั่นพลิกฟื้นตระกูล"
    },
    {
        "day": 10,
        "date_offset": 10,
        "story_title": "ฟาร์มสาวปีศาจรัก",
        "trope": "Isekai Slow-Life: ทำฟาร์มแสนสุขกับเหล่าสาวปีศาจ",
        "teaser_file": "ฟาร์มสาวปีศาจรัก_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/8QBP8Me7zaI",
        "hook_title": "ฟาร์มสาวปีศาจรัก ตอนที่ 1 | สโลว์ไลฟ์ทำฟาร์มในต่างโลก #Shorts",
        "synopsis": "หลีกหนีความวุ่นวายมาทำฟาร์มในดินแดนปีศาจ บรรยากาศอบอุ่นหัวใจยามค่ำคืน"
    },
    {
        "day": 11,
        "date_offset": 11,
        "story_title": "กระจกเงาคนตาย",
        "trope": "Viral Suspense: ย้อนความทรงจำ 30 นาทีก่อนตาย วัตถุโบราณเยาวราช",
        "teaser_file": "กระจกเงาคนตาย_Teaser_02_viral.mp4",
        "full_video_url": "https://youtu.be/-E5IgijqfSc",
        "hook_title": "กระจกเงาคนตาย ตอนที่ 1 | ความลับ 30 นาทีก่อนสิ้นใจ #Shorts",
        "synopsis": "สัมผัสวัตถุโบราณเพื่อมองเห็นภาพเหตุการณ์สุดท้ายก่อนเหยื่อจะหมดลมหายใจ"
    },
    {
        "day": 12,
        "date_offset": 12,
        "story_title": "ร้านค้าเหนือโลก สตรีมดันเจียนล่าเทพ",
        "trope": "Dimension Shop: ร้านค้ามิติพิเศษและสตรีมมิ่ง",
        "teaser_file": "รานคาเหนอโลก_สตรมดนเจยนลาเทพ_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/e90bfef727e4730819e92444783d6850",
        "hook_title": "ร้านค้าเหนือโลก สตรีมดันเจียน ตอนที่ 1 | ร้านค้าขายไอเทมต่างมิติ #Shorts",
        "synopsis": "ร้านค้าลึกลับที่ขายสินค้าพลิกชะตาชีวิต ถ่ายทอดสดการตะลุยดันเจียนสู่ทุกสายตา"
    },
    {
        "day": 13,
        "date_offset": 13,
        "story_title": "ดวงจันทร์แห่งเวทมนตร์",
        "trope": "Dark Fantasy: ปริศนาโลกวิญญาณและเด็กสาวเต้นระบำ",
        "teaser_file": "ดวงจันทร์แห่งเวทมนตร์_เรื่องราวของฮิลโคและเด็กสาวผู้เต้นระบำในความมืด_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/Emd4CPU3ePQ",
        "hook_title": "ดวงจันทร์แห่งเวทมนตร์ ตอนที่ 1 | เด็กสาวผู้เต้นระบำใต้แสงจันทร์ #Shorts",
        "synopsis": "คดีปริศนาในโลกเวทมนตร์ และบทเพลงต้องสาปที่ดังก้องยามค่ำคืน"
    },
    {
        "day": 14,
        "date_offset": 14,
        "story_title": "จากน้องสาวสู่พี่ใหญ่",
        "trope": "Heartwarming Family: สายใยครอบครัว ก้าวข้ามความเจ็บปวด",
        "teaser_file": "จากน้องสาวสู่พี่ใหญ่_สายใยแห่งความรัก_Teaser_01.mp4",
        "full_video_url": "https://youtu.be/AwrE4AMQS4k",
        "hook_title": "จากน้องสาวสู่พี่ใหญ่ ตอนที่ 1 | สายใยรักที่ไม่มีวันตัดขาด #Shorts",
        "synopsis": "เรื่องราวอันอบอุ่นหัวใจ เมื่อการปกป้องครอบครัวกลายเป็นพลังอันยิ่งใหญ่"
    }
]

def build_plan():
    # Base date: วันนี้ 2026-11-06
    base_date = datetime(2026, 11, 6)
    items = []
    
    for entry in PLAN_DATA:
        release_date = base_date + timedelta(days=entry["date_offset"])
        date_str = release_date.strftime("%Y-%m-%d")
        # เวลาปล่อย 18:30 น. เวลาไทย (UTC+7) -> 11:30 UTC
        thai_time_str = "18:30 น."
        utc_iso = f"{date_str}T11:30:00Z"
        
        file_path = os.path.join(TEASER_DIR, entry["teaser_file"])
        
        items.append({
            "day": entry["day"],
            "date": date_str,
            "thai_time": thai_time_str,
            "utc_publish_at": utc_iso,
            "story_title": entry["story_title"],
            "trope": entry["trope"],
            "video_path": file_path,
            "video_exists": os.path.exists(file_path),
            "full_video_url": entry["full_video_url"],
            "hook_title": entry["hook_title"],
            "synopsis": entry["synopsis"],
            "status": "ready_to_schedule"
        })
    
    plan_out = {
        "created_at": datetime.now().isoformat(),
        "total_days": len(items),
        "golden_hour_thai": "18:30 น. (ช่วงพีกคนฟังนิยายเสียงหลังเลิกงาน)",
        "channel": "Midnight Tales · มิดไนต์เทล",
        "schedule": items
    }
    
    with open(PLAN_FILE, "w", encoding="utf-8") as f:
        json.dump(plan_out, f, ensure_ascii=False, indent=2)
    
    print(f"✅ บันทึกแผนงานสต็อก 14 วันเรียบร้อย: {PLAN_FILE}")
    print(f"   จำนวนคลิปพร้อมปล่อย: {len(items)} คลิป (ครบ 14 วัน)")

if __name__ == "__main__":
    build_plan()
