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
                    "name": "🌐 `!novel [ชื่อเรื่อง]`",
                    "value": "ส่งนิยายขึ้น ReadAWrite (โดย เงาพันจันทร์)",
                    "inline": True
                },
                {
                    "name": "⚡ `!release`",
                    "value": "ปล่อยตอนถัดไปบน ReadAWrite ทันที",
                    "inline": True
                },
                {
                    "name": "🌊 `!wave [wave2|wave3]`",
                    "value": "ปล่อยผลงานตามระลอกเวลาทอง (เช่น `!wave wave2`)",
                    "inline": True
                },
                {
                    "name": "🧪 `!abtest [status|rotate]`",
                    "value": "ดูผล A/B Testing ปกหรือสั่งหมุนเวียนปกทันที",
                    "inline": True
                },
                {
                    "name": "💬 `!engage`",
                    "value": "ดึงสถิติสดและให้ 'เงาพันจันทร์' ตอบคอมเมนต์นักอ่าน",
                    "inline": True
                },
                {
                    "name": "🛡️ `!clean`",
                    "value": "สแกนคลีนคราบ AI และภาษาแปลกปลอมในทุกตอน 330 ตอน",
                    "inline": True
                },
                {
                    "name": "📚 `!ebook [ชื่อเรื่อง]`",
                    "value": "รวมเล่มไฟล์ E-Book (.epub) มาตรฐานขาย MEB",
                    "inline": True
                },
                {
                    "name": "🩺 `!doctor [ชื่อเรื่อง]`",
                    "value": "AI วินิจฉัยพล็อตและสร้างพิมพ์เขียวภาค 2",
                    "inline": True
                },
                {
                    "name": "🌐 `!syndicate [ชื่อเรื่อง]`",
                    "value": "ส่งนิยายข้ามค่ายไป Dek-D และ Fictionlog ทันที",
                    "inline": True
                },
                {
                    "name": "📱 `!platforms`",
                    "value": "เช็กสถานะการเชื่อมต่อ 3 แพลตฟอร์ม (RAW, Dek-D, Fictionlog)",
                    "inline": True
                },
                {
                    "name": "🎬 `!promo [ชื่อเรื่อง]`",
                    "value": "ผลิตคลิปโปรโมทสั้น 9:16 (TikTok/Shorts) พร้อมคลื่นเสียงและซับ",
                    "inline": True
                },
                {
                    "name": "🎨 `!social [ชื่อเรื่อง]`",
                    "value": "ผลิตการ์ตูนแก๊ก 4 ช่อง, แชทจำลอง, และการ์ดคำคมทอง",
                    "inline": True
                },
                {
                    "name": "🩺 `!cliffhanger`",
                    "value": "ตรวจคะแนนความค้างจุดตัดจบท้ายตอน 330 ตอน",
                    "inline": True
                },
                {
                    "name": "🌀 `!remix [ชื่อเรื่อง]`",
                    "value": "สร้างตอนพิเศษ Spin-Off จักรวาลคู่ขนาน (What-If)",
                    "inline": True
                },
                {
                    "name": "📡 `!radar` (หรือ `!trends`)",
                    "value": "สแกนเทรนด์ฮิต & วิเคราะห์โอกาสทองของนิยายเราในตลาด",
                    "inline": True
                },
                {
                    "name": "🌐 `!hub`",
                    "value": "ดู Showcase Hub & Landing Page รวมผลงานของเงาพันจันทร์",
                    "inline": True
                },
                {
                    "name": "🔓 `!privacy [จำนวน]`",
                    "value": "ปรับคลิป YouTube Unlisted เป็น Public",
                    "inline": True
                },
                {
                    "name": "📊 `!status`",
                    "value": "ดูคลังไอเดีย ยอดนิยาย และสถานะระบบวันนี้",
                    "inline": True
                }
            ],
            "footer": {"text": "ANSRE Autonomous Agent Studio • ควบคุมผ่านมือถือได้ทุกที่"}
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

    elif main_cmd == "!novel":
        title = " ".join(args).strip()
        if not title:
            send_discord_message({"content": "⚠️ กรุณาระบุชื่อเรื่อง เช่น `!novel ยอดนักสืบสปีดรัน`"}, channel_id)
            return

        send_discord_message({"content": f"🌐 กำลังนำเข้านิยาย **'{title}'** ขึ้นระบบ ReadAWrite (โดย เงาพันจันทร์)... ⏳"}, channel_id)

        def _run_novel():
            try:
                import web_novel_uploader
                res = web_novel_uploader.upload_story(title, platform="readawrite")
                if res:
                    send_discord_message({"content": f"🎉 อัปโหลดนิยาย **'{title}'** ขึ้น ReadAWrite สำเร็จครบถ้วนแล้วครับ!"}, channel_id)
                else:
                    send_discord_message({"content": f"❌ ไม่พบชุดเผยแพร่หรือเกิดข้อผิดพลาดในการอัปโหลด '{title}'"}, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ เกิดข้อผิดพลาด: `{e}`"}, channel_id)

        threading.Thread(target=_run_novel, daemon=True).start()

    elif main_cmd == "!release":
        send_discord_message({"content": "⚡ กำลังสั่งการปล่อยตอนใหม่ (Drip Release) บน ReadAWrite สู่สาธารณะทันที... ⏳"}, channel_id)

        def _run_rel():
            try:
                import auto_release_scheduler
                auto_release_scheduler.cron_tick(force=True)
            except Exception as e:
                send_discord_message({"content": f"❌ การปล่อยตอนล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_rel, daemon=True).start()

    elif main_cmd == "!wave":
        wave_name = args[0].lower() if args else "wave2"
        send_discord_message({"content": f"🌊 กำลังสั่งปล่อยงานตามระลอก **{wave_name.upper()}** สู่ ReadAWrite... ⏳"}, channel_id)

        def _run_wave():
            try:
                from auto_publishing_system import release_wave
                release_wave(wave_name)
                send_discord_message({"content": f"✅ ดำเนินการปล่อยงานตาม **{wave_name.upper()}** เสร็จสิ้นเรียบร้อยครับ!"}, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การปล่อย Wave ล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_wave, daemon=True).start()

    elif main_cmd == "!abtest":
        sub = args[0].lower() if args else "status"
        if sub in ("rotate", "swap"):
            send_discord_message({"content": "🧪 กำลังตรวจสอบ View Velocity และหมุนเวียนสลับภาพปก/คำโปรย (A/B Test)... ⏳"}, channel_id)

            def _run_rotate():
                try:
                    from ab_testing_optimizer import evaluate_and_auto_rotate
                    evaluate_and_auto_rotate()
                    send_discord_message({"content": "🎉 ดำเนินการสลับ Variant สำเร็จเรียบร้อย!"}, channel_id)
                except Exception as e:
                    send_discord_message({"content": f"❌ การสลับ Variant ล้มเหลว: `{e}`"}, channel_id)

            threading.Thread(target=_run_rotate, daemon=True).start()
        else:
            try:
                from ab_testing_optimizer import load_experiments
                exp_data = load_experiments()
                fields = []
                for t, exp in list(exp_data.get("experiments", {}).items())[:6]:
                    cur = exp.get("current_variant", "A")
                    switches = len(exp.get("switch_history", []))
                    fields.append({
                        "name": f"📖 {t[:30]}...",
                        "value": f"• กำลังรัน: `Variant {cur}` (สลับมา {switches} ครั้ง)",
                        "inline": True
                    })
                send_discord_message({
                    "embeds": [{
                        "title": "🧪 แดชบอร์ด A/B Testing ปกและคำโปรย",
                        "description": "พิมพ์ `!abtest rotate` เพื่อสั่งประเมินและหมุนเวียนปกทันที",
                        "color": 0x8B5CF6,
                        "fields": fields
                    }]
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ เกิดข้อผิดพลาด: `{e}`"}, channel_id)

    elif main_cmd == "!engage":
        send_discord_message({"content": "💬 กำลังดึงสถิติสด และให้นักเขียน **'เงาพันจันทร์'** สแกนตอบคอมเมนต์นักอ่าน... ⏳"}, channel_id)

        def _run_engage():
            try:
                from reader_engagement_engine import run_engagement_cycle
                res = run_engagement_cycle()
                send_discord_message({
                    "content": f"🎉 สรุปรอบ Engagement: ดึงสถิติ {res['metrics_count']} เรื่อง และโพสต์ตอบคอมเมนต์ไป {res['replies_sent']} ข้อความ!"
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ Engagement ล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_engage, daemon=True).start()

    elif main_cmd == "!clean":
        send_discord_message({"content": "🛡️ กำลังสแกนคลีน AI noise, JSON, และอักขระตกค้างในทุกตอน 330 ตอน... ⏳"}, channel_id)

        def _run_clean():
            try:
                from auto_content_guard import scan_and_clean_all_chapters
                res = scan_and_clean_all_chapters()
                send_discord_message({
                    "content": f"✅ คลีนเสร็จสิ้น! ตรวจทั้งหมด `{res['total']}` ตอน, แก้ไข `{res['fixed']}` ตอน, ผ่านเกณฑ์ 100% `{res['passed']}` ตอน"
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การคลีนล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_clean, daemon=True).start()

    elif main_cmd == "!ebook":
        title = " ".join(args).strip()
        if not title:
            send_discord_message({"content": "⚠️ กรุณาระบุชื่อเรื่อง เช่น `!ebook เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง`"}, channel_id)
            return
        send_discord_message({"content": f"📚 กำลังรวมเล่ม E-Book (.epub) มาตรฐาน MEB สำหรับเรื่อง **'{title}'**... ⏳"}, channel_id)

        def _run_ebook():
            try:
                from epub_packager import create_epub
                path = create_epub(title)
                send_discord_message({
                    "content": f"🎉 รวมเล่ม E-Book สำเร็จแล้วครับ!\n📂 ไฟล์: `{path}` พร้อมนำไปอัปโหลดขึ้นร้านค้า MEB Market ได้ทันที"
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การรวมเล่มล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_ebook, daemon=True).start()

    elif main_cmd == "!doctor":
        title = " ".join(args).strip()
        send_discord_message({"content": f"🩺 AI Plot Doctor กำลังตรวจวิเคราะห์เรตติ้งและวางโครงพล็อตภาคต่อ... ⏳"}, channel_id)

        def _run_doctor():
            try:
                from ai_plot_doctor import diagnose_story_and_prescribe_season2, run_doctor_for_all_flagships
                if title:
                    res = diagnose_story_and_prescribe_season2(title)
                    s2 = res["season_2_blueprint"]
                    send_discord_message({
                        "embeds": [{
                            "title": f"🩺 [Plot Doctor Blueprint] {s2['title']}",
                            "description": f"**ปมขัดแย้งหลัก:** {s2['core_conflict']}",
                            "color": 0x10B981,
                            "fields": [
                                {"name": "📋 แนวทางตอนที่ 1–4", "value": "\n".join(s2['chapter_arcs'][:4]), "inline": False},
                                {"name": "🔥 จุดไคลแมกซ์ตอนที่ 5–8", "value": "\n".join(s2['chapter_arcs'][4:]), "inline": False}
                            ]
                        }]
                    }, channel_id)
                else:
                    run_doctor_for_all_flagships()
                    send_discord_message({"content": "✅ วิเคราะห์และสร้างพิมพ์เขียวภาค 2 ครบทั้ง 4 เรื่องหลักแล้ว บันทึกใน `Plot_Doctor/` เรียบร้อยครับ!"}, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ Plot Doctor ล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_doctor, daemon=True).start()

    elif main_cmd == "!privacy":
        lim = int(args[0]) if args else 3
        send_discord_message({"content": f"🔓 กำลังปรับคลิป YouTube Unlisted เป็น Public จำนวน {lim} คลิป... ⏳"}, channel_id)

        def _run_privacy():
            try:
                from update_privacy import update_privacy
                update_privacy(mode="update", limit=lim, target_privacy="public")
                send_discord_message({"content": f"✅ ปรับสถานะเป็น Public เพิ่ม {lim} คลิปสำเร็จแล้ว!"}, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การปรับสถานะล้มเหลว: `{e}`"}, channel_id)

    elif main_cmd in ("!syndicate", "!dekd", "!fictionlog"):
        story_q = " ".join(args).strip() if args else "คุณแม่ลูกแฝด"
        target_plats = ["dekd", "fictionlog"]
        if main_cmd == "!dekd":
            target_plats = ["dekd"]
        elif main_cmd == "!fictionlog":
            target_plats = ["fictionlog"]

        send_discord_message({
            "content": f"🌐 ได้รับคำสั่งส่งนิยายข้ามค่าย '{story_q}' สู่ {', '.join(target_plats).upper()}... กำลังเริ่มดำเนินการ ⏳"
        }, channel_id)

        def _run_syndicate():
            try:
                from cross_platform_syndicator import syndicate_story
                res = syndicate_story(story_q, platforms=target_plats, dry_run=False)
                if not res.get("success"):
                    send_discord_message({"content": f"❌ การส่งนิยายล้มเหลว: `{res.get('error')}`"}, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ เกิดข้อผิดพลาดในการซิงค์: `{e}`"}, channel_id)

        threading.Thread(target=_run_syndicate, daemon=True).start()

    elif main_cmd == "!platforms":
        from cross_platform_syndicator import check_platform_auth, load_syndication_ledger
        auths = check_platform_auth()
        ledger = load_syndication_ledger()
        stories_cnt = len(ledger.get("stories", {}))

        fields = []
        for k, v in auths.items():
            icon = "✅ พร้อมใช้งาน" if v["valid"] else "❌ ต้องยืนยันตัวตน"
            fields.append({
                "name": f"{v['name']}",
                "value": f"สถานะ: **{icon}**\nผู้ใช้: `{v['author']}`",
                "inline": True
            })

        embed = {
            "title": "📱 สถานะแพลตฟอร์มนิยายและการซิงค์ข้ามค่าย",
            "description": f"ระบบรองรับการส่งพร้อมกัน 3 แพลตฟอร์ม (บันทึกใน Ledger แล้ว {stories_cnt} เรื่อง)",
            "color": 0x3B82F6,
            "fields": fields,
            "footer": {"text": "ใช้คำสั่ง !syndicate [ชื่อเรื่อง] หรือ python cross_platform_syndicator.py --auth [platform]"}
        }
        send_discord_message({"embeds": [embed]}, channel_id)

    elif main_cmd == "!promo":
        story_q = " ".join(args).strip() if args else "คุณแม่ลูกแฝด"
        send_discord_message({"content": f"🎬 กำลังเรนเดอร์วิดีโอโปรโมทสั้น (9:16 Shorts/TikTok) สำหรับ '{story_q}'... ⏳"}, channel_id)

        def _run_promo():
            try:
                from dynamic_promo_video_engine import render_dynamic_promo_video
                v_path = render_dynamic_promo_video(story_q, duration_sec=35.0)
                if v_path and os.path.exists(v_path):
                    sz_mb = os.path.getsize(v_path) / (1024 * 1024)
                    send_discord_message({
                        "embeds": [{
                            "title": f"🎬 [Promo Shorts Ready] {os.path.basename(v_path)}",
                            "description": f"ผลิตวิดีโอโปรโมทแนวตั้ง 9:16 สำหรับ TikTok, IG Reels และ YouTube Shorts สำเร็จแล้ว!",
                            "color": 0x10B981,
                            "fields": [
                                {"name": "📹 ไฟล์วิดีโอ", "value": f"`{os.path.basename(v_path)}` ({sz_mb:.1f} MB)", "inline": True},
                                {"name": "✨ องค์ประกอบ", "value": "• Viral Top Hook\n• Center 3:4 Cover Art\n• Animated Audio Waveform\n• Bottom CTA Button", "inline": True}
                            ]
                        }]
                    }, channel_id)
                else:
                    send_discord_message({"content": "❌ ไม่สามารถเรนเดอร์วิดีโอได้ (ไม่พบไฟล์เสียงหรือหน้าปก)"}, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การเรนเดอร์วิดีโอล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_promo, daemon=True).start()

    elif main_cmd == "!social":
        story_q = " ".join(args).strip() if args else "เมื่อนางร้ายหมดรัก_ท่านประธานก็เริ่มคลั่ง"
        send_discord_message({"content": f"🎨 กำลังผลิตชุดกราฟิกโซเชียล (Webtoon 4 ช่อง, แชทจำลอง, การ์ดคำคม) สำหรับ '{story_q}'... ⏳"}, channel_id)

        def _run_social():
            try:
                from viral_social_studio import generate_all_social_assets_for_story
                res = generate_all_social_assets_for_story(story_q)
                send_discord_message({
                    "embeds": [{
                        "title": f"🎨 [Social Marketing Kit] {story_q}",
                        "description": "ผลิตสื่อโปรโมทสำหรับ Facebook Page, X (Twitter), และ Lemon8 ครบเซ็ต:",
                        "color": 0xF59E0B,
                        "fields": [
                            {"name": "🖼️ มินิเว็บตูน 4 ช่อง", "value": f"`{os.path.basename(res['comic'])}`", "inline": True},
                            {"name": "💬 ภาพแชทจำลอง", "value": f"`{os.path.basename(res['chat'])}`", "inline": True},
                            {"name": "✨ การ์ดคำคมทอง", "value": f"`{os.path.basename(res['quote'])}`", "inline": True}
                        ]
                    }]
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การผลิตสื่อโซเชียลล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_social, daemon=True).start()

    elif main_cmd == "!cliffhanger":
        send_discord_message({"content": "🩺 AI Cliffhanger Auditor กำลังตรวจคะแนนความค้างของจุดตัดจบท้ายตอน 330 ตอน... ⏳"}, channel_id)

        def _run_cliff():
            try:
                from cliffhanger_and_scene_engine import audit_all_flagship_chapters
                results = audit_all_flagship_chapters(dry_run=True)
                low_cnt = sum(1 for r in results if r["score_before"] < 7)
                send_discord_message({
                    "embeds": [{
                        "title": "🩺 [Cliffhanger Retention Report]",
                        "description": f"ผลการวิเคราะห์ 200 คำสุดท้ายของแต่ละตอน เพื่อกระตุ้น Binge-Reading Rate:",
                        "color": 0x3B82F6,
                        "fields": [
                            {"name": "📊 จำนวนตอนที่ตรวจ", "value": f"{len(results)} ตอน", "inline": True},
                            {"name": "⚠️ ตอนที่ควรปรับให้ค้างขึ้น", "value": f"{low_cnt} ตอน", "inline": True},
                            {"name": "💡 การปรับปรุง", "value": "เติม Dramatic Punchlines + โพลล์ชวนอ่านต่อท้ายตอน", "inline": False}
                        ]
                    }]
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การตรวจ Cliffhanger ล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_cliff, daemon=True).start()

    elif main_cmd == "!remix":
        story_q = " ".join(args).strip() if args else "คุณแม่ลูกแฝดยุค_70"
        send_discord_message({"content": f"🌀 Trope Remixer กำลังเขียนตอนพิเศษ Spin-Off จักรวาลคู่ขนานสำหรับ '{story_q}'... ⏳"}, channel_id)

        def _run_remix():
            try:
                from trend_trope_remixer import generate_spin_off_chapter
                res = generate_spin_off_chapter(story_q, "modern_au")
                send_discord_message({
                    "embeds": [{
                        "title": f"🌀 [Spin-Off What-If Ready] {res['title']}",
                        "description": "สร้างตอนพิเศษจักรวาลคู่ขนานดักกระแสความนิยมเรียบร้อยแล้ว!",
                        "color": 0x8B5CF6,
                        "fields": [
                            {"name": "📁 บันทึกที่", "value": f"`{os.path.basename(res['file'])}`", "inline": True},
                            {"name": "📝 ความยาว", "value": f"~{res['words']} คำ", "inline": True}
                        ]
                    }]
                }, channel_id)
            except Exception as e:
                send_discord_message({"content": f"❌ การเขียนตอนพิเศษล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_remix, daemon=True).start()

    elif main_cmd in ("!radar", "!trends"):
        send_discord_message({"content": "📡 กำลังเชื่อมต่อ Playwright สแกนกระแส Dek-D Novel และจัดอันดับ Market-Fit... ⏳"}, channel_id)

        def _run_radar():
            try:
                from trend_scraping_radar import dispatch_radar_discord_report
                dispatch_radar_discord_report()
            except Exception as e:
                send_discord_message({"content": f"❌ การสแกน Market Radar ล้มเหลว: `{e}`"}, channel_id)

        threading.Thread(target=_run_radar, daemon=True).start()

    elif main_cmd == "!hub":
        embed = {
            "title": "🌟 [Author Brand Hub] เงาพันจันทร์ (Panjan Studio)",
            "description": "ศูนย์รวมผลงานนิยาย มัลติมีเดีย และเว็บตูน 4 ช่อง ครบทุกเรื่อง:",
            "color": 0xF59E0B,
            "fields": [
                {"name": "📚 คลังนิยายเรือธง", "value": "• ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70\n• เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง\n• รักกับเจ้าหญิงเพลย์บอย\n• สมาคมประกันภัยลี้ลับ", "inline": False},
                {"name": "🎨 มัลติมีเดียในฮับ", "value": "• มินิเว็บตูน 4 ช่อง\n• ภาพแชทตัวละครจำลอง\n• การ์ดคำคมทอง Dark Luxury\n• นิยายเสียง & คลิปโปรโมทสั้น 9:16", "inline": False},
                {"name": "💻 วิธีเปิดดูผ่านเครื่อง", "value": "รันคำสั่ง `python author_showcase_hub.py --open` หรือ `python auto_publishing_system.py --hub`", "inline": False}
            ],
            "footer": {"text": "Panjan Autonomous Creative Studio • Hub Online"}
        }
        send_discord_message({"embeds": [embed]}, channel_id)


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
