"""
ANSRE netcfg — LAN-first / Tailscale-fallback endpoint resolver
================================================================
ปัญหา: URL ของ Mac mini ตั้งเป็นชื่อ Tailscale (pj-mac-mini.tail9bbbd4.ts.net)
       ซึ่ง resolve ไม่ได้บ่อย → ทุกอย่างตกไป Gemini (แพง/throttle)

แก้: ก่อนใช้งาน ลองยิง LAN IP (ในบ้าน เร็ว) ก่อน — ต่อไม่ได้ค่อยไป Tailscale (นอกบ้าน)
     แล้วเขียน URL ที่ใช้ได้กลับเข้า os.environ ให้ทุก provider อ่านต่อ

ตั้งค่า (ไม่บังคับ — มี default ให้):
  ANSRE_NET_PRIMARY     LAN host/IP ของ Mac mini   (default 192.168.1.108)
  ANSRE_NET_FALLBACK    Tailscale host             (default pj-mac-mini.tail9bbbd4.ts.net)
  ANSRE_NET_AUTORESOLVE 1=เปิด (default) · 0=ปิด

ใช้งาน: import ที่ต้นไฟล์ provider — apply() รันให้เองตอน import
        (llm_provider import ตัวนี้ → cover_generator import llm_provider ก่อน image_provider
         จึงครอบ image ด้วยโดยไม่ต้องแก้ image_provider)
"""
import os
import socket
from urllib.parse import urlparse, urlunparse

# โหลด .env เอง (เผื่อ import ก่อน provider หรือเรียกตรงจาก CLI) — setdefault ไม่ทับของที่มีอยู่
_ENV = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

PRIMARY = os.environ.get("ANSRE_NET_PRIMARY", "192.168.1.108")
FALLBACK = os.environ.get("ANSRE_NET_FALLBACK", "pj-mac-mini.tail9bbbd4.ts.net")
_AUTO = os.environ.get("ANSRE_NET_AUTORESOLVE", "1").lower() in ("1", "true", "yes", "on")
_TIMEOUT = float(os.environ.get("ANSRE_NET_TIMEOUT", "1.5") or 1.5)

# URL env ที่อาจชี้ไป Mac mini (gateway / local LLM / local image)
_VARS = ["ANSRE_GATEWAY_URL", "LOCAL_LLM_BASE_URL", "LOCAL_IMAGE_BASE_URL"]

_reach_cache = {}   # (host,port) -> bool (ต่อครั้งเดียวต่อ process)
_done = False
resolved = {}       # var -> (chosen_host หรือ None) ให้ doctor เรียกดูได้


def _reachable(host, port):
    key = (host, port)
    if key in _reach_cache:
        return _reach_cache[key]
    ok = False
    try:
        with socket.create_connection((host, port), timeout=_TIMEOUT):
            ok = True
    except Exception:
        ok = False
    _reach_cache[key] = ok
    return ok


def _swap_host(url, host):
    p = urlparse(url)
    netloc = host + (f":{p.port}" if p.port else "")
    if p.username:  # คง user:pass@ ถ้ามี
        cred = p.username + (f":{p.password}" if p.password else "") + "@"
        netloc = cred + netloc
    return urlunparse(p._replace(netloc=netloc))


def _resolve_one(url):
    """คืน (url ที่ใช้ได้, host ที่เลือก) — LAN ก่อน, Tailscale ทีหลัง"""
    try:
        p = urlparse(url)
    except Exception:
        return url, None
    h = p.hostname
    if h not in (PRIMARY, FALLBACK):
        return url, None  # ไม่ใช่ endpoint Mac mini → ไม่ยุ่ง
    port = p.port or (443 if p.scheme == "https" else 80)
    for host in (PRIMARY, FALLBACK):   # ลำดับสำคัญ: LAN ก่อน
        if _reachable(host, port):
            return _swap_host(url, host), host
    return url, None  # ทั้งคู่ต่อไม่ได้ → คงเดิม (provider จะ fallback Gemini เอง)


def apply(force=False):
    """resolve ทุก URL var แล้วเขียนกลับ os.environ (รันครั้งเดียวต่อ process)"""
    global _done
    if (_done and not force) or not _AUTO:
        return resolved
    _done = True
    for v in _VARS:
        cur = os.environ.get(v)
        if not cur:
            continue
        new, host = _resolve_one(cur)
        resolved[v] = host
        if new != cur:
            os.environ[v] = new
    return resolved


def status():
    """สรุปผล resolve ให้ doctor/health แสดง"""
    out = {}
    for v in _VARS:
        cur = os.environ.get(v)
        if cur:
            out[v] = {"url": cur, "host": resolved.get(v)}
    return out


# รันตอน import
apply()


if __name__ == "__main__":
    print(f"PRIMARY(LAN)={PRIMARY} · FALLBACK(Tailscale)={FALLBACK} · auto={_AUTO}")
    for v, info in status().items():
        via = info["host"] or "(เดิม/ต่อไม่ได้)"
        print(f"  {v}\n    → {info['url']}   [via {via}]")
