"""
ANSRE — YouTube OAuth Authorizer (รันครั้งเดียว)
=================================================
สร้าง youtube_token.json ที่มี refresh_token เพื่อให้ publisher อัปโหลดอัตโนมัติ
โดยไม่ต้องล็อกอินซ้ำ

วิธีใช้:
  1. ดาวน์โหลด client_secret.json จาก Google Cloud Console
     (APIs & Services → Credentials → OAuth client ID ชนิด "Desktop app")
     วางไว้ในโฟลเดอร์นี้
  2. รัน:  .venv/bin/python authorize_youtube.py
  3. เบราว์เซอร์จะเปิดให้ล็อกอิน + อนุญาต → ได้ youtube_token.json
  4. ตั้งใน .env:  PUBLISH_YOUTUBE=1

หมายเหตุ: ใช้ scope youtube.upload เท่านั้น (อัปโหลดได้ ไม่แตะอย่างอื่น)
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRET = os.path.join(ROOT, "client_secret.json")
TOKEN_OUT = os.path.join(ROOT, "youtube_token.json")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    if not os.path.exists(CLIENT_SECRET):
        print("❌ ไม่พบ client_secret.json ในโฟลเดอร์นี้")
        print("   1) ไปที่ https://console.cloud.google.com/ → สร้างโปรเจกต์")
        print("   2) เปิด YouTube Data API v3 (APIs & Services → Library)")
        print("   3) สร้าง OAuth client ID ชนิด 'Desktop app' → ดาวน์โหลด JSON")
        print("   4) เปลี่ยนชื่อเป็น client_secret.json วางในโฟลเดอร์นี้ แล้วรันใหม่")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("❌ ขาด lib — รัน: .venv/bin/pip install google-auth-oauthlib")
        sys.exit(1)

    print("🔑 เปิดเบราว์เซอร์ให้ล็อกอิน Google + อนุญาตสิทธิ์อัปโหลด YouTube ...")
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent")  # prompt=consent → ได้ refresh_token แน่นอน

    if not creds.refresh_token:
        print("⚠️ ไม่ได้ refresh_token — ลบ youtube_token.json (ถ้ามี) แล้วรันใหม่")
    with open(TOKEN_OUT, "w", encoding="utf-8") as f:
        f.write(creds.to_json())
    print(f"✅ บันทึก {TOKEN_OUT} แล้ว (มี refresh_token: {bool(creds.refresh_token)})")
    print("   ต่อไป: ตั้ง PUBLISH_YOUTUBE=1 ใน .env → ทดสอบ dry-run → กดเผยแพร่จริงได้เลย")


if __name__ == "__main__":
    main()
