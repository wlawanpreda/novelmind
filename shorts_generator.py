"""
ANSRE Shorts Generator — สร้าง Short (9:16) ต่อตอน สำหรับ YouTube Shorts + TikTok
================================================================================
แต่ละตอน → คลิปสั้น 9:16: ปกแคปชั่น (ชื่อ+hook) + เสียง hook ~50s + fade
ใช้ปก/รูปฉากของเรื่อง · เบิร์นข้อความไทยด้วย PIL (reuse teaser_generator)

ใช้:  python shorts_generator.py "<ชื่อเรื่อง>" [วินาที=50]
"""
import os
import re
import sys
import glob
import subprocess

import teaser_generator as tg

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AP = os.path.join(SB, "05_Active_Projects")


def _base(story):
    bases = sorted(set(re.sub(r"_Audiobook_\d+\.mp3$", "", os.path.basename(p))
                   for p in glob.glob(os.path.join(AP, "Audio_Output", "*_Audiobook_*.mp3"))))
    key = re.sub(r"[\s_:：]+", "", story)
    for b in bases:
        bk = re.sub(r"[\s_:：]+", "", b)
        if bk == key or key in bk or bk in key:
            return b
    toks = [t for t in re.split(r"[_\s]+", story) if len(t) >= 3]
    return next((b for b in bases if any(t in b for t in toks)), None)


def _cover(base):
    for name in (f"{base}_Cover_captioned.jpg", f"{base}_Cover.png", f"{base}_Cover.jpg"):
        fp = os.path.join(AP, "Covers", name)
        if os.path.exists(fp):
            return fp
    return None


def _logline(base):
    """คำโปรยสะอาดจาก Outline (ตัด markdown/เครดิต/label)"""
    fp = os.path.join(SB, "02_Concept_Extraction", f"{base}_Outline.md")
    try:
        lines = open(fp, encoding="utf-8").read().splitlines()
    except Exception:
        return ""
    for i, ln in enumerate(lines):
        if "คำโปรย" in ln or "logline" in ln.lower():
            after = re.split(r"[:：]", ln, maxsplit=1)
            c = re.sub(r"[*_`>#]", "", after[1]).strip() if len(after) > 1 else ""
            if len(c) >= 15:
                return c[:140]
            for nxt in lines[i + 1:i + 4]:
                s = re.sub(r"[*_`>#]", "", nxt).strip()
                if len(s) >= 15 and not s.lower().startswith(("inspired", "source")):
                    return s[:140]
    return ""


def _chapter_hook(base, n):
    """hook เฉพาะตอน: ดึงประโยคเปิดจาก .srt ของตอนนั้น (ต่างกันทุกตอน) ตัดให้กระชับ"""
    srt = os.path.join(AP, "Audio_Output", f"{base}_Audiobook_{int(n):02d}.srt")
    try:
        txt = open(srt, encoding="utf-8").read()
    except Exception:
        return ""
    # บล็อกแรกที่เป็นเนื้อ (ข้าม index/timecode)
    for block in txt.split("\n\n"):
        body = "\n".join(l for l in block.splitlines()
                         if l.strip() and not l.strip().isdigit() and "-->" not in l)
        body = body.strip()
        if len(body) < 15:
            continue
        # เอาประโยคแรก ~14 คำ ให้เป็น hook สั้นกระชับ
        first = re.split(r"[.。!?\n]", body)[0]
        words = first.split()
        hook = " ".join(words[:16])
        if len(hook) > 8:
            return hook[:120] + ("…" if len(words) > 16 else "")
    return ""


def make_short(story, n, dur=50, base=None):
    base = base or _base(story)
    if not base:
        return {"ok": False, "error": f"ไม่พบเสียงของ '{story}'"}
    audio = os.path.join(AP, "Audio_Output", f"{base}_Audiobook_{int(n):02d}.mp3")
    if not os.path.exists(audio):
        return {"ok": False, "error": f"ไม่พบเสียงตอน {n}"}
    cover = _cover(base)
    if not cover:
        return {"ok": False, "error": "ไม่พบปก"}

    title = base.replace("_", " ")
    # hook เฉพาะตอน (ประโยคเปิดของตอนนั้น) → ดึงคนดู · ตอน 1 ใช้คำโปรยเรื่อง
    ch_hook = _chapter_hook(base, n)
    hook = (f"🔥 ตอน {int(n)} | {ch_hook}" if ch_hook else f"ตอนที่ {int(n)} · {_logline(base)}") \
        if int(n) > 1 else (_logline(base) or ch_hook)
    # เบิร์นปก 9:16 (reuse teaser_generator) — ชื่อบน + hook ล่าง
    capped = tg.caption_cover(cover, title, hook) or cover

    out_dir = os.path.join(AP, "Shorts")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{base}_Short_{int(n):02d}.mp4")

    # 9:16 1080x1920: ปกแคปชั่นเต็มจอ (มันเป็น 9:16 อยู่แล้ว) + เสียง hook dur วินาที + fade
    vf = (f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
          f"fade=t=in:st=0:d=0.4,fade=t=out:st={max(dur-0.6,1)}:d=0.6")
    af = f"afade=t=out:st={max(dur-0.6,1)}:d=0.6"
    cmd = ["ffmpeg", "-y", "-loop", "1", "-i", capped, "-t", str(dur), "-i", audio,
           "-map", "0:v", "-map", "1:a", "-vf", vf, "-af", af,
           "-c:v", "libx264", "-tune", "stillimage", "-preset", "veryfast",
           "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-pix_fmt", "yuv420p",
           "-t", str(dur), "-shortest", out]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        return {"ok": False, "error": f"ffmpeg ล้มเหลว: {r.stderr[-200:]}"}
    mb = round(os.path.getsize(out) / 1e6, 1)
    print(f"[short] ✅ ตอน {int(n)} → {out} ({mb}MB, {dur}s 9:16)")
    return {"ok": True, "file": out, "n": int(n), "size_mb": mb}


def make_all(story, dur=50):
    base = _base(story)
    if not base:
        return {"ok": False, "error": f"ไม่พบเสียงของ '{story}'"}
    nums = sorted(int(re.search(r"_Audiobook_(\d+)\.mp3$", p).group(1))
                  for p in glob.glob(os.path.join(AP, "Audio_Output", f"{base}_Audiobook_*.mp3")))
    done = []
    for n in nums:
        r = make_short(story, n, dur, base=base)
        if r.get("ok"):
            done.append(r)
    return {"ok": bool(done), "base": base, "shorts": done, "count": len(done)}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('usage: python shorts_generator.py "<ชื่อเรื่อง>" [วินาที=50]')
        sys.exit(1)
    d = int(sys.argv[2]) if len(sys.argv) > 2 else 50
    res = make_all(sys.argv[1], d)
    print("RESULT:", f"OK {res.get('count')} shorts" if res.get("ok") else "FAILED — " + res.get("error", ""))
