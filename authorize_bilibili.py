#!/usr/bin/env python3
"""
authorize_bilibili.py — ล็อกอิน Bilibili อัตโนมัติเพื่อดึง Cookie (SESSDATA, bili_jct, DedeUserID) ลง .env
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
_VENV_PY = os.path.join(ROOT, ".venv", "bin", "python")
if os.path.exists(_VENV_PY) and sys.executable != _VENV_PY:
    try:
        import playwright
    except ImportError:
        os.execv(_VENV_PY, [_VENV_PY] + sys.argv)

from playwright.sync_api import sync_playwright

def login_and_save():
    print("\n=======================================================")
    print(" 📺 Bilibili Automatic Authorizer")
    print("=======================================================")
    print("[*] กำลังเปิดเบราว์เซอร์เพื่อเข้าสู่หน้าล็อกอิน Bilibili...")
    print("[*] กรุณาสแกน QR Code ด้วยแอป Bilibili หรือล็อกอินในหน้าต่างที่เปิดขึ้น")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://passport.bilibili.com/login", timeout=60000)
        
        # รอจนกว่าจะล็อกอินสำเร็จ (redirect ไป bilibili.com หรือพบ cookie SESSDATA)
        logged_in = False
        start = time.time()
        while time.time() - start < 180: # รอสูงสุด 3 นาที
            cookies = context.cookies()
            c_dict = {c["name"]: c["value"] for c in cookies}
            if "SESSDATA" in c_dict and "bili_jct" in c_dict:
                sessdata = c_dict["SESSDATA"]
                bili_jct = c_dict["bili_jct"]
                dedeuserid = c_dict.get("DedeUserID", "")
                print("\n✅ ตรวจพบการล็อกอินสำเร็จ!")
                print(f"  • SESSDATA (len: {len(sessdata)}): {sessdata[:15]}...")
                print(f"  • bili_jct: {bili_jct}")
                print(f"  • DedeUserID: {dedeuserid}")
                
                # บันทึกลง .env
                env_path = os.path.join(ROOT, ".env")
                lines = []
                if os.path.exists(env_path):
                    with open(env_path, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                
                new_lines = []
                keys_updated = set()
                for line in lines:
                    k = line.split("=")[0].strip() if "=" in line else ""
                    if k == "BILIBILI_SESSDATA":
                        new_lines.append(f"BILIBILI_SESSDATA={sessdata}\n")
                        keys_updated.add(k)
                    elif k == "BILIBILI_BILI_JCT":
                        new_lines.append(f"BILIBILI_BILI_JCT={bili_jct}\n")
                        keys_updated.add(k)
                    elif k == "BILIBILI_DEDEUSERID":
                        new_lines.append(f"BILIBILI_DEDEUSERID={dedeuserid}\n")
                        keys_updated.add(k)
                    elif k == "PUBLISH_BILIBILI":
                        new_lines.append("PUBLISH_BILIBILI=1\n")
                        keys_updated.add(k)
                    else:
                        new_lines.append(line)
                
                if "PUBLISH_BILIBILI" not in keys_updated:
                    new_lines.append("PUBLISH_BILIBILI=1\n")
                if "BILIBILI_SESSDATA" not in keys_updated:
                    new_lines.append(f"BILIBILI_SESSDATA={sessdata}\n")
                if "BILIBILI_BILI_JCT" not in keys_updated:
                    new_lines.append(f"BILIBILI_BILI_JCT={bili_jct}\n")
                if "BILIBILI_DEDEUSERID" not in keys_updated:
                    new_lines.append(f"BILIBILI_DEDEUSERID={dedeuserid}\n")
                
                with open(env_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                
                print(f"\n💾 บันทึกการตั้งค่าลง {env_path} เรียบร้อยแล้ว!")
                logged_in = True
                break
            time.sleep(2)
            
        browser.close()
        if not logged_in:
            print("\n❌ หมดเวลารอการล็อกอิน (3 นาที) กรุณาลองใหม่อีกครั้ง")

if __name__ == "__main__":
    login_and_save()
