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

def _num(v):
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def compute_popularity(novels: list) -> list:
    """ให้คะแนนความนิยม 0-100 (normalize ในชุด) + จัดอันดับ (rank)"""
    def signal(n):
        # สัญญาณหลักตามแหล่ง: Syosetu=points, RR=views; เสริมด้วย bookmarks
        s = _num(n.get("global_points")) or _num(n.get("weekly_points"))
        if not s:
            s = _num(n.get("views")) / 100.0   # scale views ให้เทียบเคียง points
        return s + _num(n.get("bookmarks"))

    sigs = [signal(n) for n in novels]
    mx = max(sigs) if sigs else 0
    for n, s in zip(novels, sigs):
        score = round(100 * s / mx) if mx else 0
        if n.get("rating"):  # RR rating 0-5 → bonus สูงสุด +10
            score = min(100, score + int(_num(n.get("rating")) * 2))
        n["popularity_score"] = int(score)
    novels.sort(key=lambda x: x.get("popularity_score", 0), reverse=True)
    for i, n in enumerate(novels, 1):
        n["rank"] = i
    return novels


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

    # ตัวเลขความนิยม (เก็บให้ครบ ไม่ทิ้งของที่ scraper ดึงมา)
    rating = novel.get("rating", 0)
    views = int(_num(novel.get("views")))
    reviews = int(_num(novel.get("reviews")))
    points = int(_num(novel.get("global_points")) or _num(novel.get("weekly_points")))
    length = int(_num(novel.get("length_chars")))

    content = f"""---
id: "{novel.get('id')}"
source: "{novel.get('source')}"
title: "{novel.get('title')}"
author: "{novel.get('author')}"
genre: "{novel.get('genre')}"
bookmarks: {int(_num(novel.get('bookmarks')))}
chapters: {novel.get('chapters', 0)}
rating: {rating}
views: {views}
reviews: {reviews}
points: {points}
length_chars: {length}
popularity_score: {novel.get('popularity_score', 0)}
rank: {novel.get('rank', 0)}
last_updated: "{novel.get('last_updated', '')}"
url: "{novel.get('url', '')}"
scouted_at: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
status: "Scouted"
tags:
{tags_formatted}
---

# {novel.get('title')}

## 📊 สัญญาณความนิยม (Popularity Signals)
- **คะแนนความนิยม (Popularity Score):** `{novel.get('popularity_score', 0)}/100`  ·  **อันดับในชุด:** #{novel.get('rank', 0)}
- **ยอดบุ๊กมาร์ก/ผู้ติดตาม:** {int(_num(novel.get('bookmarks'))):,}
- **เรตติ้ง:** {rating if rating else '—'} {'/5' if rating else ''}  ·  **ยอดวิว:** {views:,}  ·  **จำนวนรีวิว:** {reviews:,}
- **คะแนนแพลตฟอร์ม (points):** {points:,}  ·  **ความยาว:** {length:,} ตัวอักษร
- **จำนวนตอน:** {novel.get('chapters')} ตอน  ·  **อัปเดตล่าสุด:** {novel.get('last_updated')}

## 📖 ข้อมูลพื้นฐาน (Basic Info)
- **แหล่งที่มา:** [{novel.get('source')}]({novel.get('url')})
- **ผู้เขียน:** {novel.get('author')}
- **หมวดหมู่:** {novel.get('genre')}

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
        
    # 2.5 คำนวณคะแนนความนิยม + จัดอันดับ (เรียงเด่นสุดขึ้นก่อน)
    all_novels = compute_popularity(all_novels)
    if all_novels:
        print(f"[*] จัดอันดับ {len(all_novels)} เรื่อง — เด่นสุด: '{all_novels[0].get('title')}' "
              f"(score {all_novels[0].get('popularity_score')}/100)")

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
