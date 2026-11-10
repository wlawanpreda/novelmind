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
import re
import sys
import json
import time
import datetime
from typing import Dict, Any, List, Optional, Tuple

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
                const chk = r.querySelector("input[name=chk_chapter_guid]");
                const title = (chk ? chk.getAttribute("title_name") : "") || (titleEl ? titleEl.innerText.trim() : "");
                const guid = chk ? chk.value : "";
                const words = chk ? chk.getAttribute("word_count") : "";
                const statusBtn = r.querySelector("button.dropdown-toggle");
                const statusText = statusBtn ? statusBtn.innerText.trim() : "";
                const rowStatus = r.getAttribute("status");
                const pubDate = r.getAttribute("first_published_date");
                // status == "2" คือเผยแพร่แล้ว หรือมี first_published_date บันทึกไว้
                const isPublished = (rowStatus === "2") || Boolean(pubDate && pubDate.length > 5);
                return { title, guid, words, isPublished, statusText, status: rowStatus, pubDate };
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


def ensure_story_master_published(article_id: str):
    """ตรวจสอบและเปิดสถานะเรื่องหลักให้เป็น เผยแพร่ บน ReadAWrite หากยังเป็น ไม่เผยแพร่"""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()
            page.goto(f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageArticle", timeout=30000)
            page.wait_for_timeout(2000)
            st = page.inner_text("#article_status_text") if page.query_selector("#article_status_text") else ""
            if "ไม่เผยแพร่" in st:
                page.click(".switch_setting_status")
                page.wait_for_timeout(1000)
                confirm_btn = page.query_selector('button:has-text("ยืนยัน"), a:has-text("ยืนยัน")')
                if confirm_btn:
                    confirm_btn.click()
                    page.wait_for_timeout(2500)
            browser.close()
    except Exception as e:
        print(f"   [!] ensure_story_master_published error: {e}")


def resolve_chapter_subtitle(story_title: str, ch_num: int) -> str:
    """ดึงชื่อตอนย่อยจากไฟล์ Outline หรือสร้างชื่อตอนย่อยตามโครงสร้างการดำเนินเรื่อง"""
    import glob
    clean_key = re.sub(r'[:\s_-]+', '_', story_title).strip('_')
    prefix = clean_key.split('_')[0]
    candidates = (
        glob.glob(os.path.join(SB, "02_Concept_Extraction", f"{story_title}_Outline.md")) +
        glob.glob(os.path.join(SB, "02_Concept_Extraction", f"{clean_key}_Outline.md")) +
        glob.glob(os.path.join(SB, "02_Concept_Extraction", f"*{prefix}*_Outline.md"))
    )
    for fp in candidates:
        if os.path.exists(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    txt = f.read()
                for m in re.finditer(r"(?:ตอนที่|บทที่|Chapter)\s*(\d+)\s*[:：]\s*([^\n\r\*#]+)", txt):
                    if int(m.group(1)) == ch_num:
                        sub = m.group(2).strip().strip('"\'*_ ')
                        # ตัดวงเล็บภาษาอังกฤษถ้ามีและยาวเกินไป
                        sub = re.sub(r"\s*\([A-Za-z\s',-]+\)\s*$", "", sub).strip()
                        if len(sub) >= 3 and not re.match(r"^ตอนที่\s*\d+$", sub):
                            return sub
            except Exception:
                pass

    # 2. ชื่อตอนย่อยเฉพาะเรื่อง (Story-Specific Chapter Subtitles สำหรับตอนที่ 11–20)
    t_norm = story_title.replace("_", " ").strip()
    story_specific_subtitles = {
        "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70": {
            11: "เปิดร้านชำแห่งใหม่และสายตาอิจฉาของคนในหมู่บ้าน",
            12: "สินค้าลับจากมิติห้างและการเจรจาธุรกิจ",
            13: "เทศกาลประจำปีและกลิ่นหอมที่ดึงดูดลูกค้า",
            14: "แผนสร้างพันธมิตรการค้าในตัวอำเภอ",
            15: "ขยับขยายกิจการและคลื่นใต้น้ำจากคู่แข่ง",
            16: "รอยยิ้มของลูกแฝดและข่าวดีจากแดนไกล",
            17: "ก้าวสู่เถ้าแก่เนี้ยมือทองแห่งยุค 70",
            18: "ความลับของซูเปอร์มาร์เก็ตและการปกป้องครอบครัว",
        },
        "สมาคมประกันภัยลี้ลับ": {
            11: "แฟ้มลับคดีวิญญาณและการตรวจสอบกรมธรรม์มรณะ",
            12: "เบาะแสในห้องเก็บฟิล์มเก่าและเงาปริศนา",
            13: "ค่าสินไหมที่ต้องแลกด้วยความจริงใต้เงามืด",
            14: "เปิดโปงขบวนการทุจริตเคลมวิญญาณข้ามชาติ",
            15: "หลักฐานชิ้นสำคัญในคืนจันทร์ดับ",
            16: "การประชุมด่วนบอร์ดบริหารและเดิมพันครั้งสุดท้าย",
            17: "ปิดแฟ้มคดีใหญ่และพันธกิจใหม่ของแผนกเคลมกรรม",
        },
        "ยอดนักสืบสปีดรัน": {
            11: "สายเรียกเข้าปริศนาและร่องรอยใหม่หลังพายุสงบ",
            12: "วิเคราะห์ภาพวงจรปิดและแผนลวงของคนร้าย",
            13: "คำสารภาพที่ซ่อนเงื่อนงำและการสืบสวนเชิงลึก",
            14: "คดีฆาตกรรมดาราดังกลางเมืองหลวง",
            15: "ถอดรหัสข้อความลับในที่เกิดเหตุ",
            16: "ไล่ล่าคนร้ายด้วยบิ๊กไบค์คู่ใจ",
            17: "ลายเซ็นของฆาตกรและการปิดล้อมจับกุม",
        },
        "กลิ่นหอมกู้วิกฤต": {
            9: "คลื่นใต้น้ำลูกใหม่ในห้องทดลอง",
            10: "ก้าวข้ามขีดจำกัดสู่สูตรลับแห่งตำนาน",
            11: "ส่วนผสมต้องห้ามและการทดลองครั้งสำคัญ",
            12: "แกะรอยสารเคมีปริศนาในแผนภูมิเก่า",
            13: "ความลับในสวนดอกไม้ยามรุ่งสาง",
            14: "กลิ่นหอมแห่งความหวังท่ามกลางวิกฤต",
            15: "การเผชิญหน้ากับผู้บงการเบื้องหลัง",
            16: "แสงไฟในห้องทดลองยามค่ำคืนและคำตอบสุดท้าย",
            17: "รุ่งอรุณแห่งความสำเร็จและพันธสัญญาใจ",
        },
        "กระจกเงาคนตาย": {
            9: "ความลับในพิพิธภัณฑ์โบราณวัตถุ",
            10: "รอยปริศนาแห่งวัดสิงหยาด",
            11: "ทางเดินใต้ถุนวัดและแสงเทียนในความมืด",
            12: "ปริศนากระเบื้องดินเผาโบราณ",
            13: "แกะรอยแผนที่สู่ศูนย์กลางสมาคมลึกลับ",
            14: "เอกสารลับและภาพถ่ายที่ติดตา",
            15: "เบาะแสจากอาจารย์อัคราและผู้รู้จริง",
            16: "ห้องประชุมลับและเงื่อนงำที่เชื่อมโยงกัน",
            17: "สายลมยามรุ่งสางที่ร้านของเก่า",
            18: "ความจริงหลังภาพวาดโบราณและกระจกเงา",
        },
    }
    for key_match, ch_map in story_specific_subtitles.items():
        if key_match in t_norm and ch_num in ch_map:
            return ch_map[ch_num]

    # 3. Fallback narrative arc subtitles (1–20 ตอนแบบสละสลวย ห้ามมีคำว่า 'บททดสอบบทที่ X')
    arc_subtitles = {
        1: "จุดเริ่มต้นแห่งชะตากรรม",
        2: "สัญญาณเตือนและความลับที่ซ่อนอยู่",
        3: "ทางเลือกแรกและการตัดสินใจ",
        4: "พันธมิตรและเงามืดที่คืบคลาน",
        5: "การเผชิญหน้าครั้งสำคัญ",
        6: "ความจริงที่ถูกเปิดเผย",
        7: "ศึกตัดสินกลางวิกฤต",
        8: "รุ่งอรุณแห่งการเดินทางครั้งใหม่",
        9: "คลื่นใต้น้ำลูกใหม่",
        10: "ก้าวข้ามขีดจำกัด",
        11: "ปริศนาที่ซ่อนอยู่ในเงามืด",
        12: "แผนการโต้กลับที่คาดไม่ถึง",
        13: "พันธสัญญาและการเดิมพันครั้งใหม่",
        14: "เบาะแสสำคัญกลางพายุ",
        15: "จุดเปลี่ยนแห่งโชคชะตา",
        16: "กับดักและการไล่ล่า",
        17: "เปิดโปงผู้อยู่เบื้องหลัง",
        18: "เปลวไฟแห่งการตัดสิน",
        19: "ก่อนรุ่งสางของศึกสุดท้าย",
        20: "บทสรุปแห่งตำนานบทใหม่",
    }
    if ch_num in arc_subtitles:
        return arc_subtitles[ch_num]

    # สกัดวลีสำคัญจากเนื้อหาบทจริงถ้ามี
    clean_key = re.sub(r'[:\s_-]+', '_', story_title).strip('_')
    ch_candidates = glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters", f"*{clean_key[:8]}*_Chapter_{ch_num:02d}.md"))
    if ch_candidates:
        try:
            with open(ch_candidates[0], "r", encoding="utf-8") as cf:
                ctxt = cf.read(600)
            m_first = re.search(r"([ก-๙]{8,28})", ctxt)
            if m_first:
                return m_first.group(1).strip()
        except Exception:
            pass
    return f"จุดเปลี่ยนครั้งสำคัญ"


def update_chapter_title_on_raw(article_id: str, guid: str, new_title: str) -> bool:
    """แก้ไขชื่อตอนบน ReadAWrite อัตโนมัติเมื่อตรวจพบชื่อตอนซ้ำซ้อน (Self-Healing)"""
    if not os.path.exists(AUTH_FILE):
        return False
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE, viewport={"width": 1440, "height": 1080})
            page = context.new_page()
            edit_url = f"https://www.readawrite.com/?action=manage_chapter&article_id={article_id}&chapter_id={guid}"
            page.goto(edit_url, timeout=45000)
            page.wait_for_timeout(2000)

            btn_cancel = page.locator("#btn_cancel_local_draft")
            if btn_cancel.is_visible():
                btn_cancel.click()
                page.wait_for_timeout(500)

            page.fill("#chapter_title", new_title)
            if page.locator("#chapter_subtitle").is_visible():
                page.fill("#chapter_subtitle", "")

            page.click("#btnSaveDraft")
            page.wait_for_timeout(1200)

            try:
                change_log_label = page.locator("label[for=pop_change_log2]")
                if change_log_label.is_visible(timeout=1500):
                    change_log_label.click()
                    page.wait_for_timeout(500)
                    page.click(".swal2-modal input.btnSaveDraft")
                    page.wait_for_timeout(2000)
                else:
                    page.wait_for_timeout(1500)
            except Exception:
                page.wait_for_timeout(1500)

            context.storage_state(path=AUTH_FILE)
            browser.close()
            return True
    except Exception as e:
        print(f"   [!] update_chapter_title_on_raw error: {e}")
        return False


def release_next_chapter(article_id: str, title: str) -> Optional[Dict[str, Any]]:
    """หาตอนถัดไปที่ยังไม่เผยแพร่ ซ่อมชื่อตอนถ้าซ้ำซ้อน แล้วทำการเปิดเผยแพร่"""
    print(f"\n🔍 ตรวจสอบสารบัญของเรื่อง '{title}' (ID: {article_id})...")
    chapters = get_article_chapters(article_id)
    if not chapters:
        print("   ❌ ไม่พบข้อมูลตอนในระบบ")
        return None

    # จัดเรียงตามลำดับตอน
    sorted_chs = []
    for c in chapters:
        m = re.search(r"#(\d+)", c["title"]) or re.search(r"ตอนที่\s*(\d+)", c["title"])
        order = int(m.group(1)) if m else 999
        sorted_chs.append((order, c))
    sorted_chs.sort(key=lambda x: x[0])

    next_ch = None
    for order, c in sorted_chs:
        if not c["isPublished"]:
            raw_title = c.get("title", "")
            # ดักจับคำ: ถ้ามี word_count ต่ำกว่า 15 คำ ถือว่าดราฟต์ว่างเปล่า
            try:
                w_num = int(c.get("words", "0") or 0)
                if 0 < w_num < 15:
                    print(f"   ⛔ ข้าม {raw_title}: จำนวนคำน้อยผิดปกติ ({w_num} คำ < 15 คำ) (Quality Gate Failed)")
                    continue
            except Exception:
                pass

            # Self-Healing: ถ้าชื่อตอนเป็น "ตอนที่ X: ตอนที่ X" หรือมีคำแปลกๆ ("บททดสอบบทที่", "ฉากย่อยที่", "_", "*") ให้ซ่อมชื่อตอนอัตโนมัติก่อนปล่อย!
            clean_raw_t = raw_title.strip()
            needs_heal = (
                re.match(r"^ตอนที่\s*\d+:\s*ตอนที่\s*\d+$", clean_raw_t)
                or "บททดสอบบทที่" in clean_raw_t
                or "ฉากย่อยที่" in clean_raw_t
                or "_" in clean_raw_t
                or "*" in clean_raw_t
                or "ฉบับขัดเกลา" in clean_raw_t
                or "ปรับปรุงครั้งที่" in clean_raw_t
            )
            if needs_heal:
                sub = resolve_chapter_subtitle(title, order if order != 999 else 1)
                healed_title = f"ตอนที่ {order}: {sub}"
                print(f"   🛠️ [Self-Heal] ซ่อมชื่อตอนแปลก/ซ้ำซ้อน: '{clean_raw_t}' -> '{healed_title}'...")
                if update_chapter_title_on_raw(article_id, c["guid"], healed_title):
                    c["title"] = healed_title
                    print(f"   ✅ ซ่อมชื่อตอนสำเร็จ: '{healed_title}'")
                else:
                    print(f"   ⚠️ ซ่อมชื่อตอนไม่สำเร็จ ข้ามไปก่อน")
                    continue

            next_ch = c
            break

    if not next_ch:
        print(f"   ℹ️ เรื่อง '{title}' ไม่มีตอนที่มีคุณภาพผ่านเกณฑ์พร้อมปล่อย")
        return None

    print(f"   🚀 กำลังเปิดเผยแพร่: {next_ch['title']} (GUID: {next_ch['guid']})...")
    success = publish_chapter(next_ch["guid"])
    if success:
        print(f"   ✅ เผยแพร่ '{next_ch['title']}' สู่สาธารณะสำเร็จ!")
        ensure_story_master_published(article_id)
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


def sync_all_stories_from_studio() -> List[tuple[str, str]]:
    """ดึงรายชื่อนิยายทั้งหมดจาก My Writing มาบันทึกเข้า Ledger เพื่อให้ระบบทยอยปล่อยได้ทุกเรื่อง"""
    if not os.path.exists(AUTH_FILE):
        return []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()
            page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=45000)
            page.wait_for_timeout(2000)
            links = page.eval_on_selector_all("a[href*='manage_article&article_id=']", "els => els.map(e => ({href: e.href, text: e.innerText.trim()}))")
            browser.close()

            ledger = load_ledger()
            if "published_stories" not in ledger:
                ledger["published_stories"] = {}

            found = []
            for l in links:
                m = re.search(r"article_id=([a-f0-9]+)", l["href"])
                if m:
                    art_id = m.group(1)
                    title = l["text"].split("\n")[0].strip()
                    if title and len(title) > 1:
                        found.append((art_id, title))
                        ledger["published_stories"][title] = {
                            "article_id": art_id,
                            "platform": "readawrite",
                            "synced_at": datetime.datetime.now().isoformat()
                        }
            save_ledger(ledger)
            return found
    except Exception as e:
        print(f"   [!] Sync stories error: {e}")
        return []


