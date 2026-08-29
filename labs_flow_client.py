"""
labs_flow_client.py — Google Labs FX (Flow) Playwright Automation Worker
========================================================================

ทำงานร่วมกับ Google Labs Flow (ImageFX / Flow Tool):
  URL: https://labs.google/fx/tools/flow/project/e9ca79fa-9e1d-4705-a27b-567977709bf4

ความสามารถ:
  1. เก็บ Persistent Browser Session (ล็อกอิน Google เพียงครั้งเดียว เซสชันจะถูกจำไว้ตลอด)
  2. ส่ง Prompt สร้างรูปผ่าน Playwright อัตโนมัติ
  3. ดักจับและดาวน์โหลดรูปที่เรนเดอร์เสร็จบันทึกเข้า SecondBrain
  4. ทำงานแบบ Worker ต่อเนื่อง (Queue Worker) ค่อยๆ เจนทีละรูปตามคิวพร้อม Cool-down เพื่อความปลอดภัย

การใช้งาน:
  1. ล็อกอินครั้งแรก (เปิดหน้าต่างให้ล็อกอิน Google):
     python labs_flow_client.py --login

  2. ทดสอบเจน 1 รูป:
     python labs_flow_client.py --prompt "A mystical detective in cyberpunk Bangkok, cinematic lighting, 8k" --output test_cover.jpg

  3. รันคิวอัตโนมัติ (เก็บงานที่ยังไม่มีปก/รูปฉาก ค่อยๆ เจนต่อเนื่อง):
     python labs_flow_client.py --auto
"""
from __future__ import annotations

import os
import re
import sys
import time
import json
import glob
import urllib.request
from typing import Optional, Dict, Any

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
PROFILE_DIR = os.path.join(ROOT, ".labs_flow_profile")

DEFAULT_FLOW_URL = os.environ.get(
    "LABS_FLOW_URL",
    "https://labs.google/fx/tools/flow/project/e9ca79fa-9e1d-4705-a27b-567977709bf4"
)


def ensure_playwright():
    try:
        from playwright.sync_api import sync_playwright
        return sync_playwright
    except ImportError:
        print("[!] Playwright is not installed. Run: pip install playwright && playwright install chromium")
        return None


def open_login_browser(flow_url: str = DEFAULT_FLOW_URL):
    """เปิดเบราว์เซอร์ให้ผู้ใช้ล็อกอิน Google Account บน Google Labs ครั้งแรก"""
    sync_pw = ensure_playwright()
    if not sync_pw:
        return

    os.makedirs(PROFILE_DIR, exist_ok=True)
    print(f"[*] เปิดหน้าต่างเบราว์เซอร์สำหรับล็อกอิน Google Labs...")
    print(f"[*] Profile Directory: {PROFILE_DIR}")
    print(f"[*] URL: {flow_url}")
    print(f"[*] เมื่อล็อกอินและเข้าหน้าโปรเจกต์สำเร็จแล้ว ให้ปิดหน้าต่างเบราว์เซอร์ได้เลย")

    with sync_pw() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=False,
            viewport={"width": 1280, "height": 850},
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = context.new_page()
        page.goto(flow_url)
        
        # รอให้ผู้ใช้ล็อกอินจนกว่าจะปิดหน้าต่าง
        try:
            while len(context.pages) > 0:
                time.sleep(1)
        except Exception:
            pass
        context.close()
    print("[+] บันทึกเซสชันการล็อกอินเรียบร้อยแล้ว!")


