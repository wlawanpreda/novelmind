"""
podcast_rss.py — Production-Grade Podcast RSS Feed Engine (Spotify & Apple Podcasts)
===================================================================================

รวบรวมนิยายเสียงฉบับเต็ม (Master Long-Form Audiobooks) สร้างเป็น Podcast RSS 2.0
ที่ได้มาตรฐาน iTunes / Spotify สำหรับนำ URL ไปผูกกับ Spotify for Podcasters,
Apple Podcasts, และ Podbean เพื่อสตรีมสู่ผู้ฟังทั่วโลก

CLI:
  python podcast_rss.py                   # สร้าง podcast_feed.xml ใน Exports/Audiobooks/
  python podcast_rss.py --base-url "https://cdn.example.com/audio"
"""
from __future__ import annotations

import os
import re
import glob
import json
import time
import email.utils
from datetime import datetime
from typing import Dict, Any, List, Optional
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
EXPORTS_DIR = os.path.join(SB, "05_Active_Projects", "Exports", "Audiobooks")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
CATALOG_PATH = os.path.join(EXPORTS_DIR, "audiobooks_catalog.json")
FEED_OUTPUT_PATH = os.path.join(EXPORTS_DIR, "podcast_feed.xml")

# Load .env
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def find_cover_image(title: str) -> str:
    """หาภาพปกสำหรับใส่เป็น Podcast Artwork"""
    candidates = [
        f"{title}_Cover_captioned.jpg",
        f"{title}_Cover.jpg",
        f"{title}_Cover.png",
        f"{title}.jpg"
    ]
    for fn in candidates:
        fp = os.path.join(COVERS_DIR, fn)
        if os.path.exists(fp) and os.path.getsize(fp) > 1000:
            return fp
    if os.path.exists(COVERS_DIR):
        for f in os.listdir(COVERS_DIR):
            if "Cover" in f and (f.endswith(".jpg") or f.endswith(".png")):
                for i in range(max(1, len(title) - 3)):
                    chunk = title[i:i+4]
                    if chunk in f:
                        return os.path.join(COVERS_DIR, f)
    return ""


