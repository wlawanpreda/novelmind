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
def get_redirect_uri() -> str:
    env_uri = os.environ.get("TIKTOK_REDIRECT_URI", "").strip()
    if env_uri:
        return env_uri
    try:
        req = urllib.request.Request("http://127.0.0.1:4040/api/tunnels")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            data = json.loads(r.read().decode())
            for t in data.get("tunnels", []):
                if t.get("proto") == "https":
                    url = t.get("public_url")
                    return f"{url}/callback"
    except Exception:
        pass
    return "http://localhost:9876/callback"


class _Catcher(BaseHTTPRequestHandler):
    code = None
    state = None

    def do_GET(self):
        q = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(q.query)
        _Catcher.code = (params.get("code") or [None])[0]
        _Catcher.state = (params.get("state") or [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        ok = bool(_Catcher.code)
        msg = ("✅ อนุญาตสิทธิ์ TikTok สำเร็จแล้ว! — กลับไปที่เทอร์มินัลได้เลยครับ" if ok
               else "❌ ไม่ได้รับ authorization code — กรุณาลองใหม่อีกครั้ง")
        self.wfile.write(f"<html><body style='font-family:sans-serif;padding:40px;text-align:center'><h2>{msg}</h2></body></html>".encode())

    def log_message(self, *a):
        pass


def _exchange(code, verifier=None, redirect_uri=None):
    post_data = {
        "client_key": CLIENT_KEY,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri or REDIRECT_URI,
    }
    if verifier:
        post_data["code_verifier"] = verifier

    data = urllib.parse.urlencode(post_data).encode()
    req = urllib.request.Request(TOKEN_URL, data=data,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    global REDIRECT_URI
    REDIRECT_URI = get_redirect_uri()

    if not CLIENT_KEY or not CLIENT_SECRET:
        print("❌ ไม่พบ TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET ใน .env")
        print("   ดูขั้นตอนเตรียม App ที่หัวไฟล์นี้ (developers.tiktok.com)")
        sys.exit(1)

    state = secrets.token_urlsafe(16)
    # PKCE (TikTok รองรับ)
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

    # รับ Traffic จาก ngrok หรือ localhost ที่พอร์ต 9876 เสมอ
    listen_port = 9876
    parsed = urllib.parse.urlparse(REDIRECT_URI)
    if parsed.port:
        listen_port = parsed.port
    server = HTTPServer(("0.0.0.0", listen_port), _Catcher)

    print("\n=======================================================")
    print(" 🎵 TikTok OAuth Authorization")
    print("=======================================================")
    print(f"🔗 Target Redirect URI: {REDIRECT_URI}")
    parsed_domain = parsed.netloc.split(":")[0]
    print(f"\n📋 [สำคัญ] กรุณาตรวจสอบใน TikTok Developer Portal -> Login Kit:")
    print(f"   • Redirect domain : {parsed_domain}")
    print(f"   • Redirect URI    : {REDIRECT_URI}\n")
    print("🔑 กำลังเปิดเบราว์เซอร์เพื่อขอสิทธิ์ TikTok ...")
    print(f"   ถ้าหน้าต่างไม่เปิดขึ้นมาเอง ให้คลิกลิงก์นี้:\n   {auth}\n")
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
    tok = _exchange(code, verifier=verifier, redirect_uri=REDIRECT_URI)
    if "access_token" not in tok:
        print(f"❌ แลก token ไม่สำเร็จ: {json.dumps(tok, ensure_ascii=False)[:300]}"); sys.exit(1)

    tok["_obtained_at"] = int(time.time())
    with open(TOKEN_OUT, "w", encoding="utf-8") as f:
        json.dump(tok, f, ensure_ascii=False, indent=2)
    print(f"✅ บันทึก {TOKEN_OUT} เรียบร้อยแล้ว!")
    print(f"   access_token อายุ ~{tok.get('expires_in','?')}s · refresh อายุ ~{tok.get('refresh_expires_in','?')}s")
    print("   🚀 ระบบพร้อมปล่อยคลิปสู่ TikTok อัตโนมัติในรอบ Orchestrator แล้วครับ")


if __name__ == "__main__":
    main()
