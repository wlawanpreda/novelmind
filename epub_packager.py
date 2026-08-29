"""
epub_packager.py — Production-Grade EPUB & Web Novel Packager for ANSRE
========================================================================

รวมบทนิยาย (Chapters 1..N), ภาพปก, คำโปรย, และสารบัญ NCX เป็นไฟล์ .epub มาตรฐาน
พร้อมวางจำหน่ายบน Meb Market, ReadAWrite, Dek-D, Apple Books และ Kindle
และสร้างแพ็กเกจพร้อมเผยแพร่สำหรับเว็บนิยายลงใน Publish_Queue อัตโนมัติ

CLI:
  python epub_packager.py <ชื่อเรื่อง>              # แพ็กเกจเรื่องเดียว
  python epub_packager.py --all                    # แพ็กเกจทุกเรื่องที่มีบท >= 4 ตอน
  python epub_packager.py --all --min-chapters 8   # แพ็กเกจเฉพาะเรื่องที่มีบท >= 8 ตอน
"""
from __future__ import annotations

import os
import re
import glob
import json
import zipfile
import tempfile
from datetime import datetime
from typing import List, Dict, Any, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
STORIES_DIR = os.path.join(SB, "05_Active_Projects")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
EXPORTS_DIR = os.path.join(SB, "05_Active_Projects", "Exports")
QUEUE_DIR = os.path.join(SB, "05_Active_Projects", "Publish_Queue")

os.makedirs(EXPORTS_DIR, exist_ok=True)
os.makedirs(QUEUE_DIR, exist_ok=True)


