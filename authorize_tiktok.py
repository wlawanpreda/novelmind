"""
ANSRE — TikTok OAuth Authorizer (รันครั้งเดียว)
================================================
สร้าง tiktok_token.json (access_token + refresh_token + วันหมดอายุ) ให้ publisher.publish_tiktok()
อัปโหลดอัตโนมัติผ่าน Content Posting API โดยไม่ต้องล็อกอินซ้ำ

เตรียมก่อนรัน (ทำครั้งเดียว — ต้องมีบัญชี TikTok ก่อน):
  1. ไป https://developers.tiktok.com/ → Manage apps → สร้าง App
  2. เพิ่ม product "Login Kit" + "Content Posting API"
  3. ขอ scope: user.info.basic, video.upload, video.publish
  4. ตั้ง Redirect URI ของแอปให้ตรงกับด้านล่าง (ดีฟอลต์: http://localhost:9876/callback)
  5. คัดลอก Client key + Client secret มาใส่ .env:
        TIKTOK_CLIENT_KEY=...
        TIKTOK_CLIENT_SECRET=...
        # (ออปชัน) TIKTOK_REDIRECT_URI=http://localhost:9876/callback
  6. รัน:  .venv/bin/python authorize_tiktok.py

หลังได้ token:
  - ตั้ง PUBLISH_TIKTOK=1 ใน .env
  - TIKTOK_PRIVACY=SELF_ONLY ก่อน (บังคับจนกว่า App จะผ่าน Audit) → ผ่านแล้วค่อยเปลี่ยนเป็น PUBLIC_TO_EVERYONE

หมายเหตุ: access_token อายุ ~24 ชม. — publisher ควรรีเฟรชด้วย refresh_token (อายุ ~365 วัน) ก่อนใช้
"""
import os
import sys
import json
import time
import base64
import hashlib
import secrets
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_OUT = os.path.join(ROOT, "tiktok_token.json")

AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPES = "user.info.basic,video.upload,video.publish"

# โหลด .env (ค่าจำเป็น)
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    for _l in open(_ENV, encoding="utf-8"):
        _l = _l.strip()
        if _l and not _l.startswith("#") and "=" in _l:
            _k, _v = _l.split("=", 1)
            os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

CLIENT_KEY = os.environ.get("TIKTOK_CLIENT_KEY", "")
CLIENT_SECRET = os.environ.get("TIKTOK_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("TIKTOK_REDIRECT_URI", "http://localhost:9876/callback")


class _Catcher(BaseHTTPRequestHandler):
    code = None
    state = None

    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        if q.path != urllib.parse.urlparse(REDIRECT_URI).path:
            self.send_response(404); self.end_headers(); return
        params = urllib.parse.parse_qs(q.query)
        _Catcher.code = (params.get("code") or [None])[0]
        _Catcher.state = (params.get("state") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = bool(_Catcher.code)
        msg = ("✅ อนุญาตสำเร็จ — กลับไปที่เทอร์มินัลได้เลย" if ok
               else "❌ ไม่ได้รับ code — ลองใหม่")
        self.wfile.write(f"<html><body style='font-family:sans-serif;padding:40px'><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *a):
        pass


def _exchange(code):
    data = urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    if not CLIENT_KEY or not CLIENT_SECRET:
        print("❌ ไม่พบ TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET ใน .env")
        print("   ดูขั้นตอนเตรียม App ที่หัวไฟล์นี้ (developers.tiktok.com)")
        sys.exit(1)

    state = secrets.token_urlsafe(16)
    # PKCE (TikTok รองรับ) — เพิ่มความปลอดภัย
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")

    auth = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_key": CLIENT_KEY,
        "scope": SCOPES,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })

    parsed = urllib.parse.urlparse(REDIRECT_URI)
    host, port = parsed.hostname or "localhost", parsed.port or 80
    server = HTTPServer((host, port), _Catcher)

    print("🔑 เปิดเบราว์เซอร์ให้ล็อกอิน TikTok + อนุญาตสิทธิ์อัปโหลด ...")
    print(f"   ถ้าไม่เด้งเอง เปิดลิงก์นี้:\n   {auth}\n")
    try:
        import webbrowser
        webbrowser.open(auth)
    except Exception:
        pass

    server.timeout = 300
    server.handle_request()  # รอ callback 1 ครั้ง
    code = _Catcher.code
    if not code:
        print("❌ ไม่ได้รับ authorization code (timeout/ปฏิเสธ)"); sys.exit(1)
    if _Catcher.state != state:
        print("⚠️ state ไม่ตรง — อาจถูกแทรกแซง ยกเลิกเพื่อความปลอดภัย"); sys.exit(1)

    print("🔄 แลก code เป็น access_token ...")
    tok = _exchange(code)
    if "access_token" not in tok:
        print(f"❌ แลก token ไม่สำเร็จ: {json.dumps(tok, ensure_ascii=False)[:300]}"); sys.exit(1)

    tok["_obtained_at"] = int(time.time())
    with open(TOKEN_OUT, "w", encoding="utf-8") as f:
        json.dump(tok, f, ensure_ascii=False, indent=2)
    print(f"✅ บันทึก {TOKEN_OUT} แล้ว")
    print(f"   access_token อายุ ~{tok.get('expires_in','?')}s · refresh อายุ ~{tok.get('refresh_expires_in','?')}s")
    print("   ต่อไป: ใส่ TIKTOK_ACCESS_TOKEN จากไฟล์นี้ลง .env หรือให้ publisher อ่านไฟล์โดยตรง")
    print("   แล้วตั้ง PUBLISH_TIKTOK=1 + TIKTOK_PRIVACY=SELF_ONLY (จนกว่าจะผ่าน Audit)")


if __name__ == "__main__":
    main()
