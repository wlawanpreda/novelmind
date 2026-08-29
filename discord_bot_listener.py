"""
discord_bot_listener.py — Interactive Discord Bot Command Listener for ANSRE Studio
=====================================================================================

รับคำสั่งสดจากห้อง Discord 'writer-feedback' (Channel ID: 1542471943893164055)
คำสั่งที่รองรับ:
  !scout [jp|kr|cn|us|all]  — สั่ง Playwright ไปส่องนิยายต่างประเทศและดัดแปลงเป็น Original Thai IP
  !write [ชื่อเรื่อง]        — สั่งเขียนบทนิยายและเข้าลูปรีวิว 3 รอบ
  !review [ชื่อเรื่อง]       — สั่ง Multi-Agent Review Board ตรวจ 3 รอบ
  !publish                  — ตรวจสอบและอัปโหลดคลิปที่พร้อมขึ้น YouTube Shorts
  !status                   — ตรวจสอบสถานะผลผลิตและคลังนิยายใน SecondBrain
  !help                     — แสดงเมนูคำสั่งทั้งหมด
"""
from __future__ import annotations

import os
import re
import sys
import time
import json
import glob
import threading
import urllib.request
from datetime import datetime
from typing import Dict, Any, Optional, List

ROOT = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

SECOND_BRAIN = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
DEFAULT_CHANNEL_ID = "1542471943893164055"  # writer-feedback

from discord_reporter import _get_bot_token, send_discord_message


def fetch_recent_messages(channel_id: str = DEFAULT_CHANNEL_ID, limit: int = 10) -> List[Dict[str, Any]]:
    """ดึงข้อความล่าสุดจากห้อง Discord"""
    token = _get_bot_token()
    if not token:
        return []
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages?limit={limit}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bot {token}",
        "User-Agent": "ANSRE-Discord-Bot/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[!] Discord fetch error: {e}")
        return []


