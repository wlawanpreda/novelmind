#!/usr/bin/env python3
"""
author_showcase_hub.py — Author Brand Showcase & Media Hub Runner
================================================================
เซิร์ฟเวอร์และตัวเปิดหน้า Showcase Landing Page สำหรับ "เงาพันจันทร์":
1. Static Web Server: รันเซิร์ฟเวอร์ HTTP บนพอร์ต 8088 หรือพอร์ตที่ว่าง
2. Direct Browser Opener: เปิดหน้าเว็บขึ้นบนเบราว์เซอร์อัตโนมัติ
3. Standalone HTML Viewer: เปิดผ่านไฟล์ตรง file:// หากไม่ต้องการเปิดพอร์ต
"""

from __future__ import annotations

import os
import sys
import webbrowser
import http.server
import socketserver
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
HUB_DIR = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Showcase_Hub")
INDEX_FILE = os.path.join(HUB_DIR, "index.html")
DEFAULT_PORT = 8088


def open_local_file_in_browser():
    """เปิดไฟล์ index.html ในเบราว์เซอร์ตรงๆ โดยไม่ต้องรันเซิร์ฟเวอร์"""
    if os.path.exists(INDEX_FILE):
        print(f"\n🌐 กำลังเปิด Author Showcase Hub บนเบราว์เซอร์...")
        print(f"   📁 ไฟล์: {INDEX_FILE}")
        if sys.platform == "darwin":
            subprocess.run(["open", INDEX_FILE])
        else:
            webbrowser.open(f"file://{INDEX_FILE}")
        return True
    return False


def start_showcase_server(port: int = DEFAULT_PORT):
    """รัน Local HTTP Server สำหรับแสดงหน้าเว็บ Showcase Hub"""
    os.chdir(HUB_DIR)
    
    # ตรวจสอบพอร์ตว่าง
    actual_port = port
    for p in range(port, port + 10):
        try:
            handler = http.server.SimpleHTTPRequestHandler
            httpd = socketserver.TCPServer(("", p), handler)
            actual_port = p
            break
        except OSError:
            continue

    url = f"http://localhost:{actual_port}"
    print("\n" + "=" * 65)
    print(" 🌟 NovelMind Author Brand Hub & Showcase Landing Page")
    print("=" * 65)
    print(f" 🖋️ นามปากกา: เงาพันจันทร์ (Panjan Studio)")
    print(f" 🌐 URL เซิร์ฟเวอร์: {url}")
    print(f" 📁 ไดเรกทอรีเว็บ: {HUB_DIR}")
    print("-" * 65)
    print(" 👉 กด Ctrl+C เพื่อหยุดการทำงานของเซิร์ฟเวอร์")
    print("=" * 65 + "\n")

    # เปิดเบราว์เซอร์อัตโนมัติ
    if "--no-open" not in sys.argv:
        webbrowser.open(url)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 หยุดการทำงานของ Showcase Hub Server แล้วครับ")
        httpd.server_close()


if __name__ == "__main__":
    if "--open" in sys.argv or "--file" in sys.argv:
        open_local_file_in_browser()
    else:
        open_local_file_in_browser()
        print(f"💡 สามารถรันเป็น Local Server ได้ด้วยคำสั่ง: python author_showcase_hub.py --server")
