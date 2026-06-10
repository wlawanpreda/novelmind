"""
ANSRE Podcast Episodes — เรนเดอร์หนังสือเสียงรายตอนเป็นวิดีโอ episode (16:9)
========================================================================
แปลง Audiobook_NN.mp3 + ปก → วิดีโอเต็มความยาว (ปกกลางจอ + พื้นหลังเบลอ)
สำหรับอัปขึ้น YouTube แล้วจัดเป็น "Podcast" (playlist → ตั้งเป็น podcast)

แต่ละตอน = 1 episode (EP.1 = ตอน 1, EP.2 = ตอน 2, ...)

ใช้:  python podcast.py "<ชื่อเรื่อง>" [ตอน]        # ไม่ใส่ตอน = ทำทุกตอนที่มีเสียง
      python podcast.py "<ชื่อเรื่อง>" 1
"""
import os
import re
import sys
import glob
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AP = os.path.join(SB, "05_Active_Projects")


def _base(story):
    """หา base ของไฟล์เสียงจากชื่อเรื่อง (จับคู่ยืดหยุ่น)"""
    bases = sorted(set(re.sub(r"_Audiobook_\d+\.mp3$", "", os.path.basename(p))
                   for p in glob.glob(os.path.join(AP, "Audio_Output", "*_Audiobook_*.mp3"))))
    key = re.sub(r"[\s_:：]+", "", story)
    for b in bases:
        bk = re.sub(r"[\s_:：]+", "", b)
        if bk == key or key in bk or bk in key:
            return b
    toks = [t for t in re.split(r"[_\s]+", story) if len(t) >= 3]
    for b in bases:
        if any(t in b for t in toks):
            return b
    return None


def _cover(base):
    for name in (f"{base}_Cover.png", f"{base}_Cover.jpg", f"{base}_Cover_captioned.jpg"):
        fp = os.path.join(AP, "Covers", name)
        if os.path.exists(fp):
            return fp
    return None


def make_episode(story, n, base=None, cover=None):
    base = base or _base(story)
    if not base:
        return {"ok": False, "error": f"ไม่พบไฟล์เสียงของ '{story}'"}
    audio = os.path.join(AP, "Audio_Output", f"{base}_Audiobook_{int(n):02d}.mp3")
    if not os.path.exists(audio):
        return {"ok": False, "error": f"ไม่พบเสียงตอน {n}"}
    cover = cover or _cover(base)
    if not cover:
        return {"ok": False, "error": "ไม่พบปก"}

    out_dir = os.path.join(AP, "Podcast_Episodes")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{base}_EP{int(n):02d}.mp4")

    # ปกกลางจอ 1280x720 + พื้นหลังเบลอจากปกเดียวกัน (ดูเป็นมืออาชีพ)
    fc = ("[0:v]scale=1280:720:force_original_aspect_ratio=increase,"
          "crop=1280:720,boxblur=24:4[bg];"
          "[0:v]scale=-2:660[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", cover, "-i", audio,
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast",
           "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        return {"ok": False, "error": f"ffmpeg ล้มเหลว: {r.stderr[-200:]}"}

    mb = round(os.path.getsize(out) / 1e6, 1)
    print(f"[podcast] ✅ EP.{int(n)} → {out} ({mb}MB)")
    return {"ok": True, "file": out, "ep": int(n), "size_mb": mb}


def make_all(story):
    base = _base(story)
    if not base:
        return {"ok": False, "error": f"ไม่พบเสียงของ '{story}'"}
    cover = _cover(base)
    eps = sorted(glob.glob(os.path.join(AP, "Audio_Output", f"{base}_Audiobook_*.mp3")))
    nums = sorted(int(re.search(r"_Audiobook_(\d+)\.mp3$", p).group(1)) for p in eps)
    done = []
    for n in nums:
        r = make_episode(story, n, base=base, cover=cover)
        if r.get("ok"):
            done.append(r)
    return {"ok": bool(done), "episodes": done, "count": len(done), "base": base}


def publish_episodes(story, dry=False):
    """เรนเดอร์ + อัปทุก episode ขึ้น YouTube (long-form) — คืนลิงก์ต่อตอน"""
    import publisher
    rend = make_all(story)
    if not rend.get("ok"):
        return rend
    base = rend["base"]
    # คำโปรยเรื่อง (ใช้ teaser ตัวใดตัวหนึ่งเป็นแหล่ง metadata)
    teaser = next(iter(glob.glob(os.path.join(AP, "Teaser*", f"{base}*.mp4"))), None)
    syn = publisher.build_metadata(SB, teaser)["description"] if teaser else ""
    story_title = base.replace("_", " ")
    ledger = publisher.load_ledger(SB)
    out = []
    for ep in rend["episodes"]:
        n = ep["ep"]
        key = f"{base}_EP{n:02d}.mp4"
        entry = ledger.get(key, {})
        if entry.get("youtube", "").startswith("http"):
            out.append({"ep": n, "url": entry["youtube"], "skipped": True})
            continue
        meta = {"title": f"{story_title} — EP.{n}",
                "description": f"📖 ตอนที่ {n}\n\n{syn}",
                "tags": ["นิยายเสียง", "audiobook", "พอดแคสต์", "เล่าเรื่อง", "นิยาย"]}
        url = publisher.publish_youtube(ep["file"], meta, dry, as_shorts=False)
        if not dry and url.startswith("http"):
            entry["youtube"] = url
            ledger[key] = entry
            publisher.save_ledger(SB, ledger)
        out.append({"ep": n, "url": url})
    return {"ok": True, "base": base, "story": story_title, "episodes": out, "count": len(out)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python podcast.py "<ชื่อเรื่อง>" [ตอน|--publish|--publish-dry]')
        sys.exit(1)
    if "--publish" in sys.argv or "--publish-dry" in sys.argv:
        import json as _j
        res = publish_episodes(sys.argv[1], dry=("--publish-dry" in sys.argv))
        print(_j.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0)
    story = sys.argv[1]
    if len(sys.argv) > 2:
        res = make_episode(story, sys.argv[2])
    else:
        res = make_all(story)
    print("RESULT:", "OK" if res.get("ok") else "FAILED — " + res.get("error", ""))
