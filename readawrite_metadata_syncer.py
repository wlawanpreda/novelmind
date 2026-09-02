#!/usr/bin/env python3
"""
readawrite_metadata_syncer.py — ระบบซิงค์ปก เรื่องย่อ และรายละเอียดนิยายทั้งหมดขึ้น ReadAWrite
=======================================================================================
ทำหน้าที่:
1. สแกนนิยายทั้งหมด 38 เรื่องใน My Writing บน ReadAWrite
2. จับคู่กับภาพปกคุณภาพสูงใน SecondBrain/05_Active_Projects/Covers/
3. สกัดเรื่องย่อและคำโปรยระดับมืออาชีพจาก SecondBrain/02_Concept_Extraction/ หรือ Idea Vault
4. อัปโหลดภาพปก ผ่านระบบ Crop Modal และบันทึกข้อมูลอัตโนมัติ 100% ผ่าน Playwright
"""

from __future__ import annotations

import os
import re
import sys
import glob
import time
from typing import Dict, Any, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
OUTLINES_DIR = os.path.join(SB, "02_Concept_Extraction")
CHARACTERS_DIR = os.path.join(SB, "04_Character_Database")


def get_clean_stem(text: str) -> str:
    """ทำความสะอาดชื่อเรื่องเพื่อใช้จับคู่ข้ามระบบ"""
    return re.sub(r"[\s_:\*—\-\(\)\[\]]", "", text).lower()


def extract_synopsis_from_outline(outline_path: str, fallback_title: str) -> str:
    """สกัดคำโปรย/เรื่องย่อที่น่าติดตามจาก Outline หรือสร้างคำโปรยมาตรฐาน"""
    if os.path.exists(outline_path):
        try:
            with open(outline_path, "r", encoding="utf-8") as f:
                content = f.read()

            # หา Logline หรือ Concept หรือ สรุปเนื้อเรื่อง
            m = re.search(r"(?:Logline|แก่นเรื่อง|คำโปรย|เรื่องย่อ|Concept)[\s:]*([^\n]+(?:\n[^\n#]+)*)", content, re.I)
            if m:
                syn = m.group(1).strip()
                syn = re.sub(r"^[>\-\*\s]+", "", syn)
                if len(syn) > 40:
                    return syn[:350].strip()

            # หากไม่พบ section เจาะจง ดึงย่อหน้าแรกหลัง Title
            paragraphs = [p.strip() for p in content.split("\n\n") if p.strip() and not p.startswith("#")]
            for p in paragraphs:
                clean_p = re.sub(r"^[>\-\*\s]+", "", p)
                if len(clean_p) >= 50:
                    return clean_p[:350].strip()
        except Exception:
            pass

    return f"เรื่องราวสุดเข้มข้นใน '{fallback_title}' ติดตามความสนุก ชวนลุ้นระทึก และปริศนาครบทุกตอน โดย เงาพันจันทร์"


