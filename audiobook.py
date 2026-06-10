"""
ANSRE Audiobook Compiler — รวมไฟล์เสียงทุกตอนเป็นหนังสือเสียงทั้งเล่ม
====================================================================
ต่อ mp3 ทุกตอนของเรื่อง + intro/outro (ถ้ามี) + สร้าง chapter markers
(timestamp สำหรับ YouTube/Spotify) จาก duration จริงของแต่ละไฟล์

ใช้:  python audiobook.py "<ชื่อเรื่อง/ฐานไฟล์>"  [./SecondBrain]
"""
import os
import re
import sys
import glob
import tempfile
import subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))


def _dur(fp):
    """ความยาว (วินาที) ของไฟล์เสียง"""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", fp], capture_output=True, text=True)
        return float(r.stdout.strip())
    except Exception:
        return 0.0


def _ts(sec):
    """วินาที → H:MM:SS หรือ M:SS"""
    sec = int(sec)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _base_from(sb, title):
    """หา base ของไฟล์เสียงจากชื่อเรื่อง (จับคู่ยืดหยุ่น)"""
    adir = os.path.join(sb, "05_Active_Projects", "Audio_Output")
    bases = sorted(set(re.sub(r"_Audiobook_\d+\.mp3$", "", os.path.basename(p))
                       for p in glob.glob(os.path.join(adir, "*_Audiobook_*.mp3"))))
    if not bases:
        return None
    key = re.sub(r"[\s_:：]+", "", title)
    for b in bases:
        bk = re.sub(r"[\s_:：]+", "", b)
        if bk == key or key in bk or bk in key:
            return b
    toks = [t for t in re.split(r"[_\s]+", title) if len(t) >= 3]
    for b in bases:
        if any(t in b for t in toks):
            return b
    return None


def compile_audiobook(sb, title):
    adir = os.path.join(sb, "05_Active_Projects", "Audio_Output")
    base = _base_from(sb, title)
    if not base:
        return {"ok": False, "error": f"ไม่พบไฟล์เสียงของ '{title}'"}
    chapters = sorted(glob.glob(os.path.join(adir, f"{base}_Audiobook_*.mp3")))
    if not chapters:
        return {"ok": False, "error": "ไม่พบตอนเสียง"}

    out_dir = os.path.join(sb, "05_Active_Projects", "Audiobooks")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{base}_FULL.mp3")

    # intro/outro ถ้ามีไฟล์วางไว้ใน Audio_Assets/
    assets = os.path.join(sb, "05_Active_Projects", "Audio_Assets")
    intro = next((p for p in (os.path.join(assets, "intro.mp3"),) if os.path.exists(p)), None)
    outro = next((p for p in (os.path.join(assets, "outro.mp3"),) if os.path.exists(p)), None)

    seq = ([intro] if intro else []) + chapters + ([outro] if outro else [])
    # chapter markers — เริ่มนับ offset หลัง intro
    markers = []
    t = _dur(intro) if intro else 0.0
    for i, ch in enumerate(chapters, 1):
        markers.append((t, i))
        t += _dur(ch)
    total = t + (_dur(outro) if outro else 0.0)

    with tempfile.TemporaryDirectory() as tmp:
        listf = os.path.join(tmp, "list.txt")
        with open(listf, "w", encoding="utf-8") as f:
            for p in seq:
                f.write(f"file '{p}'\n")
        # re-encode สม่ำเสมอ (มี intro/outro คนละ param ได้) → mp3 192k 44.1k
        cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf,
               "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "44100", out]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            # ลอง copy ถ้า re-encode พลาด
            cmd2 = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", listf, "-c", "copy", out]
            r = subprocess.run(cmd2, capture_output=True, text=True)
            if r.returncode != 0:
                return {"ok": False, "error": f"รวมเสียงล้มเหลว: {r.stderr[-200:]}"}

    # เขียน chapter markers (YouTube/Spotify timestamp format)
    lines = [f"# {title} — หนังสือเสียงรวมเล่ม", f"# ความยาวรวม {_ts(total)} · {len(chapters)} ตอน", ""]
    for sec, n in markers:
        lines.append(f"{_ts(sec)} ตอนที่ {n}")
    marker_fp = os.path.join(out_dir, f"{base}_chapters.txt")
    with open(marker_fp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    mb = round(os.path.getsize(out) / 1e6, 1)
    print(f"[audiobook] ✅ {len(chapters)} ตอน → {out} ({mb}MB, {_ts(total)})")
    print(f"[audiobook] markers → {marker_fp}")
    return {"ok": True, "file": out, "markers": marker_fp, "chapters": len(chapters),
            "duration": _ts(total), "size_mb": mb, "intro": bool(intro), "outro": bool(outro),
            "marker_list": [f"{_ts(s)} ตอนที่ {n}" for s, n in markers]}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python audiobook.py \"<ชื่อเรื่อง>\" [SB]")
        sys.exit(1)
    sb = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "SecondBrain")
    res = compile_audiobook(sb, sys.argv[1])
    print("RESULT:", "OK" if res.get("ok") else "FAILED — " + res.get("error", ""))
