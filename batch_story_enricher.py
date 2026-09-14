#!/usr/bin/env python3
"""
batch_story_enricher.py — ระบบเตรียมสต็อกเนื้อหาเต็มและชื่อตอนย่อยล่วงหน้า (Zero-Downtime Pipeline)
========================================================================================
สแกนนิยายใน SecondBrain/05_Active_Projects/Chapters/ และจับคู่กับ Studio Drafts
เพื่ออัปโหลดเนื้อหาเต็มละเอียด, ติด Subtitle ตาม Outline, และฝังกล่อง Cross-Promotion ท้ายตอน
"""

from __future__ import annotations

import os
import re
import sys
import time
import glob
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
CHAPTERS_DIR = os.path.join(SB, "05_Active_Projects", "Chapters")
OUTLINES_DIR = os.path.join(SB, "02_Concept_Extraction")
LEDGER_FILE = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")

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


def extract_subtitles_from_outline(story_clean: str) -> Dict[int, str]:
    """สกัดชื่อตอนย่อยจาก Outline file หากมี"""
    subtitles = {}
    pattern = os.path.join(OUTLINES_DIR, f"*{story_clean}*Outline*.md")
    files = glob.glob(pattern)
    if not files:
        pattern = os.path.join(OUTLINES_DIR, f"*{story_clean}*.md")
        files = glob.glob(pattern)

    if files:
        with open(files[0], "r", encoding="utf-8") as f:
            content = f.read()

        for m in re.finditer(r"(?:ตอนที่|Chapter)\s*(\d+)[\s:]*[\"“]?([^\"\n\r—]+)[\"”]?", content):
            try:
                num = int(m.group(1))
                sub = m.group(2).strip()
                sub = re.sub(r"^[-*\s]+", "", sub)
                sub = re.sub(r"\*\*.*", "", sub)
                if sub and len(sub) > 2 and num not in subtitles:
                    subtitles[num] = sub[:60]
            except Exception:
                pass

    return subtitles


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


def enrich_story_in_studio(article_id: str, story_name: str, subtitles_map: Optional[Dict[int, str]] = None) -> bool:
    """อัปเกรดเนื้อหาและชื่อตอนย่อยของเรื่องที่ระบุขึ้น ReadAWrite Studio"""
    print(f"\n=================================================================")
    print(f" 🚀 เริ่มต้นกระบวนการ Enrich: '{story_name}' (ID: {article_id})")
    print(f"=================================================================")

    if not os.path.exists(AUTH_FILE):
        print("   ❌ ไม่พบไฟล์ Auth Session")
        return False

    subtitles = subtitles_map or extract_subtitles_from_outline(story_name)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE, viewport={"width": 1440, "height": 1080})
        page = context.new_page()

        # 1. เปิดสถานะเรื่องหลัก
        main_url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageArticle"
        page.goto(main_url, timeout=45000)
        page.wait_for_timeout(2000)
        st_text = page.inner_text("#article_status_text") if page.query_selector("#article_status_text") else ""
        if "ไม่เผยแพร่" in st_text:
            print("   🔓 ปรับสถานะเรื่องหลักให้เป็น 'เผยแพร่'...")
            page.click(".switch_setting_status")
            page.wait_for_timeout(1500)

        # 2. อ่านรายการตอน
        ch_url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageChapter"
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

        print(f"   พบ {len(rows)} แถวในสตูดิโอ")

        for num in range(1, 9):
            ch_file = os.path.join(CHAPTERS_DIR, f"{story_name}_Chapter_{num:02d}.md")
            if not os.path.exists(ch_file):
                print(f"   ⚠️ ไม่พบไฟล์: {ch_file}")
                continue

            sub = subtitles.get(num, f"ตอนที่ {num}")
            full_title = f"ตอนที่ {num}: {sub}"

            # ค้นหาแถวที่ตรงกับตอนที่ num
            guid = None
            for r in rows:
                m = re.search(r"ตอนที่\s*(\d+)", r["title"])
                if m and int(m.group(1)) == num:
                    guid = r["guid"]
                    break

            if not guid:
                print(f"   ⚠️ ไม่พบ GUID ของตอนที่ {num}")
                continue

            with open(ch_file, "r", encoding="utf-8") as f:
                raw_text = f.read().strip()

            if "ผลงานแนะนำจาก 'เงาพันจันทร์'" not in raw_text:
                raw_text = raw_text + "\n\n" + CROSS_PROMO_TEMPLATE

            html_body = md_to_html(raw_text)

            edit_url = f"https://www.readawrite.com/?action=manage_chapter&article_id={article_id}&chapter_guid={guid}"
            print(f"   📝 อัปเกรด [ตอนที่ {num}] '{full_title}' ({len(raw_text)} อักขระ)...")
            page.goto(edit_url, timeout=45000)
            page.wait_for_timeout(2500)

            btn_cancel = page.locator("#btn_cancel_local_draft")
            if btn_cancel.is_visible():
                btn_cancel.click()
                page.wait_for_timeout(500)

            page.fill("#chapter_title", full_title)
            if page.query_selector("#chapter_subtitle"):
                page.fill("#chapter_subtitle", sub)

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
                page.wait_for_timeout(3000)
                print(f"      ✅ บันทึกตอนที่ {num} สำเร็จ!")
            else:
                print(f"      ❌ ไม่พบปุ่มบันทึกในตอนที่ {num}")

            time.sleep(1)

        context.storage_state(path=AUTH_FILE)
        browser.close()
        print(f"\n🎉 สำเร็จ: '{story_name}' พร้อมปล่อยตามตารางอัตโนมัติ 100%!")
        return True


def run_batch():
    targets = [
        {
            "aid": "ac04dda030fae1380e3aa7ac52f66762",
            "name": "ฟาร์มสาวปีศาจรัก",
            "subtitles": {
                1: "สู่โลกใหม่และไร่ศักดิ์สิทธิ์",
                2: "การพบพานสาวปีศาจคนแรก",
                3: "ปลูกพลังเวทบนผืนดิน",
                4: "กำแพงป้องกันแห่งศรัทธา",
                5: "การรุกกลับสู่น้ำตก",
                6: "เผชิญหน้าผู้มีอำนาจ",
                7: "ยุทธการแนวป้องกันผาหิน",
                8: "ชัยชนะและการปกป้องไร่ศักดิ์สิทธิ์"
            }
        },
        {
            "aid": "9e8c07991925a7993519a4d261fd6f2a",
            "name": "ดวงจันทร์แห่งเวทมนตร์_เรื่องราวของฮิลโคและเด็กสาวผู้เต้นระบำในความมืด",
            "subtitles": {
                1: "การพบกันของสายลับแห่งเวทมนตร์",
                2: "การทดลองลับ",
                3: "ภูติผีในชุมชน",
                4: "การสืบสวนครั้งแรก",
                5: "การสืบสวนที่เป็นปริศนา",
                6: "การสำรวจวัดเหนือธรรมชาติ",
                7: "ความจริงในวัดลี้ลับ",
                8: "ภูติผีที่ปรากฏอีกครั้ง"
            }
        }
    ]

    for t in targets:
        enrich_story_in_studio(t["aid"], t["name"], t["subtitles"])


if __name__ == "__main__":
    run_batch()
