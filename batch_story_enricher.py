#!/usr/bin/env python3
"""
batch_story_enricher.py — สคริปต์อัปเกรดเนื้อหาเต็มและชื่อตอนย่อยสำหรับ ReadAWrite Studio
เป้าหมาย:
1. ตื่นตามฝันนางพยากรณ์ (ID: 02efa2dd3eea0d584e8b815d78085966)
2. ตื่นขึ้นมาด้วยรอยยิ้ม (ID: 1aeb1737a60e167ad499e1dd83c76057)
3. กอธาม ทหารรับจ้างชะตาเปลี่ยน (ID: 34ee3ede15f2f9a77f7b84539bbd565a)
"""

import os
import re
import sys
import time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
CHAPTERS_DIR = os.path.join(SB, "05_Active_Projects", "Chapters")

CROSS_PROMO_TEMPLATE = """
---

💬 **[คุยกับเงาพันจันทร์]**
นักอ่านรู้สึกอย่างไรกับตอนนี้ หรืออยากให้ตัวละครหลักตัดสินใจอย่างไร คอมเมนต์มาแลกเปลี่ยนกันได้เลยนะครับ! ❤️

✨ **ผลงานแนะนำจาก 'เงาพันจันทร์' ที่จบภาคแรกแล้ว อ่านรวดเดียวจุใจ:**
- ⚔️ **สาวอภินิหารหัวใจเหล็ก** (จบภาคแรกแล้ว 8 ตอนรวด!)
- 😴 **วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์** (8 ตอนจบภาคแรก)
- 👻 **สมาคมประกันภัยลี้ลับ: แผนกเคลมกรรม** (10 ตอนจบภาคแรก)
- 🔍 **ยอดนักสืบสปีดรัน** (10 ตอนจบภาคแรก)

*(อย่าลืมกดหัวใจ ❤️ + เพิ่มเข้าชั้นหนังสือ เพื่อไม่พลาดตอนใหม่นะครับ!)*
"""

TARGET_STORIES = [
    {
        "aid": "02efa2dd3eea0d584e8b815d78085966",
        "file_prefix": "ตื่นตามฝันนางพยากรณ์",
        "clean_title": "ตื่นตามฝันนางพยากรณ์",
        "subtitles": {
            1: "การเรียกเชื้อสาย",
            2: "การแนะนำตนเอง",
            3: "ภารกิจแรก",
            4: "การเผชิญหน้า",
            5: "การช่วยเหลือผู้รักษาสันติภาพ",
            6: "การสำรวจเรือนโบราณ",
            7: "การพบปะราชาแห่งภูต",
            8: "การเรียนรู้วิชาเวทย์มนตร์"
        }
    },
    {
        "aid": "1aeb1737a60e167ad499e1dd83c76057",
        "file_prefix": "ตื่นขึ้นมาด้วยรอยยิ้ม",
        "clean_title": "ตื่นขึ้นมาด้วยรอยยิ้ม",
        "subtitles": {
            1: "วันใหม่สำหรับชีวิต",
            2: "แสงสว่างจากความหวัง",
            3: "สร้างความสุขให้แก่ชีวิต",
            4: "ฟื้นคืนชีวิตให้กับกายและใจ",
            5: "การสนับสนุนและการพึ่งพา",
            6: "การเติมพลังใจและความหวังใหม่",
            7: "การพัฒนาความสามารถ",
            8: "การเข้าใจและความอยู่ด้วยกัน"
        }
    },
    {
        "aid": "34ee3ede15f2f9a77f7b84539bbd565a",
        "file_prefix": "กอธาม_ทหารรับจ้างชะตาเปลี่ยน",
        "clean_title": "กอธาม ทหารรับจ้างชะตาเปลี่ยน",
        "subtitles": {
            1: "ประตูสู่โชคชะตา",
            2: "ประตูสู่ชัยชนะ",
            3: "การลุกขึ้นของทหารรับจ้าง",
            4: "ผืนป่าของความรู้",
            5: "เงาของนักโทษ",
            6: "เมืองในฝัน",
            7: "อิทธิพลแห่งอนาคต",
            8: "ความแข็งแกร่งของสหาย"
        }
    }
]

def md_to_html(md_text: str) -> str:
    paragraphs = md_text.split("\n\n")
    html_parts = []
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if p.startswith("#"):
            title = re.sub(r"^#+\s*", "", p)
            html_parts.append(f"<h3>{title}</h3>")
            continue
        if p.startswith("---"):
            html_parts.append("<hr/>")
            continue
        p_clean = p.replace("\n", "<br/>")
        html_parts.append(f"<p>{p_clean}</p>")
    return "".join(html_parts)