def find_cover_image(title: str) -> Optional[str]:
    """ค้นหาภาพปกที่มีความคมชัดและดีที่สุดของเรื่อง"""
    candidates = [
        f"{title}_Cover_captioned.jpg",
        f"{title}_Cover_captioned.png",
        f"{title}_Cover.jpg",
        f"{title}_Cover.png",
        f"{title}.jpg",
        f"{title}.png"
    ]
    for fn in candidates:
        fp = os.path.join(COVERS_DIR, fn)
        if os.path.exists(fp) and os.path.getsize(fp) > 1000:
            return fp
    matches = glob.glob(os.path.join(COVERS_DIR, f"*{title}*Cover*.*"))
    if matches:
        return sorted(matches)[0]
    if os.path.exists(COVERS_DIR):
        all_covers = [f for f in os.listdir(COVERS_DIR) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        for i in range(max(1, len(title) - 3)):
            chunk = title[i:i+4]
            for cf in all_covers:
                if chunk in cf and "Cover" in cf:
                    return os.path.join(COVERS_DIR, cf)
    return None


def extract_synopsis_and_meta(title: str) -> Dict[str, Any]:
    """ค้นหาและสกัดคำโปรย/เรื่องย่อจาก Outline หรือ Scouting Pool"""
    meta = {
        "title": title,
        "logline": f"นิยายผจญภัยแฟนตาซีสุดเข้มข้น '{title}'",
        "synopsis": f"เรื่องราวการผจญภัยและการต่อสู้ท่ามกลางชะตากรรมที่ท้าทายใน '{title}'",
        "tags": ["นิยายแฟนตาซี", "ผจญภัย", "ระบบ", "เอาชีวิตรอด", "แปลไทย", "OriginalIP"],
        "category": "แฟนตาซี / ผจญภัย"
    }
    
    outline_fp = os.path.join(SB, "02_Concept_Extraction", f"{title}_Outline.md")
    if not os.path.exists(outline_fp):
        candidates = glob.glob(os.path.join(SB, "02_Concept_Extraction", f"*{title}*.md"))
        if candidates:
            outline_fp = candidates[0]
            
    if os.path.exists(outline_fp):
        try:
            with open(outline_fp, "r", encoding="utf-8") as f:
                txt = f.read()
                m_log = re.search(r"(?:คำโปรย|Logline|แกนเรื่อง)[:：]?\s*([^\n]+)", txt, re.IGNORECASE)
                if m_log:
                    meta["logline"] = m_log.group(1).strip()
                m_syn = re.search(r"(?:แนวคิดแกนเรื่อง|เรื่องย่อ|Core Premise)[:：]?\s*\n(.*?)(?=\n##|\n---|\Z)", txt, re.DOTALL)
                if m_syn:
                    clean_syn = m_syn.group(1).strip()
                    if len(clean_syn) > 30:
                        meta["synopsis"] = clean_syn[:1500]
        except Exception:
            pass
            
    return meta


def find_story_chapters(title: str) -> List[Dict[str, Any]]:
    """ค้นหาไฟล์บททั้งหมดของเรื่อง เรียงตามลำดับตอน 1, 2, 3..."""
    patterns = [
        os.path.join(STORIES_DIR, "Chapters", f"{title}_Chapter_*.md"),
        os.path.join(STORIES_DIR, "Chapters", f"{title}_*.md"),
        os.path.join(STORIES_DIR, f"{title}_Chapter_*.md"),
    ]
    files = []
    for pat in patterns:
        files.extend(glob.glob(pat))
        
    files = [f for f in set(files) if "_AudioScript_" not in f and "_Characters" not in f and "_Outline" not in f]
    chapters = []

    for fp in files:
        fname = os.path.basename(fp)
        m = re.search(r"_(\d+)\.md$", fname)
        ch_num = int(m.group(1)) if m else 1
        
        with open(fp, "r", encoding="utf-8") as f:
            content = f.read()

        clean_text = re.sub(r"^---\n.*?\n---\n", "", content, flags=re.DOTALL).strip()
        chapters.append({
            "num": ch_num,
            "filename": fname,
            "filepath": fp,
            "content": clean_text
        })

    chapters.sort(key=lambda x: x["num"])
    return chapters


def create_epub(title: str, author: str = "ANSRE Studio", output_path: Optional[str] = None) -> str:
    """สร้างไฟล์ EPUB มาตรฐานสมบูรณ์ (Cover + TOC NCX + Styling + Chapters)"""
    chapters = find_story_chapters(title)
    if not chapters:
        raise FileNotFoundError(f"ไม่พบบทนิยายของเรื่อง '{title}' ใน {STORIES_DIR}")

    if not output_path:
        safe = re.sub(r'[^\w\-_\s฀-๿]', '', title).strip().replace(' ', '_')
        output_path = os.path.join(EXPORTS_DIR, f"{safe}.epub")

    cover_fp = find_cover_image(title)
    meta_info = extract_synopsis_and_meta(title)

    with tempfile.TemporaryDirectory() as temp_dir:
        oebps = os.path.join(temp_dir, "OEBPS")
        meta_inf = os.path.join(temp_dir, "META-INF")
        os.makedirs(oebps, exist_ok=True)
        os.makedirs(meta_inf, exist_ok=True)

        # 1. mimetype (ต้องไม่บีบอัด)
        with open(os.path.join(temp_dir, "mimetype"), "w", encoding="utf-8") as f:
            f.write("application/epub+zip")

        # 2. META-INF/container.xml
        with open(os.path.join(meta_inf, "container.xml"), "w", encoding="utf-8") as f:
            f.write("""<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>""")

        # 3. CSS Style
        css_content = """
body { font-family: 'Sarabun', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.85; margin: 5%; color: #1F2937; background-color: #FAFAFA; }
h1 { color: #1E3A8A; text-align: center; margin-top: 1.5rem; margin-bottom: 2rem; font-size: 1.8rem; }
h2 { color: #1D4ED8; border-bottom: 2px solid #E5E7EB; padding-bottom: 0.6rem; margin-top: 2rem; font-size: 1.4rem; }
p { text-indent: 2em; margin: 0.9em 0; text-align: justify; }
.cover-container { text-align: center; padding: 1rem 0; }
.cover-image { max-width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.synopsis-box { background: #EEF2FF; border-left: 4px solid #4F46E5; padding: 1.2rem; border-radius: 6px; margin: 1.5rem 0; }
.synopsis-title { font-weight: bold; color: #3730A3; font-size: 1.1rem; margin-bottom: 0.5rem; }
.tag-badge { display: inline-block; background: #E0E7FF; color: #3730A3; padding: 0.2rem 0.6rem; border-radius: 12px; font-size: 0.85rem; margin-right: 0.4rem; margin-bottom: 0.4rem; }
"""
        with open(os.path.join(oebps, "style.css"), "w", encoding="utf-8") as f:
            f.write(css_content)

        manifest_items = [
            '<item id="css" href="style.css" media-type="text/css"/>',
            '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
        ]
        spine_items = []
        ncx_navpoints = []
        play_order = 1

        # 4. Handle Cover Image
        has_cover = False
        cover_filename = None
        if cover_fp and os.path.exists(cover_fp):
            ext = os.path.splitext(cover_fp)[1].lower()
            mime_type = "image/png" if ext == ".png" else "image/jpeg"
            cover_filename = f"cover{ext}"
            target_cover = os.path.join(oebps, cover_filename)
            
            with open(cover_fp, "rb") as src, open(target_cover, "wb") as dst:
                dst.write(src.read())

            manifest_items.append(f'<item id="cover-image" href="{cover_filename}" media-type="{mime_type}"/>')
            manifest_items.append('<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append('<itemref idref="cover-page"/>')
            
            cover_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="th">
<head>
  <title>หน้าปก — {title}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <div class="cover-container">
    <img src="{cover_filename}" alt="ภาพปก {title}" class="cover-image"/>
  </div>
</body>
</html>"""
            with open(os.path.join(oebps, "cover.xhtml"), "w", encoding="utf-8") as f:
                f.write(cover_xhtml)
            has_cover = True

            ncx_navpoints.append(f"""    <navPoint id="navPoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>หน้าปก</text></navLabel>
      <content src="cover.xhtml"/>
    </navPoint>""")
            play_order += 1

        # 5. Synopsis / Intro Page
        synopsis_xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="th">
<head>
  <title>{title} — เรื่องย่อ</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <h1>{title}</h1>
  <div class="synopsis-box">
    <div class="synopsis-title">📖 เรื่องย่อและคำโปรย</div>
    <p><em>"{meta_info['logline']}"</em></p>
    <p>{meta_info['synopsis']}</p>
  </div>
  <p><strong>ผู้ประพันธ์:</strong> {author}</p>
  <p><strong>หมวดหมู่:</strong> {meta_info['category']}</p>
  <div>
    {' '.join([f'<span class="tag-badge">#{t}</span>' for t in meta_info['tags']])}
  </div>
</body>
</html>"""
        with open(os.path.join(oebps, "synopsis.xhtml"), "w", encoding="utf-8") as f:
            f.write(synopsis_xhtml)

        manifest_items.append('<item id="synopsis-page" href="synopsis.xhtml" media-type="application/xhtml+xml"/>')
        spine_items.append('<itemref idref="synopsis-page"/>')
        ncx_navpoints.append(f"""    <navPoint id="navPoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>เรื่องย่อ & ข้อมูลนิยาย</text></navLabel>
      <content src="synopsis.xhtml"/>
    </navPoint>""")
        play_order += 1

        # 6. Chapters XHTML
        for ch in chapters:
            ch_id = f"chapter_{ch['num']:02d}"
            ch_filename = f"{ch_id}.xhtml"
            paragraphs = ch["content"].split("\n\n")
            p_html = "".join([f"<p>{p.strip().replace(chr(10), '<br/>')}</p>" for p in paragraphs if p.strip()])

            xhtml = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="th">
<head>
  <title>{title} — ตอนที่ {ch['num']}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <h2>ตอนที่ {ch['num']}</h2>
  {p_html}
</body>
</html>"""
            with open(os.path.join(oebps, ch_filename), "w", encoding="utf-8") as f:
                f.write(xhtml)

            manifest_items.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch_id}"/>')
            ncx_navpoints.append(f"""    <navPoint id="navPoint-{play_order}" playOrder="{play_order}">
      <navLabel><text>ตอนที่ {ch['num']}</text></navLabel>
      <content src="{ch_filename}"/>
    </navPoint>""")
            play_order += 1

        # 7. toc.ncx
        ncx_str = "\n".join(ncx_navpoints)
        ncx_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head>
    <meta name="dtb:uid" content="urn:uuid:{abs(hash(title))}"/>
    <meta name="dtb:depth" content="1"/>
    <meta name="dtb:totalPageCount" content="0"/>
    <meta name="dtb:maxPageNumber" content="0"/>
  </head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
{ncx_str}
  </navMap>
</ncx>"""
        with open(os.path.join(oebps, "toc.ncx"), "w", encoding="utf-8") as f:
            f.write(ncx_content)

        # 8. content.opf
        manifest_str = "\n    ".join(manifest_items)
        spine_str = "\n    ".join(spine_items)
        cover_meta = '    <meta name="cover" content="cover-image"/>\n' if has_cover else ""

        opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="BookId" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>th</dc:language>
    <dc:identifier id="BookId">urn:uuid:{abs(hash(title))}</dc:identifier>
    <dc:date>{datetime.now().strftime('%Y-%m-%d')}</dc:date>
    <dc:description>{meta_info['logline']}</dc:description>
{cover_meta}  </metadata>
  <manifest>
    {manifest_str}
  </manifest>
  <spine toc="ncx">
    {spine_str}
  </spine>
</package>"""
        with open(os.path.join(oebps, "content.opf"), "w", encoding="utf-8") as f:
            f.write(opf)

        # 9. Create Zip / EPUB archive
        with zipfile.ZipFile(output_path, "w") as zf:
            zf.write(os.path.join(temp_dir, "mimetype"), "mimetype", compress_type=zipfile.ZIP_STORED)
            zf.write(os.path.join(meta_inf, "container.xml"), "META-INF/container.xml", compress_type=zipfile.ZIP_DEFLATED)
            zf.write(os.path.join(oebps, "style.css"), "OEBPS/style.css", compress_type=zipfile.ZIP_DEFLATED)
            zf.write(os.path.join(oebps, "toc.ncx"), "OEBPS/toc.ncx", compress_type=zipfile.ZIP_DEFLATED)
            zf.write(os.path.join(oebps, "content.opf"), "OEBPS/content.opf", compress_type=zipfile.ZIP_DEFLATED)
            if has_cover and cover_filename:
                zf.write(os.path.join(oebps, cover_filename), f"OEBPS/{cover_filename}", compress_type=zipfile.ZIP_DEFLATED)
                zf.write(os.path.join(oebps, "cover.xhtml"), "OEBPS/cover.xhtml", compress_type=zipfile.ZIP_DEFLATED)
            zf.write(os.path.join(oebps, "synopsis.xhtml"), "OEBPS/synopsis.xhtml", compress_type=zipfile.ZIP_DEFLATED)
            for ch in chapters:
                ch_fn = f"chapter_{ch['num']:02d}.xhtml"
                zf.write(os.path.join(oebps, ch_fn), f"OEBPS/{ch_fn}", compress_type=zipfile.ZIP_DEFLATED)

    # 10. สร้าง Web Novel Publishing Kit (ReadAWrite / Dek-D) ใน Publish_Queue
    queue_pkg = os.path.join(QUEUE_DIR, f"{title}_WEB_PUBLISH_KIT.md")
    total_words = sum(len(ch["content"].split()) for ch in chapters)
    suggested_price = 59 if len(chapters) <= 5 else (99 if len(chapters) <= 12 else 149)
    
    kit_content = f"""# 📚 ชุดเผยแพร่นิยาย: {title}
**สถานะ:** พร้อมอัปโหลดขึ้น ReadAWrite, Meb, Dek-D, และ Fictionlog
**จำนวนตอน:** {len(chapters)} ตอน (~{total_words:,} คำ)
**ราคาเล่ม E-Book แนะนำ:** {suggested_price} บาท (หรือ 2–3 เหรียญ/ตอน สำหรับระบบอ่านรายตอน)

---
### 🏷️ ข้อมูลสำหรับกรอกหน้านิยาย (Metadata)
* **ชื่อเรื่อง:** {title}
* **หมวดหมู่:** {meta_info['category']}
* **คำโปรยสั้น (Logline):**
> {meta_info['logline']}

* **เรื่องย่อฉบับเต็ม:**
{meta_info['synopsis']}

* **แท็กค้นหา (Tags):**
`{'`, `'.join(meta_info['tags'])}`

* **ไฟล์ภาพปก:** `{cover_fp or 'ยังไม่มีภาพปก'}`
* **ไฟล์ E-Book พร้อมขาย (.epub):** `{output_path}`

---
### 📖 สารบัญและเนื้อหารายตอน (Copy-Paste)
"""
    for ch in chapters:
        kit_content += f"\n\n---\n## 🔖 ตอนที่ {ch['num']}\n\n{ch['content']}\n"

    with open(queue_pkg, "w", encoding="utf-8") as qf:
        qf.write(kit_content)

    print(f"[+] สร้างไฟล์ E-Book สำเร็จ: {output_path} (รวม {len(chapters)} ตอน + ปก + TOC NCX)")
    print(f"    └── สร้างชุดเผยแพร่เว็บนิยาย: {queue_pkg}")
    return output_path


def package_all_eligible_stories(min_chapters: int = 4) -> List[str]:
    """แพ็กเกจทุกเรื่องที่มีจำนวนตอน >= min_chapters เป็น EPUB และชุดพร้อมขาย"""
    ch_files = glob.glob(os.path.join(STORIES_DIR, "Chapters", "*.md"))
    titles = set()
    for fp in ch_files:
        fn = os.path.basename(fp)
        m = re.match(r"^(.*?)_Chapter_\d+\.md$", fn)
        if m:
            titles.add(m.group(1))

    results = []
    catalog = []
    print(f"[*] ตรวจพบ {len(titles)} เรื่องในระบบ — กำลังคัดกรองเรื่องที่มี >= {min_chapters} ตอน...")

    for t in sorted(titles):
        chapters = find_story_chapters(t)
        if len(chapters) >= min_chapters:
            try:
                epub_file = create_epub(t)
                results.append(epub_file)
                cover_file = find_cover_image(t)
                meta = extract_synopsis_and_meta(t)
                catalog.append({
                    "title": t,
                    "chapters_count": len(chapters),
                    "epub_path": epub_file,
                    "cover_path": cover_file,
                    "logline": meta["logline"],
                    "category": meta["category"],
                    "suggested_price_thb": 59 if len(chapters) <= 5 else (99 if len(chapters) <= 12 else 149)
                })
            except Exception as e:
                print(f"[!] เกิดข้อผิดพลาดกับเรื่อง {t}: {e}")

    catalog_path = os.path.join(EXPORTS_DIR, "catalog.json")
    with open(catalog_path, "w", encoding="utf-8") as cf:
        json.dump(catalog, cf, ensure_ascii=False, indent=2)

    print(f"\n✨ แพ็กเกจสำเร็จทั้งหมด {len(results)} เรื่อง! บันทึกแค็ตตาล็อกลง {catalog_path}")
    return results


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--all" in args:
        min_ch = 4
        if "--min-chapters" in args:
            idx = args.index("--min-chapters")
            if idx + 1 < len(args):
                min_ch = int(args[idx + 1])
        package_all_eligible_stories(min_ch)
    elif args:
        create_epub(args[0])
    else:
        print("Usage:")
        print("  python epub_packager.py <ชื่อเรื่อง>")
        print("  python epub_packager.py --all [--min-chapters 4]")