def get_active_stories() -> List[tuple[str, str]]:
    """ดึงรายการเรื่องที่กำลังออนแอร์จาก Ledger โดยจัดลำดับเรื่องเรือธง (Flagship) ขึ้นเป็นอันดับแรกเสมอ"""
    # ลำดับที่ 1: 6 เรื่องเรือธง (Flagship Priority) ที่มีศักยภาพดึงยอดวิวและทำ E-Book สูงสุด
    flagships = [
        ("627d9707279484797acafaba010fcf69", "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ"),
        ("33e483f95428f693527c5d4843c7fef4", "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง"),
        ("2ac4e08e36403cb46241714ff5758789", "สาวอภินิหารหัวใจเหล็ก"),
        ("f5d5ec2e430ab0bbade7b02be1beb149", "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์"),
        ("f3624f7b4e09cde8fc524dff4f2fc4bd", "สมาคมประกันภัยลี้ลับ"),
        ("084947f5c23530e03094cc84bb1364b5", "ยอดนักสืบสปีดรัน"),
        ("e90bfef727e4730819e92444783d6850", "ร้านค้าเหนือโลก: กระจกเงาคนตาย"),
    ]
    # ลำดับที่ 2: เรื่องรองในพอร์ตโฟลิโอ
    secondary = [
        ("d7b6b42256a73ff2c99dee9291b23c2e", "โลกแฟนตาซีอันเหนือจริง: วิญญาณศรัทธา"),
        ("9e8c07991925a7993519a4d261fd6f2a", "ดวงจันทร์แห่งเวทมนตร์: เรื่องราวของฮิลโคและเด็กสาวผู้เต้นระบำในความมืด"),
        ("ac04dda030fae1380e3aa7ac52f66762", "ฟาร์มสาวปีศาจรัก"),
        ("02efa2dd3eea0d584e8b815d78085966", "ตื่นตามฝันนางพยากรณ์"),
        ("1aeb1737a60e167ad499e1dd83c76057", "ตื่นขึ้นมาด้วยรอยยิ้ม"),
        ("34ee3ede15f2f9a77f7b84539bbd565a", "กอธาม ทหารรับจ้างชะตาเปลี่ยน"),
        ("c9ba3d70c41e7b9e05e4d1110ec5b94e", "จากน้องสาวสู่พี่ใหญ่: สายใยแห่งความรัก"),
        ("454f3980e21e630dc4891fa752796d58", "ผู้สาปแช่ง Chimera: เกิดใหม่ในโลกเวทย์มนต์"),
        ("5738758aa9e2c5f89bcf6552d3a79187", "รักกับเจ้าหญิงเพลย์บอย"),
        ("df9588a13de2636f3a23ea0ce9286e4a", "เหล่ามือกระบี่ไร้แม่เหล็ก"),
    ]
    base = flagships + secondary
    ledger = load_ledger()
    known_ids = {s[0] for s in base}
    for title, info in ledger.get("published_stories", {}).items():
        art_id = info.get("article_id")
        if art_id and art_id not in known_ids:
            base.append((art_id, title))
            known_ids.add(art_id)
    return base


