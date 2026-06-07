import argparse
import os
import json
from datetime import datetime
from scraper.syosetu import fetch_syosetu_novels
from scraper.royalroad import fetch_royalroad_novels

def sanitize_filename(name: str) -> str:
    """Keep only alphanumeric and underscore characters for filenames."""
    clean = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
    return clean.replace(' ', '_')

def ensure_dirs(base_path: str):
    """Ensure Second Brain directory structures exist."""
    folders = [
        "01_Scouting_Pool",
        "02_Concept_Extraction",
        "03_World_Building",
        "04_Character_Database",
        "05_Active_Projects"
    ]
    for folder in folders:
        os.makedirs(os.path.join(base_path, folder), exist_ok=True)

def write_to_obsidian(novel: dict, second_brain_dir: str):
    """Write novel metadata as a structured markdown file in the Obsidian vault."""
    scouting_pool_dir = os.path.join(second_brain_dir, "01_Scouting_Pool")
    safe_title = sanitize_filename(novel.get("title", "untitled"))
    
    # Slice title if it's too long
    if len(safe_title) > 60:
        safe_title = safe_title[:57] + "..."
        
    filename = f"{novel.get('source')}_{novel.get('id')}_{safe_title}.md"
    filepath = os.path.join(scouting_pool_dir, filename)
    
    tags_formatted = "\n".join([f"  - {tag}" for tag in novel.get("tags", [])])
    
    content = f"""---
id: "{novel.get('id')}"
source: "{novel.get('source')}"
title: "{novel.get('title')}"
author: "{novel.get('author')}"
genre: "{novel.get('genre')}"
bookmarks: {novel.get('bookmarks', 0)}
chapters: {novel.get('chapters', 0)}
last_updated: "{novel.get('last_updated', '')}"
url: "{novel.get('url', '')}"
scouted_at: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
status: "Scouted"
tags:
{tags_formatted}
---

# {novel.get('title')}

## 📖 ข้อมูลพื้นฐาน (Basic Info)
- **แหล่งที่มา:** [{novel.get('source')}]({novel.get('url')})
- **ผู้เขียน:** {novel.get('author')}
- **หมวดหมู่:** {novel.get('genre')}
- **จำนวนตอนสะสม:** {novel.get('chapters')} ตอน
- **ยอดบุ๊กมาร์ก/ผู้ติดตาม:** {novel.get('bookmarks', 0):,}
- **อัปเดตล่าสุด:** {novel.get('last_updated')}

## 📝 เรื่องย่อ (Synopsis)
{novel.get('synopsis')}

---

## 🛠️ ขั้นตอนถัดไปในระบบ ANSRE (ANSRE Pipeline Status)
- [ ] **Step 1: ตรวจสอบลิขสิทธิ์ในไทยเบื้องต้น (Copyright Check)**
- [ ] **Step 2: สกัดแก่นเรื่องและจุดดึงดูดใจ (Core Concept Extraction)**
- [ ] **Step 3: ปรับแต่งฉากและตัวละครให้เข้ากับบริบทไทย (Localization & Design)**
- [ ] **Step 4: เจนตอนแรกและบทนิยายเสียง (Text & Audio Generation)**
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath

def main():
    parser = argparse.ArgumentParser(description="ANSRE scouting engine")
    parser.add_argument("--source", type=str, default="all", choices=["syosetu", "royalroad", "all"],
                        help="Novel sources to scrape (default: all)")
    parser.add_argument("--limit", type=int, default=10,
                        help="Number of novels to fetch per source (default: 10)")
    parser.add_argument("--outdir", type=str, default="./SecondBrain",
                        help="Path to Second Brain directory (default: ./SecondBrain)")
    parser.add_argument("--json-out", type=str, default=None,
                        help="Path to output merged JSON data file")
    
    args = parser.parse_args()
    
    ensure_dirs(args.outdir)
    
    all_novels = []
    
    # 1. Fetch Syosetu
    if args.source in ["syosetu", "all"]:
        print(f"[*] Fetching top {args.limit} novels from Syosetu...")
        syosetu_novels = fetch_syosetu_novels(limit=args.limit, order="weekly_point")
        print(f"[+] Found {len(syosetu_novels)} novels from Syosetu.")
        all_novels.extend(syosetu_novels)
        
    # 2. Fetch Royal Road
    if args.source in ["royalroad", "all"]:
        print(f"[*] Fetching top {args.limit} novels from Royal Road...")
        rr_novels = fetch_royalroad_novels(limit=args.limit)
        print(f"[+] Found {len(rr_novels)} novels from Royal Road.")
        all_novels.extend(rr_novels)
        
    # 3. Write to Obsidian
    print(f"[*] Exporting novels to Second Brain ({args.outdir})...")
    written_count = 0
    for novel in all_novels:
        try:
            filepath = write_to_obsidian(novel, args.outdir)
            written_count += 1
        except Exception as e:
            print(f"[!] Error writing novel {novel.get('title')}: {e}")
            
    print(f"[+] Successfully exported {written_count} novels to the Second Brain.")
    
    # 4. Save JSON if requested
    if args.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(args.json_out)), exist_ok=True)
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(all_novels, f, ensure_ascii=False, indent=4)
        print(f"[+] Saved raw data to JSON: {args.json_out}")

if __name__ == "__main__":
    main()
