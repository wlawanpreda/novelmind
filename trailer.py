"""
ANSRE Channel Trailer — รวม teaser เด่นๆ เป็นคลิปแนะนำช่อง (montage)
====================================================================
ตัดช่วงเปิดของแต่ละ teaser มาต่อกัน → คลิปแนะนำช่องดึง subscriber
ใช้:  python trailer.py [./SecondBrain] [--clip 6] [--limit 6]
"""
import os
import sys
import glob
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
_FLAGS = ("--clip", "--limit")


def _arg(name, default):
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def _sb_arg():
    # positional path = arg ที่ไม่ใช่ flag และไม่ใช่ค่าตามหลัง flag
    skip = set()
    for fl in _FLAGS:
        if fl in sys.argv:
            skip.add(sys.argv.index(fl) + 1)
    for i, a in enumerate(sys.argv[1:], 1):
        if a.startswith("--") or i in skip:
            continue
        return a
    return os.path.join(ROOT, "SecondBrain")


SB = _sb_arg()


def make_trailer(sb=SB, clip_sec=6, limit=6, out=None):
    ap = os.path.join(sb, "05_Active_Projects")
    teasers = sorted(set(glob.glob(os.path.join(ap, "Teasers", "*.mp4")) +
                         glob.glob(os.path.join(ap, "Teaser_Output", "*.mp4"))))
    teasers = [t for t in teasers if "_CHANNEL_TRAILER" not in t][:limit]
    if len(teasers) < 2:
        return {"ok": False, "error": f"ต้องมี teaser อย่างน้อย 2 คลิป (มี {len(teasers)})"}

    out_dir = os.path.join(ap, "Trailers")
    os.makedirs(out_dir, exist_ok=True)
    out = out or os.path.join(out_dir, "_CHANNEL_TRAILER.mp4")

    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for i, t in enumerate(teasers):
            p = os.path.join(tmp, f"part_{i:02d}.mp4")
            # ตัด clip_sec วินาทีแรก + normalize เป็น 1080x1920 h264/aac ให้ต่อกันได้เนียน
            cmd = ["ffmpeg", "-y", "-t", str(clip_sec), "-i", t,
                   "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=25,fade=t=in:st=0:d=0.3,fade=t=out:st=" + str(max(clip_sec - 0.4, 0.5)) + ":d=0.4",
                   "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-b:a", "160k",
                   "-ar", "44100", "-pix_fmt", "yuv420p", p]
            r = subprocess.run(cmd, capture_output=True, text=True)
            if r.returncode == 0 and os.path.exists(p):
                parts.append(p)
            else:
                print(f"[trailer] ข้าม {os.path.basename(t)}: {r.stderr[-200:]}")
        if len(parts) < 2:
            return {"ok": False, "error": "ตัดคลิปไม่สำเร็จพอ"}
        listf = os.path.join(tmp, "list.txt")
        with open(listf, "w", encoding="utf-8") as f:
            for p in parts:
                f.write(f"file '{p}'\n")
        r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf,
                            "-c", "copy", out], capture_output=True, text=True)
        if r.returncode != 0:
            return {"ok": False, "error": f"concat ล้มเหลว: {r.stderr[-200:]}"}

    mb = round(os.path.getsize(out) / 1e6, 1)
    print(f"[trailer] ✅ รวม {len(parts)} คลิป × {clip_sec}s → {out} ({mb}MB)")
    return {"ok": True, "file": out, "clips": len(parts), "size_mb": mb}


if __name__ == "__main__":
    r = make_trailer(SB, clip_sec=int(_arg("--clip", 6)), limit=int(_arg("--limit", 6)))
    print("RESULT:", "OK" if r.get("ok") else "FAILED — " + r.get("error", ""))
