"""
ANSRE Export Pack — รวมทรัพย์สินทุกอย่างของเรื่องเป็น zip เดียวพร้อมปล่อย
=======================================================================
รวม ปก · เสียง(ตอน+รวมเล่ม) · teaser · trailer · caption/SEO · บท · bible
+ README.txt สรุปวิธีปล่อยทีละแพลตฟอร์ม → SecondBrain/.../Exports/<base>_pack.zip

ใช้:  python export_pack.py "<ชื่อเรื่อง>" [./SecondBrain]
"""
import os
import re
import sys
import glob
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))

# โฟลเดอร์ → ป้ายกำกับในแพ็ก (จัดกลุ่มให้อ่านง่าย)
SPECS = [
    ("Covers", ["{b}_Cover.png", "{b}_Cover_captioned.jpg", "{b}_Cover.jpg"], "01_ปก"),
    ("Captions", ["{b}_Caption.md"], "02_แคปชั่น_SEO"),
    ("Teasers", ["{b}_Teaser.mp4"], "03_teaser"),
    ("Teaser_Output", ["{b}*.mp4"], "03_teaser"),
    ("Trailers", ["{b}_*.mp4"], "04_trailer"),
    ("Audiobooks", ["{b}_FULL.mp3", "{b}_chapters.txt"], "05_หนังสือเสียงเล่ม"),
    ("Audio_Output", ["{b}_Audiobook_*.mp3"], "06_เสียงรายตอน"),
    ("Chapters", ["{b}_Chapter_*.md"], "07_บท"),
    ("Story_Bible", ["{b}*.md"], "08_story_bible"),
    ("AB_Tests", ["{b}_AB.md"], "09_AB_variants"),
]


def _base_for(sb, title):
    """หา base จากชื่อเรื่อง โดยดูจากไฟล์บท/ปก (จับคู่ยืดหยุ่น)"""
    cands = set()
    for pat in ("Chapters/*_Chapter_01.md", "Covers/*_Cover*.png", "Covers/*_Cover*.jpg"):
        for p in glob.glob(os.path.join(sb, "05_Active_Projects", pat)):
            b = re.sub(r"_(Chapter|Cover).*$", "", os.path.basename(p))
            cands.add(b)
    if not cands:
        return None
    key = re.sub(r"[\s_:：]+", "", title)
    for b in sorted(cands):
        bk = re.sub(r"[\s_:：]+", "", b)
        if bk == key or key in bk or bk in key:
            return b
    toks = [t for t in re.split(r"[_\s]+", title) if len(t) >= 3]
    for b in sorted(cands):
        if any(t in b for t in toks):
            return b
    return None


def build_pack(sb, title):
    ap = os.path.join(sb, "05_Active_Projects")
    base = _base_for(sb, title)
    if not base:
        return {"ok": False, "error": f"ไม่พบทรัพย์สินของ '{title}'"}

    # เก็บไฟล์ที่จะใส่: (arcname, path)
    items, groups = [], {}
    for folder, pats, label in SPECS:
        for pat in pats:
            for fp in sorted(glob.glob(os.path.join(ap, folder, pat.format(b=base)))):
                if not os.path.isfile(fp):
                    continue
                arc = f"{label}/{os.path.basename(fp)}"
                if arc in dict(items):
                    continue
                items.append((arc, fp))
                groups.setdefault(label, []).append(os.path.basename(fp))

    if not items:
        return {"ok": False, "error": "ไม่มีไฟล์ให้แพ็ก (ยังไม่ได้สร้างสื่อ?)"}

    # README สรุปวิธีปล่อย
    cap = ""
    capf = os.path.join(ap, "Captions", f"{base}_Caption.md")
    if os.path.exists(capf):
        with open(capf, "r", encoding="utf-8") as f:
            cap = f.read()
    readme = [f"# แพ็กพร้อมปล่อย: {title}", "",
              "ไฟล์ในแพ็กนี้จัดกลุ่มตามลำดับการใช้งาน:", ""]
    for label in sorted(groups):
        readme.append(f"## {label}")
        for n in groups[label]:
            readme.append(f"  - {n}")
        readme.append("")
    readme += ["## วิธีปล่อย (แนะนำ)",
               "1. YouTube/TikTok: อัปโหลด teaser/trailer (03/04) ใช้ caption (02) เป็นชื่อ+คำอธิบาย",
               "2. หนังสือเสียง: อัปโหลด 05_FULL.mp3 + วาง chapters.txt เป็น timestamp ใน description",
               "3. แพลตฟอร์มนิยาย: ลงบท (07) ใช้ปก (01) เป็นหน้าปก",
               "", "## Caption/SEO (คัดลอกไปใช้ได้เลย)", "", cap or "(ยังไม่ได้สร้าง caption — กดปุ่ม Caption/SEO ก่อน)"]

    out_dir = os.path.join(ap, "Exports")
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{base}_pack.zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", "\n".join(readme))
        for arc, fp in items:
            z.write(fp, arc)

    mb = round(os.path.getsize(out) / 1e6, 2)
    print(f"[export] ✅ {len(items)} ไฟล์ ({len(groups)} กลุ่ม) → {out} ({mb}MB)")
    return {"ok": True, "file": out, "base": base, "count": len(items),
            "groups": {k: len(v) for k, v in groups.items()}, "size_mb": mb}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python export_pack.py \"<ชื่อเรื่อง>\" [SB]")
        sys.exit(1)
    sb = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "SecondBrain")
    res = build_pack(sb, sys.argv[1])
    print("RESULT:", "OK" if res.get("ok") else "FAILED — " + res.get("error", ""))
