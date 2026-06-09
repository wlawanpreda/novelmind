"""
ANSRE Backup — สำรอง SecondBrain ทั้งหมด (บท/ปก/เสียง/teaser/ledger) เป็น .zip
==============================================================================
งานทั้งหมดอยู่ใน SecondBrain (gitignored) — ไม่มีสำเนา = เสี่ยงหายถาวร
ใช้:  python backup.py [./SecondBrain]            สำรอง 1 ครั้ง (เก็บล่าสุด 10 ไฟล์)
      python backup.py --auto                     สำรองเฉพาะถ้าเกิน 24 ชม.จากครั้งก่อน
"""
import os
import sys
import glob
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")
BACKUP_DIR = os.path.join(ROOT, "backups")
_SKIP_DIRS = {"__pycache__", ".tasks"}
_KEEP = 10  # เก็บไฟล์ backup ล่าสุดกี่ไฟล์


def _ts():
    from datetime import datetime
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def list_backups():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    out = []
    for p in sorted(glob.glob(os.path.join(BACKUP_DIR, "ansre_backup_*.zip")), reverse=True):
        out.append({"name": os.path.basename(p),
                    "size_mb": round(os.path.getsize(p) / 1e6, 1),
                    "mtime": os.path.getmtime(p)})
    return out


def make_backup(sb=SB, rotate=True):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = f"ansre_backup_{_ts()}.zip"
    path = os.path.join(BACKUP_DIR, name)
    count = size = 0
    if not os.path.isdir(sb):
        return {"ok": False, "error": f"ไม่พบ {sb}"}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(sb):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for f in files:
                if f.endswith((".pyc",)):
                    continue
                fp = os.path.join(root, f)
                try:
                    z.write(fp, os.path.relpath(fp, ROOT))
                    count += 1
                    size += os.path.getsize(fp)
                except OSError:
                    pass
    if rotate:
        for old in sorted(glob.glob(os.path.join(BACKUP_DIR, "ansre_backup_*.zip")))[:-_KEEP]:
            try:
                os.remove(old)
            except OSError:
                pass
    out_mb = round(os.path.getsize(path) / 1e6, 1)
    print(f"[backup] ✅ {name} — {count} ไฟล์ · {out_mb}MB (บีบอัดจาก {round(size/1e6,1)}MB)")
    return {"ok": True, "name": name, "files": count, "size_mb": out_mb, "path": path}


def auto_backup():
    """สำรองเฉพาะถ้าครั้งล่าสุดเกิน 24 ชม. (เรียกจาก orchestrator/worker)"""
    import time
    last = list_backups()
    if last and (time.time() - last[0]["mtime"]) < 24 * 3600:
        return {"ok": True, "skipped": True}
    return make_backup()


if __name__ == "__main__":
    if "--auto" in sys.argv:
        r = auto_backup()
        print("[backup] auto:", "ข้าม (สำรองไป <24ชม.)" if r.get("skipped") else "สำรองแล้ว")
    else:
        sb = next((a for a in sys.argv[1:] if not a.startswith("--")), SB)
        make_backup(sb)
