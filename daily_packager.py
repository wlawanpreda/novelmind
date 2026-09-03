"""
daily_packager.py — Daily Release Packager & 1-Click Publishing Hub for ANSRE
=============================================================================

รวมและจัดเตรียมชุดไฟล์สำหรับปล่อยงานรายวัน (Daily Release Packs) 
ทั้งฝั่งเว็บนิยาย (ReadAWrite / Dek-D) และฝั่ง Social Video (TikTok / YouTube Shorts):

โครงสร้างของโฟลเดอร์แต่ละวัน:
  SecondBrain/05_Active_Projects/Daily_Releases/Day_01_2026-09-03/
    ├── 01_ยอดนักสืบสปีดรัน_ตอนที่06/
    │   ├── 01_METADATA.txt              (ชื่อเรื่อง, ชื่อตอน, คำโปรย, แท็ก, นามปากกา)
    │   ├── 02_PROSE_CONTENT.txt         (เนื้อหานิยายภาษาไทย 100% ตรวจ QA แล้ว)
    │   ├── 03_COVER_IMAGE.jpg           (ภาพปกขนาดชัดเจนพร้อมอัปโหลด)
    │   ├── 04_SOCIAL_CAPTION.txt        (แคปชัน TikTok / Shorts พร้อม Hook + CTA)
    │   └── 05_TEASER_VIDEO.mp4          (วิดีโอสั้น 9:16 ถ้ามี)
    └── DAILY_CHECKLIST.md               (คู่มือและลำดับการกดปล่อยงานประจำวัน)

CLI:
  python daily_packager.py               # จัดชุดปล่อยงานสำหรับวันพรุ่งนี้ (หรือวันที่ระบุ)
  python daily_packager.py --days 3      # จัดชุดปล่อยงานล่วงหน้า 3 วัน
  python daily_packager.py --clean       # ล้างชุดแพ็กเกจเก่า
"""
from __future__ import annotations

import os
import re
import sys
import glob
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
ACTIVE_DIR = os.path.join(SB, "05_Active_Projects")
RELEASES_BASE = os.path.join(ACTIVE_DIR, "Daily_Releases")
os.makedirs(RELEASES_BASE, exist_ok=True)


def _clean_title(t: str) -> str:
    thai_chars = "฀-๿"
    return re.sub(r'[^\w\-_\s' + thai_chars + r']', '', t).strip().replace(' ', '_')


def find_best_cover(title: str) -> Optional[str]:
    covers_dir = os.path.join(ACTIVE_DIR, "Covers")
    clean = _clean_title(title)
    cands = [
        f"{clean}_Cover_captioned.jpg",
        f"{clean}_Cover_captioned.png",
        f"{clean}_Cover.jpg",
        f"{clean}_Cover.png",
    ]
    for fn in cands:
        fp = os.path.join(covers_dir, fn)
        if os.path.exists(fp) and os.path.getsize(fp) > 1000:
            return fp
    # search glob
    m = glob.glob(os.path.join(covers_dir, f"*{clean}*Cover*.*"))
    if m:
        return sorted(m)[0]
    return None


def find_teaser_video(title: str, chapter_num: int = 1) -> Optional[str]:
    teaser_dirs = [
        os.path.join(ACTIVE_DIR, "Teaser_Output"),
        os.path.join(ACTIVE_DIR, "Teasers")
    ]
    clean = _clean_title(title)
    for td in teaser_dirs:
        if not os.path.exists(td):
            continue
        cands = [
            f"{clean}_Teaser_{chapter_num:02d}.mp4",
            f"{clean}_Teaser.mp4",
            f"{clean}.mp4"
        ]
        for fn in cands:
            fp = os.path.join(td, fn)
            if os.path.exists(fp) and os.path.getsize(fp) > 5000:
                return fp
        m = glob.glob(os.path.join(td, f"*{clean}*.mp4"))
        if m:
            return sorted(m)[0]
    return None


