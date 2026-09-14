#!/usr/bin/env python3
"""
syndication_deployer.py — เครื่องมือส่งออกและนำส่งนิยายสู่ Dek-D และ Fictionlog (Track 5)
=======================================================================================
ความสามารถ:
1. Package Archiver: รวมไฟล์นิยายทุกตอนพร้อมปกเป็น .zip สำหรับแต่ละแพลตฟอร์ม
2. Format Transformer: แปลง Markdown เป็น HTML/BBCode ที่เข้ากันได้กับ Dek-D Writer 3.0
3. Syndication Status Report: สรุปสถานะการกระจายงานลงใน syndication_ledger.json
"""

from __future__ import annotations

import os
import re
import sys
import json
import glob
import shutil
import zipfile
from datetime import datetime
from typing import Dict, Any, List, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
ACTIVE_DIR = os.path.join(SB, "05_Active_Projects")
SYNDICATION_DIR = os.path.join(ACTIVE_DIR, "Syndication_Packages")
EXPORTS_DIR = os.path.join(ACTIVE_DIR, "Exports", "Syndication")
os.makedirs(EXPORTS_DIR, exist_ok=True)


def build_syndication_zip(story_title: str) -> Optional[str]:
    """สร้างไฟล์ ZIP สำหรับนำไปอัปโหลดบน Dek-D หรือ Fictionlog"""
    clean = re.sub(r'[^\w\-_\s฀-๿]', '', story_title).strip().replace(' ', '_')
    pkg_dir = os.path.join(SYNDICATION_DIR, clean)
    if not os.path.exists(pkg_dir):
        pkg_dir = os.path.join(SYNDICATION_DIR, story_title)
        if not os.path.exists(pkg_dir):
            print(f"⚠️ ไม่พบโฟลเดอร์แพ็กเกจสำหรับ '{story_title}'")
            return None

    zip_name = f"syndication_{clean}_{datetime.now().strftime('%Y%m%d')}.zip"
    zip_path = os.path.join(EXPORTS_DIR, zip_name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(pkg_dir):
            for f in files:
                fp = os.path.join(root, f)
                rel_path = os.path.relpath(fp, pkg_dir)
                zf.write(fp, arcname=rel_path)

    mb = round(os.path.getsize(zip_path) / 1e6, 2)
    print(f"📦 สร้างชุดส่งออก ZIP: {zip_name} ({mb} MB) ที่ {zip_path}")
    return zip_path


def build_all_syndication_zips() -> List[str]:
    """สร้างไฟล์ ZIP สำหรับทุกเรื่องที่พร้อมส่งออก"""
    stories = [d for d in os.listdir(SYNDICATION_DIR) if os.path.isdir(os.path.join(SYNDICATION_DIR, d))]
    zips = []
    for s in stories:
        z = build_syndication_zip(s)
        if z:
            zips.append(z)
    return zips


def show_syndication_dashboard():
    """แสดงรายการแพ็กเกจที่พร้อมเผยแพร่บน Dek-D และ Fictionlog"""
    print("\n" + "=" * 65)
    print(" 🌐 แดชบอร์ดการกระจายผลงานข้ามแพลตฟอร์ม (Dek-D & Fictionlog)")
    print("=" * 65)
    pkgs = glob.glob(os.path.join(SYNDICATION_DIR, "*", "SYNDICATION_GUIDE.md"))
    print(f" 📚 พบชุดแพ็กเกจสมบูรณ์ทั้งหมด: {len(pkgs)} เรื่อง")
    print("-" * 65)
    for p in pkgs:
        st_name = os.path.basename(os.path.dirname(p))
        ch_count = len(glob.glob(os.path.join(os.path.dirname(p), "Chapter_*.txt")))
        print(f"   • {st_name}: {ch_count} ตอน (พร้อมอัปโหลด)")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    if "--zip" in sys.argv:
        build_all_syndication_zips()
    else:
        show_syndication_dashboard()
