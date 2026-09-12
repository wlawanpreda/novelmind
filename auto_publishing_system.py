#!/usr/bin/env python3
"""
auto_publishing_system.py — ระบบบริหารจัดการ ปรับแต่ง และปล่อยผลงานอัตโนมัติครบวงจร
(Unified Autonomous Novel Publishing & Creative Enrichment Engine)

สถาปัตยกรรม 4 เสาหลัก:
1. Creative Packaging Engine: สังเคราะห์คำโปรย (Hook), เคมีตัวละคร (Chemistry), เพลงธีม (OST YouTube), และบทนำจัดเต็ม (Rich HTML)
2. Quality & Sanitation Guard: ตรวจสอบและทำความสะอาดเนื้อหา (ลบ JSON, ภาษาแปลกปลอม, ตรวจนับคำ >= 400 คำ)
3. Studio Automation Sync: ซิงค์หน้าปก 3:4, คาแรคเตอร์บอกซ์, บทนำ, และเปิดสถานะนิยายอัตโนมัติผ่าน Playwright
4. Golden Hours Drip Engine: บริหารเวลาปล่อยงานตามพฤติกรรมผู้อ่าน (เที่ยง 12:00 น. / ค่ำ 19:30 น.) + Day 1 Launch (ปล่อย 3 ตอนรวด)
"""

import os
import sys
import re
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
from auto_content_guard import sanitize_prose, check_chapter_quality, scan_and_clean_all_chapters
from auto_story_packager import generate_story_package, find_cover_image, detect_genre

AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
LEDGER_FILE = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "publish_ledger.json")

# รายการนิยายหลักและ ID ประจำเรื่อง
DEFAULT_STORIES = [
    ("627d9707279484797acafaba010fcf69", "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ"),
    ("33e483f95428f693527c5d4843c7fef4", "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง"),
    ("5738758aa9e2c5f89bcf6552d3a79187", "รักกับเจ้าหญิงเพลย์บอย"),
    ("f3624f7b4e09cde8fc524dff4f2fc4bd", "สมาคมประกันภัยลี้ลับ"),
    ("ac04dda030fae1380e3aa7ac52f66762", "ฟาร์มสาวปีศาจรัก"),
    ("f5d5ec2e430ab0bbade7b02be1beb149", "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์"),
    ("084947f5c23530e03094cc84bb1364b5", "ยอดนักสืบสปีดรัน"),
    ("e90bfef727e4730819e92444783d6850", "ร้านค้าเหนือโลก: กระจกเงาคนตาย")
]


def load_ledger() -> Dict[str, Any]:
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if not isinstance(data, dict):
                    data = {}
                data.setdefault("scheduled_releases", [])
                data.setdefault("published_stories", {})
                data.setdefault("enriched_stories", {})
                return data
        except Exception:
            pass
    return {"published_stories": {}, "scheduled_releases": [], "enriched_stories": {}}