def handle_command(cmd_text: str, author: str, channel_id: str = DEFAULT_CHANNEL_ID):
    """ประมวลผลคำสั่ง Discord"""
    parts = cmd_text.strip().split()
    if not parts:
        return
    main_cmd = parts[0].lower()
    args = parts[1:]

    print(f"[*] [Discord Command] ได้รับคำสั่ง '{cmd_text}' จาก @{author}")

    if main_cmd == "!help":
        embed = {
            "title": "🤖 เมนูคำสั่ง ANSRE Multi-Agent Studio",
            "description": f"สวัสดีคุณ @{author}! คุณสามารถพิมพ์สั่งงานระบบสตูดิโออัตโนมัติได้ดังนี้:",
            "color": 0x3B82F6,
            "fields": [
                {
                    "name": "🌍 `!scout [ประเทศ]`",
                    "value": "ส่องนิยายเทรนด์โลก (เช่น `!scout kr`, `!scout jp`, `!scout all`)",
                    "inline": False
                },
                {
                    "name": "✍️ `!write [ชื่อเรื่อง]`",
                    "value": "สั่งเขียนและเข้าลูปรีวิว 3 รอบ (เช่น `!write หมอฟันยุคเหนือธรรมชาติ`)",
                    "inline": False
                },
                {
                    "name": "🎭 `!review [ชื่อเรื่อง]`",
                    "value": "สั่ง Multi-Agent Review Board ตรวจ 3 รอบ (เช่น `!review ยอดนักสืบสปีดรัน`)",
                    "inline": False
                },
                {
                    "name": "🚀 `!publish`",
                    "value": "อัปโหลดคลิป Teaser ที่พร้อมขึ้น YouTube Shorts",
                    "inline": True
                },
                {
                    "name": "📊 `!status`",
                    "value": "ดูคลังไอเดีย ยอดนิยาย และสถานะระบบวันนี้",
                    "inline": True
                }
            ],
            "footer": {"text": "ANSRE Autonomous Agent Studio"}
        }
        send_discord_message({"embeds": [embed]}, channel_id)

    elif main_cmd == "!status":
        pool_cnt = len(glob.glob(os.path.join(SECOND_BRAIN, "01_Scouting_Pool", "*.md")))
        idea_cnt = len(glob.glob(os.path.join(SECOND_BRAIN, "00_Idea_Vault", "*.md")))
        proj_cnt = len(glob.glob(os.path.join(SECOND_BRAIN, "05_Active_Projects", "Stories", "*.md")))
        audio_cnt = len(glob.glob(os.path.join(SECOND_BRAIN, "05_Active_Projects", "Audio_Final", "*.mp3")))

        embed = {
            "title": "📊 สถานะปัจจุบันของคลังนิยาย SecondBrain",
            "color": 0x10B981,
            "fields": [
                {"name": "🌍 Scouting Pool (นิยายต่างประเทศ)", "value": f"**{pool_cnt}** เรื่อง", "inline": True},
                {"name": "💡 Idea Vault (คลังไอเดีย)", "value": f"**{idea_cnt}** ไอเดีย", "inline": True},
                {"name": "📚 ผลงานนิยายต้นฉบับ", "value": f"**{proj_cnt}** บท", "inline": True},
                {"name": "🎧 หนังสือเสียงและคลิปวิดีโอ", "value": f"**{audio_cnt}** ไฟล์", "inline": True},
                {"name": "⚙️ Backend ปัจจุบัน", "value": f"`{os.environ.get('LLM_BACKEND', 'local')}` (Mac mini LAN)", "inline": False}
            ],
            "footer": {"text": f"ตรวจสอบเมื่อ {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
        }
        send_discord_message({"embeds": [embed]}, channel_id)

    elif main_cmd == "!scout":
        country = (args[0].upper() if args else "ALL")
        send_discord_message({
            "content": f"🔍 กำลังสั่งการ **Playwright Browser Crawler** ไปส่องนิยายประเทศ `{country}`... สักครู่ครับ!"
        }, channel_id)

        def _run_scout():
            try:
                from global_scout import run_global_scout
                c_list = ["JP", "US", "KR", "CN"] if country == "ALL" else [country]
                run_global_scout(countries=c_list, limit_per_country=2)
            except Exception as e:
                send_discord_message({"content": f"❌ การส่องนิยายล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_scout, daemon=True).start()

    elif main_cmd == "!review":
        title = " ".join(args).strip()
        if not title:
            send_discord_message({"content": "⚠️ กรุณาระบุชื่อเรื่อง เช่น `!review ยอดนักสืบสปีดรัน`"}, channel_id)
            return

        send_discord_message({
            "content": f"🎭 กำลังเรียกคณะกรรมการ **Multi-Agent Review Board (4 ด้าน)** รีวิวเรื่อง **'{title}'** วนซ้ำ 3 รอบ... ⏳"
        }, channel_id)

        def _run_rev():
            try:
                from multi_reviewer import run_multi_agent_review_loop, send_review_summary_to_discord
                from agent_writer import find_novel_file
                _, prose = find_novel_file(title, SECOND_BRAIN)
                res = run_multi_agent_review_loop(title, prose)
                send_review_summary_to_discord(title, res, chapter=1)
            except Exception as e:
                send_discord_message({"content": f"❌ การรีวิวเรื่อง '{title}' เกิดข้อผิดพลาด: `{e}`"}, channel_id)

        threading.Thread(target=_run_rev, daemon=True).start()

    elif main_cmd == "!publish":
        send_discord_message({"content": "🚀 กำลังตรวจสอบและส่งออกวิดีโอขึ้น YouTube Shorts... ⏳"}, channel_id)

        def _run_pub():
            try:
                from publisher import publish_latest_batch
                publish_latest_batch()
            except Exception as e:
                send_discord_message({"content": f"❌ การเผยแพร่เกิดข้อผิดพลาด: `{e}`"}, channel_id)

        threading.Thread(target=_run_pub, daemon=True).start()


def start_listening_loop(poll_interval: int = 4):
    """รันลูปเฝ้าตรวจข้อความคำสั่งจาก Discord ตลอดเวลา"""
    print(f"[*] 🎧 ANSRE Discord Command Listener เริ่มต้นทำงานแล้ว (Channel: {DEFAULT_CHANNEL_ID})...")
    processed_ids = set()
    
    # Load recent to skip initial backlog
    initial_msgs = fetch_recent_messages(limit=5)
    for m in initial_msgs:
        processed_ids.add(m["id"])

    while True:
        try:
            msgs = fetch_recent_messages(limit=5)
            # Process in chronological order
            for m in reversed(msgs):
                mid = m["id"]
                if mid in processed_ids:
                    continue
                processed_ids.add(mid)
                content = m.get("content", "").strip()
                author_data = m.get("author", {})
                author = author_data.get("username", "unknown")
                is_bot = author_data.get("bot", False)

                # ข้ามข้อความจากบอท
                if is_bot:
                    continue

                if content.startswith("!"):
                    handle_command(content, author, DEFAULT_CHANNEL_ID)

        except Exception as e:
            print(f"[!] Listener loop error: {e}")

        time.sleep(poll_interval)


if __name__ == "__main__":
    start_listening_loop()