def find_assets_for_title(title: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """จับคู่ภาพปก, ไฟล์ Outline, และ Character Database ที่ตรงกับชื่อเรื่อง"""
    clean_t = get_clean_stem(title)

    # 1. ปก
    cover_file = None
    for p in glob.glob(os.path.join(COVERS_DIR, "*_Cover.*")):
        stem = get_clean_stem(os.path.basename(p).split("_Cover")[0])
        if stem and (stem in clean_t or clean_t in stem):
            cover_file = p
            break

    # 2. Outline
    outline_file = None
    for p in glob.glob(os.path.join(OUTLINES_DIR, "*_Outline.md")):
        stem = get_clean_stem(os.path.basename(p).split("_Outline")[0])
        if stem and (stem in clean_t or clean_t in stem):
            outline_file = p
            break

    # 3. Characters
    char_file = None
    for p in glob.glob(os.path.join(CHARACTERS_DIR, "*_Characters.md")):
        stem = get_clean_stem(os.path.basename(p).split("_Characters")[0])
        if stem and (stem in clean_t or clean_t in stem):
            char_file = p
            break

    return cover_file, outline_file, char_file


def sync_single_story_metadata(page, aid: str, title: str, cover_path: Optional[str],
                               synopsis: str, update_cover: bool = True) -> bool:
    """อัปเดตปกและเรื่องย่อของนิยายเรื่องหนึ่งบน ReadAWrite ผ่าน Playwright"""
    setting_url = f"https://www.readawrite.com/?action=manage_article&article_id={aid}&tab=articleSetting"
    try:
        page.goto(setting_url, timeout=35000)
        page.wait_for_timeout(2000)

        # 1. กรอกเรื่องย่อ
        if synopsis:
            page.fill("#article_synopsis", synopsis)

        # 2. ติ๊กเครื่องหมาย AI Cover (ตามเงื่อนไขแพลตฟอร์ม)
        page.evaluate("() => { const r = document.querySelector('#is_ai_cover1'); if (r) r.checked = true; }")

        # 3. อัปโหลดภาพปก (ถ้ามีไฟล์ และต้องการอัปเดต)
        if update_cover and cover_path and os.path.exists(cover_path):
            file_input = page.query_selector("input#article_image")
            if file_input:
                file_input.set_input_files(os.path.abspath(cover_path))
                page.wait_for_timeout(2500)

                # กดปุ่มครอปรูปใน Modal
                crop_btn = page.query_selector("#modal button[onclick*='article.cropToImg()'], button:has-text('ครอปรูป')")
                if crop_btn and crop_btn.is_visible():
                    crop_btn.click()
                    page.wait_for_timeout(2500)

                # ปิด Backdrop / Modal ถ้าค้าง
                page.evaluate("() => { try { $('#modal').modal('hide'); $('.modal-backdrop').remove(); } catch(e){} }")
                page.wait_for_timeout(1000)

        # 4. ยืนยันคำเตือนระดับภาพ (ถ้ามี)
        page.evaluate("""() => {
            const btn = document.querySelector('#btnAcceptImageLevelWarning, #btnAcceptAdultImageWarning');
            if (btn) btn.click();
        }""")
        page.wait_for_timeout(800)

        # 5. บันทึกบทความ
        save_btn = page.query_selector("#btnSaveArticle")
        if save_btn:
            save_btn.click()
            page.wait_for_timeout(4000)
            return True
        return False
    except Exception as e:
        print(f"      [!] ผิดพลาดในการอัปเดต {title} ({aid}): {e}")
        return False


def run_mass_sync(limit: Optional[int] = None, force_cover: bool = False, dry_run: bool = False):
    """รันซิงค์ข้อมูลนิยายทั้งหมดในระบบ"""
    if not os.path.exists(AUTH_FILE):
        print(f"[!] ไม่พบไฟล์เซสชัน {AUTH_FILE}")
        return

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=AUTH_FILE,
            viewport={"width": 1440, "height": 1080}
        )
        page = context.new_page()

        print("[*] ดึงรายชื่อนิยายจาก ReadAWrite My Writing...")
        page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=45000)
        page.wait_for_timeout(2000)

        links = page.query_selector_all("a[href*=manage_article]")
        seen = set()
        stories = []
        for a in links:
            href = a.get_attribute("href") or ""
            m = re.search(r"article_id=([a-f0-9]+)", href)
            if not m:
                continue
            aid = m.group(1)
            if aid in seen:
                continue
            seen.add(aid)
            t = a.inner_text().strip().split("\n")[0].strip()
            stories.append((aid, t))

        print(f"[*] พบนิยายทั้งหมด {len(stories)} เรื่อง")

        count = 0
        success_count = 0
        for aid, title in stories:
            if limit and count >= limit:
                break
            count += 1

            cov, outl, char_f = find_assets_for_title(title)
            synopsis = extract_synopsis_from_outline(outl or "", title) if outl else ""

            cov_name = os.path.basename(cov) if cov else "ไม่มีปก"
            print(f"[{count}/{len(stories)}] เรื่อง: {title}")
            print(f"    - AID: {aid}")
            print(f"    - Cover: {cov_name}")
            print(f"    - Synopsis: {synopsis[:60]}...")

            if dry_run:
                print("    [dry-run] ข้ามการบันทึก")
                continue

            ok = sync_single_story_metadata(page, aid, title, cov, synopsis, update_cover=bool(cov))
            if ok:
                success_count += 1
                print(f"    ✅ อัปเดตสำเร็จ!")
            else:
                print(f"    ❌ ล้มเหลว")

            time.sleep(1.5)

        print(f"\n[*] สรุปผล: อัปเดตสำเร็จ {success_count}/{count} เรื่อง")
        browser.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ReadAWrite Mass Metadata Syncer")
    parser.add_argument("--limit", type=int, default=None, help="จำกัดจำนวนเรื่องที่จะซิงค์")
    parser.add_argument("--force-cover", action="store_true", help="บังคับอัปโหลดปกใหม่ทุกเรื่อง")
    parser.add_argument("--dry-run", action="store_true", help="ทดสอบจำลองขั้นตอนโดยไม่บันทึกจริง")
    args = parser.parse_args()

    run_mass_sync(limit=args.limit, force_cover=args.force_cover, dry_run=args.dry_run)
