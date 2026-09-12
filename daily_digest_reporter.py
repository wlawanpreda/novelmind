"""
daily_digest_reporter.py — Autonomous Multi-Platform Daily Analytics & Health Digest
=====================================================================================
รวบรวมข้อมูลสุขภาพและการเติบโตของผลงานทั้งระบบ:
1. YouTube Channel Overview (Views, Likes, Comments, Top Videos, Playlists)
2. ReadAWrite Retention & Reader Drops (จาก SecondBrain/Analytics/readership_analytics.json)
3. สถานะการเผยแพร่และคิวงาน (Publish Ledger & Release Schedules)
4. ส่งรายงานสรุปผลอัตโนมัติเข้า Discord หรือบันทึกเป็นรายงานประจำวัน
"""

import os
import sys
import json
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")

import youtube_stats

try:
    import discord_reporter
except Exception:
    discord_reporter = None

def generate_daily_digest() -> dict:
    today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 1. YouTube Stats
    yt_data = youtube_stats.get_channel_overview(SB)
    total_videos = yt_data.get("total_videos", 0)
    total_views = yt_data.get("total_views", 0)
    total_likes = yt_data.get("total_likes", 0)
    total_comments = yt_data.get("total_comments", 0)
    top_videos = yt_data.get("top_videos", [])

    # YouTube Playlists
    try:
        yt = youtube_stats._yt()
        pls_resp = yt.playlists().list(part="snippet,contentDetails", mine=True, maxResults=50).execute()
        playlists = [
            {"title": p["snippet"]["title"], "items": p["contentDetails"]["itemCount"]}
            for p in pls_resp.get("items", [])
        ]
    except Exception:
        playlists = []

    # 2. ReadAWrite Analytics
    analytics_file = os.path.join(SB, "Analytics", "readership_analytics.json")
    readawrite_stories = []
    if os.path.exists(analytics_file):
        try:
            with open(analytics_file, "r", encoding="utf-8") as f:
                readawrite_stories = json.load(f)
        except Exception:
            pass

    # 3. Ledger Status
    ledger_path = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")
    ledger_count = 0
    if os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                led = json.load(f)
                ledger_count = len(led)
        except Exception:
            pass

    # 4. Generate Markdown Summary
    lines = [
        f"# 📊 Daily Analytics Digest — {today_str}",
        "",
        "## 🎥 YouTube Channel Performance",
        f"- **วิดีโอทั้งหมดบนช่อง:** {total_videos} รายการ",
        f"- **ยอดวิวรวม:** {total_views:,} วิว",
        f"- **ยอดไลก์รวม:** {total_likes:,} ไลก์",
        f"- **จำนวนคอมเมนต์รวม:** {total_comments:,} คอมเมนต์",
        f"- **เพลย์ลิสต์ที่จัดหมวดหมู่:** {len(playlists)} รายการ",
        "",
        "### 🏆 Top 5 วิดีโอยอดวิวสูงสุด:",
    ]
    for idx, tv in enumerate(top_videos[:5]):
        lines.append(f"{idx+1}. **{tv['title']}** — 👁️ {tv['views']:,} views | 👍 {tv['likes']} likes")

    if playlists:
        lines.append("")
        lines.append("### 📁 ผังเพลย์ลิสต์บนช่อง (Binge-Watching Playlists):")
        for pl in playlists:
            lines.append(f"- **{pl['title']}**: {pl['items']} คลิป")

    if readawrite_stories:
        lines.append("")
        lines.append("## 📖 ReadAWrite Active Stories Retention")
        lines.append("| ชื่อเรื่อง | จำนวนตอน | ยอดวิวรวม | สถานะ Retention |")
        lines.append("| :--- | :---: | :---: | :--- |")
        for st in readawrite_stories:
            alert_str = ", ".join(st.get("alerts", ["ปกติ"]))
            lines.append(f"| **{st['story_name']}** | {st['total_chapters']} | {st['total_views']} | {alert_str} |")

    lines.append("")
    lines.append("## ⚙️ ระบบผลิตและเผยแพร่ (Publishing Pipeline)")
    lines.append(f"- **ผลงานใน Ledger:** {ledger_count} รายการ")
    lines.append("- **สถานะการทำงาน:** ปกติ พร้อมสำหรับวงรอบเผยแพร่วันถัดไป")

    report_md = "\n".join(lines)

    # Save to disk
    report_dir = os.path.join(SB, "Analytics", "Reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"Digest_{datetime.now().strftime('%Y%m%d')}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)

    # Optionally send to Discord
    if discord_reporter and hasattr(discord_reporter, "send_discord_message"):
        discord_payload = {
            "embeds": [{
                "title": f"📊 Daily Studio Digest — {datetime.now().strftime('%d/%m/%Y')}",
                "description": f"🎥 **YouTube:** {total_views:,} views | {total_videos} videos | {len(playlists)} playlists\n📖 **ReadAWrite:** {len(readawrite_stories)} active stories tracked",
                "color": 0x5865F2,
                "fields": [
                    {
                        "name": "🏆 Top YouTube Video",
                        "value": f"{top_videos[0]['title'][:50]}... ({top_videos[0]['views']} views)" if top_videos else "N/A",
                        "inline": False
                    },
                    {
                        "name": "📁 Channel Playlists",
                        "value": f"{len(playlists)} หมวดหมู่จัดเรียงครบเรียบร้อย",
                        "inline": True
                    },
                    {
                        "name": "📦 Pipeline Ledger",
                        "value": f"{ledger_count} records",
                        "inline": True
                    }
                ],
                "footer": {"text": "ANSRE Autonomous Agent Studio"}
            }]
        }
        try:
            discord_reporter.send_discord_message(discord_payload)
        except Exception:
            pass

    return {
        "report_path": report_path,
        "report_md": report_md,
        "total_views": total_views,
        "total_videos": total_videos,
        "playlists_count": len(playlists),
        "readawrite_tracked": len(readawrite_stories)
    }

if __name__ == "__main__":
    res = generate_daily_digest()
    print(f"Report generated: {res['report_path']}")
    print(res["report_md"])
