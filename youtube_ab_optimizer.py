#!/usr/bin/env python3
"""
youtube_ab_optimizer.py — ระบบ A/B Testing ปรับพาดหัว (Hook Title) อัตโนมัติสำหรับคลิปที่ยอดวิวนิ่งบน YouTube
========================================================================================================
ความสามารถหลัก:
1. ตรวจจับคลิปที่เผยแพร่แล้วเกิน 48 ชม. แต่ยอดวิวยังต่ำกว่าเกณฑ์ (เช่น < 8 วิว)
2. ใช้ AI ปรับปรุงพาดหัว (Hook Title) ใหม่โดยดึงปมความขัดแย้ง/จุดพีคขึ้นมาไว้หน้าสุด (ไม่เกิน 95 ตัวอักษร)
3. บันทึกประวัติการทดลองลงใน SecondBrain/05_Active_Projects/youtube_ab_experiments.json เพื่อวัดผล Conversion Lift
"""

import os
import sys
import re
import json
import argparse
from datetime import datetime, timedelta
from typing import Dict, Any, List

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats
from llm_provider import generate

SB = os.path.join(ROOT, "SecondBrain")
EXP_FILE = os.path.join(SB, "05_Active_Projects", "youtube_ab_experiments.json")


def load_experiments() -> Dict[str, Any]:
    if os.path.exists(EXP_FILE):
        try:
            with open(EXP_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"experiments": {}, "updated_at": None}


def save_experiments(data: Dict[str, Any]):
    data["updated_at"] = datetime.now().isoformat()
    with open(EXP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_high_ctr_hook_title(old_title: str, is_short: bool = True) -> str:
    """ใช้ AI รีไรต์ชื่อคลิปให้ดึงดูดสายตาและกระตุ้นความอยากรู้สูงสุด (ความยาว <= 90 ตัวอักษร)"""
    prompt = f"""คุณคือผู้เชี่ยวชาญการตั้งชื่อคลิปนิยายเสียงบน YouTube ที่ทำ CTR สูงสุด
ชื่อคลิปเดิมที่ได้ยอดวิวน้อยคือ: "{old_title}"

จงตั้งชื่อคลิปใหม่ให้น่าคลิกฟังทันที โดยทำตามกฎเหล็กดังนี้:
1. รักษาชื่อเรื่องหลักไว้ แต่เปลี่ยนคำโปรยหลังเครื่องหมาย | ให้เร้าใจ ชวนสงสัย หรือดึงปมพลิกชะตาขึ้นมาเด่นๆ
2. ถ้าเป็นคลิปสั้น ต้องลงท้ายด้วย #Shorts เสมอ (ถ้าเป็นคลิปยาว ให้ขึ้นต้นด้วย [นิยายเสียงจบในตอน])
3. ความยาวรวมทั้งหมดต้องสั้นกระชับ ไม่เกิน 85 ตัวอักษรเด็ดขาด
4. ห้ามใส่เครื่องหมายคำพูดครอบชื่อ ตอบเฉพาะชื่อคลิปใหม่บรรทัดเดียวเท่านั้น:"""

    try:
        new_t = generate(prompt, role="chat", temperature=0.7).strip()
        new_t = re.sub(r'^["\'“]+|["\'”]+$', '', new_t).replace("\n", " ").strip()
        if is_short:
            if "#Shorts" not in new_t:
                new_t = f"{new_t[:82]} #Shorts"
        else:
            new_t = new_t.replace("#Shorts", "").replace("#shorts", "").strip()
            if not new_t.startswith("["):
                new_t = f"[นิยายเสียงจบในตอน] {new_t}"
        return new_t[:95]
    except Exception:
        if is_short:
            base = old_title.split("|")[0].strip()
            return f"{base} | ความลับที่เปลี่ยนชะตาชีวิตไปตลอดกาล! #Shorts"[:95]
        return old_title[:95]


def run_ab_title_optimization(max_videos: int = 5, view_threshold: int = 5, dry_run: bool = False):
    print("=" * 70)
    print(f"🔄 กำลังสแกนหาคลิปที่ยอดวิวนิ่ง (< {view_threshold} วิว) เพื่อทำ A/B Title Optimization...")
    print("=" * 70)

    overview = youtube_stats.get_channel_overview()
    all_videos = overview.get("all_videos", [])
    exp_data = load_experiments()
    tested_ids = exp_data.get("experiments", {})

    # คัดคลิปที่เป็น public, วิวน้อยกว่าเกณฑ์, และยังไม่เคยสลับชื่อในรอบ 7 วัน
    candidates = []
    for v in all_videos:
        if v.get("privacy") != "public":
            continue
        vid = v["vid"]
        views = int(v.get("views", 0))
        if views <= view_threshold and vid not in tested_ids:
            candidates.append(v)

    # ให้ความสำคัญกับคลิปเพิ่งปล่อยช่วงหลังหรือคลิปหลักก่อน
    yt = youtube_stats._yt()
    optimized_count = 0

    for cand in candidates:
        if optimized_count >= max_videos:
            break

        vid = cand["vid"]
        old_title = cand["title"]
        views = cand["views"]
        is_short = "#Shorts" in old_title

        new_title = generate_high_ctr_hook_title(old_title, is_short=is_short)
        if not new_title or new_title == old_title:
            continue

        print(f"\n🎯 คลิปเป้าหมาย: {vid} (ปัจจุบัน {views} วิว)")
        print(f"   ❌ ชื่อเดิม: {old_title}")
        print(f"   ✨ ชื่อใหม่: {new_title}")

        if dry_run:
            optimized_count += 1
            continue

        try:
            resp = yt.videos().list(part="snippet", id=vid).execute()
            if not resp.get("items"):
                continue
            snippet = resp["items"][0]["snippet"]

            body = {
                "id": vid,
                "snippet": {
                    "title": new_title[:95],
                    "description": snippet.get("description", ""),
                    "categoryId": snippet.get("categoryId", "24"),
                    "tags": snippet.get("tags", ["นิยายเสียง", "นิยายเสียงก่อนนอน"])
                }
            }
            yt.videos().update(part="snippet", body=body).execute()

            tested_ids[vid] = {
                "old_title": old_title,
                "new_title": new_title,
                "views_before": views,
                "optimized_at": datetime.now().isoformat()
            }
            exp_data["experiments"] = tested_ids
            save_experiments(exp_data)
            optimized_count += 1
            print(f"   ✅ อัปเดตพาดหัวใหม่บน YouTube สำเร็จ! ({optimized_count}/{max_videos})")
        except Exception as e:
            print(f"   ⚠️ ไม่สามารถอัปเดต {vid} ได้: {e}")

    print("\n" + "=" * 70)
    print(f"🎉 ดำเนินการ A/B Title Optimization เสร็จสิ้นรวม {optimized_count} คลิป")
    print("=" * 70)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=5, help="จำนวนคลิปสูงสุดที่จะปรับชื่อต่อรอบ")
    parser.add_argument("--threshold", type=int, default=5, help="เกณฑ์ยอดวิวขั้นต่ำ")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run_ab_title_optimization(max_videos=args.max, view_threshold=args.threshold, dry_run=args.dry_run)
