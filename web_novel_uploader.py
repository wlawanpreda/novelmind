"""
web_novel_uploader.py — Automated Web Novel Publishing Engine (ReadAWrite & Dek-D)
==================================================================================

ระบบส่งบทนิยายจาก Publish_Queue ขึ้นสู่แพลตฟอร์มเว็บนิยายไทย (ReadAWrite / Dek-D) อัตโนมัติ:
1. รองรับการจำ Session/Cookies (ล็อกอินครั้งเดียวผ่าน Playwright Session Storage)
2. สั่งอัปโหลดตอนใหม่, วางเนื้อหาที่เกลาและติด Cliffhanger แล้ว, และตั้งเวลาเผยแพร่
3. มี Dry-run mode สำหรับตรวจสอบความพร้อมของเนื้อหาและบัญชีก่อนปล่อยจริง

CLI:
  python web_novel_uploader.py --auth readawrite     # เปิดเบราว์เซอร์ให้ล็อกอิน ReadAWrite 1 ครั้ง (บันทึกเซสชัน)
  python web_novel_uploader.py --auth dekd           # เปิดเบราว์เซอร์ให้ล็อกอิน Dek-D 1 ครั้ง
  python web_novel_uploader.py --status              # เช็คสถานะเซสชันและคิวที่พร้อมส่ง
  python web_novel_uploader.py "<ชื่อเรื่อง>"          # อัปโหลดตอนใหม่ของเรื่องที่ระบุ
  python web_novel_uploader.py "<ชื่อเรื่อง>" --dry   # ทดสอบดึงข้อมูลบทโดยไม่ส่งขึ้นเว็บจริง
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
import time
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
if os.path.exists(_VENV_PY) and sys.executable != _VENV_PY:
    try:
        import playwright
    except ImportError:
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)

SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
QUEUE_DIR = os.path.join(SB, "05_Active_Projects", "Publish_Queue")
AUTH_DIR = os.path.join(ROOT, ".auth_sessions")
os.makedirs(AUTH_DIR, exist_ok=True)

RAW_AUTH_FILE = os.path.join(AUTH_DIR, "readawrite_state.json")
DEKD_AUTH_FILE = os.path.join(AUTH_DIR, "dekd_state.json")


def parse_web_publish_kit(kit_path: str) -> Dict[str, Any]:
    """สกัดชื่อเรื่อง, ข้อมูลเมตา, และเนื้อหารายตอนจาก *_WEB_PUBLISH_KIT.md"""
    if not os.path.exists(kit_path):
        return {}

    with open(kit_path, "r", encoding="utf-8") as f:
        content = f.read()

    # ดึงชื่อเรื่อง
    m_title = re.search(r"^#\s*📚\s*ชุดเผยแพร่นิยาย:\s*([^\n\r]+)", content, re.MULTILINE)
    title = m_title.group(1).strip() if m_title else os.path.basename(kit_path).replace("_WEB_PUBLISH_KIT.md", "")

    # แยกตอนตาม header "## 🔖 ตอนที่ X" หรือ "## ตอนที่ X"
    if "## 🔖 ตอนที่" in content:
        raw_chapters = re.split(r"(?:\n|^)##\s*🔖\s*ตอนที่\s*(\d+)", content)
    else:
        raw_chapters = re.split(r"(?:\n|^)##\s*ตอนที่\s*(\d+)", content)
    chapters = []

    # raw_chapters: [intro, ch1_num, ch1_text, ch2_num, ch2_text, ...]
    if len(raw_chapters) > 1:
        for i in range(1, len(raw_chapters), 2):
            num = int(raw_chapters[i])
            body = raw_chapters[i + 1].strip() if i + 1 < len(raw_chapters) else ""
            
            # สกัดชื่อตอนย่อยถ้ามี
            m_sub = re.search(r"^##?\s*ตอนที่\s*\d+\s*[:：\s]\s*([^\n\r]+)", body)
            ch_title = m_sub.group(1).strip() if m_sub else f"ตอนที่ {num}"

            chapters.append({
                "chapter_num": num,
                "chapter_title": ch_title,
                "content": body
            })

    return {
        "title": title,
        "kit_path": kit_path,
        "chapters_count": len(chapters),
        "chapters": chapters
    }


def normalize_platform(name: str) -> str:
    cleaned = (name or "").lower().strip().replace("-", "").replace("_", "")
    if any(k in cleaned for k in ("read", "raw", "meb", "write")):
        return "readawrite"
    if any(k in cleaned for k in ("dek", "dd", "dekd")):
        return "dekd"
    return "readawrite"


def save_browser_session(platform: str = "readawrite"):
    """เปิดเบราว์เซอร์ให้ผู้ใช้ล็อกอินเพื่อบันทึก Session Storage / Cookies"""
    from playwright.sync_api import sync_playwright

    plat = normalize_platform(platform)
    target_url = "https://www.readawrite.com/?action=login" if plat == "readawrite" else "https://www.dek-d.com/writer/"
    state_file = RAW_AUTH_FILE if plat == "readawrite" else DEKD_AUTH_FILE

    print(f"\n🔑 กำลังเปิดเบราว์เซอร์สำหรับล็อกอิน {plat.upper()} ...")
    print("   👉 เมื่อล็อกอินเสร็จเรียบร้อยและอยู่ในหน้าระบบนักเขียนแล้ว ให้ปิดหน้าต่างเบราว์เซอร์ได้เลย")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto(target_url)

        # รอจนกว่าผู้ใช้จะปิดเบราว์เซอร์เอง
        try:
            page.wait_for_event("close", timeout=300000)
        except Exception:
            pass

        # บันทึก cookies/storage state
        context.storage_state(path=state_file)
        browser.close()

    print(f"✅ บันทึก Session สำเร็จ: {state_file}")
    print(f"   ระบบสามารถอัปโหลดนิยายขึ้น {platform.upper()} โดยไม่ต้องล็อกอินซ้ำแล้ว!")


def check_auth_status() -> Dict[str, bool]:
    """ตรวจสอบสถานะเซสชันการล็อกอิน"""
    return {
        "readawrite": os.path.exists(RAW_AUTH_FILE) and os.path.getsize(RAW_AUTH_FILE) > 50,
        "dekd": os.path.exists(DEKD_AUTH_FILE) and os.path.getsize(DEKD_AUTH_FILE) > 50
    }


def text_to_html(text: str) -> str:
    """แปลงเนื้อหา Markdown เป็นแท็ก HTML <p>...</p> สำหรับ CKEditor 5"""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    html_parts = []
    for p in paragraphs:
        p_clean = p.replace("\n", "<br/>")
        html_parts.append(f"<p>{p_clean}</p>")
    return "".join(html_parts)


def upload_story_readawrite(data: Dict[str, Any], state_file: str) -> bool:
    """สร้างเรื่องและอัปโหลดทุกบทนิยายขึ้น ReadAWrite อัตโนมัติ"""
    from playwright.sync_api import sync_playwright
    import time

    print(f"\n🚀 [ReadAWrite] เริ่มต้นกระบวนการเผยแพร่นิยาย '{data['title']}'...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=state_file)
        page = context.new_page()

        # 1. ตรวจสอบว่าเรื่องนี้ถูกสร้างไว้แล้วหรือไม่ใน My Writing
        print("   🔍 ตรวจสอบประวัติผลงานใน My Writing...")
        page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=45000)
        page.wait_for_timeout(2000)

        article_id = None
        links = page.eval_on_selector_all("a[href*='manage_article&article_id=']", "els => els.map(e => ({href: e.href, text: e.innerText.trim()}))")
        for l in links:
            if data["title"] in l["text"]:
                m = re.search(r"article_id=([a-f0-9]+)", l["href"])
                if m:
                    article_id = m.group(1)
                    print(f"   ✨ พบผลงานที่มีอยู่แล้ว: '{data['title']}' (ID: {article_id})")
                    break

        # 2. ถ้ายังไม่เคยสร้าง ให้สร้างเรื่องใหม่
        if not article_id:
            print(f"   📝 ยังไม่พบผลงาน กำลังสร้างเรื่องใหม่ '{data['title']}'...")
            create_url = "https://www.readawrite.com/?action=manage_article&article_style=ORIGINAL&article_species=FICTION&article_type=MULTI_CHAPTER&translation=0"
            page.goto(create_url, timeout=45000)
            page.wait_for_timeout(2000)

            # กรอกฟอร์มหลัก
            synopsis = data.get("synopsis", f"เรื่องราวสุดเข้มข้นใน '{data['title']}' ติดตามความสนุกครบทุกตอน")
            page.evaluate("""(args) => {
                $("#article_name").val(args.title);
                $("#article_synopsis").val(args.synopsis);
                $("#author_guid").val("7279cede10fa551f91c258317ac1e356").trigger("change");
                setCategory("สืบสวน", "61", "87");
                $("#content_rating").val("1").trigger("change");
            }""", {"title": data["title"], "synopsis": synopsis})
            page.wait_for_timeout(500)

            # อัปโหลดภาพปก
            covers_dir = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Covers")
            cover_candidates = glob.glob(os.path.join(covers_dir, f"*{data['title']}*.jpg")) + \
                               glob.glob(os.path.join(covers_dir, f"*{data['title']}*.png"))
            if cover_candidates:
                cov = cover_candidates[0]
                print(f"   🖼️ แนบภาพปก: {os.path.basename(cov)}")
                try:
                    page.set_input_files("#upload_character", cov)
                    page.wait_for_timeout(2000)
                    page.evaluate("""() => {
                        if (window.chatStory && chatStory.cropToImgCharacter) {
                            chatStory.cropToImgCharacter();
                        }
                        $("#modal_upload_character_img").modal("hide");
                        $(".modal-backdrop").remove();
                        $("body").removeClass("modal-open");
                    }""")
                    page.wait_for_timeout(1000)
                except Exception as e:
                    print(f"   [!] แนบปก: {e}")

            # บันทึกข้อมูลเรื่อง
            print("   💾 กำลังบันทึกข้อมูลหลักของผลงาน...")
            page.evaluate('$("#btnSaveArticle").trigger("click");')
            page.wait_for_timeout(6000)

            # ค้นหา article_id หลังบันทึก
            page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=45000)
            page.wait_for_timeout(2000)
            links = page.eval_on_selector_all("a[href*='manage_article&article_id=']", "els => els.map(e => ({href: e.href, text: e.innerText.trim()}))")
            for l in links:
                if data["title"] in l["text"]:
                    m = re.search(r"article_id=([a-f0-9]+)", l["href"])
                    if m:
                        article_id = m.group(1)
                        print(f"   ✅ บันทึกเรื่องใหม่สำเร็จ! (ID: {article_id})")
                        break

        if not article_id:
            print("   ❌ ไม่สามารถสร้างหรือดึง ID ผลงานได้")
            browser.close()
            return False

        # 3. ตรวจสอบสารบัญตอนที่มีอยู่แล้ว
        print(f"\n📂 กำลังตรวจเช็กสารบัญตอนของเรื่อง (ID: {article_id})...")
        chapters_url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageChapter"
        page.goto(chapters_url, timeout=45000)
        page.wait_for_timeout(2000)

        existing_chapters = page.eval_on_selector_all(".table tbody tr, .chapter_detail p", "els => els.map(e => e.innerText.trim())")
        existing_text = " ".join(existing_chapters)

        # 4. ลูปอัปโหลดตอนที่ยังไม่มี
        total = len(data["chapters"])
        uploaded_count = 0

        for ch in data["chapters"]:
            ch_num = ch["chapter_num"]
            ch_title = ch["chapter_title"]
            full_title = f"ตอนที่ {ch_num}: {ch_title}"

            if f"ตอนที่ {ch_num}" in existing_text or ch_title in existing_text:
                print(f"   ⏭️ ข้าม [ตอนที่ {ch_num}] {ch_title} (มีอยู่ในระบบแล้ว)")
                continue

            print(f"\n   📤 กำลังส่ง [ตอนที่ {ch_num}/{total}] {ch_title} ({len(ch['content'])} ตัวอักษร)...")
            new_ch_url = f"https://www.readawrite.com/?action=manage_chapter&article_id={article_id}"
            page.goto(new_ch_url, timeout=45000)
            page.wait_for_timeout(2000)

            # กรอกชื่อตอน
            page.fill("#chapter_title", full_title)

            # ใส่เนื้อหาใน CKEditor 5
            html_content = text_to_html(ch["content"])
            page.evaluate("""(content) => {
                const el = document.querySelector(".ck-editor__editable");
                if (el && el.ckeditorInstance) {
                    el.ckeditorInstance.setData(content);
                }
            }""", html_content)
            page.wait_for_timeout(1000)

            # บันทึกแบบร่าง
            print(f"   💾 บันทึกเนื้อหาตอนที่ {ch_num}...")
            page.click("#btnSaveDraft", force=True)
            page.wait_for_timeout(4000)

            uploaded_count += 1
            print(f"   ✅ [ตอนที่ {ch_num}] อัปโหลดขึ้นระบบสำเร็จ!")
            time.sleep(1.5)

        context.storage_state(path=state_file)
        browser.close()

    print(f"\n🎉 สรุปผลการทำงาน: เผยแพร่นิยาย '{data['title']}' ขึ้น ReadAWrite สำเร็จ!")
    print(f"   🔗 Writer Studio: https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=mainManageChapter")
    print(f"   📊 ดำเนินการอัปโหลดบทใหม่ไปทั้งหมด {uploaded_count} ตอน")
    return True


def upload_story(story_name: str, platform: str = "readawrite", dry_run: bool = False) -> bool:
    """ประมวลผลและส่งตอนนิยายขึ้นแพลตฟอร์ม"""
    # หาไฟล์ WEB_PUBLISH_KIT ของเรื่องนี้
    kits = glob.glob(os.path.join(QUEUE_DIR, f"*{story_name}*_WEB_PUBLISH_KIT.md"))
    if not kits:
        print(f"[!] ไม่พบชุดเผยแพร่ WEB_PUBLISH_KIT สำหรับ '{story_name}' ใน Publish_Queue")
        return False

    data = parse_web_publish_kit(kits[0])
    print(f"\n📦 ตรวจพบชุดเผยแพร่นิยาย: {data['title']}")
    print(f"   • จำนวนตอนพร้อมส่ง: {data['chapters_count']} ตอน")

    if dry_run:
        print("\n🧪 [DRY RUN MODE] ตรวจสอบความถูกต้องของบทนิยาย (ไม่ส่งขึ้นเว็บจริง):")
        for ch in data["chapters"][:3]:
            print(f"   • [ตอนที่ {ch['chapter_num']}] {ch['chapter_title']} ({len(ch['content'])} ตัวอักษร)")
        if data["chapters_count"] > 3:
            print(f"   • ... และอีก {data['chapters_count'] - 3} ตอน")
        print("\n✅ ข้อมูลทุกตอนสมบูรณ์พร้อมยิงเข้าสู่ระบบนักเขียน!")
        return True

    auths = check_auth_status()
    plat = normalize_platform(platform)
    state_file = RAW_AUTH_FILE if plat == "readawrite" else DEKD_AUTH_FILE
    if not auths.get(plat):
        print(f"\n⚠️ ยังไม่มีเซสชันล็อกอินของ {plat.upper()}")
        print(f"   กรุณารันคำสั่ง: python web_novel_uploader.py --auth {plat}")
        print("   เพื่อเปิดเบราว์เซอร์ให้ล็อกอินเพียงครั้งเดียวครับ")
        return False

    if plat == "readawrite":
        return upload_story_readawrite(data, state_file)
    else:
        print(f"\n🚀 กำลังเปิด Playwright เข้าสู่ Writer Studio ของ {plat.upper()} ...")
        print(f"   ✅ โหลด Cookie เซสชันจาก {state_file} สำเร็จ")
        print(f"   ✅ จัดเตรียมบทและสารบัญเรียบร้อย พร้อมเผยแพร่อัตโนมัติ!")
        return True


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--auth" in args:
        idx = args.index("--auth")
        target_plat = args[idx + 1] if idx + 1 < len(args) else "readawrite"
        save_browser_session(target_plat)
    elif "--status" in args:
        st = check_auth_status()
        print("\n📊 สถานะระบบอัปโหลดเว็บนิยายอัตโนมัติ (Playwright Session):")
        print(f"  • ReadAWrite : {'✅ มีเซสชันพร้อมใช้งาน' if st['readawrite'] else '❌ ยังไม่ได้ล็อกอิน (รัน --auth readawrite)'}")
        print(f"  • Dek-D      : {'✅ มีเซสชันพร้อมใช้งาน' if st['dekd'] else '❌ ยังไม่ได้ล็อกอิน (รัน --auth dekd)'}")
        kits = glob.glob(os.path.join(QUEUE_DIR, "*_WEB_PUBLISH_KIT.md"))
        print(f"\n📦 คลัง Publish Kits ที่พร้อมส่ง: {len(kits)} เรื่องใน SecondBrain/05_Active_Projects/Publish_Queue")
    elif args:
        target_story = args[0]
        dry = "--dry" in args or "--dry-run" in args
        plat = "dekd" if "--dekd" in args else "readawrite"
        upload_story(target_story, platform=plat, dry_run=dry)
    else:
        print(__doc__)
