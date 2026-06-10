"""
ANSRE Publisher (Phase 4) — เผยแพร่ teaser/นิยายออกแพลตฟอร์มจริงอัตโนมัติ
=========================================================================

อ่าน teaser .mp4 ที่ผลิตเสร็จใน Teaser_Output แล้วอัปโหลดไปยังแพลตฟอร์มที่เปิดใช้:
  - YouTube Shorts  (YouTube Data API v3 — ใช้ token.json ที่ authorize ไว้ล่วงหน้า)
  - TikTok          (Content Posting API — ใช้ access token)
  - นิยาย Dek-D/Fictionlog (ไม่มี public API → เข้าคิว manual + แพ็กไฟล์พร้อมโพสต์)

ออกแบบให้ "ปลอดภัยเมื่อยังไม่มี credential": แพลตฟอร์มไหนไม่ได้เปิด/ไม่มี creds จะข้าม
พร้อม log ไม่ทำให้ทั้งระบบล้ม. ทุกการเผยแพร่บันทึกลง ledger กันโพสต์ซ้ำ (idempotent)

เปิดใช้ผ่าน .env:
  PUBLISH_YOUTUBE=1
  YOUTUBE_TOKEN_FILE=youtube_token.json      # OAuth credential (มี refresh_token)
  YOUTUBE_PRIVACY=unlisted                   # private|unlisted|public

  PUBLISH_TIKTOK=1
  TIKTOK_ACCESS_TOKEN=...

  PUBLISH_NOVEL=1                            # เข้าคิว manual (กึ่งอัตโนมัติ)

CLI:
  python publisher.py --once [SecondBrain]   # อัปโหลดทุกชิ้นที่ยังไม่เผยแพร่
  python publisher.py --dry-run              # ดูว่าจะทำอะไร โดยไม่อัปจริง
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.abspath(__file__))

# ---- load .env ----
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))


def _enabled(name: str) -> bool:
    return os.environ.get(name, "0").lower() in ("1", "true", "yes", "on")


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Ledger (กันโพสต์ซ้ำ)
# ---------------------------------------------------------------------------
def ledger_path(sb: str) -> str:
    return os.path.join(sb, "05_Active_Projects", "publish_ledger.json")


def load_ledger(sb: str) -> dict:
    p = ledger_path(sb)
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_ledger(sb: str, ledger: dict):
    p = ledger_path(sb)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(ledger, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Metadata: ดึง title/desc/hashtags จาก outline + ชื่อไฟล์
# ---------------------------------------------------------------------------
# คำที่ห้ามหลุดสู่ผู้ชม (เครดิตต้นฉบับ/เมตา) — บรรทัดที่ขึ้นต้นด้วยพวกนี้จะถูกข้าม
_SKIP_PREFIX = ("inspired by", "original", "source", "based on", "ต้นฉบับ", "แรงบันดาลใจ")


def _clean_line(s: str) -> str:
    """ตัด markdown + ป้ายกำกับนำหน้า (เช่น 'คำโปรย:') ให้เหลือเนื้อสะอาด"""
    s = re.sub(r"[*_`>#]", "", s).strip()                  # markdown
    s = re.sub(r"^\s*[-•]\s*", "", s)                       # bullet
    s = re.sub(r"^\s*\(?[^:：]{1,18}[:：]\s*", "", s)        # ป้ายกำกับสั้นนำหน้า "label:"
    return s.strip()


def _extract_synopsis(fp: str) -> str:
    """ดึงคำโปรยสะอาดจากไฟล์ — ชอบบรรทัด 'คำโปรย/logline' ก่อน, ข้ามเครดิต/heading/แฮชแท็ก"""
    try:
        with open(fp, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception:
        return ""
    for i, line in enumerate(lines):                       # 1) บรรทัดคำโปรย
        if "คำโปรย" in line or "logline" in line.lower():
            # ตัดป้ายกำกับ "คำโปรย...(Logline):" ทิ้ง — เอาเฉพาะเนื้อหลัง ":"
            after = re.split(r"[:：]", line, 1)
            inline = _clean_line(after[1]) if len(after) > 1 else ""
            if len(inline) >= 15:                          # คำโปรยอยู่ inline หลัง ":"
                return inline[:400]
            # เป็นแค่หัวข้อ — เนื้อคำโปรยอยู่บรรทัดถัดไป
            for nxt in lines[i + 1:i + 4]:
                s = nxt.strip()
                if not s or s.startswith(("#", "---")):
                    continue
                if any(s.lower().startswith(p) for p in _SKIP_PREFIX):
                    continue
                cc = _clean_line(s)
                if len(cc) >= 15:
                    return cc[:400]
            break
    buf = ""                                               # 2) เนื้อแรกๆ ที่สะอาด
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "---")) or s.startswith("#"):
            continue
        if any(s.lower().startswith(p) for p in _SKIP_PREFIX):
            continue
        c = _clean_line(s)
        if c and not c.startswith("#"):
            buf += c + " "
        if len(buf) > 280:
            break
    return buf.strip()[:400]


def build_metadata(sb: str, teaser_path: str) -> dict:
    base = os.path.basename(teaser_path)
    stem = re.sub(r"_Teaser.*$", "", base)
    # ชื่อเรื่อง = ส่วนหน้า _Teaser
    title = stem.replace("_", " ").strip() or "ANSRE Story"

    # ใช้ Caption/SEO ที่สร้างไว้ก่อน (สะอาด+ดึงดูดกว่า) ไม่งั้นดึงคำโปรยจาก Outline
    synopsis = ""
    cap_fp = os.path.join(sb, "05_Active_Projects", "Captions", f"{stem}_Caption.md")
    if os.path.exists(cap_fp):
        synopsis = _extract_synopsis(cap_fp)
    if not synopsis:
        outline = os.path.join(sb, "02_Concept_Extraction", f"{stem}_Outline.md")
        if os.path.exists(outline):
            synopsis = _extract_synopsis(outline)

    hashtags = ["นิยาย", "นิยายเสียง", "audiobook", "เล่าเรื่อง", "shorts"]
    description = (synopsis.strip() or f"ติดตามนิยายเรื่อง {title}") + "\n\n" + " ".join("#" + h for h in hashtags)
    return {"title": title[:95], "description": description[:4900], "tags": hashtags}


# ---------------------------------------------------------------------------
# Adapter: YouTube Shorts
# ---------------------------------------------------------------------------
def publish_youtube(teaser_path: str, meta: dict, dry: bool) -> str:
    if not _enabled("PUBLISH_YOUTUBE"):
        return "disabled"
    token_file = os.environ.get("YOUTUBE_TOKEN_FILE", os.path.join(ROOT, "youtube_token.json"))
    if not os.path.exists(token_file):
        log(f"  [youtube] ข้าม — ไม่พบ token file: {token_file} (ดู README การ authorize)")
        return "no_creds"
    if dry:
        log(f"  [youtube] dry-run: would upload '{meta['title']}' (#Shorts)")
        return "dry"
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        creds = Credentials.from_authorized_user_file(
            token_file, ["https://www.googleapis.com/auth/youtube.upload"])
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)

        # บังคับให้เป็น Shorts: ใส่ #Shorts ใน title/description (วิดีโอ 9:16 < 60s)
        title = (meta["title"] + " #Shorts")[:99]
        body = {
            "snippet": {"title": title, "description": meta["description"], "tags": meta["tags"],
                        "categoryId": "24"},
            "status": {"privacyStatus": os.environ.get("YOUTUBE_PRIVACY", "unlisted"),
                       "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(teaser_path, chunksize=-1, resumable=True, mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        vid = resp.get("id")
        log(f"  [youtube] ✅ uploaded: https://youtu.be/{vid}")
        return f"https://youtu.be/{vid}"
    except Exception as e:  # noqa: BLE001
        log(f"  [youtube] ❌ error: {e}")
        return f"error: {e}"


# ---------------------------------------------------------------------------
# Adapter: TikTok (Content Posting API — direct post)
# ---------------------------------------------------------------------------
def publish_tiktok(teaser_path: str, meta: dict, dry: bool) -> str:
    if not _enabled("PUBLISH_TIKTOK"):
        return "disabled"
    token = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if not token:
        log("  [tiktok] ข้าม — ไม่มี TIKTOK_ACCESS_TOKEN")
        return "no_creds"
    if dry:
        log(f"  [tiktok] dry-run: would upload '{meta['title']}'")
        return "dry"
    try:
        import requests
        size = os.path.getsize(teaser_path)
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        init = requests.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers=headers,
            json={
                "post_info": {"title": meta["title"][:150], "privacy_level": "SELF_ONLY",
                              "disable_comment": False},
                "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                                "chunk_size": size, "total_chunk_count": 1},
            }, timeout=60)
        if init.status_code != 200:
            log(f"  [tiktok] ❌ init failed: {init.status_code} {init.text[:200]}")
            return f"error: init {init.status_code}"
        data = init.json()["data"]
        upload_url = data["upload_url"]
        with open(teaser_path, "rb") as vf:
            put = requests.put(
                upload_url, data=vf.read(),
                headers={"Content-Range": f"bytes 0-{size-1}/{size}",
                         "Content-Type": "video/mp4"}, timeout=300)
        if put.status_code not in (200, 201, 206):
            log(f"  [tiktok] ❌ upload failed: {put.status_code}")
            return f"error: upload {put.status_code}"
        log(f"  [tiktok] ✅ submitted (publish_id={data.get('publish_id')})")
        return f"publish_id:{data.get('publish_id')}"
    except Exception as e:  # noqa: BLE001
        log(f"  [tiktok] ❌ error: {e}")
        return f"error: {e}"


# ---------------------------------------------------------------------------
# Adapter: นิยาย Dek-D/Fictionlog (ไม่มี API → เข้าคิว manual + แพ็กไฟล์)
# ---------------------------------------------------------------------------
def publish_novel(sb: str, teaser_path: str, meta: dict, dry: bool) -> str:
    if not _enabled("PUBLISH_NOVEL"):
        return "disabled"
    queue_dir = os.path.join(sb, "05_Active_Projects", "Publish_Queue")
    title_key = re.sub(r"_Teaser.*$", "", os.path.basename(teaser_path))
    # หาบทนิยายที่เกี่ยวข้องเพื่อแพ็กให้พร้อมก๊อปวาง
    chapters = sorted(glob.glob(os.path.join(sb, "05_Active_Projects", "Chapters", f"{title_key}*")))
    if dry:
        log(f"  [novel] dry-run: would queue '{meta['title']}' ({len(chapters)} chapter files)")
        return "dry"
    os.makedirs(queue_dir, exist_ok=True)
    pkg = os.path.join(queue_dir, f"{title_key}_PUBLISH.md")
    try:
        body = [f"# 📤 พร้อมเผยแพร่: {meta['title']}", "",
                "> ⚠️ Dek-D/Fictionlog ไม่มี public API — ก๊อปเนื้อหาด้านล่างไปโพสต์เอง",
                "", "## คำโปรย", meta["description"], "", "## บทนิยาย", ""]
        for ch in chapters:
            try:
                with open(ch, "r", encoding="utf-8") as f:
                    body.append(f"\n### {os.path.basename(ch)}\n")
                    body.append(f.read())
            except Exception:
                continue
        with open(pkg, "w", encoding="utf-8") as f:
            f.write("\n".join(body))
        log(f"  [novel] ✅ queued for manual post: {pkg}")
        return f"queued:{pkg}"
    except Exception as e:  # noqa: BLE001
        log(f"  [novel] ❌ error: {e}")
        return f"error: {e}"


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def run(sb: str, dry: bool = False):
    # teaser อาจอยู่ทั้ง Teasers (ใหม่) และ Teaser_Output (เดิม)
    teasers = sorted(set(
        glob.glob(os.path.join(sb, "05_Active_Projects", "Teasers", "*.mp4")) +
        glob.glob(os.path.join(sb, "05_Active_Projects", "Teaser_Output", "*.mp4"))))
    if not teasers:
        log(f"[publisher] ไม่พบ teaser ใน Teasers/ หรือ Teaser_Output/")
        return
    log(f"[publisher] พบ {len(teasers)} teaser | enabled: "
        f"YT={_enabled('PUBLISH_YOUTUBE')} TT={_enabled('PUBLISH_TIKTOK')} Novel={_enabled('PUBLISH_NOVEL')}")

    ledger = load_ledger(sb)
    for tpath in teasers:
        key = os.path.basename(tpath)
        entry = ledger.get(key, {})
        meta = build_metadata(sb, tpath)
        log(f"--- {meta['title']} ---")

        targets = [
            ("youtube", lambda: publish_youtube(tpath, meta, dry)),
            ("tiktok", lambda: publish_tiktok(tpath, meta, dry)),
            ("novel", lambda: publish_novel(sb, tpath, meta, dry)),
        ]
        for name, fn in targets:
            prev = entry.get(name, "")
            # ข้ามเฉพาะที่สำเร็จจริงแล้ว (ไม่ลองซ้ำ); ส่วนที่ error/no_creds ลองใหม่รอบหน้าได้
            if prev and not prev.startswith(("error", "no_creds", "disabled", "dry")):
                log(f"  [{name}] ข้าม — เผยแพร่แล้ว ({prev[:48]})")
                continue
            result = fn()
            entry[name] = result
        if not dry:
            ledger[key] = entry
            save_ledger(sb, ledger)
    log("[publisher] เสร็จสิ้น")


def main():
    args = sys.argv[1:]
    dry = "--dry-run" in args
    sb = "./SecondBrain"
    for a in args:
        if not a.startswith("--"):
            sb = a
    run(sb, dry=dry)


if __name__ == "__main__":
    main()
