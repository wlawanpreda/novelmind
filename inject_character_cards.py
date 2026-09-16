#!/usr/bin/env python3
"""
inject_character_cards.py — ReadAWrite Visual Character Codex Injector
======================================================================
ฝังการ์ดแนะนำตัวละครดีไซน์หรูหรา (Visual Character Cards) ลงในตอนที่ 1
ของนิยายเรื่องเป้าหมาย เพื่อดึงดูดนักอ่านตั้งแต่แรกพบและลดอัตรา Drop-off
"""

import os
import sys
import time
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")

FARM_CARD_HTML = """
<div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border: 2px solid #eab308; border-radius: 12px; padding: 18px 20px; margin-bottom: 25px; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; box-shadow: 0 4px 20px rgba(0,0,0,0.3);">
  <div style="text-align: center; margin-bottom: 16px;">
    <span style="background: #eab308; color: #000; font-weight: bold; font-size: 13px; padding: 4px 14px; border-radius: 20px; text-transform: uppercase; letter-spacing: 1px;">🌟 ข้อมูลตัวละครหลัก (Character Codex)</span>
    <h3 style="color: #fbbf24; margin: 10px 0 4px 0; font-size: 20px;">ทำความรู้จักตัวละครสำคัญแห่งฟาร์มศักดิ์สิทธิ์</h3>
    <p style="color: #94a3b8; font-size: 13px; margin: 0;">ภาพประกอบตัวละครอย่างเป็นทางการโดย เงาพันจันทร์</p>
  </div>
  
  <div style="display: flex; flex-direction: column; gap: 12px;">
    <div style="background: rgba(255,255,255,0.06); border-left: 4px solid #38bdf8; border-radius: 8px; padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
        <span style="font-weight: bold; color: #38bdf8; font-size: 16px;">🌱 อาคิน (Akin)</span>
        <span style="background: #0284c7; color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500;">เจ้าของฟาร์ม / ผู้ปลุกพลังผืนดิน</span>
      </div>
      <p style="margin: 6px 0 0 0; color: #cbd5e1; font-size: 13.5px; line-height: 1.55;">
        เด็กหนุ่มผู้ข้ามมิติมาพร้อมระบบฟาร์มศักดิ์สิทธิ์ มีความสามารถฟื้นฟูผืนดินที่ปนเปื้อนคำสาปและปลูกพืชผลเวทมนตร์ระดับตำนาน อบอุ่น ใจดี แต่เฉียบขาดเมื่อต้องปกป้องครอบครัวและคนในไร่
      </p>
    </div>

    <div style="background: rgba(255,255,255,0.06); border-left: 4px solid #f43f5e; border-radius: 8px; padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
        <span style="font-weight: bold; color: #f43f5e; font-size: 16px;">🔥 มาเรีย (Maria)</span>
        <span style="background: #e11d48; color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500;">สาวปีศาจเผ่าเพลิง / หัวหน้าองครักษ์ฟาร์ม</span>
      </div>
      <p style="margin: 6px 0 0 0; color: #cbd5e1; font-size: 13.5px; line-height: 1.55;">
        สาวปีศาจเขาแดงผู้ครอบครองเปลวเพลิงบริสุทธิ์ ปากร้ายแต่ใจอ่อน ซื่อสัตย์ต่ออาคินสุดหัวใจ ยอมทุ่มเททุกสิ่งเพื่อพิทักษ์ความสงบสุขของฟาร์มแห่งนี้
      </p>
    </div>

    <div style="background: rgba(255,255,255,0.06); border-left: 4px solid #a855f7; border-radius: 8px; padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
        <span style="font-weight: bold; color: #a855f7; font-size: 16px;">🌿 โซลิ (Soli)</span>
        <span style="background: #9333ea; color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500;">ภูตพฤกษาพิทักษ์ / ผู้ดูแลเรือนกระจก</span>
      </div>
      <p style="margin: 6px 0 0 0; color: #cbd5e1; font-size: 13.5px; line-height: 1.55;">
        ภูตสาวตัวน้อยผู้สามารถสื่อสารกับพืชพรรณโบราณ ช่วยอาคินค้นคว้าวิจัยสมุนไพรเวทมนตร์หายาก คอยสร้างรอยยิ้มและความสดใสให้แก่ทุกคนในไร่
      </p>
    </div>
  </div>
</div>
<hr style="border: none; border-top: 1px dashed rgba(255,255,255,0.2); margin: 25px 0;"/>
"""

