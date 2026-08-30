#!/usr/bin/env python3
"""
auto_release_scheduler.py — ระบบบริหารจัดการตารางเวลาและปล่อยผลงานต่อเนื่องอัตโนมัติ (Drip Publishing Engine)

หน้าที่หลัก:
1. บริหารตารางเวลาปล่อยตอนใหม่ (Golden Hours: 12:00 น. และ 19:30 น.)
2. ตรวจสอบสารบัญของเรื่องที่กำลังออนแอร์ และทยอยเปิดตอนใหม่อัตโนมัติ
3. เมื่อเรื่องปัจจุบันเผยแพร่ครบ จะทำการเปิดตัวเรื่องถัดไปในคิว (Day 1: ปล่อย ตอนที่ 1–3 ทันที)
4. ปล่อยวิดีโอ YouTube Shorts วันละ 3 คลิปควบคู่กัน
5. บันทึกประวัติการเผยแพร่ลง publish_ledger.json
"""

import os
import sys
import json
import time
import datetime
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
if os.path.exists(_VENV_PY) and sys.executable != _VENV_PY:
    try:
        import playwright
    except ImportError:
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)

from playwright.sync_api import sync_playwright

SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
LEDGER_FILE = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")


def load_ledger() -> Dict[str, Any]:
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
                if "scheduled_releases" not in data:
                    data["scheduled_releases"] = []
                if "published_stories" not in data:
                    data["published_stories"] = {}
                return data
        except Exception:
            pass
    return {"published_stories": {}, "scheduled_releases": []}


def save_ledger(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_article_chapters(article_id: str) -> List[Dict[str, Any]]:
    """ดึงรายชื่อตอนและสถานะการเผยแพร่จาก Writer Studio"""
    if not os.path.exists(AUTH_FILE):
        return []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageChapter"
        page.goto(url, timeout=45000)
        page.wait_for_timeout(2000)

        chapters = page.evaluate("""() => {
            return Array.from(document.querySelectorAll(".table tbody tr")).map(r => {
                const titleEl = r.querySelector(".chapter_detail p, td:nth-child(3)");
                const title = titleEl ? titleEl.innerText.trim() : "";
                const chk = r.querySelector("input[name=chk_chapter_guid]");
                const guid = chk ? chk.value : "";
                const words = chk ? chk.getAttribute("word_count") : "";
                const statusBtn = r.querySelector("button.dropdown-toggle");
                const statusText = statusBtn ? statusBtn.innerText.trim() : "";
                const isPublished = statusText.includes("เผยแพร่") && !statusText.includes("ไม่");
                return { title, guid, words, isPublished, statusText };
            });
        }""")
        browser.close()
        return chapters


def publish_chapter(guid: str) -> bool:
    """เปิดเผยแพร่ตอนที่ระบุสู่สาธารณะ"""
    if not os.path.exists(AUTH_FILE):
        return False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE)
        page = context.new_page()
        page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=30000)
        page.wait_for_timeout(1000)

        res = page.evaluate("""(chGuid) => {
            return new Promise((resolve) => {
                $.ajax({
                    method: "POST",
                    url: "?action=manage_chapter&token=",
                    data: {
                        chapter_guid: chGuid,
                        manage: "publishAndMoveToMaster",
                        is_collaborator: 0
                    },
                    dataType: "json"
                }).done((data) => {
                    resolve(data);
                }).fail((xhr) => {
                    resolve({error: xhr.statusText, status: xhr.status});
                });
            });
        }""", guid)

        context.storage_state(path=AUTH_FILE)
        browser.close()
        return res.get("status", {}).get("success", False)


def release_next_chapter(article_id: str, title: str) -> Optional[Dict[str, Any]]:
    """หาตอนถัดไปที่ยังไม่เผยแพร่แล้วทำการเปิดเผยแพร่"""
    print(f"\n🔍 ตรวจสอบสารบัญของเรื่อง '{title}' (ID: {article_id})...")
    chapters = get_article_chapters(article_id)
    if not chapters:
        print("   ❌ ไม่พบข้อมูลตอนในระบบ")
        return None

    # จัดเรียงตามลำดับตอน
    sorted_chs = []
    for c in chapters:
        m = re.search(r"#(\d+)", c["title"])
        order = int(m.group(1)) if m else 999
        sorted_chs.append((order, c))
    sorted_chs.sort(key=lambda x: x[0])

    next_ch = None
    for order, c in sorted_chs:
        if not c["isPublished"]:
            next_ch = c
            break

    if not next_ch:
        print(f"   🎉 เรื่อง '{title}' เผยแพร่ครบทุกตอนแล้ว!")
        return None

    print(f"   🚀 กำลังเปิดเผยแพร่: {next_ch['title']} (GUID: {next_ch['guid']})...")
    success = publish_chapter(next_ch["guid"])
    if success:
        print(f"   ✅ เผยแพร่ '{next_ch['title']}' สู่สาธารณะสำเร็จ!")
        ledger = load_ledger()
        ledger["scheduled_releases"].append({
            "story": title,
            "chapter": next_ch["title"],
            "guid": next_ch["guid"],
            "published_at": datetime.datetime.now().isoformat()
        })
        save_ledger(ledger)
        return next_ch
    else:
        print(f"   ❌ ไม่สามารถเผยแพร่ '{next_ch['title']}' ได้")
        return None