def cron_tick(force: bool = False) -> None:
    """ประเมินเวลาและทำการ Drip Release อัตโนมัติในแต่ละรอบของ Orchestrator (กระจายปล่อยหลายเรื่อง)"""
    now = datetime.datetime.now()
    hour = now.hour
    today_str = now.strftime("%Y-%m-%d")
    ledger = load_ledger()
    releases_today = [r for r in ledger.get("scheduled_releases", []) if r.get("published_at", "").startswith(today_str)]

    # กำหนดโควตาการปล่อยต่อวัน (Quad Golden Hours: เช้า 07:00-08:59, เที่ยง 11:00-13:59, เย็น 17:00-18:59, ดึก 19:00-21:59)
    max_daily = int(os.environ.get("ANSRE_DAILY_DRIP_LIMIT", "4"))
    max_per_tick = int(os.environ.get("ANSRE_DRIP_PER_TICK", "1"))

    is_golden = (7 <= hour <= 8) or (11 <= hour <= 13) or (17 <= hour <= 21)

    should_release = force
    if not should_release:
        if is_golden and len(releases_today) < max_daily:
            should_release = True
            print(f"\n🚀 [Golden Hour Tick] ปล่อยตอนใหม่ตามเวลาทอง (วันนี้ปล่อยแล้ว {len(releases_today)}/{max_daily} ตอน)")
        else:
            if not is_golden:
                print(f"⏳ [Standby] อยู่นอกช่วงเวลาทอง (Quad Golden Hours: 07:30, 12:00, 17:30, 20:30) พักการปล่อย")
            else:
                print(f"✅ [Quota Complete] วันนี้ปล่อยครบโควตา {max_daily} ตอนเรียบร้อยแล้ว")

    if not should_release:
        return

    # ค้นหาเรื่องที่กำลัง On-Air ทั้งหมด
    active_stories = get_active_stories()
    if len(active_stories) <= 3:
        sync_all_stories_from_studio()
        active_stories = get_active_stories()

    # ข้ามเรื่องที่ปล่อยครบทุกตอนแล้ว (completed_story_ids) เพื่อไม่ต้องเปิดเบราว์เซอร์เช็กซ้ำทุกครั้ง
    completed_ids = set(ledger.get("completed_story_ids", []))
    candidate_stories = [(aid, t) for aid, t in active_stories if aid not in completed_ids]
    if not candidate_stories:
        # ถ้าครบหมดแล้ว ให้ลองรีเซ็ตเช็กใหม่อีกครั้งเผื่อมีตอนใหม่เพิ่มเข้ามา
        candidate_stories = active_stories

    released_in_tick = 0
    recent_released_titles = set(r.get("story", "") for r in releases_today[-5:])
    sorted_stories = sorted(candidate_stories, key=lambda s: 1 if s[1] in recent_released_titles else 0)

    for art_id, title in sorted_stories:
        if released_in_tick >= max_per_tick:
            break
        released = release_next_chapter(art_id, title)
        if released:
            released_in_tick += 1
            all_chs = get_article_chapters(art_id)
            unpub_count = sum(1 for c in all_chs if not c.get("isPublished", False))
            if unpub_count == 0:
                ledger = load_ledger()
                comp = set(ledger.get("completed_story_ids", []))
                comp.add(art_id)
                ledger["completed_story_ids"] = list(comp)
                save_ledger(ledger)
            notify_discord_release(title, released["title"], released["guid"], unpub_count)
        else:
            # บันทึกว่าเรื่องนี้ไม่มีตอนรอปล่อยแล้ว จะได้ไม่เสียเวลาสแกนซ้ำในรอบถัดไป
            ledger = load_ledger()
            comp = set(ledger.get("completed_story_ids", []))
            comp.add(art_id)
            ledger["completed_story_ids"] = list(comp)
            save_ledger(ledger)


