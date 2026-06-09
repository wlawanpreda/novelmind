"""
ANSRE Finish — เติมสินทรัพย์ที่ขาดให้เรื่องที่เขียนแล้ว (idempotent)
====================================================================
ทำให้เรื่องที่มีบทแล้วแต่ขาด ปก/teaser ให้ครบ พร้อมปล่อย
- ปก: ComfyUI (local) ข้ามเรื่องที่มีปกแล้ว
- teaser: สร้างจาก audio+ปก ที่มีอยู่ (ข้ามเรื่องที่มี teaser แล้ว)
- audio (TTS) ช้า — ทำเฉพาะเมื่อใส่ --audio

ใช้:  python finish.py [./SecondBrain] [--only "ชื่อเรื่อง"] [--audio]
"""
import os
import sys
import glob
import re

# ปกผ่าน ComfyUI ตรง (เลี่ยง gateway ที่อาจตั้ง IMAGE_BACKEND=gemini โควต้าหมด)
os.environ.setdefault("IMAGE_BACKEND", "local")
os.environ["ANSRE_GATEWAY_INTERNAL"] = "1"

SB = "./SecondBrain"
args = [a for a in sys.argv[1:]]
ONLY = None
DO_AUDIO = "--audio" in args
if "--only" in args:
    i = args.index("--only")
    ONLY = args[i + 1] if i + 1 < len(args) else None
    args = args[:i] + args[i + 2:]
args = [a for a in args if not a.startswith("--")]
if args:
    SB = args[0]

AP = os.path.join(SB, "05_Active_Projects")


def _slug(t):
    return re.sub(r"[^\w\-_\s฀-๿]", "", t or "").strip().replace(" ", "_")


def _g(*p):
    return glob.glob(os.path.join(AP, *p))


def _processed_stories():
    """(title, base) ของเรื่องที่ status=Processed"""
    out = []
    for fp in glob.glob(os.path.join(SB, "01_Scouting_Pool", "*.md")):
        txt = open(fp, encoding="utf-8").read(3000)
        m = re.match(r"^---\s*\n(.*?)\n---", txt, re.DOTALL)
        fm = {}
        if m:
            for line in m.group(1).splitlines():
                if ":" in line and not line.startswith(" "):
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip().strip('"').strip("'")
        if fm.get("status") != "Processed":
            continue
        title = fm.get("recreation_title") or fm.get("thai_working_title") or fm.get("title")
        if ONLY and ONLY not in (title or "") and ONLY not in (fm.get("title") or ""):
            continue
        out.append((title, _slug(title)))
    return out


def main():
    stories = _processed_stories()
    print(f"[finish] ตรวจ {len(stories)} เรื่อง" + (f" (เฉพาะ '{ONLY}')" if ONLY else ""))

    need_cover = [(t, b) for t, b in stories if _g("Chapters", f"{b}_Chapter_*.md") and not _g("Covers", f"{b}_Cover*")]
    print(f"[finish] ขาดปก {len(need_cover)} เรื่อง")
    if need_cover:
        try:
            import cover_generator
            cover_generator.process_covers(SB)   # ข้ามที่มีแล้ว เติมที่ขาด
        except Exception as e:
            print(f"[finish] ปก: {e}")

    if DO_AUDIO:
        need_audio = [(t, b) for t, b in stories
                      if _g("Audio_Scripts", f"{b}_AudioScript_*.md") and not _g("Audio_Output", f"{b}_Audiobook_*.mp3")]
        print(f"[finish] ขาดเสียง {len(need_audio)} เรื่อง — กำลังเจน (edge-tts ช้า)...")
        try:
            import audio_engine
            for t, b in need_audio:
                sc = sorted(_g("Audio_Scripts", f"{b}_AudioScript_*.md"))
                if sc:
                    out = os.path.join(AP, "Audio_Output", os.path.basename(sc[0]).replace(".md", ".mp3").replace("AudioScript_", "Audiobook_"))
                    audio_engine.render_script_to_audio(sc[0], out)
        except Exception as e:
            print(f"[finish] เสียง: {e}")

    # teaser: เรื่องที่มี audio+ปก แต่ยังไม่มี teaser
    os.makedirs(os.path.join(AP, "Teasers"), exist_ok=True)
    import teaser_generator as T
    made = 0
    for t, b in stories:
        if _g("Teasers", f"{b}_Teaser*"):
            continue
        audio = sorted(_g("Audio_Output", f"{b}_Audiobook_*.mp3"))
        cover = (_g("Covers", f"{b}_Cover.png") or _g("Covers", f"{b}_Cover.jpg") or _g("Covers", f"{b}_Cover*"))
        if not (audio and cover):
            continue
        out = os.path.join(AP, "Teasers", f"{b}_Teaser.mp4")
        print(f"[finish] ตัด teaser: {t}")
        try:
            ok = T.generate_teaser(audio_path=audio[0], cover_path=cover[0], output_path=out,
                                   max_duration_sec=60, display_title=(t or b)[:40], hook="")
            if ok and os.path.exists(out):
                made += 1
        except Exception as e:
            print(f"[finish] teaser '{t}': {e}")

    print(f"[finish] ✅ เสร็จ — teaser ใหม่ {made} คลิป")


if __name__ == "__main__":
    main()