def generate_image_via_flow(
    prompt: str,
    output_path: str,
    flow_url: str = DEFAULT_FLOW_URL,
    headless: bool = True,
    timeout: int = 120
) -> bool:
    """สั่งสร้างรูป 1 รูปผ่าน Google Labs Flow และบันทึกลง output_path"""
    sync_pw = ensure_playwright()
    if not sync_pw:
        return False

    os.makedirs(PROFILE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    print(f"[flow] กำลังส่ง prompt ไปยัง Google Labs Flow...")
    print(f"[flow] Prompt: {prompt[:80]}...")

    with sync_pw() as p:
        try:
            # ใช้ Persistent Context เพื่อดึง Session เดิมที่ล็อกอินไว้
            context = p.chromium.launch_persistent_context(
                user_data_dir=PROFILE_DIR,
                headless=headless,
                viewport={"width": 1280, "height": 900},
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox"
                ]
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(flow_url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)

            # ตรวจสอบว่าต้องล็อกอินหรือไม่ (เช็กเฉพาะ URL หรือ input email ชัดเจน)
            if "accounts.google.com" in page.url or page.locator('input[type="email"]').count() > 0:
                print("[!] พบหน้า Sign-in: ต้องรัน 'python labs_flow_client.py --login' เพื่อล็อกอินครั้งแรกก่อน")
                context.close()
                return False

            # ค้นหาช่องกรอก Prompt (ContentEditable / TextArea / Input)
            input_selector = None
            selectors = [
                'div[contenteditable="true"]',
                'textarea[placeholder*="What do you want to create" i]',
                'input[placeholder*="What do you want to create" i]',
                'textarea[placeholder*="create" i]',
                'textarea',
                'input[type="text"]'
            ]
            for sel in selectors:
                loc = page.locator(sel)
                if loc.count() > 0 and loc.first.is_visible():
                    input_selector = sel
                    break

            if not input_selector:
                print(f"[!] ไม่พบช่องใส่ prompt บนหน้าเว็บ (URL: {page.url})", flush=True)
                page.screenshot(path=os.path.join(ROOT, "flow_debug.png"))
                context.close()
                return False

            # บันทึกรูปที่มีอยู่เดิมก่อนส่ง Prompt เพื่อเทียบหารูปใหม่
            initial_imgs = set()
            for img in page.locator("img").all():
                src = img.get_attribute("src") or ""
                if src:
                    initial_imgs.add(src)

            # กรอก Prompt และส่งคำสั่ง
            prompt_box = page.locator(input_selector).first
            prompt_box.click()
            prompt_box.fill(prompt)
            page.wait_for_timeout(800)

            # หาปุ่ม Submit หรือกด Enter
            btn_selectors = [
                'button:has(svg)',
                'button[aria-label*="Submit" i]',
                'button[aria-label*="Generate" i]',
                'button[aria-label*="Send" i]',
                'button[type="submit"]'
            ]
            clicked = False
            for b_sel in btn_selectors:
                btn = page.locator(b_sel).last
                if btn.count() > 0 and btn.is_visible():
                    try:
                        btn.click()
                        clicked = True
                        break
                    except Exception:
                        pass

            if not clicked:
                prompt_box.press("Enter")

            print("[flow] ส่งคำสั่งสร้างรูปแล้ว กำลังรอประมวลผล...", flush=True)

            # ดักจับภาพใหม่ที่สร้างเสร็จ
            start_time = time.time()
            img_src = None
            
            while time.time() - start_time < timeout:
                page.wait_for_timeout(3000)
                imgs = page.locator("img").all()
                for img in imgs:
                    src = img.get_attribute("src") or ""
                    box = img.bounding_box()
                    w = box["width"] if box else 0
                    if ("media.getMediaUrlRedirect" in src or "googleusercontent" in src) and w > 200:
                        if src not in initial_imgs or (time.time() - start_time > 15):
                            img_src = src
                            break
                if img_src:
                    break

            if not img_src:
                print("[!] หมดเวลารอภาพ หรือไม่พบรูปผลลัพธ์ใหม่", flush=True)
                page.screenshot(path=os.path.join(ROOT, "flow_timeout.png"))
                context.close()
                return False

            if img_src.startswith("/"):
                img_src = "https://labs.google" + img_src

            print(f"[flow] พบรูปผลลัพธ์: {img_src[:70]}... กำลังดาวน์โหลด", flush=True)
            res = page.request.get(img_src)
            if res.ok:
                with open(output_path, "wb") as f:
                    f.write(res.body())
                print(f"[flow] ✅ บันทึกรูปภาพสำเร็จ: {output_path} (ขนาด {len(res.body()):,} bytes)", flush=True)
                context.close()
                return True
            else:
                print(f"[flow] ❌ ดาวน์โหลดภาพล้มเหลว (HTTP {res.status})", flush=True)
                context.close()
                return False
        except Exception as e:
            print(f"[flow] ❌ Error ระหว่างสร้างรูป: {e}")
            return False


def run_auto_queue(delay_seconds: int = 15):
    """สแกนโปรเจกต์ที่ยังขาดภาพปก/ภาพฉาก แล้วค่อยๆ เจนทีละเรื่องพร้อมหน่วงเวลา"""
    covers_dir = os.path.join(SB, "05_Active_Projects", "Covers")
    concepts_dir = os.path.join(SB, "02_Concept_Extraction")
    os.makedirs(covers_dir, exist_ok=True)

    outlines = glob.glob(os.path.join(concepts_dir, "*_Outline.md"))
    print(f"[*] พบ {len(outlines)} Outline กำลังตรวจสอบงานที่ขาดรูปภาพ...")

    missing_tasks = []
    for out_p in outlines:
        stem = re.sub(r"_Outline\.md$", "", os.path.basename(out_p))
        cover_p = os.path.join(covers_dir, f"{stem}_Cover.jpg")
        if not os.path.exists(cover_p):
            # สร้าง Prompt จาก Outline
            try:
                with open(out_p, "r", encoding="utf-8") as f:
                    text = f.read()
                # สกัดจุดเด่นหรือ visual prompt
                m_title = stem.replace("_", " ")
                prompt = f"Book cover art for fantasy thriller novel '{m_title}', highly detailed, dramatic lighting, cinematic composition, anime digital art style, 8k masterpiece"
                missing_tasks.append({"title": stem, "prompt": prompt, "out": cover_p})
            except Exception:
                continue

    if not missing_tasks:
        print("[+] ทุกเรื่องมีภาพปกครบถ้วนแล้ว ไม่ต้องเจนเพิ่ม!")
        return

    print(f"[*] มีงานที่ต้องเจนรูปทั้งหมด {len(missing_tasks)} ชิ้น (จะค่อยๆ ทยอยทำทีละชิ้น เว้นช่วง {delay_seconds}s)")

    for idx, task in enumerate(missing_tasks, 1):
        print(f"\n[{idx}/{len(missing_tasks)}] กำลังเจนภาพปก: {task['title']}")
        ok = generate_image_via_flow(
            prompt=task["prompt"],
            output_path=task["out"],
            headless=True
        )
        if ok:
            print(f"    [+] เสร็จสิ้น รอพัก {delay_seconds} วินาที...")
            time.sleep(delay_seconds)
        else:
            print(f"    [-] ข้ามไปยังงานถัดไป...")
            time.sleep(5)


def main():
    args = sys.argv[1:]
    if "--login" in args:
        open_login_browser()
    elif "--auto" in args:
        run_auto_queue()
    elif "--prompt" in args:
        p_idx = args.index("--prompt") + 1
        prompt = args[p_idx] if p_idx < len(args) else "Epic novel cover, masterpiece"
        out_idx = args.index("--output") + 1 if "--output" in args else -1
        out_path = args[out_idx] if out_idx > 0 and out_idx < len(args) else "flow_output.jpg"
        headless = "--visible" not in args
        generate_image_via_flow(prompt, out_path, headless=headless)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
