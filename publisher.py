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
  TIKTOK_PRIVACY=SELF_ONLY                    # SELF_ONLY|PUBLIC_TO_EVERYONE|FRIENDS — public ได้ต่อเมื่อ App ผ่าน audit

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

try:
    from discord_reporter import send_media_and_publish_report
except Exception:
    send_media_and_publish_report = None

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
# Metadata: ดึง title/desc/hashtags จาก audioscript/srt/outline + ชื่อไฟล์
# ---------------------------------------------------------------------------
# คำที่ห้ามหลุดสู่ผู้ชม (เครดิตต้นฉบับ/เมตา/บทสนทนา AI) — บรรทัดหรือข้อความที่มีพวกนี้จะถูกข้าม/ตัดทิ้ง
_SKIP_PREFIX = (
    "inspired by", "original", "source", "based on", "ต้นฉบับ", "แรงบันดาลใจ",
    "ในฐานะ", "audio production director", "chief literary editor", "ยอดเยี่ยม",
    "แน่นอนครับ", "โอเคครับ", "เอาล่ะ", "ท่านผู้แต่ง", "ผู้กำกับ", "แปลงบท",
    "บทนิยายเสียง", "บทพากย์", "voice actor", "narrator", "sound effect", "sfx:"
)


def _clean_line(s: str) -> str:
    """ตัด markdown + ป้ายกำกับนำหน้า (เช่น 'คำโปรย:') ให้เหลือเนื้อสะอาด"""
    s = re.sub(r"[*_`>#\[\]\(\)]", "", s).strip()                  # markdown + brackets
    s = re.sub(r"^\s*[-•]\s*", "", s)                             # bullet
    s = re.sub(r"^\s*\(?[^:：]{1,18}[:：]\s*", "", s)              # ป้ายกำกับสั้นนำหน้า "label:"
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _is_meta_talk(text: str) -> bool:
    """ตรวจสอบว่าเป็นข้อความคุย meta ของ AI หรือไม่"""
    t = text.lower()
    return any(p in t for p in _SKIP_PREFIX)


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
            if len(inline) >= 15 and not _is_meta_talk(inline):
                return inline[:400]
            # เป็นแค่หัวข้อ — เนื้อคำโปรยอยู่บรรทัดถัดไป
            for nxt in lines[i + 1:i + 4]:
                s = nxt.strip()
                if not s or s.startswith(("#", "---")):
                    continue
                if _is_meta_talk(s):
                    continue
                cc = _clean_line(s)
                if len(cc) >= 15 and not _is_meta_talk(cc):
                    return cc[:400]
            break
    buf = ""                                               # 2) เนื้อแรกๆ ที่สะอาด
    for line in lines:
        s = line.strip()
        if not s or s.startswith(("#", "---")) or s.startswith("#"):
            continue
        if _is_meta_talk(s):
            continue
        c = _clean_line(s)
        if c and not _is_meta_talk(c):
            buf += c + " "
        if len(buf) > 280:
            break
    return buf.strip()[:400]


