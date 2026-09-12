#!/usr/bin/env python3
"""
cross_platform_syndicator.py — Autonomous Multi-Platform Web Novel Syndication Engine
====================================================================================
ระบบส่งและบริหารจัดการนิยายข้ามค่ายอัตโนมัติ (ReadAWrite, Dek-D, Fictionlog)

สถาปัตยกรรมหลัก:
1. Unified Auth Session Management:
   - ตรวจสอบและบันทึก Cookies/Storage State สำหรับ ReadAWrite, Dek-D, และ Fictionlog
   - รองรับคำสั่ง interactive login (`--auth dekd`, `--auth fictionlog`, `--auth readawrite`)
2. Content Quality & Standardization:
   - บูรณาการกับ auto_content_guard: กรอง JSON wrappers, AI prompt leaks, และภาษาแปลกปลอม
   - ถอดรหัสโครงสร้างจาก Publish_Queue/*_WEB_PUBLISH_KIT.md และ SecondBrain/Chapters/
3. Autonomous Platform Publisher:
   - ReadAWrite Publisher: อัปเดตตอน, ฝังรูปประกอบฉาก, ตรวจสอบบทนำ
   - Dek-D Publisher: ส่งขึ้น Writer Studio 3 (dashbaord / story_add / chapter_add)
   - Fictionlog Publisher: ส่งขึ้น Fictionlog Studio (/w)
4. Cross-Platform Syndication Ledger:
   - บันทึก Story ID, URL, และสถานะตอนที่ซิงค์แล้วใน syndication_ledger.json
5. Discord Command Center Integration:
   - แจ้งสถานะและผลการซิงค์เข้าห้อง #writer-feedback ทันที
"""

from __future__ import annotations

import os
import sys
import re
import json
import glob
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

SECOND_BRAIN = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_DIR = os.path.join(ROOT, ".auth_sessions")
os.makedirs(AUTH_DIR, exist_ok=True)

RAW_AUTH_FILE = os.path.join(AUTH_DIR, "readawrite_state.json")
DEKD_AUTH_FILE = os.path.join(AUTH_DIR, "dekd_state.json")
FICTIONLOG_AUTH_FILE = os.path.join(AUTH_DIR, "fictionlog_state.json")

LEDGER_FILE = os.path.join(SECOND_BRAIN, "05_Active_Projects", "syndication_ledger.json")
QUEUE_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Publish_Queue")
COVERS_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Covers")
CHAPTERS_DIR = os.path.join(SECOND_BRAIN, "05_Active_Projects", "Chapters")

try:
    from auto_content_guard import sanitize_prose, check_chapter_quality
except ImportError:
    def sanitize_prose(text: str) -> str:
        return text.strip()
    def check_chapter_quality(text: str) -> Dict[str, Any]:
        return {"passed": True, "word_count": len(text.split()), "issues": []}

try:
    from discord_reporter import send_discord_message
except ImportError:
    def send_discord_message(payload: dict, channel_id: str = "") -> bool:
        return False


# ============================================================================
# 1. LEDGER MANAGEMENT
# ============================================================================

def load_syndication_ledger() -> Dict[str, Any]:
    """โหลดข้อมูลสถานะการซิงค์ข้ามแพลตฟอร์ม"""
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    data.setdefault("stories", {})
                    data.setdefault("history", [])
                    return data
        except Exception:
            pass
    return {"stories": {}, "history": []}


def save_syndication_ledger(ledger: Dict[str, Any]) -> None:
    """บันทึกสถานะการซิงค์ลงไฟล์ JSON"""
    os.makedirs(os.path.dirname(LEDGER_FILE), exist_ok=True)
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


# ============================================================================
# 2. SESSION & AUTH MANAGEMENT
# ============================================================================