def build_podcast_feed(base_url: str = None) -> str:
    """สร้าง XML RSS 2.0 สำหรับ Podcast"""
    cdn_base = base_url or os.environ.get("PODCAST_CDN_BASE", "https://raw.githubusercontent.com/wlawanpreda/novelmind/master/SecondBrain/05_Active_Projects/Exports/Audiobooks")
    channel_title = os.environ.get("PODCAST_TITLE", "NovelMind & ANSRE — นวนิยายเสียงไทย")
    channel_desc = os.environ.get("PODCAST_DESC", "คลังนิยายเสียงคุณภาพสูง เล่าเรื่องเข้มข้น ผจญภัย แฟนตาซี สืบสวน และไซไฟ บรรยายเสียงเสมือนจริง เหมาะสำหรับฟังตอนทำงาน เดินทาง หรือฟังก่อนนอน")
    channel_link = os.environ.get("PODCAST_LINK", "https://github.com/wlawanpreda/novelmind")
    channel_author = os.environ.get("PODCAST_AUTHOR", "NovelMind & ANSRE Studio")
    channel_email = os.environ.get("PODCAST_EMAIL", "wlawanpreda@gmail.com")
    channel_image = os.environ.get("PODCAST_COVER_URL", f"{cdn_base}/channel_cover.jpg")

    items_data = []
    if os.path.exists(CATALOG_PATH):
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                items_data = json.load(f)
        except Exception:
            pass

    # ถ้าไม่มีใน catalog ให้สแกนไฟล์ MP3 ตรง
    if not items_data:
        mp3s = glob.glob(os.path.join(EXPORTS_DIR, "*_Full_Audiobook.mp3"))
        for m in mp3s:
            bn = os.path.basename(m).replace("_Full_Audiobook.mp3", "")
            items_data.append({
                "title": bn,
                "chapters_count": 1,
                "total_duration": "30:00",
                "mp3_path": m
            })

    items_xml = []
    now_rfc822 = email.utils.formatdate(time.time(), usegmt=True)

    for idx, item in enumerate(items_data):
        raw_title = item.get("title", f"Episode {idx+1}")
        clean_title = raw_title.replace("_", " ").strip()
        mp3_path = item.get("mp3_path", "")
        file_size = os.path.getsize(mp3_path) if mp3_path and os.path.exists(mp3_path) else 10000000

        mp3_filename = os.path.basename(mp3_path) if mp3_path else f"{raw_title}_Full_Audiobook.mp3"
        enclosure_url = f"{cdn_base}/{mp3_filename}"

        # ดึง description ถ้ามี
        desc_text = f"นวนิยายเสียงเรื่อง '{clean_title}' ความยาว {item.get('total_duration', '')} รวมทุกตอนจบภาค ฟังเพลิน สนุก ตื่นเต้น เหมาะสำหรับการพักผ่อนและทำงาน"
        desc_path = item.get("desc_path")
        if desc_path and os.path.exists(desc_path):
            try:
                with open(desc_path, "r", encoding="utf-8") as df:
                    desc_text = df.read()
            except Exception:
                pass

        # หาวันที่สร้างไฟล์
        pub_date = now_rfc822
        if mp3_path and os.path.exists(mp3_path):
            mtime = os.path.getmtime(mp3_path)
            pub_date = email.utils.formatdate(mtime, usegmt=True)

        cover_path = find_cover_image(raw_title)
        cover_url = f"{cdn_base}/{os.path.basename(cover_path)}" if cover_path else channel_image

        import hashlib
        item_id = hashlib.md5(raw_title.encode('utf-8')).hexdigest()[:12]
        item_xml = f"""    <item>
      <title>{escape(clean_title)} (นิยายเสียงเต็มเรื่อง)</title>
      <link>{escape(channel_link)}</link>
      <guid isPermaLink="false">ansre-audio-{item_id}</guid>
      <pubDate>{pub_date}</pubDate>
      <description>{escape(desc_text[:1500])}</description>
      <enclosure url="{escape(enclosure_url)}" length="{file_size}" type="audio/mpeg"/>
      <itunes:duration>{escape(item.get("total_duration", "00:30:00"))}</itunes:duration>
      <itunes:author>{escape(channel_author)}</itunes:author>
      <itunes:summary>{escape(clean_title)} — นิยายเสียงฉบับสมบูรณ์</itunes:summary>
      <itunes:image href="{escape(cover_url)}"/>
      <itunes:explicit>false</itunes:explicit>
      <itunes:episodeType>full</itunes:episodeType>
    </item>"""
        items_xml.append(item_xml)

    full_rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" 
     xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
     xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>{escape(channel_title)}</title>
    <link>{escape(channel_link)}</link>
    <language>th-TH</language>
    <copyright>Copyright 2026 {escape(channel_author)}</copyright>
    <description>{escape(channel_desc)}</description>
    <itunes:author>{escape(channel_author)}</itunes:author>
    <itunes:type>episodic</itunes:type>
    <itunes:owner>
      <itunes:name>{escape(channel_author)}</itunes:name>
      <itunes:email>{escape(channel_email)}</itunes:email>
    </itunes:owner>
    <itunes:image href="{escape(channel_image)}"/>
    <itunes:category text="Fiction">
      <itunes:category text="Drama"/>
    </itunes:category>
    <itunes:category text="Arts">
      <itunes:category text="Books"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
{chr(10).join(items_xml)}
  </channel>
</rss>
"""
    with open(FEED_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(full_rss.strip())

    print(f"✅ บันทึก Podcast RSS Feed สำเร็จ: {FEED_OUTPUT_PATH}")
    print(f"   • จำนวน Episodes: {len(items_xml)} ตอน")
    print(f"   • Spotify / Apple Podcasts Compliant: พร้อมส่งตรวจบน Spotify for Podcasters")
    return FEED_OUTPUT_PATH


if __name__ == "__main__":
    import sys
    base = None
    if "--base-url" in sys.argv:
        idx = sys.argv.index("--base-url")
        if idx + 1 < len(sys.argv):
            base = sys.argv[idx + 1]
    build_podcast_feed(base)