def _extract_chapter_info(sb: str, stem: str, ep: int) -> dict:
    """ดึงชื่อตอนและ hook สั้นๆ จาก AudioScript หรือ Chapter หรือ SRT"""
    ap = os.path.join(sb, "05_Active_Projects")
    ch_title = ""
    hook = ""

    # 1. ลองหาจาก Chapter ต้นฉบับก่อน (มักจะสะอาดที่สุด)
    ch_candidates = [
        os.path.join(ap, "Chapters", f"{stem}_Chapter_{ep:02d}.md"),
        os.path.join(ap, "Chapters", f"{stem}_Chapter_{ep}.md"),
    ]
    for cp in ch_candidates:
        if os.path.exists(cp):
            try:
                with open(cp, "r", encoding="utf-8") as f:
                    content = f.read()
                # หาชื่อตอนจาก heading เช่น "# ตอนที่ 1: ..." หรือ "## ตอนที่ 1 ..."
                m_title = re.search(r"ตอนที่\s*\d+\s*[:：\s]\s*([^\n\r#\(\)]+)", content)
                if m_title:
                    raw_sub = _clean_line(m_title.group(1))
                    if raw_sub and not _is_meta_talk(raw_sub) and len(raw_sub) <= 40:
                        ch_title = raw_sub
                # หาประโยคเปิดบรรทัดแรกที่สะอาด
                for ln in content.splitlines():
                    cln = _clean_line(ln)
                    if len(cln) >= 20 and not _is_meta_talk(cln):
                        hook = cln[:55]
                        break
            except Exception:
                pass
            if ch_title or hook:
                break

    # 2. ถ้ายังไม่ได้ ให้หาจาก AudioScript
    if not ch_title or not hook:
        script_candidates = [
            os.path.join(ap, "Audio_Scripts", f"{stem}_AudioScript_{ep:02d}.md"),
            os.path.join(ap, "Audio_Scripts", f"{stem}_AudioScript_{ep}.md"),
        ]
        for sc_p in script_candidates:
            if os.path.exists(sc_p):
                try:
                    with open(sc_p, "r", encoding="utf-8") as f:
                        content = f.read()
                    if not ch_title:
                        m_title = re.search(r"ตอนที่\s*\d+\s*[:：\s]\s*([^\n\r#\(\)]+)", content)
                        if m_title:
                            raw_sub = _clean_line(m_title.group(1))
                            if raw_sub and not _is_meta_talk(raw_sub) and len(raw_sub) <= 40:
                                ch_title = raw_sub
                    if not hook:
                        lines = [ln.strip() for ln in content.splitlines() if ln.strip() and not ln.strip().startswith(("#", "*", "["))]
                        for ln in lines:
                            cleaned = _clean_line(ln)
                            if len(cleaned) >= 20 and not _is_meta_talk(cleaned):
                                hook = cleaned[:55]
                                break
                except Exception:
                    pass
                if ch_title and hook:
                    break

    # 3. ถ้ายังไม่ได้ hook ลองหาจาก SRT
    if not hook:
        srt_candidates = [
            os.path.join(ap, "Audio_Output", f"{stem}_Audiobook_{ep:02d}.srt"),
            os.path.join(ap, "Audio_Output", f"{stem}_{ep:02d}.srt"),
            os.path.join(ap, "Teaser_Output", f"{stem}_Teaser_{ep:02d}.srt"),
        ]
        for srt_p in srt_candidates:
            if os.path.exists(srt_p):
                try:
                    with open(srt_p, "r", encoding="utf-8") as f:
                        lines = [ln.strip() for ln in f if ln.strip() and not ln.strip().isdigit() and "-->" not in ln]
                    for ln in lines:
                        cln = _clean_line(ln)
                        if len(cln) >= 15 and not _is_meta_talk(cln):
                            hook = cln[:55]
                            break
                except Exception:
                    pass
                if hook:
                    break

    return {"chapter_title": ch_title, "hook": hook}


def build_metadata(sb: str, teaser_path: str) -> dict:
    base = os.path.basename(teaser_path)
    stem = re.sub(r"_Teaser.*$", "", base)
    story_name = stem.replace("_", " ").strip() or "ANSRE Story"

    # ดึงหมายเลขตอนถ้ามี
    m_ep = re.search(r"Teaser_(\d+)", base)
    ep = int(m_ep.group(1)) if m_ep else 1

    ch_info = _extract_chapter_info(sb, stem, ep)
    chapter_subtitle = ch_info.get("chapter_title", "")
    hook = ch_info.get("hook", "")

    # สร้าง Title ที่ดึงดูดและมี SEO
    if chapter_subtitle:
        raw_title = f"{story_name} ตอนที่ {ep}: {chapter_subtitle}"
    elif hook:
        raw_title = f"{story_name} ตอนที่ {ep} | {hook}"
    else:
        raw_title = f"{story_name} ตอนที่ {ep} (นิยายเสียง)"

    # ใช้ Caption/SEO ที่สร้างไว้ก่อน ไม่งั้นดึงคำโปรยจาก Outline
    synopsis = ""
    cap_fp = os.path.join(sb, "05_Active_Projects", "Captions", f"{stem}_Caption.md")
    if os.path.exists(cap_fp):
        synopsis = _extract_synopsis(cap_fp)
    if not synopsis:
        outline = os.path.join(sb, "02_Concept_Extraction", f"{stem}_Outline.md")
        if os.path.exists(outline):
            synopsis = _extract_synopsis(outline)

    hashtags = ["Shorts", "นิยายเสียง", "นิยาย", "audiobook", "เล่าเรื่อง", "เรื่องเล่า", "นิยายแปล", "สปีดรัน"]
    desc_lines = [
        f"🎧 {raw_title}",
        "",
        f"📖 เรื่องย่อ: {synopsis.strip() or f'ติดตามความสนุกของนิยายเรื่อง {story_name}'}",
        "",
        "⚡ ฝากกด Like & กด Subscribe เพื่อติดตามตอนใหม่ทุกวันครับ!",
        "",
        " ".join("#" + h for h in hashtags)
    ]
    description = "\n".join(desc_lines)

    return {
        "title": raw_title[:90],
        "description": description[:4900],
        "tags": [h.lower() for h in hashtags] + [story_name, f"ตอนที่ {ep}"],
        "episode": ep,
        "story_name": story_name,
    }


