"""
ANSRE YouTube Stats — ดึงสถิติคลิปจาก ledger มาวิเคราะห์ (ต้องมี scope youtube.readonly)
=====================================================================================
ใช้:  python youtube_stats.py "<ชื่อเรื่อง>"      # เฉพาะเรื่อง
      python youtube_stats.py                      # ทุกคลิปใน ledger
"""
import os
import re
import sys

import publisher

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")


def _yt():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    token = os.environ.get("YOUTUBE_TOKEN_FILE", os.path.join(ROOT, "youtube_token.json"))
    creds = Credentials.from_authorized_user_file(
        token, ["https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.readonly"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)


def collect(filter_base=None):
    led = publisher.load_ledger(SB)
    rows = []
    for k, v in led.items():
        if filter_base and not k.startswith(filter_base):
            continue
        url = v.get("youtube", "") if isinstance(v, dict) else ""
        m = re.search(r"youtu\.be/([\w-]+)", str(url))
        if m:
            rows.append({"key": k, "vid": m.group(1), "url": str(url)})
    return rows


def fetch_stats(rows):
    yt = _yt()
    out = []
    ids = [r["vid"] for r in rows]
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        resp = yt.videos().list(part="statistics,snippet,contentDetails",
                                id=",".join(chunk)).execute()
        for it in resp.get("items", []):
            s = it.get("statistics", {})
            out.append({
                "vid": it["id"],
                "title": it["snippet"]["title"],
                "published": it["snippet"].get("publishedAt", "")[:10],
                "privacy": it.get("status", {}).get("privacyStatus", "?"),
                "views": int(s.get("viewCount", 0) or 0),
                "likes": int(s.get("likeCount", 0) or 0),
                "comments": int(s.get("commentCount", 0) or 0),
            })
    return out


if __name__ == "__main__":
    base = None
    if len(sys.argv) > 1:
        # หา base จากชื่อเรื่อง
        import glob
        key = re.sub(r"[\s_:：]+", "", sys.argv[1])
        bases = set(re.sub(r"_(Teaser|EP|Audiobook).*", "", os.path.basename(p))
                    for p in glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters", "*_Chapter_*.md")))
        base = next((b for b in bases if re.sub(r"[\s_:：]+", "", b) in key or key in re.sub(r"[\s_:：]+", "", b)), sys.argv[1])
    rows = collect(base)
    if not rows:
        print("ไม่พบวิดีโอใน ledger"); sys.exit(1)
    print(f"ดึงสถิติ {len(rows)} วิดีโอ...")
    try:
        stats = fetch_stats(rows)
    except Exception as e:
        print(f"❌ ดึงไม่ได้: {str(e)[:200]}")
        print("→ ต้อง re-authorize เพิ่ม scope: .venv/bin/python authorize_youtube.py")
        sys.exit(1)
    stats.sort(key=lambda x: x["views"], reverse=True)
    tot_v = sum(s["views"] for s in stats)
    print(f"\n=== สถิติรวม: {tot_v} views · {sum(s['likes'] for s in stats)} likes · {sum(s['comments'] for s in stats)} comments ===\n")
    for s in stats:
        print(f"  👁{s['views']:>5} ❤{s['likes']:>3} 💬{s['comments']:>2} [{s['privacy']}] {s['title'][:45]}")
