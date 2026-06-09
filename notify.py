"""
ANSRE Notify — แจ้งเตือนผ่าน Discord webhook
=============================================
ตั้ง ANSRE_DISCORD_WEBHOOK ใน .env (ความลับ — ไม่ commit)
ใช้:  from notify import notify; notify("ผลิตเสร็จ 3 เรื่อง", "Pipeline", "good")
CLI:  python notify.py "ข้อความทดสอบ"
"""
import os
import json
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

_COLORS = {"info": 0x22D3EE, "good": 0x34D399, "warn": 0xFBBF24, "bad": 0xF87171}


def enabled():
    return bool(os.environ.get("ANSRE_DISCORD_WEBHOOK", "").strip())


def notify(msg, title=None, level="info"):
    """ส่งแจ้งเตือนเข้า Discord (เงียบถ้าไม่ได้ตั้ง webhook)"""
    url = os.environ.get("ANSRE_DISCORD_WEBHOOK", "").strip()
    if not url:
        return False
    embed = {"description": str(msg)[:1900], "color": _COLORS.get(level, _COLORS["info"])}
    if title:
        embed["title"] = str(title)[:240]
    embed["footer"] = {"text": "ANSRE Story Studio"}
    data = json.dumps({"embeds": [embed]}).encode()
    try:
        req = urllib.request.Request(url, data=data, headers={
            "Content-Type": "application/json",
            "User-Agent": "ANSRE-Bot/1.0 (+https://github.com/wlawanpreda/novelmind)"})
        urllib.request.urlopen(req, timeout=10).read()
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[notify] Discord ล้มเหลว: {e}")
        return False


if __name__ == "__main__":
    import sys
    msg = sys.argv[1] if len(sys.argv) > 1 else "🔔 ทดสอบการแจ้งเตือนจาก ANSRE — ใช้งานได้แล้ว!"
    if not enabled():
        print("[notify] ยังไม่ตั้ง ANSRE_DISCORD_WEBHOOK ใน .env")
    else:
        ok = notify(msg, "ANSRE ทดสอบแจ้งเตือน", "good")
        print("ส่งแล้ว ✅" if ok else "ส่งไม่สำเร็จ ❌")