CHIMERA_CARD_HTML = """
<div style="background: linear-gradient(135deg, #18181b 0%, #09090b 100%); border: 2px solid #a855f7; border-radius: 12px; padding: 18px 20px; margin-bottom: 25px; color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; box-shadow: 0 4px 20px rgba(0,0,0,0.4);">
  <div style="text-align: center; margin-bottom: 16px;">
    <span style="background: #a855f7; color: #fff; font-weight: bold; font-size: 13px; padding: 4px 14px; border-radius: 20px; text-transform: uppercase; letter-spacing: 1px;">⚡ ข้อมูลตัวละครหลัก (Character Codex)</span>
    <h3 style="color: #c084fc; margin: 10px 0 4px 0; font-size: 20px;">แนะนำตัวละครสำคัญ: ผู้สาปแช่ง Chimera</h3>
    <p style="color: #a1a1aa; font-size: 13px; margin: 0;">ภาพประกอบตัวละครอย่างเป็นทางการโดย เงาพันจันทร์</p>
  </div>
  
  <div style="display: flex; flex-direction: column; gap: 12px;">
    <div style="background: rgba(255,255,255,0.06); border-left: 4px solid #c084fc; border-radius: 8px; padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
        <span style="font-weight: bold; color: #c084fc; font-size: 16px;">🐺 คิเมร่า (Chimera / พระเอก)</span>
        <span style="background: #7e22ce; color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500;">ผู้เกิดใหม่ / ผู้กลืนกินแก่นเวทมนตร์</span>
      </div>
      <p style="margin: 6px 0 0 0; color: #e4e4e7; font-size: 13.5px; line-height: 1.55;">
        ชายหนุ่มผู้ถูกขับไล่และสาปแช่ง แต่ฟื้นตื่นขึ้นมาในร่างคิเมร่าไร้พ่าย มีพลังหลอมรวมยีนสัตว์อสูรและกลืนกินพลังเวทมนตร์ของศัตรูมาเป็นของตนเอง
      </p>
    </div>

    <div style="background: rgba(255,255,255,0.06); border-left: 4px solid #38bdf8; border-radius: 8px; padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
        <span style="font-weight: bold; color: #38bdf8; font-size: 16px;">✨ เอียร์ (Eir)</span>
        <span style="background: #0284c7; color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500;">จอมเวทแสงศักดิ์สิทธิ์ / ผู้เยียวยา</span>
      </div>
      <p style="margin: 6px 0 0 0; color: #e4e4e7; font-size: 13.5px; line-height: 1.55;">
        จอมเวทสาวผู้เปี่ยมด้วยความเมตตา มองเห็นจิตใจอันแท้จริงของคิเมร่า คอยร่ายเวทเยียวยาและเป็นแสงสว่างชี้นำทางไม่ให้เขาตกสู่ความมืดมิด
      </p>
    </div>

    <div style="background: rgba(255,255,255,0.06); border-left: 4px solid #f59e0b; border-radius: 8px; padding: 12px 14px;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
        <span style="font-weight: bold; color: #f59e0b; font-size: 16px;">📜 มาสเตอร์ฟิน (Master Phin)</span>
        <span style="background: #d97706; color: white; font-size: 11px; padding: 2px 10px; border-radius: 10px; font-weight: 500;">นักเล่นแร่แปรธาตุ / ปราชญ์เงา</span>
      </div>
      <p style="margin: 6px 0 0 0; color: #e4e4e7; font-size: 13.5px; line-height: 1.55;">
        อาจารย์ลึกลับผู้ล่วงรู้ความลับของวงจรอักขระโบราณ คอยแนะนำเคล็ดวิชาและมอบอุปกรณ์เวทมนตร์เพื่อช่วยคิเมร่าปลดล็อกขีดจำกัดพลัง
      </p>
    </div>
  </div>
</div>
<hr style="border: none; border-top: 1px dashed rgba(255,255,255,0.2); margin: 25px 0;"/>
"""