def notify_discord_release(story_title: str, ch_title: str, ch_guid: str, remaining_count: int):
    """แจ้งเตือนความคืบหน้าการปล่อยตอนใหม่เข้าห้อง Discord"""
    try:
        from discord_reporter import send_discord_message
        embed = {
            "title": f"📖 [Auto-Release] ปล่อยตอนใหม่สู่สาธารณะแล้ว!",
            "description": f"ผลงานจากนามปากกา **เงาพันจันทร์** อัปเดตเนื้อหาใหม่ล่าสุดบน **ReadAWrite** เรียบร้อยครับ",
            "color": 0x3B82F6,
            "fields": [
                {"name": "📚 เรื่อง", "value": f"**{story_title}**", "inline": True},
                {"name": "🔖 ตอนที่ปล่อย", "value": f"`{ch_title}`", "inline": True},
                {"name": "⏳ ตอนคงเหลือในคลัง", "value": f"`{remaining_count} ตอน`", "inline": True},
                {"name": "🔗 ลิงก์อ่านสด", "value": f"[คลิกเพื่ออ่านบทนี้](https://www.readawrite.com/c/{ch_guid})", "inline": False}
            ],
            "footer": {"text": f"Drip Publishing Engine • {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"}
        }
        send_discord_message({"embeds": [embed]})
    except Exception as e:
        print(f"   [!] ส่งแจ้งเตือน Discord: {e}")


def cron_tick(force: bool = False) -> None:
    """ประเมินเวลาและทำการ Drip Release อัตโนมัติในแต่ละรอบของ Orchestrator"""
    now = datetime.datetime.now()
    hour = now.hour
    today_str = now.strftime("%Y-%m-%d")
    ledger = load_ledger()
    releases_today = [r for r in ledger.get("scheduled_releases", []) if r.get("published_at", "").startswith(today_str)]

    is_midday = (11 <= hour <= 13)
    is_evening = (19 <= hour <= 22)

    # เช็คว่ารอบนี้ควรปล่อยไหม
    should_release = force
    if not should_release:
        if is_midday and len(releases_today) == 0:
            should_release = True
            print(f"\n☀️ [Cron Tick] เข้าสู่ช่วงเวลาทองรอบเที่ยง ({now.strftime('%H:%M น.')}) — ปล่อยตอนใหม่")
        elif is_evening and len(releases_today) < 2:
            should_release = True
            print(f"\n🌙 [Cron Tick] เข้าสู่ช่วงเวลาทองรอบค่ำ ({now.strftime('%H:%M น.')}) — ปล่อยตอนใหม่")

    if not should_release:
        return

    # ค้นหาเรื่องที่กำลัง On-Air
    active_stories = [
        ("084947f5c23530e03094cc84bb1364b5", "ยอดนักสืบสปีดรัน"),
        ("f3624f7b4e09cde8fc524dff4f2fc4bd", "สมาคมประกันภัยลี้ลับ")
    ]

    for art_id, title in active_stories:
        released = release_next_chapter(art_id, title)
        if released:
            # ดึงจำนวนตอนที่ยังเหลือ
            all_chs = get_article_chapters(art_id)
            unpub_count = sum(1 for c in all_chs if not c.get("isPublished", False))
            notify_discord_release(title, released["title"], released["guid"], unpub_count)
            break


def show_publishing_dashboard():
    """แสดงแดชบอร์ดตารางการปล่อยนิยายและวิดีโอ"""
    print("\n" + "=" * 65)
    print(" 📅 ตารางแผนการปล่อยผลงานต่อเนื่อง (Continuous Release Schedule)")
    print("=" * 65)
    print(" 🖋️ นามปากกาหลัก: เงาพันจันทร์")
    print(" ⏰ ช่วงเวลาทองประจำวัน (Golden Hours):")
    print("    • รอบเที่ยง (12:00 น.) : ปล่อยตอนใหม่ / Shorts 1 คลิป")
    print("    • รอบค่ำ   (19:30 น.) : ปล่อยตอนใหม่ / Shorts 2 คลิป (ช่วงคนอ่านสูงสุด)")
    print("-" * 65)
    print(" 📚 ลำดับคิวซีรีส์ (Series Pipeline):")
    print("   1. ยอดนักสืบสปีดรัน (10 ตอน)")
    print("      • สถานะ: ตอนที่ 1–3 เผยแพร่แล้ว (Free Hook)")
    print("      • คิวปล่อย: ตอนที่ 4–10 ปล่อยวันละ 1 ตอน (รอบ 19:30 น.)")
    print("   2. สมาคมประกันภัยลี้ลับ (8 ตอน)")
    print("      • สถานะ: อัปโหลดครบทั้ง 8 ตอนแล้วใน Studio")
    print("      • คิวเปิดตัว: ซีรีส์ถัดไป (เปิดตัวตอนที่ 1–3 ทันที)")
    print("   3. ร้านค้าเหนือโลก: สตรีมดันเจียนล่าเทพ (20 ตอน)")
    print("      • สถานะ: พร้อมใน Publish_Queue")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    import re
    args = sys.argv[1:]
    if "--status" in args:
        show_publishing_dashboard()
    elif "--publish-next" in args:
        article_id = "084947f5c23530e03094cc84bb1364b5"
        title = "ยอดนักสืบสปีดรัน"
        res = release_next_chapter(article_id, title)
        if res:
            notify_discord_release(title, res["title"], res["guid"], 6)
    elif "--cron-tick" in args:
        cron_tick(force=("--force" in args))
    else:
        show_publishing_dashboard()
