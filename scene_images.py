"""
ANSRE Scene Images — แตกแต่ละตอนเป็นฉาก + generate รูปต่อฉาก (สำหรับสไลด์ในวิดีโอ)
================================================================================
อ่านเนื้อบท → ให้ AI วางแผน N ฉากตามลำดับเรื่อง → สร้าง prompt อังกฤษ (คงสไตล์+ตัวละคร)
→ generate รูปผ่าน image_provider → Scene_Images/<base>_ch<NN>_s<i>.png

ใช้:  python scene_images.py "<ชื่อเรื่อง>" <ตอน> [จำนวนฉาก=5]
      python scene_images.py "<ชื่อเรื่อง>" all 5      # ทุกตอนที่มีบท
"""
import os
import re
import sys
import glob

from llm_provider import generate_json, generate
import image_provider

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AP = os.path.join(SB, "05_Active_Projects")


def _read(fp):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _base(story):
    bases = sorted(set(re.sub(r"_Chapter_\d+\.md$", "", os.path.basename(p))
                   for p in glob.glob(os.path.join(AP, "Chapters", "*_Chapter_*.md"))))
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


def plan_scenes(base, n, count=5):
    """ให้ AI แตกบทเป็น count ฉากเรียงตามเรื่อง + prompt อังกฤษ (คงตัวละคร/สไตล์)"""
    chapter = _read(os.path.join(AP, "Chapters", f"{base}_Chapter_{int(n):02d}.md"))
    chars = _read(os.path.join(SB, "04_Character_Database", f"{base}_Characters.md"))
    if not chapter:
        return None
    prompt = f"""คุณคือ Storyboard Artist & Prompt Engineer แตกบทนิยายเป็นภาพประกอบเรียงตามเหตุการณ์
ข้อมูลตัวละคร (ใช้ให้รูปหน้าตา/เครื่องแต่งกายตรงกันทุกฉาก):
{chars[:1500]}

เนื้อบท:
{chapter[:7000]}

แตกเป็น {count} ฉากสำคัญเรียงตามลำดับเวลาในบท ตอบ JSON เท่านั้น:
{{
  "style": "art style + mood ของทั้งเรื่องเป็นภาษาอังกฤษ (เช่น cinematic, warm tone, Thai setting) ใช้เหมือนกันทุกฉากเพื่อความต่อเนื่อง",
  "scenes": [
    {{"prompt": "detailed English image prompt ของฉากนี้: ใคร ทำอะไร ที่ไหน อารมณ์ มุมกล้อง แสง — ต่อท้ายด้วย style"}}
  ]
}}
(ฉากต้องสื่อเหตุการณ์จริงในบท, {count} ฉากพอดี, PG-13, ไม่มีตัวอักษรในภาพ, ภาษาอังกฤษในช่อง prompt)"""
    # 1) ลอง JSON (retry กัน gateway timeout/throttle) — ไม่ให้ทั้ง batch ล่ม
    style, scenes = "cinematic, dramatic lighting, film still", []
    for _ in range(3):
        try:
            data = generate_json(prompt, role="visual")
            style = data.get("style") or style
            scenes = [s.get("prompt", "") for s in data.get("scenes", []) if s.get("prompt")]
            if scenes:
                break
        except Exception:
            continue
    # 2) fallback: ขอเป็นข้อความบรรทัดละฉาก (ไม่ต้อง JSON) แล้วแปลงเป็น prompt
    if not scenes:
        try:
            txt = generate(
                f"""อ่านบทนี้แล้วบรรยายภาพ {count} ฉากสำคัญเรียงตามเรื่อง เป็นภาษาอังกฤษ
บรรทัดละ 1 ฉาก (detailed cinematic image prompt: who/what/where/mood/lighting) ห้ามมีเลขนำหน้า:
{chapter[:6000]}""", role="visual")
            scenes = [re.sub(r"^\s*[\d.\-•*]+\s*", "", l).strip()
                      for l in txt.splitlines() if len(l.strip()) > 20][:count]
        except Exception:
            scenes = []
    if not scenes:
        return None
    out = []
    for p in scenes[:count]:
        full = p if style.lower() in p.lower() else f"{p}, {style}"
        out.append(full + ", no text, no watermark")
    return out


def make_scenes(story, n, count=5, base=None):
    base = base or _base(story)
    if not base:
        return {"ok": False, "error": f"ไม่พบบทของ '{story}'"}
    prompts = plan_scenes(base, n, count)
    if not prompts:
        return {"ok": False, "error": f"วางแผนฉากไม่ได้ (ตอน {n})"}
    out_dir = os.path.join(AP, "Scene_Images")
    os.makedirs(out_dir, exist_ok=True)
    made = []
    for i, p in enumerate(prompts, 1):
        fp = os.path.join(out_dir, f"{base}_ch{int(n):02d}_s{i}.png")
        try:
            ok = image_provider.generate_image(p, fp, aspect_ratio="16:9")
            if ok and os.path.exists(fp):
                made.append(fp)
                print(f"[scene] ✅ ตอน {n} ฉาก {i}/{len(prompts)}", flush=True)
            else:
                print(f"[scene] ❌ ตอน {n} ฉาก {i} (gen ไม่สำเร็จ)", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"[scene] ❌ ตอน {n} ฉาก {i}: {e}", flush=True)
    return {"ok": bool(made), "base": base, "ch": int(n), "images": made, "count": len(made)}


def scene_files(base, n):
    """รายชื่อรูปฉากของตอน (เรียงตามลำดับ) — ใช้ใน podcast"""
    fps = glob.glob(os.path.join(AP, "Scene_Images", f"{base}_ch{int(n):02d}_s*.png"))
    return sorted(fps, key=lambda p: int(re.search(r"_s(\d+)\.png$", p).group(1)))


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print('usage: python scene_images.py "<ชื่อเรื่อง>" <ตอน|all> [จำนวนฉาก=5]')
        sys.exit(1)
    story = sys.argv[1]
    cnt = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    base = _base(story)
    if not base:
        print("ไม่พบเรื่อง"); sys.exit(1)
    if sys.argv[2] == "all":
        chs = sorted(int(re.search(r"_Chapter_(\d+)\.md$", p).group(1))
                     for p in glob.glob(os.path.join(AP, "Chapters", f"{base}_Chapter_*.md")))
        for n in chs:
            r = make_scenes(story, n, cnt, base=base)
            print(f"ตอน {n}: {r.get('count', 0)} รูป")
    else:
        r = make_scenes(story, int(sys.argv[2]), cnt, base=base)
        print("RESULT:", "OK" if r.get("ok") else "FAILED — " + r.get("error", ""))