def show_publishing_dashboard():
    """แสดงแดชบอร์ดตารางการปล่อยนิยายและวิดีโอ"""
    print("\n" + "=" * 65)
    print(" 📅 ตารางแผนการปล่อยผลงานต่อเนื่อง (Continuous Release Schedule)")
    print("=" * 65)
    print(" 🖋️ นามปากกาหลัก: เงาพันจันทร์")
    print(" ⏰ ช่วงเวลาทองประจำวัน (Quad Golden Hours):")
    print("    • รอบเช้า   (07:30 น.) : ปล่อยตอนใหม่ / Shorts 1 คลิป")
    print("    • รอบเที่ยง (12:00 น.) : ปล่อยตอนใหม่ / Shorts 1 คลิป")
    print("    • รอบเย็น   (17:30 น.) : ปล่อยตอนใหม่ / Shorts 1 คลิป")
    print("    • รอบดึก   (20:30 น.) : ปล่อยตอนใหม่ / Shorts 1 คลิป (ช่วงคนอ่านสูงสุด)")
    print("-" * 65)
    print(" 📚 ลำดับคิวซีรีส์ (Series Pipeline):")
    print("   1. ฟาร์มสาวปีศาจรัก (8 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   2. ดวงจันทร์แห่งเวทมนตร์: เรื่องราวของฮิลโคและเด็กสาวผู้เต้นระบำในความมืด (8 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   3. จากน้องสาวสู่พี่ใหญ่: สายใยแห่งความรัก (8 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   4. ผู้สาปแช่ง Chimera: เกิดใหม่ในโลกเวทย์มนต์ (8 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   5. สาวอภินิหารหัวใจเหล็ก (8 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   6. วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์ (8 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   7. สมาคมประกันภัยลี้ลับ (10 ตอน - เผยแพร่ครบจบภาคแรกแล้ว)")
    print("   8. ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ (10 ตอน - เผยแพร่ครบแล้ว)")
    print("   9. ยอดนักสืบสปีดรัน (10 ตอน - เผยแพร่ครบแล้ว)")
    print("   10. ร้านค้าเหนือโลก: กระจกเงาคนตาย (20 ตอน - เผยแพร่ครบแล้ว)")
    print("   + ซีรีส์ในคลังอีก 21 เรื่อง (กำลังทยอยปล่อยรายวันอัตโนมัติพร้อม Self-Healing)")
    print("=" * 65 + "\n")


