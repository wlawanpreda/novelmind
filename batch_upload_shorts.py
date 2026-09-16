#!/usr/bin/env python3
"""
batch_upload_shorts.py — Autonomous YouTube Shorts Publisher
============================================================
อัปโหลดวิดีโอแนวตั้ง (9:16) ขึ้น YouTube Shorts โดยอัตโนมัติ
พร้อมฝัง ReadAWrite Link ที่บรรทัดแรก และบันทึกลง publish_ledger.json
"""

import os
import sys
import json
import time
from typing import List, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.abspath(__file__))
TOKEN_FILE = os.path.join(ROOT, "youtube_token.json")
SB = os.path.join(ROOT, "SecondBrain")
PROMO_DIR = os.path.join(SB, "05_Active_Projects", "Promo_Shorts")
LEDGER_FILE = os.path.join(SB, "05_Active_Projects", "publish_ledger.json")

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]


def get_youtube_client():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def load_ledger() -> Dict[str, Any]:
    if os.path.exists(LEDGER_FILE):
        try:
            with open(LEDGER_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_ledger(data: Dict[str, Any]) -> None:
    with open(LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def upload_short(meta_path: str, privacy: str = "public") -> Dict[str, Any]:
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    video_path = meta.get("video_path")
    if not video_path or not os.path.exists(video_path):
        print(f"❌ ไม่พบไฟล์วิดีโอ: {video_path}")
        return {"success": False, "error": "file_not_found"}

    video_filename = os.path.basename(video_path)
    ledger = load_ledger()
    if video_filename in ledger and ledger[video_filename].get("youtube"):
        yt_url = ledger[video_filename]["youtube"]
        print(f"⏭️ วิดีโอ '{video_filename}' เคยอัปโหลดแล้ว: {yt_url}")
        return {"success": True, "url": yt_url, "skipped": True}

    title = meta["title"].strip()
    if "#Shorts" not in title:
        title = f"{title} #Shorts"
    title = title[:99]

    description = meta["description"]
    tags = meta.get("tags", ["Shorts", "นิยายเสียง", "ReadAWrite"])

    print(f"\n🚀 [YouTube Upload] กำลังส่งขึ้นช่อง: {title}")
    yt = get_youtube_client()
    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "24"
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }

    media = MediaFileUpload(video_path, chunksize=-1, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"   ⏳ กำลังอัปโหลด... {int(status.progress() * 100)}%")

    vid = resp.get("id")
    yt_url = f"https://youtu.be/{vid}"
    print(f"✅ อัปโหลดสำเร็จ: {yt_url}")

    if video_filename not in ledger:
        ledger[video_filename] = {}
    ledger[video_filename]["youtube"] = yt_url
    ledger[video_filename]["uploaded_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    save_ledger(ledger)

    return {"success": True, "url": yt_url, "video_id": vid}


def upload_all_pending_shorts(limit: int = 5):
    meta_files = sorted([
        os.path.join(PROMO_DIR, f) for f in os.listdir(PROMO_DIR)
        if f.endswith("_metadata.json")
    ])
    print(f"🔍 พบไฟล์ Promo Shorts Metadata ทั้งหมด: {len(meta_files)} ไฟล์")

    uploaded = 0
    for mf in meta_files:
        if uploaded >= limit:
            break
        res = upload_short(mf)
        if res.get("success") and not res.get("skipped"):
            uploaded += 1
            # เว้นระยะ 3-5 วินาทีระหว่างอัปโหลด
            time.sleep(3)

    print(f"\n🎉 ดำเนินการเสร็จสิ้น! อัปโหลดใหม่: {uploaded} คลิป")


if __name__ == "__main__":
    upload_all_pending_shorts()