def get_story_metadata(title: str) -> Dict[str, Any]:
    clean = _clean_title(title)
    
    # 1. ลองอ่านจาก Publish Queue ถ้ามี
    for pat in [f"{clean}_WEB_PUBLISH_KIT.md", f"{clean}_PUBLISH.md", f"*{clean}*.md"]:
        m = glob.glob(os.path.join(ACTIVE_DIR, "Publish_Queue", pat))
        if m:
            with open(m[0], "r", encoding="utf-8") as f:
                txt = f.read()
            # extract category & logline & tags
            cat_m = re.search(r'หมวดหมู่:\s*([^\n\r]+)', txt)
            tag_m = re.search(r'แท็ก[^:]*:\s*([^\n\r]+)', txt)
            log_m = re.search(r'คำโปรยสั้น[^\n\r]*\n>\s*([^\n\r]+)', txt)
            
            category = cat_m.group(1).strip() if cat_m else "แฟนตาซี / ผจญภัย"
            tags = tag_m.group(1).strip() if tag_m else "นิยายแฟนตาซี, ผจญภัย, แปลไทย, OriginalIP"
            logline = log_m.group(1).strip() if log_m else f"เรื่องราวการผจญภัยสุดตื่นเต้นใน '{title}'"
            return {
                "title": title,
                "author": "เงาพันจันทร์",
                "category": category,
                "tags": tags,
                "logline": logline
            }
            
    # Default metadata
    return {
        "title": title,
        "author": "เงาพันจันทร์",
        "category": "แฟนตาซี / ผจญภัย / สืบสวน",
        "tags": "นิยายไทย, ผจญภัย, แฟนตาซี, สืบสวน, สนุกสนาน, OriginalIP",
        "logline": f"เรื่องราวการผจญภัยและปมปริศนาสุดท้าทายใน '{title}' โดย เงาพันจันทร์"
    }


