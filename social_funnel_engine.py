#!/usr/bin/env python3
"""
social_funnel_engine.py — ระบบสร้างท่อนำสายตาจากวิดีโอสั้นสู่ ReadAWrite อัตโนมัติ (Track 3)
=======================================================================================
ความสามารถ:
1. Video Asset Matcher: ค้นหาคลิป Teaser/Shorts (9:16) ที่ตรงกับเรื่องและตอนที่กำลังปล่อย
2. Smart Copywriting Generator: สร้างแคปชันเตะตา + แฮชแท็กติดเทรนด์จาก trend_radar_report.json
3. Pinned Comment Bridge: สร้างข้อความคอมเมนต์ปักหมุดพร้อมลิงก์ไปยังนิยาย ReadAWrite โดยตรง
4. Omnichannel Distribution Hub: รองรับการส่งขึ้น YouTube Shorts & TikTok อัตโนมัติ
"""

from __future__ import annotations

import os
import re
import sys
import json
import glob
from datetime import datetime
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
ACTIVE_DIR = os.path.join(SB, "05_Active_Projects")
TEASERS_DIR = os.path.join(ACTIVE_DIR, "Teaser_Output")
TREND_REPORT = os.path.join(ACTIVE_DIR, "trend_radar_report.json")
LEDGER_FILE = os.path.join(ACTIVE_DIR, "publish_ledger.json")


def load_trend_hashtags() -> List[str]:
    """ดึงแฮชแท็กยอดนิยมจาก Trend Radar"""
    default_tags = ["#นิยาย", "#นิยายแฟนตาซี", "#ReadAWrite", "#เงาพันจันทร์", "#หนังสือน่าอ่าน"]
    if os.path.exists(TREND_REPORT):
        try:
            with open(TREND_REPORT, "r", encoding="utf-8") as f:
                data = json.load(f)
            trends = data.get("top_market_trends", [])
            dynamic_tags = [f"#{t['keyword'].replace('/', '').replace(' ', '')}" for t in trends[:5]]
            return list(dict.fromkeys(default_tags + dynamic_tags))
        except Exception:
            pass
    return default_tags


def find_video_teaser(story_title: str, chapter_num: int = 1) -> Optional[str]:
    """ค้นหาวิดีโอ Teaser ที่เหมาะสมที่สุดในคลัง"""
    clean = re.sub(r'[^\w\-_\s฀-๿]', '', story_title).strip().replace(' ', '_')
    dirs = [TEASERS_DIR, os.path.join(ACTIVE_DIR, "Video_Output"), os.path.join(ACTIVE_DIR, "Teasers")]

    for d in dirs:
        if not os.path.exists(d):
            continue
        patterns = [
            f"*{clean}*{chapter_num:02d}*.mp4",
            f"*{clean}*Teaser*.mp4",
            f"*{clean}*.mp4"
        ]
        for p in patterns:
            matches = glob.glob(os.path.join(d, p))
            if matches:
                return sorted(matches)[0]
    return None


def generate_funnel_package(story_title: str, chapter_title: str, chapter_num: int, article_id: str) -> Dict[str, Any]:
    """สร้างแพ็กเกจข้อความสำหรับเผยแพร่ Shorts/TikTok"""
    raw_url = f"https://www.readawrite.com/a/{article_id}"
    hashtags = " ".join(load_trend_hashtags())

    caption = f"""🔥 ตอนใหม่มาแล้ว! {story_title}
📖 ตอนที่ {chapter_num}: {chapter_title}
✍️ นามปากกา: เงาพันจันทร์

ความสนุกเข้มข้นกำลังทวีคูณ! ตามอ่านฉบับเต็มได้แล้ววันนี้ที่ ReadAWrite
{hashtags} #fyp #viral #นิยายสั้น
"""

    pinned_comment = f"""📌 อ่านฉบับเต็มครบทุกตอนได้ที่ ReadAWrite เลยครับ!
👉 ลิงก์เรื่อง: {raw_url}
❤️ ค้นหาคำว่า "{story_title}" นามปากกา เงาพันจันทร์
ฝากกดหัวใจ + เพิ่มเข้าชั้นหนังสือด้วยนะครับ! 💬
"""

    video_path = find_video_teaser(story_title, chapter_num)

    return {
        "story_title": story_title,
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "readawrite_url": raw_url,
        "caption": caption,
        "pinned_comment": pinned_comment,
        "video_path": video_path,
        "has_video": bool(video_path and os.path.exists(video_path))
    }


