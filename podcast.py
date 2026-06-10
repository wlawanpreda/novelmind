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


def _dur(fp):
    """ความยาว (วินาที) ของไฟล์เสียง"""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", fp], capture_output=True, text=True)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _cover(base):
    for name in (f"{base}_Cover.png", f"{base}_Cover.jpg", f"{base}_Cover_captioned.jpg"):
        fp = os.path.join(AP, "Covers", name)
        if os.path.exists(fp):
            return fp
    return None


def _render_slideshow(images, audio, out, n):
    """สไลด์โชว์: สลับรูปฉาก + Ken Burns ต่อรูป + crossfade · sync ความยาวเสียง"""
    fps = 25
    xf = 1.2                                   # crossfade วินาที
    N = len(images)
    D = _dur(audio) or (N * 8)
    L = (D + (N - 1) * xf) / N                 # ความยาวต่อรูป (ให้รวม = D หลัง crossfade)
    fr = max(int(L * fps), 40)
    zinc = round(0.18 / fr, 6)

    inp = []
    for img in images:
        inp += ["-loop", "1", "-t", f"{L:.3f}", "-i", img]
    inp += ["-i", audio]

    parts = []
    for i in range(N):
        # สลับทิศ Ken Burns: คู่ซูมเข้า / คี่แพนขวา เพื่อความหลากหลาย
        x = "iw/2-(iw/zoom/2)" if i % 2 == 0 else "iw/2-(iw/zoom/2)+(on/%d)*120" % fr
        parts.append(
            f"[{i}:v]scale=1792:1008:force_original_aspect_ratio=increase,crop=1792:1008,"
            f"zoompan=z='min(zoom+{zinc},1.16)':d={fr}:x='{x}':y='ih/2-(ih/zoom/2)':"
            f"s=1280x720:fps={fps},setsar=1[v{i}]")
    # ต่อด้วย xfade chain
    prev = "v0"
    for k in range(1, N):
        off = k * (L - xf)
        tag = f"x{k}"
        parts.append(f"[{prev}][v{k}]xfade=transition=fade:duration={xf}:offset={off:.3f}[{tag}]")
        prev = tag
    fc = ";".join(parts)

    cmd = ["ffmpeg", "-y"] + inp + ["-filter_complex", fc,
           "-map", f"[{prev}]", "-map", f"{N}:a",
           "-c:v", "libx264", "-preset", "veryfast", "-r", str(fps),
           "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p", "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        return {"ok": False, "error": f"slideshow ffmpeg ล้มเหลว: {r.stderr[-220:]}"}
    mb = round(os.path.getsize(out) / 1e6, 1)
    print(f"[podcast] ✅ EP.{n} (สไลด์ {N} ฉาก) → {out} ({mb}MB)")
    return {"ok": True, "file": out, "ep": n, "size_mb": mb, "scenes": N}


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

    # ถ้ามีรูปฉาก (>=2) → ทำ slideshow สลับรูปตามฉาก (ดึงดูดกว่าปกเดียว)
    try:
        import scene_images
        scenes = scene_images.scene_files(base, n)
    except Exception:
        scenes = []
    if len(scenes) >= 2:
        return _render_slideshow(scenes, audio, out, int(n))

    # ไม่มีรูปฉาก → fallback: ปกเดียว Ken Burns + พื้นหลังเบลอ
    fps = 25
    frames = max(int(_dur(audio) * fps), 250)
    fc = (
        "[0:v]scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,boxblur=26:4,"
        f"zoompan=z='min(zoom+0.00006,1.18)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(iw/zoom/2)':s=1280x720:fps={fps}[bg];"
        "[0:v]scale=2200:-2,"
        f"zoompan=z='min(zoom+0.00012,1.28)':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=940x720:fps={fps}[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]"
    )
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", cover, "-i", audio,
           "-filter_complex", fc, "-map", "[v]", "-map", "1:a",
           "-c:v", "libx264", "-preset", "veryfast", "-r", str(fps),
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
        cta = "\n\n▶️ ชอบเรื่องนี้? กดติดตามช่องไว้ จะได้ไม่พลาด EP ต่อไป!\n🔔 เปิดกระดิ่งแจ้งเตือนเพื่อฟังตอนใหม่ก่อนใคร"
        meta = {"title": f"{story_title} — EP.{n}",
                "description": f"📖 ตอนที่ {n}\n\n{syn}{cta}",
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
