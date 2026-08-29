"""
portfolio_manager.py — ANSRE Portfolio Matrix & Flagship Decision Engine
========================================================================

จัดกลุ่มนิยายทุกเรื่องในระบบเป็น 4 กลุ่มเชิงธุรกิจ:
1. 🚀 FLAGSHIP (Scale)   — เรื่องเรือธง: บทเยอะ, สินทรัพย์ครบ, ดันต่อให้จบภาค 15-20 ตอน + ขาย E-Book/Audiobook
2. 🧪 INCUBATING (Test) — เรื่องทดสอบตลาด: 1-3 ตอน + 1 Teaser รอดูผลตอบรับ
3. 🛠️ REWRITE (Fix)     — เรื่องที่บทหรือคะแนนรีวิวต้องปรับปรุง
4. 📦 ARCHIVE (Drop)    — เรื่องที่ยุติการผลิตเพื่อประหยัดทรัพยากร

CLI:
  python portfolio_manager.py
"""
from __future__ import annotations

import os
import re
import glob
import json
from datetime import datetime
from typing import Dict, Any, List

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
STORIES_DIR = os.path.join(SB, "05_Active_Projects")
EXPORTS_DIR = os.path.join(SB, "05_Active_Projects", "Exports")

FLAGSHIP_CANDIDATES = [
    "ยอดนักสืบสปีดรัน",
    "ร้านค้าเหนือโลก",
    "สมาคมประกันภัยลี้ลับ",
    "รหัสลับใต้เงา"
]

def scan_portfolio() -> Dict[str, Any]:
    # 1. รวบรวมเรื่องทั้งหมด
    ch_files = glob.glob(os.path.join(STORIES_DIR, "Chapters", "*.md"))
    stories_map = {}

    for fp in ch_files:
        fn = os.path.basename(fp)
        m = re.match(r"^(.*?)_Chapter_(\d+)\.md$", fn)
        if m:
            title = m.group(1)
            ch_num = int(m.group(2))
            if title not in stories_map:
                stories_map[title] = {
                    "title": title,
                    "chapters": [],
                    "has_cover": False,
                    "audio_count": 0,
                    "teaser_count": 0,
                    "has_epub": False,
                    "category": "INCUBATING",
                    "recommendation": ""
                }
            stories_map[title]["chapters"].append(ch_num)

    # 2. สำรวจ Assets
    covers = set(os.path.basename(f) for f in glob.glob(os.path.join(STORIES_DIR, "Covers", "*.*")))
    audios = glob.glob(os.path.join(STORIES_DIR, "Audio_Output", "*.mp3"))
    teasers = glob.glob(os.path.join(STORIES_DIR, "Teaser_Output", "*.mp4"))
    epubs = set(os.path.basename(f) for f in glob.glob(os.path.join(EXPORTS_DIR, "*.epub")))

    for title, data in stories_map.items():
        data["chapter_count"] = len(data["chapters"])
        # เช็กปก
        for c in covers:
            if title in c:
                data["has_cover"] = True
                break
        # เช็กเสียง
        data["audio_count"] = sum(1 for a in audios if title in os.path.basename(a))
        # เช็ก teaser
        data["teaser_count"] = sum(1 for t in teasers if title in os.path.basename(t))
        # เช็ก epub
        safe_title = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
        data["has_epub"] = f"{safe_title}.epub" in epubs

        # 3. จัดกลุ่มตาม Portfolio Matrix
        is_flagship = any(f in title for f in FLAGSHIP_CANDIDATES) or data["chapter_count"] >= 10
        if is_flagship and data["chapter_count"] >= 8:
            data["category"] = "FLAGSHIP (Scale)"
            data["recommendation"] = "🚀 ดันต่อเนื่องจนจบภาค (15-20 ตอน), ทำ Long-Form Audiobook, และดันขาย E-Book"
        elif data["chapter_count"] >= 4 and data["has_cover"]:
            data["category"] = "MATURE (Maintain)"
            data["recommendation"] = "📦 แพ็กขาย E-Book และปล่อยนิยายรายตอนเพื่อเก็บเหรียญ"
        elif data["chapter_count"] <= 3:
            data["category"] = "INCUBATING (Test)"
            data["recommendation"] = "🧪 ปล่อย 1 Teaser สู่ YouTube/TikTok เพื่อทดสอบตลาดก่อนเขียนต่อ"
        else:
            data["category"] = "NEEDS_REVIEW (Rewrite)"
            data["recommendation"] = "🛠️ ตรวจสอบคุณภาพผ่าน Multi-Reviewer ก่อนตัดสินใจ"

    # 4. บันทึกผล
    out_json = os.path.join(SB, "portfolio_matrix.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(stories_map, f, ensure_ascii=False, indent=2)

    # 5. สร้างรายงานสรุป Markdown
    out_md = os.path.join(SB, "Portfolio_Summary.md")
    lines = [
        "# 📊 ANSRE Story Portfolio Matrix & Strategic Decisions",
        f"**อัปเดตล่าสุด:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 🚀 กลุ่มที่ 1: FLAGSHIP (Scale) — เรื่องเรือธงที่ต้องทุ่มทรัพยากร",
        "เรื่องที่มีเนื้อหาแน่น สินทรัพย์พร้อม และเป็นหัวหอกในการสร้างรายได้หลัก:",
        ""
    ]
    
    flagships = [d for d in stories_map.values() if d["category"].startswith("FLAGSHIP")]
    for d in flagships:
        lines.append(f"### 👑 {d['title']}")
        lines.append(f"- **จำนวนตอน:** {d['chapter_count']} ตอน | **เสียง:** {d['audio_count']} ตอน | **Teaser:** {d['teaser_count']} คลิป | **E-Book:** {'✅ พร้อมขาย' if d['has_epub'] else '❌ ขาด'}")
        lines.append(f"- **ทิศทาง:** {d['recommendation']}")
        lines.append("")

    lines.append("## 📦 กลุ่มที่ 2: MATURE (พร้อมจำหน่าย E-Book & เว็บนิยาย)")
    matures = [d for d in stories_map.values() if d["category"].startswith("MATURE")]
    lines.append(f"ตรวจพบ {len(matures)} เรื่องที่มีบทครบพร้อมทำเงิน (E-Book .epub ผลิตเสร็จแล้วใน Exports/)")
    lines.append("")

    lines.append("## 🧪 กลุ่มที่ 3: INCUBATING (ทดสอบตลาดด้วย Teaser)")
    incubating = [d for d in stories_map.values() if d["category"].startswith("INCUBATING")]
    lines.append(f"ตรวจพบ {len(incubating)} เรื่องสั้น/ไอเดียใหม่ (ยิงทดสอบตลาด 1-3 ตอน รอดูสัญญาณวิว)")
    lines.append("")

    with open(out_md, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[+] บันทึก Portfolio Matrix: {out_json}")
    print(f"[+] สร้างรายงานสรุป: {out_md}")
    print(f"    - Flagship: {len(flagships)} เรื่อง")
    print(f"    - Mature: {len(matures)} เรื่อง")
    print(f"    - Incubating: {len(incubating)} เรื่อง")
    return stories_map

if __name__ == "__main__":
    scan_portfolio()
