#!/usr/bin/env python3
"""
syndication_manager.py — ระบบกระจายผลงานข้ามแพลตฟอร์ม (Dek-D & Fictionlog) (Track 5)
=====================================================================================
ทำหน้าที่:
1. จัดเตรียมชุดไฟล์สำหรับส่งออกนิยายที่จบแล้ว (Completed Series) ไปยัง Dek-D และ Fictionlog
2. จัดรูปแบบเนื้อหาตามข้อกำหนดของ Dek-D (Writer 3.0) และ Fictionlog
3. อัปเดตสถานะและบันทึกลง syndication_ledger.json เพื่อติดตามการกระจายงาน
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
CHAPTERS_DIR = os.path.join(ACTIVE_DIR, "Chapters")
COVERS_DIR = os.path.join(ACTIVE_DIR, "Covers")
SYNDICATION_DIR = os.path.join(ACTIVE_DIR, "Syndication_Packages")
SYNDICATION_LEDGER = os.path.join(ACTIVE_DIR, "syndication_ledger.json")


def load_syndication_ledger() -> Dict[str, Any]:
    if os.path.exists(SYNDICATION_LEDGER):
        try:
            with open(SYNDICATION_LEDGER, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"stories": {}, "history": []}


def save_syndication_ledger(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(SYNDICATION_LEDGER), exist_ok=True)
    with open(SYNDICATION_LEDGER, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def package_story_for_syndication(story_title: str) -> Dict[str, Any]:
    """แพ็กเกจนิยาย 1 เรื่องพร้อมสำหรับอัปโหลด Dek-D และ Fictionlog"""
    clean = re.sub(r'[^\w\-_\s฀-๿]', '', story_title).strip().replace(' ', '_')
    story_pkg_dir = os.path.join(SYNDICATION_DIR, clean)
    os.makedirs(story_pkg_dir, exist_ok=True)

    # ค้นหาตอนทั้งหมด
    ch_files = sorted(glob.glob(os.path.join(CHAPTERS_DIR, f"{clean}_Chapter_*.md")))
    if not ch_files:
        ch_files = sorted(glob.glob(os.path.join(CHAPTERS_DIR, f"*{clean}*_Chapter_*.md")))

    chapter_entries = []
    for f in ch_files:
        bn = os.path.basename(f)
        m = re.search(r"Chapter_(\d+)", bn)
        num = int(m.group(1)) if m else len(chapter_entries) + 1

        with open(f, "r", encoding="utf-8") as fp:
            content = fp.read().strip()

        # สกัดชื่อตอน
        sub = f"ตอนที่ {num}"
        m_title = re.search(r"#+\s*(?:ตอนที่|บทที่)\s*\d+[:\s]*([^\n\r]+)", content)
        if m_title:
            sub = f"ตอนที่ {num}: {m_title.group(1).strip()}"

        dest_file = os.path.join(story_pkg_dir, f"Chapter_{num:02d}.txt")
        with open(dest_file, "w", encoding="utf-8") as fp:
            fp.write(content)

        chapter_entries.append({
            "num": num,
            "title": sub,
            "chars": len(content),
            "file": dest_file
        })

    # บันทึกคู่มือการเผยแพร่ SYNDICATION_GUIDE.md
    guide_content = f"""# 📚 Syndication Kit: {story_title}
- **นามปากกา:** เงาพันจันทร์
- **จำนวนตอนทั้งหมด:** {len(chapter_entries)} ตอน
- **สถานะ:** จบภาคแรกสมบูรณ์ พร้อมเปิดตัวบน Dek-D และ Fictionlog

### 📋 คำแนะนำการลงผลงาน:
1. **Dek-D (Writer 3.0):**
   - เข้าหน้าเขียนนิยาย Dek-D
   - สร้างเรื่องใหม่: ใส่ชื่อเรื่อง "{story_title}" นามปากกา "เงาพันจันทร์"
   - ใช้ไฟล์ในโฟลเดอร์นี้เปิดแล้วคัดลอกลงทีละตอน
2. **Fictionlog:**
   - เข้า Studio ของ Fictionlog
   - อัปโหลดตอนที่ 1–{len(chapter_entries)} ตามลำดับ

### 📑 รายการตอน:
"""
    for ch in chapter_entries:
        guide_content += f"- **{ch['title']}** ({ch['chars']:,} ตัวอักษร)\n"

    with open(os.path.join(story_pkg_dir, "SYNDICATION_GUIDE.md"), "w", encoding="utf-8") as f:
        f.write(guide_content)

    # อัปเดต Ledger
    ledger = load_syndication_ledger()
    if "stories" not in ledger:
        ledger["stories"] = {}

    ledger["stories"][story_title] = {
        "title": story_title,
        "clean_name": clean,
        "total_chapters": len(chapter_entries),
        "package_dir": story_pkg_dir,
        "platforms": {
            "dekd": {"status": "ready_for_upload", "chapters_packaged": len(chapter_entries)},
            "fictionlog": {"status": "ready_for_upload", "chapters_packaged": len(chapter_entries)}
        },
        "packaged_at": datetime.now().isoformat()
    }
    save_syndication_ledger(ledger)

    print(f"✅ แพ็กเกจ Syndication สำเร็จ: '{story_title}' ({len(chapter_entries)} ตอน) -> {story_pkg_dir}")
    return ledger["stories"][story_title]


def package_all_completed_stories():
    """แพ็กเกจทุกเรื่องที่จบแล้วสำหรับส่งออกข้ามแพลตฟอร์ม"""
    completed = [
        "จากน้องสาวสู่พี่ใหญ่: สายใยแห่งความรัก",
        "ผู้สาปแช่ง Chimera: เกิดใหม่ในโลกเวทย์มนต์",
        "สาวอภินิหารหัวใจเหล็ก",
        "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์",
        "สมาคมประกันภัยลี้ลับ",
        "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ",
        "ยอดนักสืบสปีดรัน",
        "เหล่ามือกระบี่ไร้แม่เหล็ก",
        "กระจกเงาคนตาย"
    ]
    for s in completed:
        package_story_for_syndication(s)


if __name__ == "__main__":
    package_all_completed_stories()