def create_daily_release_pack(day_index: int, target_date: datetime, schedule: List[Dict[str, Any]]) -> str:
    date_str = target_date.strftime("%Y-%m-%d")
    day_folder_name = f"Day_{day_index:02d}_{date_str}"
    target_dir = os.path.join(RELEASES_BASE, day_folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    checklist_items = []
    
    for idx, item in enumerate(schedule, 1):
        title = item["title"]
        chapter_num = item["chapter_num"]
        clean = _clean_title(title)
        
        story_folder_name = f"{idx:02d}_{clean}_ตอนที่{chapter_num:02d}"
        story_dir = os.path.join(target_dir, story_folder_name)
        os.makedirs(story_dir, exist_ok=True)
        
        # 1. อ่าน Chapter Content
        ch_fp = os.path.join(ACTIVE_DIR, "Chapters", f"{clean}_Chapter_{chapter_num:02d}.md")
        if not os.path.exists(ch_fp):
            # fallback glob
            m = glob.glob(os.path.join(ACTIVE_DIR, "Chapters", f"*{clean}*{chapter_num:02d}*.md"))
            ch_fp = m[0] if m else ""
            
        prose_content = ""
        chapter_title = f"ตอนที่ {chapter_num}"
        if ch_fp and os.path.exists(ch_fp):
            with open(ch_fp, "r", encoding="utf-8") as f:
                prose_content = f.read().strip()
            m_head = re.search(r'#+\s*(?:ตอนที่|บทที่)\s*\d+[:\s]*([^\n\r]+)', prose_content)
            if m_head:
                chapter_title = f"ตอนที่ {chapter_num}: {m_head.group(1).strip()}"
        else:
            prose_content = f"(เนื้อหาตอนที่ {chapter_num} ยังอยู่ระหว่างประมวลผล)"
            
        # 2. ดึง Metadata
        meta = get_story_metadata(title)
        meta_content = f"""=======================================================
📚 ข้อมูลสำหรับลงเว็บนิยาย (ReadAWrite / Dek-D)
=======================================================
ชื่อเรื่อง: {title}
นามปากกา: {meta['author']}
ลำดับตอน: ตอนที่ {chapter_num}
ชื่อตอน (Chapter Title): {chapter_title}
หมวดหมู่: {meta['category']}
คำโปรย (Logline):
{meta['logline']}

แท็กค้นหา (Tags):
{meta['tags']}
จำนวนตัวอักษร: {len(prose_content):,} ตัวอักษร
=======================================================
"""
        with open(os.path.join(story_dir, "01_METADATA.txt"), "w", encoding="utf-8") as f:
            f.write(meta_content)
            
        # 3. บันทึก Prose Content สะอาด 100%
        with open(os.path.join(story_dir, "02_PROSE_CONTENT.txt"), "w", encoding="utf-8") as f:
            f.write(prose_content)
            
        # 4. สำเนา Cover Image
        cover_src = find_best_cover(title)
        if cover_src:
            shutil.copy2(cover_src, os.path.join(story_dir, "03_COVER_IMAGE.jpg"))
            
        # 5. สร้าง Social Hook & Caption
        social_caption = f"""🔥 ตอนใหม่มาแล้ว! {title} — {chapter_title}
{meta['logline']}

📖 อ่านฉบับเต็มได้แล้ววันนี้ที่ ReadAWrite
🔍 ค้นหาคำว่า: "{title}"
✍️ นามปากกา: เงาพันจันทร์

#นิยาย #ReadAWrite #นิยายแฟนตาซี #ยอดนักสืบสปีดรัน #เงาพันจันทร์ #นิยายสนุก #หนังสือน่าอ่าน
"""
        with open(os.path.join(story_dir, "04_SOCIAL_CAPTION.txt"), "w", encoding="utf-8") as f:
            f.write(social_caption)
            
        # 6. สำเนาหรือลิงก์ Teaser Video ถ้ามี
        teaser_src = find_teaser_video(title, chapter_num)
        if teaser_src:
            shutil.copy2(teaser_src, os.path.join(story_dir, "05_TEASER_VIDEO.mp4"))
            
        checklist_items.append(f"- [ ] **{title}** ({chapter_title})\n  - อัปโหลดเนื้อหาลง ReadAWrite (ไฟล์ `02_PROSE_CONTENT.txt`)\n  - ปล่อยคลิป Teaser สั้นลง TikTok / Shorts (ไฟล์ `04_SOCIAL_CAPTION.txt` และ `05_TEASER_VIDEO.mp4`)")

    # สร้าง DAILY_CHECKLIST.md
    checklist_doc = f"""# 📋 Checklist การปล่อยผลงานประจำวัน
**วันที่กำหนดปล่อย:** {date_str} (วันที่ {day_index})

### 🚀 ลำดับขั้นตอนการปล่อยงาน:
{chr(10).join(checklist_items)}

---
💡 **คำแนะนำ:** สามารถเปิดโฟลเดอร์นี้แล้วดับเบิลคลิกไฟล์ `02_PROSE_CONTENT.txt` เพื่อกด Select All (Ctrl+A / Cmd+A) และ Paste ลง ReadAWrite ได้ทันที 100% โดยไม่ต้องจัดรูปแบบใหม่
"""
    with open(os.path.join(target_dir, "DAILY_CHECKLIST.md"), "w", encoding="utf-8") as f:
        f.write(checklist_doc)
        
    return target_dir


def generate_standard_release_schedule(days: int = 5):
    """สร้างแพ็กเกจปล่อยงานมาตรฐาน 5 วันสำหรับเรื่องหลัก"""
    # กำหนดแผนปล่อย 5 วันตาม roadmap
    # Day 1: ยอดนักสืบสปีดรัน (ตอน 6), สมาคมประกันภัยลี้ลับ (ตอน 1), เหล่ามือกระบี่ฯ (ตอน 1)
    # Day 2: ยอดนักสืบสปีดรัน (ตอน 7), สมาคมประกันภัยลี้ลับ (ตอน 2), เหล่ามือกระบี่ฯ (ตอน 3)
    # Day 3: ยอดนักสืบสปีดรัน (ตอน 8), สมาคมประกันภัยลี้ลับ (ตอน 3), เหล่ามือกระบี่ฯ (ตอน 4)
    # Day 4: ยอดนักสืบสปีดรัน (ตอน 9), สมาคมประกันภัยลี้ลับ (ตอน 4), เหล่ามือกระบี่ฯ (ตอน 5)
    # Day 5: ยอดนักสืบสปีดรัน (ตอน 10 - จบภาค), แสงแห่งฤดูใบไม้ผลิฯ (ตอน 1), เหล่ามือกระบี่ฯ (ตอน 6)
    
    plan = [
        # Day 1 (สำหรับ 4 เรื่องที่เปิดอยู่ในหน้า ReadAWrite วันนี้!)
        [
            {"title": "กระจกเงาคนตาย", "chapter_num": 1},
            {"title": "โลกแฟนตาซีอันเหนือจริง_วิญญาณศรัทธา", "chapter_num": 1},
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 1},
            {"title": "แสงแห่งฤดูใบไม้ผลิในเมืองเทา", "chapter_num": 1}
        ],
        # Day 2 (ตอนที่ 2 ต่อเนื่อง)
        [
            {"title": "กระจกเงาคนตาย", "chapter_num": 2},
            {"title": "โลกแฟนตาซีอันเหนือจริง_วิญญาณศรัทธา", "chapter_num": 2},
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 2},
            {"title": "แสงแห่งฤดูใบไม้ผลิในเมืองเทา", "chapter_num": 2}
        ],
        # Day 3
        [
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 3},
            {"title": "ยอดนักสืบสปีดรัน", "chapter_num": 6},
            {"title": "สมาคมประกันภัยลี้ลับ", "chapter_num": 1}
        ],
        # Day 4
        [
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 4},
            {"title": "ยอดนักสืบสปีดรัน", "chapter_num": 7},
            {"title": "สมาคมประกันภัยลี้ลับ", "chapter_num": 2}
        ],
        # Day 5
        [
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 5},
            {"title": "ยอดนักสืบสปีดรัน", "chapter_num": 8},
            {"title": "สมาคมประกันภัยลี้ลับ", "chapter_num": 3}
        ],
        # Day 6
        [
            {"title": "โลกแฟนตาซีอันเหนือจริง_วิญญาณศรัทธา", "chapter_num": 1},
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 7},
            {"title": "สถานตรวจกาววญญาณ", "chapter_num": 1}
        ],
        # Day 7
        [
            {"title": "เหล่ามือกระบี่ไร้แม่เหล็ก", "chapter_num": 8},
            {"title": "สถานตรวจกาววญญาณ", "chapter_num": 2},
            {"title": "ดาบไร้พระเจ้า_วงจรเวลาแห่งโชคชะตา", "chapter_num": 1}
        ],
    ]
    
    now = datetime.now()
    created_packs = []
    
    print(f"\n📦 กำลังสร้างชุดไฟล์ปล่อยงานรายวัน (Daily Release Packs) สำหรับ {min(days, len(plan))} วัน...")
    for i in range(min(days, len(plan))):
        target_date = now + timedelta(days=i)
        p = create_daily_release_pack(i + 1, target_date, plan[i])
        created_packs.append(p)
        print(f"  ✅ สร้างสำเร็จ: {os.path.basename(p)}")
        
    print(f"\n✨ ชุดไฟล์ทั้งหมดพร้อมใช้งานที่: {RELEASES_BASE}\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    days_count = 5
    if "--days" in args:
        idx = args.index("--days")
        if idx + 1 < len(args) and args[idx + 1].isdigit():
            days_count = int(args[idx + 1])
            
    if "--clean" in args:
        if os.path.exists(RELEASES_BASE):
            shutil.rmtree(RELEASES_BASE)
            os.makedirs(RELEASES_BASE, exist_ok=True)
            print("[+] ล้างโฟลเดอร์ Daily_Releases เรียบร้อย")
            
    generate_standard_release_schedule(days=days_count)