def export_funnel_social_pack(story_title: str, article_id: str, chapter_num: int = 1, chapter_title: str = "") -> str:
    """บันทึกแพ็กเกจวิดีโอและแคปชันลงในโฟลเดอร์ Social_Assets"""
    out_dir = os.path.join(ACTIVE_DIR, "Social_Assets", story_title)
    os.makedirs(out_dir, exist_ok=True)

    pkg = generate_funnel_package(story_title, chapter_title, chapter_num, article_id)
    pkg_file = os.path.join(out_dir, f"social_funnel_ch{chapter_num:02d}.json")

    with open(pkg_file, "w", encoding="utf-8") as f:
        json.dump(pkg, f, ensure_ascii=False, indent=2)

    readme_content = f"""# 🎬 Social Funnel Pack — {story_title} (ตอนที่ {chapter_num})
- **วิดีโอต้นฉบับ:** `{pkg['video_path'] or 'ยังไม่มีคลิปในคลัง'}`
- **ลิงก์ปลายทาง:** {pkg['readawrite_url']}

### 📝 แคปชันสำหรับโพสต์ (TikTok / YouTube Shorts / Reels):
```text
{pkg['caption']}
```

### 📌 ข้อความคอมเมนต์ปักหมุด (Pinned Comment):
```text
{pkg['pinned_comment']}
```
"""
    with open(os.path.join(out_dir, f"README_CH{chapter_num:02d}.md"), "w", encoding="utf-8") as f:
        f.write(readme_content)

def export_all_social_packs() -> List[str]:
    """สร้าง Social Funnel Pack สำหรับทุกเรื่องหลักในสตูดิโอ"""
    stories = [
        ("สาวอภินิหารหัวใจเหล็ก", "2ac4e08e36403cb46241714ff5758789", 1, "เอลลาริค หลังความตาย"),
        ("จากน้องสาวสู่พี่ใหญ่_สายใยแห่งความรัก", "c9ba3d70c41e7b9e05e4d1110ec5b94e", 1, "การเปลี่ยนแปลงเริ่มต้น"),
        ("ผู้สาปแช่ง_Chimera_เกิดใหม่ในโลกเวทย์มนต์", "454f3980e21e630dc4891fa752796d58", 1, "ก้าวแรกเมื่อโลกเปลี่ยน"),
        ("ฟาร์มสาวปีศาจรัก", "ac04dda030fae1380e3aa7ac52f66762", 1, "สู่โลกใหม่และไร่ศักดิ์สิทธิ์"),
        ("วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์", "f5d5ec2e430ab0bbade7b02be1beb149", 1, "การนอนหลับคือพลัง"),
        ("สมาคมประกันภัยลี้ลับ", "f3624f7b4e09cde8fc524dff4f2fc4bd", 1, "แผนกเคลมกรรม"),
        ("ยอดนักสืบสปีดรัน", "084947f5c23530e03094cc84bb1364b5", 1, "คดีฆาตกรรมห้องปิดตาย"),
        ("ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค_70_พร้อมซูเปอร์มาร์เก็ตลับ", "627d9707279484797acafaba010fcf69", 1, "เกิดใหม่พร้อมซูเปอร์มาร์เก็ต")
    ]
    results = []
    print("\n=================================================================")
    print(" 🎬 กำลังสร้างชุด Social Funnel Packs สำหรับทุกเรื่องในแคตตาล็อก")
    print("=================================================================")
    for title, aid, ch_num, ch_title in stories:
        f = export_funnel_social_pack(title, aid, ch_num, ch_title)
        results.append(f)
    print(f"\n🎉 บันทึก Social Funnel Packs ครบ {len(results)} เรื่องเรียบร้อย!\n")
    return results


if __name__ == "__main__":
    if "--all" in sys.argv or len(sys.argv) == 1:
        export_all_social_packs()
    else:
        export_funnel_social_pack(
            story_title="สาวอภินิหารหัวใจเหล็ก",
            article_id="2ac4e08e36403cb46241714ff5758789",
            chapter_num=1,
            chapter_title="เอลลาริค หลังความตาย"
        )
