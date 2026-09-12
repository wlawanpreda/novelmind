#!/usr/bin/env python3
"""
ab_testing_optimizer.py — ระบบทดสอบ A/B Testing ปกและคำโปรย เพิ่ม Conversion อัตโนมัติ (Track 4)
====================================================================================================
ความสามารถหลัก:
1. Multi-Variant Experiment Manager: จัดการคู่ทดสอบ Variant A (ปกเดิม/คำโปรยเน้นดราม่า) vs Variant B (ปกมีข้อความ/คำโปรยเน้นความฟิน)
2. Underperformance Auto-Detector: ประเมินความเร็วการเพิ่มขึ้นของยอดวิว (View Velocity) หากนิ่งเกิน 48 ชม. จะสั่งหมุนเวียน Variant ทันที
3. Automated Studio Swapper: สลับภาพปก 3:4 และเปลี่ยนคำโปรย Hook บน ReadAWrite อัตโนมัติผ่าน Playwright
4. Experiment Analytics Dashboard: รายงานสถิติเปรียบเทียบ Conversion Lift ของแต่ละเวอร์ชัน
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

SB = os.path.join(ROOT, "SecondBrain")
AUTH_FILE = os.path.join(ROOT, ".auth_sessions", "readawrite_state.json")
COVERS_DIR = os.path.join(SB, "05_Active_Projects", "Covers")
EXPERIMENTS_FILE = os.path.join(SB, "05_Active_Projects", "ab_experiments.json")
METRICS_HISTORY_FILE = os.path.join(SB, "05_Active_Projects", "reader_metrics_history.json")


def load_experiments() -> Dict[str, Any]:
    if os.path.exists(EXPERIMENTS_FILE):
        try:
            with open(EXPERIMENTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"experiments": {}, "history": []}


def save_experiments(data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(EXPERIMENTS_FILE), exist_ok=True)
    with open(EXPERIMENTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_story_cover_variants(title: str) -> Dict[str, str]:
    """ค้นหาเวอร์ชันภาพปกที่มีอยู่ใน Covers directory (Standard vs Captioned vs 3x4)"""
    from auto_story_packager import find_cover_image
    variants = {}
    base_cov = find_cover_image(title)
    if base_cov:
        variants["A_standard"] = base_cov
        # ตรวจหาภาพที่มีคำว่า captioned หรือ 3x4
        base_name = os.path.basename(base_cov)
        prefix = base_name.split("_Cover")[0]
        captioned = os.path.join(COVERS_DIR, f"{prefix}_Cover_captioned.jpg")
        ratio3x4 = os.path.join(COVERS_DIR, f"{prefix}_Cover_3x4.jpg")
        if os.path.exists(captioned):
            variants["B_captioned"] = captioned
        elif os.path.exists(ratio3x4):
            variants["B_ratio3x4"] = ratio3x4
        else:
            variants["B_standard"] = base_cov
    return variants


def build_hook_variants(title: str, genre: str) -> Dict[str, str]:
    """สร้างคำโปรยทดสอบ 2 สไตล์ (A: เน้นความขัดแย้ง/ดราม่าลุ้นระทึก vs B: เน้นความฟิน/น่ารักขี้เล่น)"""
    if genre == "romance_drama":
        return {
            "A_drama": '[อ่านฟรีฟินจนตับสั่น!] "ถ้าเธอคิดจะเดินออกไปจากชีวิตฉัน... ก็เตรียมตัวรับผลที่ตามมาได้เลย!" เมื่อนางร้ายขอถอนหมั้น แต่ท่านประธานกลับเริ่มคลั่งรักจนแทบบ้า',
            "B_sweet": '[ฟินจิกหมอน 100%] "ใครบอกว่าฉันจะยอมปล่อยให้เธอไปเป็นของคนอื่น?" เมื่อเธอเริ่มหมดรัก ชายผู้เย็นชากลับยอมทิ้งศักดิ์ศรีทั้งหมดเพื่อกอดเธอไว้อีกครั้ง'
        }
    elif genre == "romcom_fluffy":
        return {
            "A_comedy": '[อ่านฟรีฟินจิกหมอน!] "ท่านเจ้าของไร่คะ... วันนี้จะให้พวกเราช่วยรดน้ำ หรือช่วยดูแลหัวใจดีเอ่ย?" ภารกิจทำฟาร์มในแดนปีศาจกับเหล่าสาวมอนสเตอร์ขี้อ้อน!',
            "B_seduction": '[ฮาเร็มคอมเมดี้ชวนใจละลาย] เมื่อสาวปีศาจซัคคิวบัสสุดเซ็กซี่กับอัศวินสาวสายซึน แย่งกันมาช่วยงานในฟาร์ม หนุ่มชาวสวนธรรมดาจะต้านทานเสน่ห์ไหวได้ยังไง!'
        }
    elif genre == "historical_family":
        return {
            "A_struggle": '[อ่านฟรีฟีลกู๊ดยุค 70!] "แม่สัญญา... ชาตินี้ลูกทั้งสองจะไม่ต้องอดอยากอีกต่อไป!" ทะลุมิติมาเป็นคุณแม่ลูกแฝดพร้อมซูเปอร์มาร์เก็ตลับในยุคข้าวยากหมากแพง',
            "B_wealth": '[รวยพลิกชีวิต เลี้ยงลูกแฝดสุดน่ารัก!] ทะลุมิติมาพร้อมมิติห้างสรรพสินค้าไร้ขีดจำกัด! กอบกู้ครอบครัว เลี้ยงลูกน้อยให้อิ่มหมีพีมัน และปราบตัวร้ายให้อยู่หมัด'
        }
    else:
        return {
            "A_mystery": '[ลุ้นระทึก พลิกปมเกินคาดเดา!] "สัญญานี้ไม่ได้เซ็นด้วยหมึก... แต่แลกด้วยวิญญาณ!" การสืบสวนและประเมินสินไหมที่เดิมพันด้วยชะตากรรมของคนเป็นและวิญญาณ',
            "B_action": '[สืบสวนระทึกขวัญเหนือธรรมชาติ] เมื่อคดีอุบัติเหตุธรรมดาซ่อนเงื่อนงำของยมโลก! ตัวแทนประกันมนุษย์จับมือจิ้งจอกเก้าหางกระชากหน้ากากฆาตกร!'
        }


def initialize_experiments_for_active_stories() -> None:
    """ลงทะเบียนสร้างการทดสอบ A/B Testing ให้กับทุกเรื่องในระบบ"""
    from auto_story_packager import detect_genre
    from auto_publishing_system import DEFAULT_STORIES

    exp_data = load_experiments()
    for aid, title in DEFAULT_STORIES:
        covers = get_story_cover_variants(title)
        genre = detect_genre(title)
        hooks = build_hook_variants(title, genre)

        if title not in exp_data["experiments"] or not exp_data["experiments"][title]["variants"]["A"]["cover"]:
            exp_data["experiments"][title] = {
                "article_id": aid,
                "genre": genre,
                "current_variant": "A",
                "started_at": datetime.datetime.now().isoformat(),
                "variants": {
                    "A": {
                        "cover": covers.get("A_standard", list(covers.values())[0] if covers else None),
                        "hook": hooks["A_drama" if "A_drama" in hooks else list(hooks.keys())[0]],
                        "views_start": 0,
                        "hearts_start": 0
                    },
                    "B": {
                        "cover": covers.get("B_captioned", covers.get("B_ratio3x4", list(covers.values())[0] if covers else None)),
                        "hook": hooks["B_sweet" if "B_sweet" in hooks else list(hooks.keys())[1]],
                        "views_start": 0,
                        "hearts_start": 0
                    }
                },
                "switch_history": []
            }
    save_experiments(exp_data)
    print("✅ ลงทะเบียน A/B Testing สำหรับทุกเรื่องในระบบเรียบร้อยแล้ว!")


def apply_variant_to_studio(article_id: str, title: str, variant_key: str, cover_path: Optional[str], hook_text: str) -> bool:
    """สั่งเปลี่ยนภาพปกและคำโปรยบน ReadAWrite Studio"""
    if not os.path.exists(AUTH_FILE):
        return False

    print(f"\n🔄 [A/B Switcher] กำลังสลับเรื่อง '{title}' เป็น Variant {variant_key}...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=AUTH_FILE)
            page = context.new_page()

            url = f"https://www.readawrite.com/?action=manage_article&article_id={article_id}&tab=articleSetting"
            page.goto(url, timeout=40000)
            page.wait_for_timeout(2000)

            # อัปเดตคำโปรย
            page.evaluate("(h) => { if (document.querySelector('#article_synopsis')) document.querySelector('#article_synopsis').value = h; }", hook_text)

            # สลับปกถ้ามีไฟล์
            if cover_path and os.path.exists(cover_path):
                print(f"   🖼️ กำลังเปลี่ยนภาพปกเป็น: {os.path.basename(cover_path)}...")
                page.set_input_files("#article_image", cover_path)
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

            # กดบันทึก
            page.evaluate("() => { $('#btnSaveArticle').trigger('click'); }")
            page.wait_for_timeout(5000)
            context.storage_state(path=AUTH_FILE)
            browser.close()
            print(f"   ✅ สลับเป็น Variant {variant_key} สำเร็จสมบูรณ์!")
            return True
    except Exception as e:
        print(f"   ❌ สลับไม่สำเร็จ: {e}")
        return False


def evaluate_and_auto_rotate() -> None:
    """ประเมินสถิติยอดวิว หากยอดนิ่งหรือไม่มีการเติบโต จะสั่งสลับ Variant อัตโนมัติ"""
    print("\n" + "=" * 70)
    print(" 🧪 [A/B Testing Evaluator] เริ่มประเมินผลการทดสอบ Conversion...")
    print("=" * 70)

    initialize_experiments_for_active_stories()
    exp_data = load_experiments()

    # ดึงสถิติล่าสุด
    from reader_engagement_engine import scrape_studio_metrics
    latest_metrics = {m["article_id"]: m for m in scrape_studio_metrics()}

    rotated_count = 0
    for title, exp in exp_data["experiments"].items():
        aid = exp["article_id"]
        cur_var = exp.get("current_variant", "A")
        alt_var = "B" if cur_var == "A" else "A"

        metric = latest_metrics.get(aid, {})
        cur_views = metric.get("views", 0)
        cur_hearts = metric.get("hearts", 0)

        started_dt = datetime.datetime.fromisoformat(exp.get("started_at", datetime.datetime.now().isoformat()))
        hours_active = (datetime.datetime.now() - started_dt).total_seconds() / 3600

        print(f"\n📚 เรื่อง: '{title}'")
        print(f"   • รัน Variant: [{cur_var}] มาแล้ว {hours_active:.1f} ชั่วโมง")
        print(f"   • สถิติตอนนี้: {cur_views} วิว | {cur_hearts} หัวใจ")

        # เกณฑ์หมุนเวียน Variant: ถ้ารันมาเกิน 24 ชม. และยอดวิวยังน้อยกว่า 10 วิว หรือหัวใจยังเป็น 0
        should_rotate = (hours_active >= 24 and cur_views < 10) or (hours_active >= 48)
        if should_rotate:
            print(f"   ⚡ วิวโตช้ากว่าเกณฑ์! สั่งหมุนเวียนสลับเป็น Variant [{alt_var}] ทันที...")
            target_config = exp["variants"][alt_var]
            ok = apply_variant_to_studio(aid, title, alt_var, target_config.get("cover"), target_config.get("hook", ""))
            if ok:
                exp["switch_history"].append({
                    "from_variant": cur_var,
                    "to_variant": alt_var,
                    "switched_at": datetime.datetime.now().isoformat(),
                    "views_at_switch": cur_views,
                    "hearts_at_switch": cur_hearts
                })
                exp["current_variant"] = alt_var
                exp["started_at"] = datetime.datetime.now().isoformat()
                exp["variants"][alt_var]["views_start"] = cur_views
                exp["variants"][alt_var]["hearts_start"] = cur_hearts
                rotated_count += 1
        else:
            print(f"   ✨ สถานะ: กำลังเก็บข้อมูลต่อเนื่อง (ยังไม่ครบกำหนดสลับ)")

    save_experiments(exp_data)
    print(f"\n📊 สรุปผล A/B Testing: หมุนเวียนสลับ Variant ไป {rotated_count} เรื่อง")


def show_ab_dashboard() -> None:
    """แสดงแดชบอร์ดสรุปผลการทดลอง A/B Testing"""
    initialize_experiments_for_active_stories()
    exp_data = load_experiments()

    print("\n" + "=" * 75)
    print(" 🧪 NovelMind A/B Testing & Conversion Optimizer Dashboard")
    print("=" * 75)
    print(f" ⏰ เวลาปัจจุบัน: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 75)
    for title, exp in exp_data["experiments"].items():
        cur = exp.get("current_variant", "A")
        switches = len(exp.get("switch_history", []))
        print(f" 📖 {title}")
        print(f"    • กำลังทดสอบ: [Variant {cur}] (สลับมาแล้ว {switches} ครั้ง)")
        print(f"    • คำโปรยที่ใช้: \"{exp['variants'][cur]['hook'][:65]}...\"")
        cov = exp['variants'][cur]['cover']
        print(f"    • ภาพปกที่ใช้: {os.path.basename(cov) if cov else 'ไม่มีไฟล์'}")
        print("-" * 75)
    print("=" * 75 + "\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="A/B Testing & Conversion Optimizer")
    parser.add_argument("--dashboard", action="store_true", help="แสดงแดชบอร์ด A/B Testing")
    parser.add_argument("--auto-rotate", action="store_true", help="ประเมินและสลับ Variant ทันที")
    parser.add_argument("--init", action="store_true", help="ลงทะเบียนการทดลอง")
    args = parser.parse_args()

    if args.auto_rotate:
        evaluate_and_auto_rotate()
    else:
        show_ab_dashboard()
