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
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
LEDGER_FILE = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")


def load_ledger() -> Dict[str, Any]:
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
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
    print("      • สถานะ: อัปโหลดเข้าสู่ระบบแล้ว")
    print("      • คิวเปิดตัว: สัปดาห์ถัดไป (เปิดตัวตอนที่ 1–3 ทันที)")
    print("   3. ร้านค้าเหนือโลก: สตรีมดันเจียนล่าเทพ (20 ตอน)")
    print("      • สถานะ: พร้อมใน Publish_Queue")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    import re
    args = sys.argv[1:]
    if "--status" in args or not args:
        show_publishing_dashboard()
    elif "--publish-next" in args:
        article_id = "084947f5c23530e03094cc84bb1364b5"
        title = "ยอดนักสืบสปีดรัน"
        release_next_chapter(article_id, title)