TARGETS = [
    {
        "story": "ฟาร์มสาวปีศาจรัก",
        "aid": "ac04dda030fae1380e3aa7ac52f66762",
        "guid": "63c6cfc44cb5b6dc0f478c6def1aa32b",
        "card_html": FARM_CARD_HTML
    },
    {
        "story": "ผู้สาปแช่ง Chimera: เกิดใหม่ในโลกเวทย์มนต์",
        "aid": "454f3980e21e630dc4891fa752796d58",
        "guid": "fce54aa777749fc56f32cd4d14c59ab1",
        "card_html": CHIMERA_CARD_HTML
    }
]


def inject_character_cards():
    if not os.path.exists(AUTH_FILE):
        print("❌ ไม่พบไฟล์ Auth Session")
        return

    print("🚀 เริ่มต้นกระบวนการฝัง Visual Character Codex บน ReadAWrite Studio...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=AUTH_FILE, viewport={"width": 1440, "height": 1080})
        page = context.new_page()

        for t in TARGETS:
            story = t["story"]
            aid = t["aid"]
            guid = t["guid"]
            card_html = t["card_html"]

            edit_url = f"https://www.readawrite.com/?action=manage_chapter&article_id={aid}&chapter_id={guid}"
            print(f"\n📖 [ตอนที่ 1] กำลังเปิดแก้ไข: '{story}' (GUID: {guid})...")
            page.goto(edit_url, timeout=45000)
            page.wait_for_timeout(3000)

            btn_cancel = page.locator("#btn_cancel_local_draft")
            if btn_cancel.is_visible():
                btn_cancel.click()
                page.wait_for_timeout(800)

            # ดึงเนื้อหาปัจจุบัน
            current_content = page.evaluate("""() => {
                const el = document.querySelector('.ck-editor__editable');
                if (el && el.ckeditorInstance) {
                    return el.ckeditorInstance.getData();
                } else if (el) {
                    return el.innerHTML;
                }
                return "";
            }""")

            if "Character Codex" in current_content or "ข้อมูลตัวละครหลัก" in current_content:
                print("   ℹ️ พบ Character Codex อยู่แล้ว ข้ามการฝังซ้ำ")
                continue

            # ฝัง Character Codex ไว้ที่ด้านบนสุดของเนื้อหา
            new_content = card_html + current_content
            page.evaluate("""(content) => {
                const el = document.querySelector('.ck-editor__editable');
                if (el && el.ckeditorInstance) {
                    el.ckeditorInstance.setData(content);
                } else if (el) {
                    el.innerHTML = content;
                }
            }""", new_content)
            page.wait_for_timeout(1500)

            # บันทึกตอน
            save_btn = page.locator("#btnSaveDraft")
            if save_btn.is_visible():
                save_btn.click()
                page.wait_for_timeout(1200)
                try:
                    change_log_label = page.locator("label[for=pop_change_log2]")
                    if change_log_label.is_visible(timeout=2000):
                        change_log_label.click()
                        page.wait_for_timeout(500)
                        page.click(".swal2-modal input.btnSaveDraft")
                        page.wait_for_timeout(3000)
                except Exception:
                    pass
                page.wait_for_timeout(2000)
                print(f"   ✅ ฝัง Character Codex สำเร็จเรียบร้อยสำหรับ '{story}'!")
            else:
                print(f"   ❌ ไม่พบปุ่มบันทึกสำหรับ '{story}'")

        context.storage_state(path=AUTH_FILE)
        browser.close()
        print("\n🎉 เสร็จสิ้นการฝัง Character Visual Codex ทั้งหมด!")


if __name__ == "__main__":
    inject_character_cards()
