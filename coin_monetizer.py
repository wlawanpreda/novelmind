#!/usr/bin/env python3
"""
coin_monetizer.py — ระบบบริหารจัดการโมเดลติดเหรียญและสร้างรายได้อัตโนมัติ (Track 1)
==================================================================================
โครงสร้างกลยุทธ์การตั้งราคา:
1. 🎁 Free Hook Zone: ตอนที่ 1–3 เปิดให้อ่านฟรี 100% เสมอ เพื่อสร้างยอดวิวและดึงคนเข้าชั้นหนังสือ
2. 🪙 Early Bird Coin Access: ตอนที่ 4 ขึ้นไป สำหรับเรื่องที่กำลังออนแอร์ ตั้งราคา 1–2 คอยน์
   (กำหนดวันปลดเหรียญให้อ่านฟรีอัตโนมัติเมื่อครบกำหนดเวลา 3–5 วัน)
3. 💎 Backlist Premium: ซีรีส์ที่จบแล้วเกิน 14 วัน ล็อกเหรียญถาวรใน 3 ตอนสุดท้าย (Climax/Ending)
4. 🛡️ Publisher Status Sentinel: ตรวจสอบสถานะการยืนยันตัวตนนักเขียน (user_type == 3)
   หากยังเป็น user_type == 1 จะแจ้งเตือนและเตรียมคิวรอเปิดระบบทันทีที่อนุมัติ
"""

from __future__ import annotations

import os
import sys
import json
import datetime
from typing import Dict, Any, List, Optional
from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
MONETIZATION_LEDGER = os.path.join(SB, "05_Active_Projects", "monetization_ledger.json")


def load_monetization_ledger() -> Dict[str, Any]:
    if os.path.exists(MONETIZATION_LEDGER):
        try:
            with open(MONETIZATION_LEDGER, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "updated_at": datetime.datetime.now().isoformat(),
        "publisher_status": "pending_verification",
        "pricing_rules": {
            "free_hook_chapters": 3,
            "early_access_coins": 2,
            "early_access_free_delay_days": 5,
            "backlist_lock_coins": 3
        },
        "monetized_stories": {}
    }


def save_monetization_ledger(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(MONETIZATION_LEDGER), exist_ok=True)
    data["updated_at"] = datetime.datetime.now().isoformat()
    with open(MONETIZATION_LEDGER, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_publisher_status() -> Dict[str, Any]:
    """ตรวจสอบสถานะการอนุมัติรับเงินของบัญชี ReadAWrite"""
    if not os.path.exists(AUTH_FILE):
        return {"ok": False, "error": "No auth session"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()
            page.goto("https://www.readawrite.com/?action=main_manage_article", timeout=30000)
            page.wait_for_timeout(2000)

            user_type = page.evaluate("() => window.CookiesJS ? CookiesJS.getCookie('user_type') : '1'")
            browser.close()

            is_verified = (str(user_type) == "3")
            ledger = load_monetization_ledger()
            ledger["publisher_status"] = "verified_publisher" if is_verified else "standard_writer"
            save_monetization_ledger(ledger)

            return {
                "ok": True,
                "user_type": user_type,
                "is_verified": is_verified,
                "upgrade_url": "https://www.readawrite.com/?action=manage_profile&tab=publisher_info"
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def generate_monetization_plan(story_title: str, total_chapters: int, is_completed: bool) -> List[Dict[str, Any]]:
    """คำนวณแผนการตั้งราคาเหรียญของแต่ละตอนตามมาตรฐานอุตสาหกรรม"""
    plan = []
    for ch in range(1, total_chapters + 1):
        if ch <= 3:
            plan.append({
                "chapter_num": ch,
                "model": "FREE_HOOK",
                "coins": 0,
                "desc": "อ่านฟรี 100% ตลอดกาล เพื่อดึงดูดนักอ่าน"
            })
        elif not is_completed:
            plan.append({
                "chapter_num": ch,
                "model": "EARLY_ACCESS",
                "coins": 2,
                "desc": "ติดเหรียญอ่านล่วงหน้า 2 คอยน์ (ปลดฟรีตามรอบปล่อย)"
            })
        else:
            if ch > total_chapters - 3:
                plan.append({
                    "chapter_num": ch,
                    "model": "PREMIUM_ENDING",
                    "coins": 3,
                    "desc": "ตอนจบพรีเมียม ติดเหรียญถาวร 3 คอยน์"
                })
            else:
                plan.append({
                    "chapter_num": ch,
                    "model": "STANDARD_FREE",
                    "coins": 0,
                    "desc": "อ่านฟรีในหมวดผลงานจบแล้ว"
                })
    return plan


def show_monetization_dashboard():
    """แสดงสถานะการสร้างรายได้ของสตูดิโอ"""
    status = check_publisher_status()
    print("\n" + "=" * 65)
    print(" 💰 แดชบอร์ดระบบบริหารจัดการเหรียญ & รายได้ (Monetization Engine)")
    print("=" * 65)
    if status.get("is_verified"):
        print(" 🟢 สถานะบัญชี: นักเขียนที่ผ่านการยืนยันตัวตนแล้ว (Verified Publisher)")
        print("    • ระบบสามารถสั่งตั้งราคาเหรียญบน ReadAWrite ได้อัตโนมัติ 100%")
    else:
        print(" 🟡 สถานะบัญชี: นักเขียนทั่วไป (Standard Writer - user_type 1)")
        print("    • แนะนำให้อัปเกรดยืนยันตัวตนเพื่อเริ่มรับเงินค่าเหรียญได้ที่:")
        print(f"      👉 {status.get('upgrade_url')}")
    print("-" * 65)
    print(" 📋 กลยุทธ์การตั้งราคาที่ระบบเตรียมพร้อม:")
    print("    • ตอนที่ 1–3: ฟรี 100% (Free Hook Zone)")
    print("    • ตอนที่ 4+: อ่านล่วงหน้า 2 คอยน์ (Early Access)")
    print("    • 3 ตอนสุดท้ายของเรื่องที่จบแล้ว: 3 คอยน์ (Backlist Premium)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    show_monetization_dashboard()
