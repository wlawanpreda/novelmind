"""
ANSRE Version History — เก็บประวัติเวอร์ชันของบท ก่อนเขียนทับ ดู/กู้คืนได้
=========================================================================
ทุกครั้งที่บทถูกเขียนทับ (chapter-loop / auto-fix) → snapshot ไฟล์เดิมไว้
เก็บใน  05_Active_Projects/.versions/<ชื่อไฟล์>/<timestamp>__<label>.md
เก็บสูงสุด KEEP เวอร์ชันล่าสุดต่อไฟล์ (เก่ากว่านั้นลบทิ้ง)
"""
import os
import re
import glob
import time
import shutil
from datetime import datetime

KEEP = 15


def _vdir(fp):
    """โฟลเดอร์เก็บเวอร์ชันของไฟล์ fp"""
    return os.path.join(os.path.dirname(fp), ".versions", os.path.basename(fp))


def snapshot(fp, label=""):
    """สำรองไฟล์ปัจจุบันเป็นเวอร์ชันใหม่ (ก่อนเขียนทับ) — คืนชื่อไฟล์เวอร์ชัน"""
    if not fp or not os.path.exists(fp):
        return None
    d = _vdir(fp)
    os.makedirs(d, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe = re.sub(r"[^\w฀-๿]+", "-", (label or "")).strip("-")[:30]
    name = f"{ts}__{safe}.md" if safe else f"{ts}.md"
    dst = os.path.join(d, name)
    try:
        shutil.copy2(fp, dst)
    except Exception:
        return None
    _prune(d)
    return name


def _prune(d):
    vs = sorted(glob.glob(os.path.join(d, "*.md")))
    for old in vs[:-KEEP]:
        try:
            os.remove(old)
        except Exception:
            pass


def list_versions(fp):
    """รายการเวอร์ชันของไฟล์ (ใหม่→เก่า)"""
    d = _vdir(fp)
    out = []
    for v in sorted(glob.glob(os.path.join(d, "*.md")), reverse=True):
        name = os.path.basename(v)
        m = re.match(r"(\d{8}-\d{6})(?:__(.*))?\.md", name)
        when, label = "", ""
        if m:
            try:
                when = datetime.strptime(m.group(1), "%Y%m%d-%H%M%S").strftime("%d/%m %H:%M")
            except Exception:
                when = m.group(1)
            label = (m.group(2) or "").replace("-", " ")
        try:
            with open(v, "r", encoding="utf-8") as fh:
                nchars = len(fh.read())
        except Exception:
            nchars = 0
        out.append({"name": name, "when": when, "label": label,
                    "size": os.path.getsize(v), "chars": nchars})
    return out


def read_version(fp, vname):
    v = os.path.join(_vdir(fp), os.path.basename(vname))
    if not os.path.exists(v):
        return None
    with open(v, "r", encoding="utf-8") as f:
        return f.read()


def restore(fp, vname):
    """กู้คืนเวอร์ชัน — snapshot ฉบับปัจจุบันไว้ก่อน (label=ก่อนกู้คืน) แล้วเขียนทับ"""
    content = read_version(fp, vname)
    if content is None:
        return {"ok": False, "error": "ไม่พบเวอร์ชันนี้"}
    snapshot(fp, "ก่อนกู้คืน")
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    return {"ok": True, "restored": vname, "chars": len(content)}