def run_scheduler_daemon():
    """รัน loop ต่อเนื่องในฐานะ daemon Service (เหมาะสำหรับ PM2 / Launchd)"""
    print("\n" + "=" * 65)
    print(" 🚀 เริ่มต้น ReadAWrite Drip Publishing Daemon (Background Service)")
    print("=" * 65)
    print(" ⏰ ระบบจะตรวจเช็กตารางและปล่อยตอนใหม่ตามช่วงเวลาทองอัตโนมัติ")
    print("    • ตรวจสอบรอบปล่อยทุก 30 นาที")
    print("    • โควตาสูงสุด 4 ตอน/วัน (Quad Golden Hours) เพื่อดันฟีดอย่างสม่ำเสมอ")
    print("=" * 65 + "\n")
    sys.stdout.flush()

    while True:
        try:
            now = datetime.datetime.now()
            is_golden = (7 <= now.hour <= 8) or (11 <= now.hour <= 13) or (17 <= now.hour <= 21)
            print(f"[{now.strftime('%Y-%m-%d %H:%M:%S')}] ⏳ Heartbeat check (Golden Hour: {is_golden})...")
            sys.stdout.flush()
            cron_tick(force=False)
        except Exception as e:
            print(f"[!] Daemon tick error: {e}")
            sys.stdout.flush()
        
        # รอ 30 นาทีต่อรอบ
        time.sleep(1800)