# ---------------------------------------------------------------------------
# Adapter: YouTube Shorts
# ---------------------------------------------------------------------------
def publish_youtube(teaser_path: str, meta: dict, dry: bool, as_shorts: bool = True) -> str:
    if not _enabled("PUBLISH_YOUTUBE"):
        return "disabled"
    token_file = os.environ.get("YOUTUBE_TOKEN_FILE", os.path.join(ROOT, "youtube_token.json"))
    if not os.path.exists(token_file):
        log(f"  [youtube] ข้าม — ไม่พบ token file: {token_file} (ดู README การ authorize)")
        return "no_creds"
    if dry:
        log(f"  [youtube] dry-run: would upload '{meta['title']}'" + (" (#Shorts)" if as_shorts else " (long-form)"))
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

        # Shorts: ต่อ #Shorts (9:16 <60s); podcast/long-form: ไม่ต่อ
        title = ((meta["title"] + " #Shorts") if as_shorts else meta["title"])[:99]
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
_TIKTOK_TOKEN_FILE = os.path.join(ROOT, "tiktok_token.json")
_TIKTOK_TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"


def _tiktok_token() -> str:
    """หา access_token: ใช้ TIKTOK_ACCESS_TOKEN ก่อน · ไม่งั้นอ่าน tiktok_token.json + refresh ถ้าใกล้หมดอายุ"""
    env_tok = os.environ.get("TIKTOK_ACCESS_TOKEN")
    if env_tok:
        return env_tok
    if not os.path.exists(_TIKTOK_TOKEN_FILE):
        return ""
    try:
        with open(_TIKTOK_TOKEN_FILE, encoding="utf-8") as f:
            tok = json.load(f)
    except Exception:
        return ""
    obtained = tok.get("_obtained_at", 0)
    expires_in = tok.get("expires_in", 0)
    # รีเฟรชถ้าเหลืออายุ < 5 นาที
    if obtained and expires_in and time.time() > obtained + expires_in - 300:
        ck = os.environ.get("TIKTOK_CLIENT_KEY", "")
        cs = os.environ.get("TIKTOK_CLIENT_SECRET", "")
        rt = tok.get("refresh_token")
        if ck and cs and rt:
            try:
                import requests
                r = requests.post(_TIKTOK_TOKEN_URL, data={
                    "client_key": ck, "client_secret": cs,
                    "grant_type": "refresh_token", "refresh_token": rt,
                }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
                new = r.json()
                if "access_token" in new:
                    new["_obtained_at"] = int(time.time())
                    with open(_TIKTOK_TOKEN_FILE, "w", encoding="utf-8") as f:
                        json.dump(new, f, ensure_ascii=False, indent=2)
                    tok = new
                    log("  [tiktok] รีเฟรช access_token แล้ว")
                else:
                    log(f"  [tiktok] รีเฟรช token ไม่สำเร็จ: {str(new)[:120]}")
            except Exception as e:  # noqa: BLE001
                log(f"  [tiktok] รีเฟรช token error: {e}")
    return tok.get("access_token", "")


def publish_tiktok(teaser_path: str, meta: dict, dry: bool) -> str:
    if not _enabled("PUBLISH_TIKTOK"):
        return "disabled"
    token = _tiktok_token()
    if not token:
        log("  [tiktok] ข้าม — ไม่มี token (ตั้ง TIKTOK_ACCESS_TOKEN หรือรัน authorize_tiktok.py)")
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
                # SELF_ONLY ก่อน App ผ่าน audit (TikTok บังคับ) — เปลี่ยนเป็น PUBLIC_TO_EVERYONE ผ่าน .env หลัง audit ผ่าน
                "post_info": {"title": meta["title"][:150],
                              "privacy_level": os.environ.get("TIKTOK_PRIVACY", "SELF_ONLY"),
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
# Adapter: Bilibili (B站 / Bilibili Global — Localization & Publishing)
# ---------------------------------------------------------------------------
def publish_bilibili(sb: str, teaser_path: str, meta: dict, dry: bool) -> str:
    if not _enabled("PUBLISH_BILIBILI"):
        return "disabled"
    try:
        import bilibili_publisher
        res = bilibili_publisher.publish_to_bilibili(teaser_path, meta, dry)
        if res.startswith("queued"):
            log(f"  [bilibili] ✅ เข้าคิวเผยแพร่พร้อมแปลจีน: {os.path.basename(teaser_path)}")
        elif res.startswith("error"):
            log(f"  [bilibili] ❌ error: {res}")
        return res
    except Exception as e:  # noqa: BLE001
        log(f"  [bilibili] ❌ error: {e}")
        return f"error: {e}"


# ---------------------------------------------------------------------------
# Adapter: นิยาย Dek-D/Fictionlog/Meb (แพ็กไฟล์ EPUB + Web Publish Kit)
# ---------------------------------------------------------------------------
def publish_novel(sb: str, teaser_path: str, meta: dict, dry: bool) -> str:
    if not _enabled("PUBLISH_NOVEL"):
        return "disabled"
    queue_dir = os.path.join(sb, "05_Active_Projects", "Publish_Queue")
    title_key = re.sub(r"_Teaser.*$", "", os.path.basename(teaser_path))
    # สร้าง EPUB พร้อมขายลง Meb และชุดเว็บนิยายสำหรับ Dek-D / ReadAWrite
    try:
        import epub_packager
        epub_packager.create_epub(title_key)
    except Exception:
        pass
    # หาบทนิยายที่เกี่ยวข้องเพื่อแพ็กให้พร้อมก๊อปวาง
    chapters = sorted(glob.glob(os.path.join(sb, "05_Active_Projects", "Chapters", f"{title_key}*")))
    if dry:
        log(f"  [novel] dry-run: would queue '{meta['title']}' ({len(chapters)} chapter files)")
        return "dry"
    os.makedirs(queue_dir, exist_ok=True)
    pkg = os.path.join(queue_dir, f"{title_key}_PUBLISH.md")
    try:
        body = [f"# 📤 พร้อมเผยแพร่: {meta['title']}", "",
                "> 🌐 ReadAWrite Auto-Upload: ทำงานผ่าน web_novel_uploader.py อัตโนมัติ",
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
        log(f"  [novel] ✅ queued for publish kit: {pkg}")

        # รันการอัปโหลดขึ้น ReadAWrite อัตโนมัติ (ถ้ามีเซสชัน)
        try:
            import web_novel_uploader
            if web_novel_uploader.check_auth_status().get("readawrite"):
                log(f"  [novel] 🚀 เริ่มต้นส่งนิยาย '{title_key}' ขึ้น ReadAWrite อัตโนมัติ...")
                res = web_novel_uploader.upload_story(title_key, platform="readawrite", dry_run=False)
                if res:
                    log(f"  [novel] 🎉 อัปโหลด '{title_key}' ขึ้น ReadAWrite สำเร็จ!")
                    return f"readawrite:uploaded:{pkg}"
        except Exception as err:
            log(f"  [novel] ⚠️ auto-upload to readawrite: {err}")

        return f"queued:{pkg}"
    except Exception as e:  # noqa: BLE001
        log(f"  [novel] ❌ error: {e}")
        return f"error: {e}"


# ---------------------------------------------------------------------------
def count_published_today(ledger: dict, platform: str = "youtube", target_date: str = None) -> int:
    """นับจำนวนชิ้นงานที่เผยแพร่สำเร็จในวันนี้"""
    target = target_date or datetime.now().strftime("%Y-%m-%d")
    count = 0
    for key, data in ledger.items():
        if isinstance(data, dict):
            pub_val = data.get(platform, "")
            pub_at = data.get(f"{platform}_published_at") or data.get("published_at", "")
            if pub_val and not str(pub_val).startswith(("error", "no_creds", "disabled", "dry")) and pub_at.startswith(target):
                count += 1
    return count


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

    daily_yt_limit = int(os.environ.get("ANSRE_DAILY_PUBLISH_LIMIT", "2"))
    daily_tt_limit = int(os.environ.get("ANSRE_DAILY_TIKTOK_LIMIT", "2"))

    log(f"[publisher] พบ {len(teasers)} teaser | enabled: "
        f"YT={_enabled('PUBLISH_YOUTUBE')} (โควตาวันละ {daily_yt_limit} คลิป) | "
        f"TT={_enabled('PUBLISH_TIKTOK')} | Bilibili={_enabled('PUBLISH_BILIBILI')} | Novel={_enabled('PUBLISH_NOVEL')}")

    ledger = load_ledger(sb)
    today_str = datetime.now().strftime("%Y-%m-%d")
    today_yt = count_published_today(ledger, "youtube", today_str)

    log(f"[publisher] วันนี้ ({today_str}) ปล่อย YouTube ไปแล้ว {today_yt}/{daily_yt_limit} คลิป")

    for tpath in teasers:
        key = os.path.basename(tpath)
        entry = ledger.get(key, {})
        meta = build_metadata(sb, tpath)

        # Quality Gate Check: ตรวจสอบความสมบูรณ์ของวิดีโอก่อนปล่อยจริง
        try:
            import quality_gate
            q_res = quality_gate.check_teaser_quality(tpath)
            if not q_res["passed"]:
                log(f"  [qa] ⚠️ ข้าม {key} — คุณภาพคลิปไม่ผ่านเกณฑ์ ({q_res['score']}/100): {q_res['issues']}")
                continue
        except Exception:
            pass

        targets = [
            ("youtube", lambda: publish_youtube(tpath, meta, dry)),
            ("tiktok", lambda: publish_tiktok(tpath, meta, dry)),
            ("bilibili", lambda: publish_bilibili(sb, tpath, meta, dry)),
            ("novel", lambda: publish_novel(sb, tpath, meta, dry)),
        ]
        
        has_action = False
        for name, fn in targets:
            prev = entry.get(name, "")
            # ข้ามเฉพาะที่สำเร็จจริงแล้ว (ไม่ลองซ้ำ); ส่วนที่ error/no_creds ลองใหม่รอบหน้าได้
            if prev and not prev.startswith(("error", "no_creds", "disabled", "dry")):
                continue

            # เช็กโควต้ารายวันสำหรับ YouTube
            if name == "youtube" and _enabled("PUBLISH_YOUTUBE") and daily_yt_limit > 0:
                current_yt = count_published_today(ledger, "youtube", today_str)
                if current_yt >= daily_yt_limit:
                    log(f"  [youtube] ⏸️ ครบโควต้าประจำวันนี้แล้ว ({current_yt}/{daily_yt_limit} คลิป) — ข้าม {meta['title']} ไว้ปล่อยวันถัดไป")
                    continue

            if not has_action:
                log(f"--- {meta['title']} ---")
                has_action = True

            result = fn()
            entry[name] = result

            if not dry and (result.startswith("http") or result.startswith("publish_id:")):
                now_iso = datetime.now().isoformat()
                entry[f"{name}_published_at"] = now_iso
                entry["published_at"] = now_iso
                entry["title"] = meta.get("title", "")

            if not dry and name == "youtube" and result.startswith("http") and send_media_and_publish_report:
                send_media_and_publish_report(
                    title=meta.get("title", ""),
                    chapter_num=meta.get("episode", 1),
                    teaser_file=tpath,
                    youtube_url=result
                )

        if not dry and has_action:
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