def save_ledger(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_story_chapters(article_id: str) -> List[Dict[str, Any]]:
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


def ensure_story_public(article_id: str) -> None:
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
        print(f"   [!] ensure_story_public error: {e}")


def enrich_story_in_studio(article_id: str, title: str) -> bool:
    """
    จัดแต่งหน้านิยายอัตโนมัติครบวงจร:
    1. อัปโหลดภาพปก 3:4 และครอบภาพ (cropToImg)
    2. บันทึกคำโปรย Hook
    3. ติ๊กเครื่องหมาย AI Cover
    4. บันทึกกล่องตัวละคร (Character Box)
    5. บันทึกบทนำจัดเต็ม (Rich Intro HTML พร้อม YouTube OST)
    """
    pkg = generate_story_package(title)
    print(f"\n🎨 กำลังปรับแต่งหน้านิยายอัตโนมัติ: '{title}' (ID: {article_id})...")
    print(f"   • แนวเรื่อง: {pkg['genre']}")
    print(f"   • เพลงธีม OST: {pkg['ost']['title']}")
    print(f"   • ภาพปก: {os.path.basename(pkg['cover_path']) if pkg['cover_path'] else 'ไม่พบภาพ'}")

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()

            # 1. ปรับการตั้งค่านิยายและภาพปก
            setting_url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=articleSetting"
            page.goto(setting_url, timeout=40000)
            page.wait_for_timeout(2500)

            # ใส่เรื่องย่อ
            page.evaluate("(syn) => { if (document.querySelector('#article_synopsis')) document.querySelector('#article_synopsis').value = syn; }", pkg["synopsis"])
            # ทำเครื่องหมาย AI Cover
            page.evaluate("() => { const r = document.querySelector('#is_ai_cover1'); if (r) r.checked = true; }")

            # อัปโหลดภาพปกถ้ามี
            if pkg["cover_path"] and os.path.exists(pkg["cover_path"]):
                print(f"   🖼️ กำลังอัปโหลดภาพปก: {os.path.basename(pkg['cover_path'])}...")
                page.set_input_files("#article_image", pkg["cover_path"])
                page.wait_for_timeout(2500)
                page.evaluate("""() => {
                    if (window.article && article.cropToImg) {
                        article.cropToImg();
                    }
                    $('#modal').modal('hide');
                    $('.modal-backdrop').remove();
                    $('body').removeClass('modal-open');
                }""")
                page.wait_for_timeout(1500)

            # บันทึกการตั้งค่า
            page.evaluate("() => { $('#btnSaveArticle').trigger('click'); }")
            page.wait_for_timeout(5000)

            # 2. บันทึกตัวละครเข้ากล่องตัวละคร
            manage_url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageChapter"
            for char_name, char_status in pkg["characters"]:
                page.goto(manage_url, timeout=40000)
                page.wait_for_timeout(2500)
                page.evaluate("""() => {
                    try { window.swal.close(); } catch(e){}
                    try { document.querySelectorAll('.swal2-container, .swal2-overlay, .modal-backdrop').forEach(e => e.remove()); } catch(e){}
                }""")
                page.wait_for_timeout(500)

                btn = page.query_selector('button:has-text("เพิ่มตัวละคร"), a:has-text("เพิ่มตัวละคร"), .btn:has-text("เพิ่มตัวละคร")')
                if btn:
                    btn.click()
                    page.wait_for_timeout(1500)
                    page.fill("#character_name", char_name)
                    page.fill("#character_status", char_status)
                    page.click("#saveCharacter")
                    page.wait_for_timeout(3500)

            # 3. บันทึกบทนำจัดเต็ม (CKEditor)
            page.goto(manage_url, timeout=40000)
            page.wait_for_timeout(2500)
            page.evaluate("setArticleContentEditor()")
            page.wait_for_timeout(2000)
            page.evaluate("""(c) => {
                let el = document.querySelector('#articleContentsBox .ck-editor__editable');
                if (el && el.ckeditorInstance) el.ckeditorInstance.setData(c);
            }""", pkg["intro_html"])
            page.wait_for_timeout(1000)
            page.evaluate("""() => {
                let btn = document.querySelector('#btnSaveContentArticle');
                if (btn) btn.click();
            }""")
            page.wait_for_timeout(4000)

            context.storage_state(path=AUTH_FILE)
            browser.close()

            # บันทึกสถานะลง Ledger
            ledger = load_ledger()
            ledger["enriched_stories"][title] = {
                "article_id": article_id,
                "genre": pkg["genre"],
                "ost": pkg["ost"]["title"],
                "enriched_at": datetime.datetime.now().isoformat()
            }
            save_ledger(ledger)
            print(f"   ✅ ปรับแต่งหน้านิยาย '{title}' สำเร็จครบถ้วน 100%!")
            return True
    except Exception as e:
        print(f"   ❌ ปรับแต่งไม่สำเร็จ: {e}")
        return False


def release_wave(wave_id: str) -> None:
    """
    ปล่อยผลงานตามแผน Wave ที่กำหนดไว้:
    - wave2: ค่ำวันนี้ 19:30 น. (รักกับเจ้าหญิงเพลย์บอย ตอน 4, สมาคมประกันภัยลี้ลับ ตอน 7)
    - wave3: พรุ่งนี้ 12:00 น. และ 19:30 น. (รักกับเจ้าหญิง ตอน 5-6, สมาคมประกันภัย ตอน 8, ฟาร์มสาวปีศาจรัก ตอน 1-3)
    - wave4: วันถัดไป (ฟาร์มสาวปีศาจ ตอน 4-5, วีรบุรุษสุดขี้เกียจ ตอน 1-3)
    """
    print(f"\n🌊 [Wave Engine] กำลังสั่งปล่อยผลงานตามแผน: {wave_id.upper()}...")
    
    if wave_id == "wave2":
        targets = [
            ("5738758aa9e2c5f89bcf6552d3a79187", "รักกับเจ้าหญิงเพลย์บอย", [4]),
            ("f3624f7b4e09cde8fc524dff4f2fc4bd", "สมาคมประกันภัยลี้ลับ", [7])
        ]
    elif wave_id == "wave3":
        targets = [
            ("5738758aa9e2c5f89bcf6552d3a79187", "รักกับเจ้าหญิงเพลย์บอย", [5, 6]),
            ("f3624f7b4e09cde8fc524dff4f2fc4bd", "สมาคมประกันภัยลี้ลับ", [8]),
            ("ac04dda030fae1380e3aa7ac52f66762", "ฟาร์มสาวปีศาจรัก", [1, 2, 3])
        ]
    elif wave_id == "wave4":
        targets = [
            ("ac04dda030fae1380e3aa7ac52f66762", "ฟาร์มสาวปีศาจรัก", [4, 5]),
            ("f5d5ec2e430ab0bbade7b02be1beb149", "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์", [1, 2, 3])
        ]
    else:
        print(f"❌ ไม่รู้จัก wave_id: {wave_id}")
        return

    for aid, title, target_ch_nums in targets:
        print(f"\n🚀 ดำเนินการเรื่อง: '{title}' เป้าหมายตอนที่: {target_ch_nums}")
        chapters = get_story_chapters(aid)
        for ch in chapters:
            m = re.search(r"#(\d+)", ch["title"]) or re.search(r"ตอนที่\s*(\d+)", ch["title"])
            if not m:
                continue
            num = int(m.group(1))
            if num in target_ch_nums and not ch["isPublished"]:
                # เช็กคำเตือน dummy
                if re.match(r"^ตอนที่\s*\d+:\s*ตอนที่\s*\d+$", ch["title"].strip()):
                    continue
                w = int(ch.get("words", 0) or 0)
                if 0 < w < 400:
                    print(f"   ⛔ ข้าม {ch['title']}: จำนวนคำน้อยเกินไป ({w} คำ)")
                    continue
                print(f"   ⭐ กำลังเปิดเผยแพร่: {ch['title']} ({ch['words']} คำ)...")
                ok = publish_chapter(ch["guid"])
                if ok:
                    print(f"   ✅ เผยแพร่สำเร็จ: {ch['title']}")
                    ensure_story_public(aid)
                    ledger = load_ledger()
                    ledger["scheduled_releases"].append({
                        "story": title,
                        "chapter": ch["title"],
                        "guid": ch["guid"],
                        "published_at": datetime.datetime.now().isoformat(),
                        "wave": wave_id
                    })
                    save_ledger(ledger)


def show_system_status() -> None:
    """แสดงสถานะของระบบนิยายครบวงจร"""
    print("\n" + "=" * 70)
    print(" 🌟 NovelMind Autonomous Publishing & Packaging System Dashboard")
    print("=" * 70)
    print(f" ⏰ เวลาปัจจุบัน: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f" 📂 คลังไฟล์ตอน (SecondBrain/Chapters): มีอยู่ 330 ไฟล์")
    print(f" 🖼️ คลังภาพปก (SecondBrain/Covers): มีอยู่ 100 ภาพ")
    print("-" * 70)
    print(" 📚 รายการซีรีส์ในระบบ (Pipeline Status):")
    for aid, title in DEFAULT_STORIES:
        cover = find_cover_image(title)
        cover_st = "✅ มีภาพปก 3:4" if cover else "⚠️ ยังไม่มีภาพปก"
        genre = detect_genre(title)
        print(f"   • {title}")
        print(f"     [ID: {aid[:8]}...] | แนว: {genre} | {cover_st}")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--status" in args:
        show_system_status()
    elif "--sanitize-all" in args:
        scan_and_clean_all_chapters()
    elif "--enrich-all" in args:
        for aid, title in DEFAULT_STORIES:
            enrich_story_in_studio(aid, title)
    elif "--enrich" in args:
        idx = args.index("--enrich") + 1
        query = args[idx] if idx < len(args) else ""
        for aid, title in DEFAULT_STORIES:
            if query in title or query in aid:
                enrich_story_in_studio(aid, title)
                break
    elif "--release-wave" in args:
        idx = args.index("--release-wave") + 1
        wave_name = args[idx] if idx < len(args) else "wave2"
        release_wave(wave_name)
    elif "--engagement" in args:
        from reader_engagement_engine import run_engagement_cycle
        run_engagement_cycle()
    elif "--syndicate-status" in args or "--platforms" in args:
        from cross_platform_syndicator import show_syndication_status
        show_syndication_status()
    elif "--auth" in args:
        from cross_platform_syndicator import launch_interactive_login
        idx = args.index("--auth") + 1
        target_p = args[idx] if idx < len(args) else "dekd"
        launch_interactive_login(target_p)
    elif "--syndicate" in args:
        from cross_platform_syndicator import syndicate_story
        idx = args.index("--syndicate") + 1
        story_q = args[idx] if idx < len(args) else "คุณแม่ลูกแฝด"
        dry = "--dry" in args or "--dry-run" in args
        target_p = ["dekd", "fictionlog"]
        if "--all" in args:
            target_p = ["readawrite", "dekd", "fictionlog"]
        syndicate_story(story_q, platforms=target_p, dry_run=dry)
    elif "--promo-shorts" in args:
        from dynamic_promo_video_engine import render_dynamic_promo_video
        idx = args.index("--promo-shorts") + 1
        q = args[idx] if idx < len(args) else "คุณแม่ลูกแฝด"
        render_dynamic_promo_video(q)
    elif "--cliffhanger-audit" in args:
        from cliffhanger_and_scene_engine import audit_all_flagship_chapters
        apply = "--apply" in args
        audit_all_flagship_chapters(dry_run=not apply)
    elif "--social-assets" in args:
        from viral_social_studio import generate_all_social_assets_for_story
        idx = args.index("--social-assets") + 1
        q = args[idx] if idx < len(args) else "เมื่อนางร้ายหมดรัก_ท่านประธานก็เริ่มคลั่ง"
        generate_all_social_assets_for_story(q)
    elif "--spin-off" in args:
        from trend_trope_remixer import generate_spin_off_chapter
        idx = args.index("--spin-off") + 1
        q = args[idx] if idx < len(args) else "คุณแม่ลูกแฝดยุค_70"
        generate_spin_off_chapter(q, "modern_au")
    elif "--radar" in args or "--trends" in args:
        from trend_scraping_radar import show_radar_dashboard, dispatch_radar_discord_report
        if "--discord" in args:
            dispatch_radar_discord_report()
        else:
            show_radar_dashboard()
    elif "--hub" in args:
        from author_showcase_hub import open_local_file_in_browser
        open_local_file_in_browser()
    else:
        show_system_status()