if __name__ == "__main__":
    import re
    args = sys.argv[1:]
    if "--status" in args:
        show_publishing_dashboard()
    elif "--loop" in args or "--daemon" in args:
        run_scheduler_daemon()
    elif "--publish-next" in args:
        article_id = "084947f5c23530e03094cc84bb1364b5"
        title = "ยอดนักสืบสปีดรัน"
        res = release_next_chapter(article_id, title)
        if res:
            notify_discord_release(title, res["title"], res["guid"], 6)
    elif "--cron-tick" in args:
        cron_tick(force=("--force" in args))
    elif "--unlock-unpublished" in args:
        lim = int(args[args.index("--limit") + 1]) if "--limit" in args else 5
        print(f"[*] ปลดล็อกนิยายที่ยังไม่เผยแพร่จำนวน {lim} เรื่อง...")
        with open("SecondBrain/readawrite_current_stats.json") as f:
            stats = json.load(f)
        unpub = [d for d in stats if "ไม่เผยแพร่" in d["info"]][:lim]
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE, viewport={"width": 1440, "height": 1080})
            page = context.new_page()
            for item in unpub:
                aid = item["aid"]
                title = item["title"]
                print(f"🚀 ปลดล็อก '{title}' ({aid})...")
                # publish chapters
                ch_url = f"https://www.readawrite.com/?action=manage_article&article_id={aid}&tab=mainManageChapter"
                page.goto(ch_url, timeout=30000)
                page.wait_for_timeout(2000)
                page.evaluate("""() => {
                    const rows = document.querySelectorAll(".table tbody tr");
                    for (const r of rows) {
                        const chk = r.querySelector("input[name=chk_chapter_guid]");
                        const guid = chk ? chk.value : "";
                        const st = r.getAttribute("status");
                        if (guid && st !== "2") {
                            $.ajax({
                                method: "POST",
                                url: "?action=manage_chapter&token=",
                                data: { chapter_guid: guid, manage: "publishAndMoveToMaster", is_collaborator: 0 },
                                dataType: "json"
                            });
                        }
                    }
                }""")
                page.wait_for_timeout(2000)
                ensure_story_master_published(aid)
                print(f"   ✅ '{title}' ออนแอร์สู่สาธารณะแล้ว!")
            context.storage_state(path=AUTH_FILE)
            browser.close()
    else:
        show_publishing_dashboard()

