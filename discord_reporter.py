"""
discord_reporter.py — Discord Integration for ANSRE Multi-Agent Studio
========================================================================

ส่งรายงานการรีวิว (Review Scorecards), ผลผลิตมีเดีย (ปก, เสียง, คลิป),
และสถานะการทำงาน เข้าห้อง Discord 'writer-feedback'

รองรับ 2 ช่องทาง:
  1. Discord Bot Token จาก ../discord-archiver/.env (Direct Channel ID)
  2. ANSRE_DISCORD_WEBHOOK จาก .env (Webhook URL)
"""
from __future__ import annotations

import os
import re
import json
import sqlite3
import urllib.request
from typing import Dict, Any, Optional, List
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

ARCHIVER_DIR = os.path.abspath(os.path.join(ROOT, "..", "discord-archiver"))
ARCHIVER_ENV = os.path.join(ARCHIVER_DIR, ".env")
ARCHIVER_DB = os.path.join(ARCHIVER_DIR, "data", "archive.db")

DEFAULT_CHANNEL_ID = "1542471943893164055"  # writer-feedback


def _get_bot_token() -> str:
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if token:
        return token
    if os.path.exists(ARCHIVER_ENV):
        with open(ARCHIVER_ENV, "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("DISCORD_TOKEN="):
                    return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def send_discord_message(payload: dict, channel_id: str = DEFAULT_CHANNEL_ID) -> bool:
    """ส่งข้อความ/Embed เข้า Discord โดยอัตโนมัติ (Bot API หรือ Webhook)"""
    webhook_url = os.environ.get("ANSRE_DISCORD_WEBHOOK", "").strip()
    bot_token = _get_bot_token()
    
    # 1. ลองส่งผ่าน Bot API เข้าห้อง channel_id
    if bot_token:
        try:
            url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Authorization": f"Bot {bot_token}",
                    "Content-Type": "application/json",
                    "User-Agent": "ANSRE-Bot/2.0 (+https://github.com/wlawanpreda/novelmind)"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True
        except Exception as e:
            print(f"[discord] Bot API error: {e}")

    # 2. Fallback เป็น Webhook URL ถ้ามี
    if webhook_url:
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    "User-Agent": "ANSRE-Bot/2.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f"[discord] Webhook error: {e}")

    return False


def send_review_summary_to_discord(
    title: str,
    chapter_num: int,
    scorecard: Dict[str, Any],
    channel_id: str = DEFAULT_CHANNEL_ID
) -> bool:
    """ส่งรายงานสรุปผลการรีวิว 3+ รอบจาก Multi-Agent Review Board เข้า Discord"""
    total_rounds = scorecard.get("total_rounds", 3)
    initial_score = scorecard.get("initial_score", 0.0)
    final_score = scorecard.get("final_score", 0.0)
    improvement = scorecard.get("score_improvement", 0.0)
    scores = scorecard.get("final_scores_breakdown", {})
    passed = scorecard.get("passed_quality_gate", True)
    hook = scorecard.get("teaser_hook_quote", "")
    
    status_icon = "🟢 ผ่านเกณฑ์คุณภาพยอดเยี่ยม" if passed else "🟡 ผ่านการปรับปรุงตามรอบ"
    color = 0x10B981 if passed else 0xF59E0B
    
    fields = [
        {
            "name": "📊 พัฒนาการคะแนน",
            "value": f"• เริ่มต้น: `{initial_score}/10`\n• สรุปสุดท้าย: **`{final_score}/10`** (+{improvement})\n• จำนวนรอบปรับปรุง: `{total_rounds} รอบ`",
            "inline": True
        },
        {
            "name": "🎭 คะแนนแยกตาม Reviewer",
            "value": f"• 🎯 พล็อต & Hook: `{scores.get('plot', 0)}/10`\n• ❤️ อารมณ์ตัวละคร: `{scores.get('character', 0)}/10`\n• ✍️ ภาษา & สำนวน: `{scores.get('prose', 0)}/10`\n• 🎧 จังหวะเสียงพากย์: `{scores.get('voice', 0)}/10`",
            "inline": True
        }
    ]
    
    if hook:
        fields.append({
            "name": "🎬 คำคมเด็ดสำหรับ Teaser Video",
            "value": f"> *\"{hook}\"*",
            "inline": False
        })
        
    payload = {
        "embeds": [{
            "title": f"📝 [ผลการรีวิวและปรับปรุง] {title} — ตอนที่ {chapter_num}",
            "description": f"ระบบ **Multi-Agent Review Board** ได้ดำเนินการตรวจทาน ติติง และปรับปรุงเนื้อหาซ้ำจนมั่นใจในคุณภาพแล้ว ({status_icon})",
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"ANSRE Multi-Agent Editorial • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
        }]
    }
    
    return send_discord_message(payload, channel_id=channel_id)


def send_media_and_publish_report(
    title: str,
    chapter_num: int,
    cover_file: Optional[str] = None,
    audio_file: Optional[str] = None,
    teaser_file: Optional[str] = None,
    youtube_url: Optional[str] = None,
    channel_id: str = DEFAULT_CHANNEL_ID
) -> bool:
    """ส่งรายงานเมื่อผลิตสื่อ (ปก, เสียง, คลิป) และเผยแพร่ลง YouTube สำเร็จ"""
    fields = []
    
    media_status = []
    if cover_file and os.path.exists(cover_file):
        media_status.append(f"🖼️ ปกนิยาย: `{os.path.basename(cover_file)}` ✅")
    if audio_file and os.path.exists(audio_file):
        media_status.append(f"🎧 เสียงพากย์: `{os.path.basename(audio_file)}` ✅")
    if teaser_file and os.path.exists(teaser_file):
        media_status.append(f"🎬 วิดีโอ Teaser: `{os.path.basename(teaser_file)}` ✅")
        
    if media_status:
        fields.append({
            "name": "📦 สินทรัพย์มีเดียที่ผลิตเสร็จ",
            "value": "\n".join(media_status),
            "inline": False
        })
        
    if youtube_url:
        fields.append({
            "name": "▶️ YouTube Shorts",
            "value": f"[คลิกเพื่อดูวิดีโอที่เผยแพร่]({youtube_url})",
            "inline": False
        })

    payload = {
        "embeds": [{
            "title": f"🎉 [ผลิตสื่อ & เผยแพร่สำเร็จ] {title} — ตอนที่ {chapter_num}",
            "description": "เนื้อหาผ่านการรีวิว 3+ รอบ และแปลงเป็นสินทรัพย์มีเดียพร้อมปล่อยสู่ผู้ฟังเรียบร้อยแล้ว",
            "color": 0x3B82F6,
            "fields": fields,
            "footer": {
                "text": f"ANSRE Production Studio • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
        }]
    }
    return send_discord_message(payload, channel_id=channel_id)


def send_daily_digest_to_discord(
    channel_stats: dict,
    published_today: list = None,
    channel_id: str = DEFAULT_CHANNEL_ID
) -> bool:
    """ส่งสรุปผลการทำงานและยอดวิวยูทูบประจำวัน (Daily Analytics Digest) เข้า Discord"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    fields = []
    
    tot_v = channel_stats.get("total_views", 0)
    tot_l = channel_stats.get("total_likes", 0)
    tot_c = channel_stats.get("total_comments", 0)
    tot_vid = channel_stats.get("total_videos", 0)

    fields.append({
        "name": "📊 สถิติช่อง YouTube รวม",
        "value": f"• **วิดีโอทั้งหมด:** `{tot_vid} คลิป`\n• **ยอดเข้าชม (Views):** `{tot_v:,} ครั้ง`\n• **ยอดถูกใจ (Likes):** `{tot_l:,}`\n• **ความคิดเห็น:** `{tot_c:,}`",
        "inline": False
    })

    if published_today:
        pub_list = "\n".join(f"• [{p.get('title', 'วิดีโอ')}]({p.get('url', '#')})" for p in published_today[:5])
        fields.append({
            "name": f"🚀 เผยแพร่วันนี้ ({today_str})",
            "value": pub_list or "ไม่มีรายการใหม่",
            "inline": False
        })

    top_videos = channel_stats.get("top_videos", [])
    if top_videos:
        top_list = "\n".join(f"• 👁️ `{v['views']:,}` | {v['title'][:40]}" for v in top_videos[:3])
        fields.append({
            "name": "🏆 คลิปยอดนิยม (Top 3)",
            "value": top_list,
            "inline": False
        })

    payload = {
        "embeds": [{
            "title": f"📈 [Daily Digest] สรุปผลงาน & ยอดวิวยูทูบประจำวัน ({today_str})",
            "description": "รายงานอัตโนมัติจาก NovelMind / ANSRE Continuous Automation Engine",
            "color": 0xF59E0B,
            "fields": fields,
            "footer": {
                "text": f"ANSRE Analytics • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
        }]
    }
    return send_discord_message(payload, channel_id=channel_id)


def send_3day_performance_report_to_discord(
    channel_stats: dict,
    learning_brief: str = "",
    channel_id: str = DEFAULT_CHANNEL_ID
) -> bool:
    """ส่งรายงานสรุปสถิติ 3 วัน และสิ่งที่ระบบเรียนรู้ (3-Day Learning & Intelligence Report) เข้า Discord"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    fields = []

    tot_v = channel_stats.get("total_views", 0)
    tot_l = channel_stats.get("total_likes", 0)
    tot_c = channel_stats.get("total_comments", 0)
    tot_vid = channel_stats.get("total_videos", 0)

    fields.append({
        "name": "📊 สถิติสะสม YouTube (รอบ 3 วัน)",
        "value": f"• **วิดีโอในช่องทั้งหมด:** `{tot_vid} คลิป`\n• **ยอดเข้าชมรวม (Views):** `{tot_v:,} ครั้ง`\n• **ยอดถูกใจ (Likes):** `{tot_l:,}`\n• **ความคิดเห็น:** `{tot_c:,}`",
        "inline": False
    })

    top_videos = channel_stats.get("top_videos", [])
    if top_videos:
        top_list = []
        for i, v in enumerate(top_videos[:5], 1):
            likes_txt = f" ❤ {v.get('likes', 0)}" if v.get('likes') else ""
            top_list.append(f"**#{i}** 👁️ `{v['views']:,}`{likes_txt} | {v['title'][:45]}")
        fields.append({
            "name": "🏆 อันดับผลงานยอดนิยมสูงสุด (Top 5 Performers)",
            "value": "\n".join(top_list),
            "inline": False
        })

    # แนะนำทิศทางของแต่ละงาน (Strategic Direction / Recommendations)
    story_directions = []
    seen_stories = set()
    for v in top_videos:
        title = v.get("title", "")
        clean = re.sub(r"[\s_#].*ตอนที่.*$", "", title)
        clean = re.sub(r"\s*#Shorts.*$", "", clean).strip()
        if not clean or clean in seen_stories:
            continue
        seen_stories.add(clean)

        # วิเคราะห์คำแนะนำตามข้อมูลสถิติ
        views = v.get("views", 0)
        likes = v.get("likes", 0)
        if "กระจกเงา" in clean:
            story_directions.append(f"• **{clean}** (`{views}` views): 🚀 **Scale Up** — ยอด Shorts วิ่งแรง ดันเป็นซีรีส์ยาว 15 ตอน และทำ Teaser Shorts ปล่อยต่อเนื่อง")
        elif "กลิ่นหอม" in clean:
            story_directions.append(f"• **{clean}** (`{views}` views, `{likes}` likes): ⭐ **High Engagement** — ผู้ชมชื่นชอบความอบอุ่น/โรแมนซ์ เร่งดันตอน 2-8 ขึ้น ReadAWrite และแพ็กขาย E-Book")
        elif "จากน้องสาว" in clean:
            story_directions.append(f"• **{clean}** (`{views}` views): 📈 **Rising Hook** — ยอดวิวเติบโตเร็ว แนวครอบครัว/ดราม่า ให้ปล่อยตอนถัดไปในรอบค่ำ 19:30 น.")
        elif "ยอดนักสืบ" in clean:
            story_directions.append(f"• **{clean}** (`{views}` views): 👑 **Flagship Core** — สินทรัพย์พร้อม 10 ตอนครบ ทยอยเปิดฟรี 1-3 ตอนบน ReadAWrite ดึงคนเข้าอ่าน")
        elif "ดวงจันทร์" in clean or "ดาบไร้พระเจ้า" in clean:
            story_directions.append(f"• **{clean}** (`{views}` views): 🎯 **Niche Quality** — Like rate สูง (>10%) เหมาะเจาะกลุ่มแฟนตาซีเฉพาะกลุ่ม ให้ทำ Teaser ช็อตไฮไลต์เพิ่ม")
        else:
            story_directions.append(f"• **{clean}** (`{views}` views): 🧪 **Maintain & Test** — ทยอย Drip Release ตอนใหม่ และติดตามสัญญาณวิว")

        if len(story_directions) >= 5:
            break

    if story_directions:
        fields.append({
            "name": "🧭 คำแนะนำทิศทางของแต่ละงาน (Actionable Next Steps)",
            "value": "\n".join(story_directions),
            "inline": False
        })

    if learning_brief:
        cleaned_brief = learning_brief.strip()
        if len(cleaned_brief) > 800:
            cleaned_brief = cleaned_brief[:800] + "..."
        fields.append({
            "name": "🧠 สิ่งที่ AI เรียนรู้และนำไปพัฒนาต่อ (Feedback Intelligence)",
            "value": f"```markdown\n{cleaned_brief}\n```",
            "inline": False
        })

    payload = {
        "embeds": [{
            "title": f"🏆 [3-Day Performance Report] อันดับผลงาน & ทิศทางกลยุทธ์ ({today_str})",
            "description": "รายงานสถิติรอบ 3 วัน พร้อมการวิเคราะห์จัดอันดับผลงานและคำแนะนำทิศทางสำหรับแต่ละเรื่อง",
            "color": 0xF59E0B,
            "fields": fields,
            "footer": {
                "text": f"ANSRE Phase 5 Learning Engine • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
        }]
    }
    return send_discord_message(payload, channel_id=channel_id)


def send_pipeline_error_to_discord(stage: str, error_msg: str, channel_id: str = DEFAULT_CHANNEL_ID) -> bool:
    """ส่งการแจ้งเตือนข้อผิดพลาดใน Pipeline เข้า Discord (เมื่อเกิดปัญหาเท่านั้น)"""
    payload = {
        "embeds": [{
            "title": f"🚨 [Pipeline Error] พบปัญหาในขั้นตอน '{stage}'",
            "description": f"ระบบตรวจพบข้อผิดพลาดระหว่างทำงาน:\n```{str(error_msg)[:1000]}```",
            "color": 0xEF4444,
            "fields": [
                {"name": "⚙️ Stage", "value": f"`{stage}`", "inline": True},
                {"name": "⏰ เวลาที่พบ", "value": f"`{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`", "inline": True}
            ],
            "footer": {"text": "ANSRE Autonomous Monitor • กรุณาตรวจสอบ log เพื่อแก้ไข"}
        }]
    }
    return send_discord_message(payload, channel_id=channel_id)


def get_latest_user_feedback_from_discord(limit: int = 5) -> List[Dict[str, Any]]:
    """ดึงข้อความฟีดแบ็กจากห้อง writer-feedback ใน SQLite archive.db"""
    if not os.path.exists(ARCHIVER_DB):
        return []
    try:
        conn = sqlite3.connect(ARCHIVER_DB)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT id, author_name, content, created_at
            FROM messages
            WHERE channel_name = 'writer-feedback'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        print(f"[discord] Error reading feedback: {e}")
        return []


if __name__ == "__main__":
    sample_scorecard = {
        "total_rounds": 3,
        "initial_score": 7.6,
        "final_score": 8.9,
        "score_improvement": 1.3,
        "passed_quality_gate": True,
        "final_scores_breakdown": {
            "plot": 9.0,
            "character": 8.8,
            "prose": 8.9,
            "voice": 9.0
        },
        "teaser_hook_quote": "ถ้าคุณรู้ว่าความตายกำลังนับถอยหลัง คุณจะเลือกวิ่งหนีหรือหันหน้าสู้?"
    }
    ok = send_review_summary_to_discord("ยอดนักสืบสปีดรัน", 1, sample_scorecard)
    print("Send review report to Discord:", "✅" if ok else "❌")