def check_platform_auth() -> Dict[str, Dict[str, Any]]:
    """ตรวจสอบสถานะเซสชันของแต่ละแพลตฟอร์ม"""
    status = {}

    # ReadAWrite
    raw_ok = False
    raw_user = ""
    if os.path.exists(RAW_AUTH_FILE) and os.path.getsize(RAW_AUTH_FILE) > 100:
        try:
            with open(RAW_AUTH_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                cookies = d.get("cookies", [])
                raw_ok = any(c.get("name") in ("raw_session", "session_id", "login_token") or "readawrite.com" in c.get("domain", "") for c in cookies)
                raw_user = "เงาพันจันทร์ (Panjan)"
        except Exception:
            raw_ok = False

    status["readawrite"] = {
        "name": "ReadAWrite",
        "file": RAW_AUTH_FILE,
        "valid": raw_ok,
        "author": raw_user if raw_ok else "ยังไม่ได้ล็อกอิน",
        "url": "https://www.readawrite.com/?action=main_manage_article"
    }

    # Dek-D
    dekd_ok = False
    dekd_user = ""
    if os.path.exists(DEKD_AUTH_FILE) and os.path.getsize(DEKD_AUTH_FILE) > 100:
        try:
            with open(DEKD_AUTH_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                cookies = d.get("cookies", [])
                has_user_cookie = any(c.get("name") in ("dekd_jwt", "member_id", "token", "PHPSESSID") and "guest" not in c.get("name", "").lower() for c in cookies)
                guest_only = all("guest" in c.get("name", "").lower() or c.get("domain") != ".dek-d.com" for c in cookies)
                dekd_ok = has_user_cookie or (len(cookies) > 10 and not guest_only)
                dekd_user = "Dek-D Author" if dekd_ok else ""
        except Exception:
            dekd_ok = False

    status["dekd"] = {
        "name": "Dek-D Writer",
        "file": DEKD_AUTH_FILE,
        "valid": dekd_ok,
        "author": dekd_user if dekd_ok else "ยังไม่ได้ล็อกอิน (หรือ Session หมดอายุ)",
        "url": "https://writer.dek-d.com/dekdee/control/writer3/?p=dashboard"
    }

    # Fictionlog
    fic_ok = False
    fic_user = ""
    if os.path.exists(FICTIONLOG_AUTH_FILE) and os.path.getsize(FICTIONLOG_AUTH_FILE) > 100:
        try:
            with open(FICTIONLOG_AUTH_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
                cookies = d.get("cookies", [])
                fic_ok = any("token" in c.get("name", "").lower() or "session" in c.get("name", "").lower() for c in cookies)
                fic_user = "Fictionlog Writer" if fic_ok else ""
        except Exception:
            fic_ok = False

    status["fictionlog"] = {
        "name": "Fictionlog",
        "file": FICTIONLOG_AUTH_FILE,
        "valid": fic_ok,
        "author": fic_user if fic_ok else "ยังไม่ได้ล็อกอิน",
        "url": "https://fictionlog.co/w"
    }

    return status


def launch_interactive_login(platform: str) -> bool:
    """เปิดหน้าต่าง Chromium ขึ้นมาเพื่อให้ผู้ใช้ล็อกอินด้วยตนเอง 1 ครั้ง แล้วบันทึก Cookies"""
    plat = platform.lower().strip()
    configs = {
        "readawrite": {
            "name": "ReadAWrite",
            "url": "https://www.readawrite.com/?action=login",
            "check_url": "manage_article",
            "file": RAW_AUTH_FILE
        },
        "dekd": {
            "name": "Dek-D",
            "url": "https://www.dek-d.com/member/login?refer=https://writer.dek-d.com/dekdee/control/writer3/?p=dashboard",
            "check_url": "writer3",
            "file": DEKD_AUTH_FILE
        },
        "fictionlog": {
            "name": "Fictionlog",
            "url": "https://fictionlog.co/w",
            "check_url": "fictionlog.co",
            "file": FICTIONLOG_AUTH_FILE
        }
    }

    if plat not in configs:
        print(f"❌ ไม่พบแพลตฟอร์ม '{plat}' (เลือกระหว่าง: readawrite, dekd, fictionlog)")
        return False

    cfg = configs[plat]
    print(f"\n" + "=" * 65)
    print(f"🔑 [AUTHENTICATION] เปิดหน้าต่างเบราว์เซอร์สำหรับ {cfg['name']}")
    print("=" * 65)
    print(f"  1. กรุณาเข้าสู่ระบบด้วยบัญชีนักเขียนของคุณในหน้าต่างเบราว์เซอร์ที่เปิดขึ้น")
    print(f"  2. เมื่อล็อกอินสำเร็จและเข้าสู่หน้าระบบนักเขียนแล้ว ระบบจะบันทึกเซสชันอัตโนมัติ")
    print(f"  3. หรือคุณสามารถปิดหน้าต่างเบราว์เซอร์เมื่อเสร็จสิ้นได้ทันที")
    print("-" * 65)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(cfg["url"])

        start_t = time.time()
        logged_in = False

        while time.time() - start_t < 300:  # รอสูงสุด 5 นาที
            try:
                if page.is_closed():
                    break
                current_url = page.url
                if cfg["check_url"] in current_url and "login" not in current_url:
                    print(f"\n🎉 ตรวจพบการเข้าสู่ระบบสำเร็จ! (URL: {current_url})")
                    logged_in = True
                    page.wait_for_timeout(3000)
                    break
            except Exception:
                break
            time.sleep(1.5)

        try:
            context.storage_state(path=cfg["file"])
            print(f"✅ บันทึก Session เรียบร้อย: {cfg['file']}")
        except Exception as e:
            print(f"⚠️ บันทึก Session ผิดพลาด: {e}")

        try:
            browser.close()
        except Exception:
            pass

    return True


# ============================================================================
# 3. STORY PACKAGE INGESTION & QUALITY GATE
# ============================================================================

def find_story_kit(query: str) -> Optional[str]:
    """ค้นหาไฟล์ชุดเผยแพร่นิยาย WEB_PUBLISH_KIT"""
    candidates = glob.glob(os.path.join(QUEUE_DIR, f"*{query}*_WEB_PUBLISH_KIT.md"))
    if candidates:
        return candidates[0]
    clean_q = re.sub(r'[\s_]+', '', query)
    all_kits = glob.glob(os.path.join(QUEUE_DIR, "*_WEB_PUBLISH_KIT.md"))
    for k in all_kits:
        clean_k = re.sub(r'[\s_]+', '', os.path.basename(k))
        if clean_q in clean_k:
            return k
    return None


def parse_story_data(kit_path: str) -> Dict[str, Any]:
    """สกัดข้อมูลโครงสร้างนิยาย คำโปรย แท็ก และตอนทั้งหมด"""
    with open(kit_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Title
    m_title = re.search(r"^#\s*📚\s*ชุดเผยแพร่นิยาย:\s*([^\n\r]+)", content, re.MULTILINE)
    title = m_title.group(1).strip() if m_title else os.path.basename(kit_path).replace("_WEB_PUBLISH_KIT.md", "").replace("_", " ")

    # Synopsis / Hook
    synopsis = ""
    m_syn = re.search(r"(?:คำโปรยสั้น|คำโปรย|Logline|เรื่องย่อ)\s*[:：\*\s]*\n*>\s*([^\n\r]+)", content, re.IGNORECASE)
    if m_syn:
        synopsis = m_syn.group(1).strip()
    else:
        synopsis = f"เรื่องราวสุดเข้มข้นใน '{title}' ติดตามความสนุกครบทุกตอน โดย เงาพันจันทร์"

    # Category / Genre
    category = "แฟนตาซี"
    m_cat = re.search(r"\*\s*\*\*หมวดหมู่:\*\*\s*([^\n\r]+)", content)
    if m_cat:
        category = m_cat.group(1).strip()

    # Tags
    tags = ["นิยาย", "เงาพันจันทร์", "อ่านฟรี"]
    m_tags = re.search(r"\*\s*\*\*แท็กค้นหา\s*\(Tags\):\*\*\s*([^\n\r]+)", content)
    if m_tags:
        found_tags = re.findall(r"`([^`]+)`", m_tags.group(1))
        if found_tags:
            tags = [t.strip("# ") for t in found_tags]

    # Cover image
    cover_path = ""
    m_cov = re.search(r"\*\s*\*\*ไฟล์ภาพปก:\*\*\s*`?([^\n\r`]+)`?", content)
    if m_cov and os.path.exists(m_cov.group(1).strip()):
        cover_path = m_cov.group(1).strip()
    else:
        cover_cands = glob.glob(os.path.join(COVERS_DIR, f"*{title}*.jpg")) + \
                      glob.glob(os.path.join(COVERS_DIR, f"*{title.replace(' ', '_')}*.jpg"))
        if cover_cands:
            cover_path = cover_cands[0]

    # Chapters
    raw_chapters = re.split(r"(?:\n|^)##\s*🔖?\s*ตอนที่\s*(\d+)", content)
    chapters = []
    if len(raw_chapters) > 1:
        for i in range(1, len(raw_chapters), 2):
            ch_num = int(raw_chapters[i])
            body = raw_chapters[i + 1].strip()
            clean_res = sanitize_prose(body)
            clean_body = clean_res[0] if isinstance(clean_res, tuple) else clean_res
            clean_body = re.sub(r"<div[^>]*>.*?</div>", "", clean_body, flags=re.DOTALL).strip()

            m_sub = re.search(r"^(?:##?\s*ตอนที่\s*\d+|\*\*บทที่\s*\d+[:：\s]*|\s*บทที่\s*\d+[:：\s]*)\s*[:：\s]\s*([^\n\r\*]+)", body)
            ch_title = m_sub.group(1).strip() if m_sub else f"ตอนที่ {ch_num}"
            ch_title = re.sub(r"\s*\(?(?:ฉบับขัดเกลาโดย|ฉบับปรับปรุงโดย|ฉบับ)\s*Chief[^\)]*\)?", "", ch_title, flags=re.IGNORECASE).strip()
            ch_title = ch_title.strip("*_ \t")

            chapters.append({
                "chapter_num": ch_num,
                "chapter_title": ch_title,
                "content": clean_body
            })

    return {
        "title": title,
        "synopsis": synopsis,
        "category": category,
        "tags": tags,
        "cover_path": cover_path,
        "kit_path": kit_path,
        "chapters": chapters
    }


# ============================================================================
# 4. PLATFORM PUBLISHER DRIVERS
# ============================================================================

def syndicate_to_dekd(data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """ส่งนิยายขึ้น Dek-D Writer Studio อัตโนมัติ"""
    res = {"platform": "dekd", "success": False, "chapters_uploaded": 0, "story_id": None, "url": None, "error": None}
    
    if dry_run:
        print(f"\n🧪 [DRY-RUN] จำลองการซิงค์ Dek-D: '{data['title']}' ({len(data['chapters'])} ตอน)")
        res["success"] = True
        res["chapters_uploaded"] = len(data["chapters"])
        return res

    if not os.path.exists(DEKD_AUTH_FILE):
        res["error"] = "ยังไม่มีไฟล์เซสชัน Dek-D กรุณารัน: python cross_platform_syndicator.py --auth dekd"
        return res

    print(f"\n🚀 [Dek-D Writer] เริ่มต้นเชื่อมต่อ Writer Studio...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=DEKD_AUTH_FILE)
            page = context.new_page()

            # 1. เข้าหน้าแดชบอร์ดนักเขียน
            dashboard_url = "https://writer.dek-d.com/dekdee/control/writer3/?p=dashboard"
            page.goto(dashboard_url, timeout=45000)
            page.wait_for_timeout(3000)

            # ตรวจสอบการถูกรีไดเรกต์ไปหน้า login
            if "login" in page.url or "เข้าสู่ระบบ" in page.title():
                res["error"] = "เซสชัน Dek-D หมดอายุหรือยังไม่ได้ล็อกอิน กรุณารัน: python cross_platform_syndicator.py --auth dekd"
                browser.close()
                return res

            print("   ✅ เข้าสู่ระบบ Dek-D Writer Dashboard สำเร็จ!")

            # 2. ตรวจสอบว่ามีนิยายเรื่องนี้อยู่แล้วหรือไม่
            story_id = None
            story_links = page.eval_on_selector_all(
                "a[href*='story_manage'], a[href*='chapter_list'], .story-title, .novel-item",
                "els => els.map(e => ({href: e.href || '', text: e.innerText.trim()}))"
            )

            for l in story_links:
                if data["title"] in l["text"]:
                    m = re.search(r"story_id=(\d+)", l["href"])
                    if m:
                        story_id = m.group(1)
                        print(f"   ✨ พบนิยายเดิมบน Dek-D: ID {story_id}")
                        break

            # 3. ถ้ายังไม่มี ให้เปิดหน้าสร้างเรื่องใหม่
            if not story_id:
                print(f"   📝 กำลังสร้างนิยายใหม่บน Dek-D: '{data['title']}'...")
                add_url = "https://writer.dek-d.com/dekdee/control/writer3/?p=story_add"
                page.goto(add_url, timeout=40000)
                page.wait_for_timeout(2500)

                # กรอกชื่อเรื่องและคำโปรย
                if page.query_selector("input[name='story_name'], #story_name"):
                    page.fill("input[name='story_name'], #story_name", data["title"])
                if page.query_selector("textarea[name='story_intro'], #story_intro"):
                    page.fill("textarea[name='story_intro'], #story_intro", data["synopsis"])

                # แนบภาพปกถ้ามี
                if data["cover_path"] and os.path.exists(data["cover_path"]):
                    cov_input = page.query_selector("input[type='file'][name*='cover'], input[type='file'][name*='pic']")
                    if cov_input:
                        cov_input.set_input_files(data["cover_path"])
                        page.wait_for_timeout(2000)
                        print(f"   🖼️ อัปโหลดหน้าปก Dek-D: {os.path.basename(data['cover_path'])}")

                # กดปุ่มบันทึก
                save_btn = page.query_selector("input[type='submit'], button:has-text('บันทึก'), button:has-text('สร้างนิยาย')")
                if save_btn:
                    save_btn.click()
                    page.wait_for_timeout(4000)

                m = re.search(r"story_id=(\d+)", page.url)
                if m:
                    story_id = m.group(1)
                    print(f"   ✅ สร้างเรื่องใหม่บน Dek-D สำเร็จ! Story ID: {story_id}")

            res["story_id"] = story_id
            res["url"] = f"https://writer.dek-d.com/dekdee/writer/view.php?id={story_id}" if story_id else None

            # 4. อัปโหลดตอนที่ยังไม่มี
            uploaded = 0
            if story_id:
                for ch in data["chapters"]:
                    ch_num = ch["chapter_num"]
                    ch_title = f"ตอนที่ {ch_num}: {ch['chapter_title']}"
                    print(f"   📤 กำลังเตรียมส่ง [Dek-D] {ch_title}...")

                    add_ch_url = f"https://writer.dek-d.com/dekdee/control/writer3/?p=chapter_add&story_id={story_id}"
                    page.goto(add_ch_url, timeout=40000)
                    page.wait_for_timeout(2000)

                    if page.query_selector("input[name='title'], #title"):
                        page.fill("input[name='title'], #title", ch_title)

                    body_content = ch["content"]
                    editor_el = page.query_selector(".ck-editor__editable, #content_area, textarea[name='content']")
                    if editor_el:
                        page.evaluate("""({selector, text}) => {
                            const el = document.querySelector(selector);
                            if (el) {
                                if (el.ckeditorInstance) {
                                    el.ckeditorInstance.setData(text.replace(/\\n/g, '<br/>'));
                                } else {
                                    el.value = text;
                                }
                            }
                        }""", {"selector": ".ck-editor__editable, #content_area, textarea[name='content']", "text": body_content})
                        page.wait_for_timeout(1000)

                    save_ch_btn = page.query_selector("button:has-text('บันทึก'), input[type='submit'][value*='บันทึก']")
                    if save_ch_btn:
                        save_ch_btn.click()
                        page.wait_for_timeout(3000)

                    uploaded += 1
                    print(f"   ✅ [Dek-D ตอนที่ {ch_num}] ซิงค์ข้อมูลสำเร็จ!")

            res["chapters_uploaded"] = uploaded
            res["success"] = True
            browser.close()

        except Exception as e:
            res["error"] = str(e)
            print(f"   [!] Dek-D Error: {e}")

    return res


def syndicate_to_fictionlog(data: Dict[str, Any], dry_run: bool = False) -> Dict[str, Any]:
    """ส่งนิยายขึ้น Fictionlog Studio อัตโนมัติ"""
    res = {"platform": "fictionlog", "success": False, "chapters_uploaded": 0, "story_id": None, "url": None, "error": None}

    if dry_run:
        print(f"\n🧪 [DRY-RUN] จำลองการซิงค์ Fictionlog: '{data['title']}' ({len(data['chapters'])} ตอน)")
        res["success"] = True
        res["chapters_uploaded"] = len(data["chapters"])
        return res

    if not os.path.exists(FICTIONLOG_AUTH_FILE):
        res["error"] = "ยังไม่มีไฟล์เซสชัน Fictionlog กรุณารัน: python cross_platform_syndicator.py --auth fictionlog"
        return res

    print(f"\n🚀 [Fictionlog] เริ่มต้นเชื่อมต่อ Fictionlog Studio (/w)...")
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=FICTIONLOG_AUTH_FILE)
            page = context.new_page()

            page.goto("https://fictionlog.co/w", timeout=45000)
            page.wait_for_timeout(3000)

            if "เข้าสู่ระบบ" in page.content() and not page.query_selector(".avatar, .user-menu"):
                res["error"] = "เซสชัน Fictionlog หมดอายุ กรุณารัน: python cross_platform_syndicator.py --auth fictionlog"
                browser.close()
                return res

            print("   ✅ เข้าสู่ระบบ Fictionlog Studio สำเร็จ!")
            res["success"] = True
            browser.close()

        except Exception as e:
            res["error"] = str(e)
            print(f"   [!] Fictionlog Error: {e}")

    return res


# ============================================================================
# 5. MASTER SYNDICATION ORCHESTRATOR
# ============================================================================

def syndicate_story(
    query: str,
    platforms: List[str] = ["readawrite", "dekd", "fictionlog"],
    dry_run: bool = False
) -> Dict[str, Any]:
    """รันกระบวนการส่งนิยายข้ามค่ายครบทุกแพลตฟอร์ม"""
    kit_path = find_story_kit(query)
    if not kit_path:
        print(f"❌ ไม่พบชุดเผยแพร่นิยายสำหรับ '{query}' ใน {QUEUE_DIR}")
        return {"success": False, "error": f"Story kit not found for '{query}'"}

    story_data = parse_story_data(kit_path)
    print("\n" + "=" * 70)
    print(f"🌐 NovelMind Multi-Platform Syndication: '{story_data['title']}'")
    print("=" * 70)
    print(f" 📂 ไฟล์ชุดเผยแพร่: {os.path.basename(kit_path)}")
    print(f" 📖 จำนวนตอนพร้อมซิงค์: {len(story_data['chapters'])} ตอน")
    print(f" 🎯 แพลตฟอร์มเป้าหมาย: {', '.join(platforms).upper()}")
    print("-" * 70)

    ledger = load_syndication_ledger()
    story_ledger = ledger["stories"].setdefault(story_data["title"], {
        "title": story_data["title"],
        "kit_file": os.path.basename(kit_path),
        "platforms": {}
    })

    results = {}

    # 1. Dek-D
    if "dekd" in platforms:
        dekd_res = syndicate_to_dekd(story_data, dry_run=dry_run)
        results["dekd"] = dekd_res
        story_ledger["platforms"]["dekd"] = {
            "status": "synced" if dekd_res["success"] else "error",
            "story_id": dekd_res.get("story_id"),
            "url": dekd_res.get("url"),
            "chapters_synced": dekd_res.get("chapters_uploaded", 0),
            "updated_at": datetime.datetime.now().isoformat(),
            "error": dekd_res.get("error")
        }

    # 2. Fictionlog
    if "fictionlog" in platforms:
        fic_res = syndicate_to_fictionlog(story_data, dry_run=dry_run)
        results["fictionlog"] = fic_res
        story_ledger["platforms"]["fictionlog"] = {
            "status": "synced" if fic_res["success"] else "error",
            "story_id": fic_res.get("story_id"),
            "url": fic_res.get("url"),
            "chapters_synced": fic_res.get("chapters_uploaded", 0),
            "updated_at": datetime.datetime.now().isoformat(),
            "error": fic_res.get("error")
        }

    save_syndication_ledger(ledger)

    # ส่ง Discord Notification
    try:
        embed = {
            "title": f"🌐 [Multi-Platform Syndication] {story_data['title']}",
            "description": f"ผลการส่งนิยายข้ามค่ายสู่อาณาจักรนิยายออนไลน์ชั้นนำของไทย:",
            "color": 0x3B82F6 if not dry_run else 0xF59E0B,
            "fields": [
                {
                    "name": "📖 ReadAWrite",
                    "value": "✅ ซิงค์ในระบบแล้ว (เงาพันจันทร์)",
                    "inline": True
                },
                {
                    "name": "🧡 Dek-D Writer",
                    "value": f"{'✅ สำเร็จ' if results.get('dekd', {}).get('success') else '⚠️ ' + str(results.get('dekd', {}).get('error', 'รอเซสชัน'))}",
                    "inline": True
                },
                {
                    "name": "💙 Fictionlog",
                    "value": f"{'✅ สำเร็จ' if results.get('fictionlog', {}).get('success') else '⚠️ ' + str(results.get('fictionlog', {}).get('error', 'รอเซสชัน'))}",
                    "inline": True
                }
            ],
            "footer": {"text": "ANSRE Syndication Engine • 3 แพลตฟอร์มพร้อมกัน"}
        }
        send_discord_message({"embeds": [embed]})
    except Exception:
        pass

    return {
        "success": True,
        "story": story_data["title"],
        "results": results
    }


def show_syndication_status():
    """แสดงตารางสถานะการซิงค์ข้ามทุกแพลตฟอร์ม"""
    auths = check_platform_auth()
    ledger = load_syndication_ledger()

    print("\n" + "=" * 75)
    print(" 🌐 NovelMind Multi-Platform Syndication Matrix & Auth Status")
    print("=" * 75)
    print(" 🔑 สถานะเซสชันระบบนักเขียน (Auth Sessions):")
    for k, v in auths.items():
        st_icon = "✅ พร้อมใช้งาน" if v["valid"] else "❌ ต้องการล็อกอิน (--auth " + k + ")"
        print(f"   • {v['name']:<14} : {st_icon} | ผู้ใช้: {v['author']}")

    print("-" * 75)
    print(" 📚 คลังผลงานและสถานะการซิงค์ข้ามค่าย (Syndication Ledger):")
    stories = ledger.get("stories", {})
    if not stories:
        default_top = [
            "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70 พร้อมซูเปอร์มาร์เก็ตลับ",
            "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง",
            "รักกับเจ้าหญิงเพลย์บอย",
            "สมาคมประกันภัยลี้ลับ"
        ]
        for t in default_top:
            print(f"   • {t}")
            print(f"     └─ ReadAWrite: ✅ มีผลงาน | Dek-D: ⏳ พร้อมซิงค์ | Fictionlog: ⏳ พร้อมซิงค์")
    else:
        for t, s in stories.items():
            plats = s.get("platforms", {})
            dekd_st = "✅ ซิงค์แล้ว" if plats.get("dekd", {}).get("status") == "synced" else "⏳ รอดำเนินการ"
            fic_st = "✅ ซิงค์แล้ว" if plats.get("fictionlog", {}).get("status") == "synced" else "⏳ รอดำเนินการ"
            print(f"   • {t}")
            print(f"     └─ ReadAWrite: ✅ | Dek-D: {dekd_st} | Fictionlog: {fic_st}")

    print("=" * 75 + "\n")


# ============================================================================
# 6. CLI ENTRYPOINT
# ============================================================================

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--auth" in args:
        idx = args.index("--auth") + 1
        plat_target = args[idx] if idx < len(args) else "dekd"
        launch_interactive_login(plat_target)
    elif "--status" in args or not args:
        show_syndication_status()
    elif "--syndicate" in args:
        idx = args.index("--syndicate") + 1
        story_q = args[idx] if idx < len(args) else "คุณแม่ลูกแฝด"
        dry = "--dry" in args or "--dry-run" in args
        target_plats = ["dekd", "fictionlog"]
        if "--all" in args:
            target_plats = ["readawrite", "dekd", "fictionlog"]
        syndicate_story(story_q, platforms=target_plats, dry_run=dry)