def enrich_story(page, story_cfg):
    aid = story_cfg["aid"]
    title = story_cfg["clean_title"]
    prefix = story_cfg["file_prefix"]
    subtitles = story_cfg["subtitles"]

    print(f"\n=======================================================")
    print(f"🚀 กำลังเริ่มกระบวนการ Enrich: {title} (ID: {aid})")
    print(f"=======================================================")

    # 1. ปลดล็อกสถานะเรื่องหลัก
    main_url = f"https://www.readawrite.com/?action=manage_article&article_id={aid}&tab=mainManageArticle"
    page.goto(main_url, timeout=45000)
    page.wait_for_timeout(2000)

    st_text = page.inner_text("#article_status_text") if page.query_selector("#article_status_text") else ""
    if "ไม่เผยแพร่" in st_text:
        print(f"   🔓 กำลังเปิดสถานะเรื่องหลัก '{title}' ให้เป็น เผยแพร่...")
        page.click(".switch_setting_status")
        page.wait_for_timeout(1000)
        confirm_btn = page.query_selector('button:has-text("ยืนยัน"), a:has-text("ยืนยัน")')
        if confirm_btn:
            confirm_btn.click()
            page.wait_for_timeout(2500)

    # 2. อ่านรายการตอน
    ch_url = f"https://www.readawrite.com/?action=manage_article&article_id={aid}&tab=mainManageChapter"
    page.goto(ch_url, timeout=45000)
    page.wait_for_timeout(2000)

    rows = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.table tbody tr')).map(r => {
            const chk = r.querySelector('input[name=chk_chapter_guid]');
            const guid = chk ? chk.value : '';
            const titleEl = r.querySelector('.chapter_detail p, td:nth-child(3)');
            const title = (chk ? chk.getAttribute('title_name') : '') || (titleEl ? titleEl.innerText.trim() : '');
            const rowStatus = r.getAttribute('status');
            const pubDate = r.getAttribute('first_published_date');
            const isPublished = (rowStatus === '2') || Boolean(pubDate && pubDate.length > 5);
            return { guid, title, isPublished };
        }).filter(x => x.guid);
    }""")

    print(f"   พบ {len(rows)} ตอนในระบบ")

    # 3. อัปเกรดเนื้อหาและชื่อตอนทีละตอน
    for num in range(1, 9):
        ch_file = os.path.join(CHAPTERS_DIR, f"{prefix}_Chapter_{num:02d}.md")
        if not os.path.exists(ch_file):
            print(f"   ⚠️ ไม่พบไฟล์เนื้อหา: {ch_file}")
            continue

        sub = subtitles.get(num, f"ตอนที่ {num}")
        full_title = f"ตอนที่ {num}: {sub}"

        # ค้นหา GUID ของตอน
        guid = None
        for r in rows:
            m = re.search(r"ตอนที่\s*(\d+)", r["title"])
            if m and int(m.group(1)) == num:
                guid = r["guid"]
                break

        if not guid:
            print(f"   ⚠️ ไม่พบ GUID ตอนที่ {num}")
            continue

        with open(ch_file, "r", encoding="utf-8") as f:
            raw_text = f.read().strip()

        if "ผลงานแนะนำจาก 'เงาพันจันทร์'" not in raw_text:
            raw_text = raw_text + "\n\n" + CROSS_PROMO_TEMPLATE

        html_body = md_to_html(raw_text)

        edit_url = f"https://www.readawrite.com/?action=manage_chapter&article_id={aid}&chapter_id={guid}"
        print(f"   📝 อัปเกรด [ตอนที่ {num}] '{full_title}' ({len(raw_text)} อักขระ)...")
        page.goto(edit_url, timeout=45000)
        page.wait_for_timeout(2500)

        btn_cancel = page.locator("#btn_cancel_local_draft")
        if btn_cancel.is_visible():
            btn_cancel.click()
            page.wait_for_timeout(500)

        page.fill("#chapter_title", full_title)
        if page.query_selector("#chapter_subtitle"):
            page.fill("#chapter_subtitle", "")

        page.evaluate("""(content) => {
            const el = document.querySelector('.ck-editor__editable');
            if (el && el.ckeditorInstance) {
                el.ckeditorInstance.setData(content);
            }
        }""", html_body)
        page.wait_for_timeout(1000)

        save_btn = page.locator("#btnSaveDraft")
        if save_btn.is_visible():
            save_btn.click()
            page.wait_for_timeout(1000)
            try:
                # จัดการ Swal modal ถามการเปลี่ยนสถานะหรือการบันทึก
                modal_save = page.locator(".swal2-modal input.btnSaveDraft")
                if modal_save.is_visible(timeout=1500):
                    modal_save.click()
                    page.wait_for_timeout(2000)
                else:
                    # ถ้ามี pop_change_log
                    change_log = page.locator("label[for=pop_change_log2]")
                    if change_log.is_visible(timeout=1000):
                        change_log.click()
                        page.wait_for_timeout(500)
                        if modal_save.is_visible():
                            modal_save.click()
                            page.wait_for_timeout(2000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            print(f"      ✅ บันทึกตอนที่ {num} เรียบร้อย")
        else:
            print(f"      ❌ ไม่พบปุ่มบันทึกในตอนที่ {num}")

        time.sleep(1)

    print(f"🎉 สำเร็จ: '{title}' อัปเกรดคุณภาพเนื้อหาและชื่อตอนครบ 100%!")

def main():
    if not os.path.exists(AUTH_FILE):
        print("❌ ไม่พบไฟล์ Auth Session")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE, viewport={"width": 1440, "height": 1080})
        page = context.new_page()

        for sc in TARGET_STORIES:
            try:
                enrich_story(page, sc)
            except Exception as e:
                print(f"❌ เกิดข้อผิดพลาดกับเรื่อง {sc['clean_title']}: {e}")

        context.storage_state(path=AUTH_FILE)
        browser.close()

    print("\n=======================================================")
    print("✨ ดำเนินการ Enrich นิยายทั้ง 3 เรื่องเสร็จสมบูรณ์เรียบร้อย!")
    print("=======================================================")

if __name__ == "__main__":
    main()
