"""
ANSRE Auto-fix — ซ่อมเรื่องที่ Health Check เจอว่าพัง (อัตโนมัติ)
================================================================
- บทมี error ดิบหลุด / สั้นผิดปกติ → ลบแล้ว regenerate ใหม่ (chapter_continuer)
- ไฟล์ตัวละครหลุดภาษาจีน/AI meta-talk → เขียนใหม่เป็นไทยล้วน (จาก outline)

ใช้:  python autofix.py [./SecondBrain] [--only "ชื่อเรื่อง"] [--all]
"""
import os
import sys
import re
import glob
import story_health

SB = "./SecondBrain"
args = sys.argv[1:]
ONLY = None
DO_ALL = "--all" in args
if "--only" in args:
    i = args.index("--only")
    ONLY = args[i + 1] if i + 1 < len(args) else None
    args = args[:i] + args[i + 2:]
for a in args:
    if not a.startswith("--"):
        SB = a


def _processed():
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
        out.append((title, story_health._slug(title)))
    return out


def fix_story(title, base):
    fixed = []
    h = story_health.scan_story(SB, base, title)
    if h["status"] == "green":
        print(f"[autofix] '{title}' สุขภาพดีอยู่แล้ว — ข้าม")
        return fixed
    ch_dir = os.path.join(SB, "05_Active_Projects", "Chapters")

    # 1) บท red (error) หรือ yellow สั้น → ลบ + regenerate
    bad = set()
    for i in h["issues"]:
        if i["where"].startswith("ตอน") and (
                (i["sev"] == "red") or ("สั้น" in i["label"])):
            mnum = re.search(r"\d+", i["where"])
            if mnum:
                bad.add(int(mnum.group(0)))
    for n in sorted(bad):
        fp = os.path.join(ch_dir, f"{base}_Chapter_{n:02d}.md")
        prev = os.path.join(ch_dir, f"{base}_Chapter_{n - 1:02d}.md")
        if n == 1 or not os.path.exists(prev):
            print(f"[autofix] ตอน {n}: ไม่มีตอนก่อนหน้า — ข้าม regenerate (ควรเขียนใหม่ทั้งเรื่อง)")
            continue
        if os.path.exists(fp):
            try:
                import versions
                versions.snapshot(fp, "ก่อน-autofix")
            except Exception:
                pass
            os.remove(fp)
        asf = os.path.join(SB, "05_Active_Projects", "Audio_Scripts", f"{base}_AudioScript_{n:02d}.md")
        if os.path.exists(asf):
            os.remove(asf)
        print(f"[autofix] regenerate ตอน {n} ของ '{title}'...")
        try:
            import chapter_continuer
            ok = chapter_continuer.write_next_chapter(SB, base, n)
            if ok:
                fixed.append(f"เขียนตอน {n} ใหม่")
        except Exception as e:
            print(f"[autofix] ตอน {n} ล้มเหลว: {e}")

    # 2) ไฟล์ตัวละคร red (CJK/meta) → เขียนใหม่จาก outline
    if any("ตัวละคร" in i["where"] and i["sev"] == "red" for i in h["issues"]):
        out_fp = os.path.join(SB, "02_Concept_Extraction", f"{base}_Outline.md")
        char_fp = os.path.join(SB, "04_Character_Database", f"{base}_Characters.md")
        if os.path.exists(out_fp):
            print(f"[autofix] เขียนไฟล์ตัวละครใหม่ (ลบ CJK/meta) ของ '{title}'...")
            try:
                from agent_writer import run_stage_2_characters
                outline = open(out_fp, encoding="utf-8").read()
                chars = run_stage_2_characters(title, outline)
                with open(char_fp, "w", encoding="utf-8") as f:
                    f.write(f"# Characters Database: {title}\n\n" + chars)
                fixed.append("เขียนไฟล์ตัวละครใหม่")
            except Exception as e:
                print(f"[autofix] ตัวละครล้มเหลว: {e}")

    after = story_health.scan_story(SB, base, title)
    print(f"[autofix] '{title}': {h['status']} → {after['status']} · แก้ {len(fixed)} จุด {fixed}")
    return fixed


def main():
    stories = _processed()
    if not DO_ALL and not ONLY:
        # default: เฉพาะเรื่องที่ red (พังจริง)
        stories = [(t, b) for t, b in stories if story_health.scan_story(SB, b, t)["status"] == "red"]
    print(f"[autofix] จะซ่อม {len(stories)} เรื่อง")
    total = 0
    for t, b in stories:
        total += len(fix_story(t, b))
    print(f"[autofix] ✅ เสร็จ — แก้รวม {total} จุด")
    try:
        from notify import notify
        notify(f"ซ่อม {len(stories)} เรื่อง · แก้ {total} จุด", "🔧 Auto-fix เสร็จ", "good")
    except Exception:
        pass


if __name__ == "__main__":
    main()
