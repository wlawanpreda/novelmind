"""
ANSRE Studio Engine — ความสามารถระดับสตูดิโอสำหรับการแต่งนิยายแบบครบวงจร
========================================================================
ต่อยอดจาก pipeline หลัก เพิ่ม "งานสร้างสรรค์" ที่ UI เรียกใช้:

  1. idea_loop      — AI loop: คอมเมนต์ + ขัดเกลาไอเดียทีละรอบ
  2. chapter_loop   — AI loop: คอมเมนต์ + เขียนบทใหม่ให้ดีขึ้นทีละรอบ
  3. visual_prompts — prompt สร้างภาพตัวละคร/ฉาก (Midjourney/Imagen/Flux/SDXL)
  4. video_prompts  — ข้อมูล shot-by-shot สำหรับ Google Flow (Veo) / Kling / Runway / Pika
  5. story_bible    — รวมข้อมูลโลก/ตัวละคร/ไทม์ไลน์เป็นไฟล์เดียว

ทุก LLM call ผ่าน llm_provider (role → backend ตาม .env)
ผลลัพธ์เก็บใน SecondBrain/05_Active_Projects/<หมวด>/

CLI:
  python studio.py visual <title>
  python studio.py video <title>
  python studio.py idea-loop <idea_id> [rounds]
  python studio.py chapter-loop <title> [ch] [rounds]
  python studio.py bible <title>
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json

from llm_provider import generate, generate_json

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
AP = os.path.join(SB, "05_Active_Projects")

# ---- load .env ----
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

THAI = "฀-๿"


def _slug(t):
    return re.sub(r"[^\w\-_\s" + THAI + r"]", "", t).strip().replace(" ", "_")


def _read(fp):
    try:
        with open(fp, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def _find(folder, pattern):
    hits = glob.glob(os.path.join(SB, folder, pattern))
    return hits[0] if hits else None


def list_projects():
    """รายชื่อเรื่องที่มีอยู่ (base name จากไฟล์ Outline)"""
    out = []
    for fp in sorted(glob.glob(os.path.join(SB, "02_Concept_Extraction", "*_Outline.md"))):
        base = os.path.basename(fp).replace("_Outline.md", "")
        out.append(base)
    return out


def _match_base(title):
    """หา base name ของโปรเจกต์จาก title ที่ผู้ใช้พิมพ์ (ยืดหยุ่น)"""
    projects = list_projects()
    if not projects:
        return None
    key = _slug(title)
    # 1) ตรงเป๊ะ / เป็น substring สองทาง
    for b in projects:
        if b == key or key in b or b in key:
            return b
    # 2) token overlap (คำยาว >=3)
    toks = [t for t in re.split(r"[_\s]+", key) if len(t) >= 3]
    for b in projects:
        if any(t in b for t in toks):
            return b
    # 3) เหลือเรื่องเดียว ใช้เลย
    return projects[0] if len(projects) == 1 else None


def _project_files(title):
    """หา outline/characters/chapter ของเรื่อง (จับคู่ base name แบบยืดหยุ่น)"""
    base = _match_base(title) or _slug(title)
    outline = _find("02_Concept_Extraction", f"{base}_Outline.md")
    chars = _find("04_Character_Database", f"{base}_Characters.md")
    chapter = _find("05_Active_Projects/Chapters", f"{base}_Chapter_01.md")
    return outline, chars, chapter


def _save(folder, name, content):
    d = os.path.join(AP, folder)
    os.makedirs(d, exist_ok=True)
    fp = os.path.join(d, name)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(content)
    return fp


# ---------------------------------------------------------------------------
# 3. Visual prompts — ภาพตัวละคร + ฉาก/คอนเซ็ป (สำหรับ image gen)
# ---------------------------------------------------------------------------
def visual_prompts(title):
    outline, chars, chapter = _project_files(title)
    src = _read(chars) or _read(outline)
    if not src:
        return {"ok": False, "error": f"ไม่พบข้อมูลตัวละคร/โครงเรื่องของ '{title}'"}
    prompt = f"""คุณคือ Concept Artist & Prompt Engineer สร้าง image-generation prompts จากนิยายไทย
ข้อมูลตัวละคร/โครงเรื่อง:
{src[:6000]}

สร้าง prompt ภาษาอังกฤษ (ใช้ได้กับ Midjourney/Imagen/Flux/SDXL) ตอบ JSON เท่านั้น:
{{
  "characters": [
    {{"name":"ชื่อตัวละคร","prompt":"detailed English portrait prompt: appearance, age, clothing, mood, art style, lighting","negative":"things to avoid"}}
  ],
  "scenes": [
    {{"title":"ชื่อฉาก/คอนเซ็ป","prompt":"detailed English scene prompt: setting, atmosphere, composition, cinematic style"}}
  ],
  "style_guide":"แนวภาพรวมของเรื่อง (สี โทน สไตล์) เป็นภาษาอังกฤษ"
}}
(ตัวละคร 2-4 ตัว, ฉาก 3-5 ฉาก, PG-13, no text in image)"""
    data = generate_json(prompt, role="visual")
    md = [f"# 🎨 Visual Prompts: {title}", "", f"**Style:** {data.get('style_guide','')}", "", "## ตัวละคร"]
    for c in data.get("characters", []):
        md += [f"### {c.get('name','')}", f"```\n{c.get('prompt','')}\n```",
               f"*negative:* {c.get('negative','')}", ""]
    md += ["## ฉาก / คอนเซ็ป"]
    for s in data.get("scenes", []):
        md += [f"### {s.get('title','')}", f"```\n{s.get('prompt','')}\n```", ""]
    fp = _save("Visual_Prompts", f"{_match_base(title) or _slug(title)}_Visual.md", "\n".join(md))
    print(f"[visual] บันทึก {len(data.get('characters',[]))} ตัวละคร + {len(data.get('scenes',[]))} ฉาก → {fp}")
    return {"ok": True, "data": data, "file": fp}


# ---------------------------------------------------------------------------
# 4. Video prompts — shot-by-shot สำหรับ Google Flow (Veo) / Kling / Runway
# ---------------------------------------------------------------------------
def video_prompts(title):
    outline, chars, chapter = _project_files(title)
    src = _read(chapter) or _read(outline)
    if not src:
        return {"ok": False, "error": f"ไม่พบบท/โครงเรื่องของ '{title}'"}
    prompt = f"""คุณคือ AI Film Director สร้าง shot list + video-generation prompts จากนิยาย
สำหรับใช้กับ Google Flow (Veo 3), Kling, Runway Gen-3, Pika, Hailuo
เนื้อหา:
{src[:6000]}

แตกเป็น 5-8 ช็อตสำหรับทำเป็นคลิปสั้น (teaser/trailer) ตอบ JSON เท่านั้น:
{{
  "logline":"ประโยคขายเรื่องสั้นๆ",
  "shots":[
    {{"n":1,"duration_sec":5,"prompt":"detailed English video prompt: subject, action, setting, camera movement, lighting, mood, cinematic style","camera":"shot type + movement (e.g. slow dolly in)","audio_cue":"เสียง/ดนตรีที่ควรมี"}}
  ],
  "music":"แนวเพลงประกอบ","aspect_ratio":"9:16"
}}
(ภาษาอังกฤษในช่อง prompt, PG-13, ต่อเนื่องเล่าเรื่องได้)"""
    data = generate_json(prompt, role="video")
    md = [f"# 🎬 Video / Flow Prompts: {title}", "",
          f"**Logline:** {data.get('logline','')}", f"**Music:** {data.get('music','')} | **Ratio:** {data.get('aspect_ratio','9:16')}",
          "", "> ใช้กับ: Google Flow (Veo 3) · Kling · Runway Gen-3 · Pika · Hailuo", "", "## Shot List"]
    for s in data.get("shots", []):
        md += [f"### Shot {s.get('n','')} ({s.get('duration_sec','')}s) — {s.get('camera','')}",
               f"```\n{s.get('prompt','')}\n```", f"*audio:* {s.get('audio_cue','')}", ""]
    fp = _save("Video_Prompts", f"{_match_base(title) or _slug(title)}_Video.md", "\n".join(md))
    print(f"[video] บันทึก {len(data.get('shots',[]))} ช็อต → {fp}")
    return {"ok": True, "data": data, "file": fp}


# ---------------------------------------------------------------------------
# 5. Story bible — รวมโลก/ตัวละคร/กฎ เป็นไฟล์เดียว
# ---------------------------------------------------------------------------
def story_bible(title):
    outline, chars, chapter = _project_files(title)
    parts = [f"# 📖 Story Bible: {title}", ""]
    if outline:
        parts += ["## โครงเรื่อง & กฎของโลก", _read(outline), ""]
    if chars:
        parts += ["## ฐานข้อมูลตัวละคร", _read(chars), ""]
    fp = _save("Story_Bible", f"{_match_base(title) or _slug(title)}_Bible.md", "\n".join(parts))
    print(f"[bible] → {fp}")
    return {"ok": True, "file": fp}


# ---------------------------------------------------------------------------
# 3b. Audio script — (สร้าง/อัปเดต) script นิยายเสียงจากบท
# ---------------------------------------------------------------------------
def audio_script(title, ch=1):
    base = _match_base(title) or _slug(title)
    ch_fp = _find("05_Active_Projects/Chapters", f"{base}_Chapter_{int(ch):02d}.md")
    text = _read(ch_fp)
    if not text:
        return {"ok": False, "error": f"ไม่พบบทที่ {ch} ของ '{title}'"}
    from agent_writer import run_stage_6_audio_script
    out = run_stage_6_audio_script(f"{title} ตอนที่ {ch}", text)
    fp = _save("Audio_Scripts", f"{base}_AudioScript_{int(ch):02d}.md", out)
    print(f"[audio-script] → {fp} ({len(out)} ตัวอักษร)")
    return {"ok": True, "file": fp, "chars": len(out)}


# ---------------------------------------------------------------------------
# 0. develop → promote → write (คลิกเดียวจบ)
# ---------------------------------------------------------------------------
def develop_promote_write(idea_id):
    import ideation
    print("[1/3] 🧩 พัฒนาเนื้อหา (คอนเซ็ป/ตัวละคร/ชื่อ/ปม)...", flush=True)
    ideation.develop_idea(idea_id, "all")
    print("[2/3] 📤 promote เข้าคิวเขียน...", flush=True)
    pool_fp = ideation.promote(idea_id)
    if not pool_fp:
        print("[!] promote ล้มเหลว")
        return False
    hit = ideation._find_idea(idea_id)
    title = hit[1].get("title") if hit else None
    print(f"[3/3] ✍️ เขียนนิยาย: {title} ...", flush=True)
    from agent_writer import process_analyzed_novels
    process_analyzed_novels(SB, only=title)
    print("✅ เสร็จครบ — พัฒนา → promote → เขียน", flush=True)
    return True


# ---------------------------------------------------------------------------
# 1. Idea loop — คอมเมนต์ + ขัดเกลาไอเดียทีละรอบ
# ---------------------------------------------------------------------------
def idea_loop(idea_id, rounds=3):
    import ideation
    match = [(fp, fm, b) for fp, fm, b in ideation.load_ideas() if fm.get("id") == idea_id or idea_id in fp]
    if not match:
        print(f"[idea-loop] ไม่พบไอเดีย {idea_id}")
        return {"ok": False, "error": "ไม่พบไอเดีย"}
    fp, fm, body = match[0]
    current = f"{fm.get('title','')}\n{fm.get('logline','')}\n{body}"
    history = []
    for r in range(1, rounds + 1):
        print(f"\n===== IDEA LOOP รอบ {r}/{rounds} =====")
        critique = generate(
            f"วิจารณ์ไอเดียนิยายนี้แบบตรงไปตรงมา ชี้จุดอ่อน + เสนอวิธีทำให้ปังขึ้น (สั้น กระชับ):\n{current}",
            role="editor")
        print(f"[คอมเมนต์] {critique[:200]}")
        current = generate(
            f"ปรับปรุงไอเดียนิยายนี้ตามคำวิจารณ์ ให้ดีขึ้นชัดเจน (คงเป็นไอเดีย/logline/premise สั้นๆ):\n\nไอเดียเดิม:\n{current}\n\nคำวิจารณ์:\n{critique}",
            role="brainstorm", temperature=0.9)
        print(f"[ปรับปรุง] {current[:200]}")
        history.append({"round": r, "critique": critique, "improved": current})
    # บันทึกผลกลับเข้าไอเดีย
    body2 = body + f"\n\n## 🔄 ผลจาก AI Loop ({rounds} รอบ)\n{current}\n"
    ideation.write_md(fp, fm, body2)
    print(f"[idea-loop] เสร็จ {rounds} รอบ บันทึกแล้ว")
    return {"ok": True, "rounds": history, "final": current}


# ---------------------------------------------------------------------------
# 2. Chapter loop — คอมเมนต์ (3 มุมมอง) + เขียนใหม่ทีละรอบ
# ---------------------------------------------------------------------------
def chapter_loop(title, ch=1, rounds=2):
    _, chars, _ = _project_files(title)
    ch_fp = _find("05_Active_Projects/Chapters", f"*{_slug(title)}*_Chapter_{int(ch):02d}.md")
    if not ch_fp:
        return {"ok": False, "error": f"ไม่พบบทที่ {ch} ของ '{title}'"}
    text = _read(ch_fp)
    characters = _read(chars)
    history = []
    for r in range(1, rounds + 1):
        print(f"\n===== CHAPTER LOOP รอบ {r}/{rounds} =====")
        review = generate(
            f"""คุณคือทีมวิจารณ์ 3 คน (นักอ่านสายมวลชน / บรรณาธิการ / นักการตลาด)
วิจารณ์บทนี้แบบตรงไปตรงมา ชี้จุดที่ควรปรับ 3-5 ข้อ:
{text[:8000]}""", role="reviewer")
        print(f"[รีวิว] {review[:200]}")
        from agent_writer import strip_meta, NO_META, generate_content_safe
        text = strip_meta(generate_content_safe("enhancer",
            f"""เขียนบทนี้ใหม่ตามคำวิจารณ์ ให้ดีขึ้นชัดเจน คงโครงเรื่อง/ตัวละครเดิม:

ข้อมูลตัวละคร:
{characters[:1500]}

บทเดิม:
{text[:8000]}

คำวิจารณ์:
{review}""" + NO_META))
        history.append({"round": r, "review": review, "chars": len(text)})
        print(f"[เขียนใหม่] {len(text)} ตัวอักษร")
    with open(ch_fp, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[chapter-loop] เสร็จ {rounds} รอบ บันทึกทับบทเดิมแล้ว")
    return {"ok": True, "rounds": history, "chars": len(text)}


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "help"
    if cmd == "visual" and len(a) > 1:
        visual_prompts(a[1])
    elif cmd == "video" and len(a) > 1:
        video_prompts(a[1])
    elif cmd == "bible" and len(a) > 1:
        story_bible(a[1])
    elif cmd == "devwrite" and len(a) > 1:
        develop_promote_write(a[1])
    elif cmd == "audio-script" and len(a) > 1:
        audio_script(a[1], int(a[2]) if len(a) > 2 else 1)
    elif cmd == "idea-loop" and len(a) > 1:
        idea_loop(a[1], int(a[2]) if len(a) > 2 else 3)
    elif cmd == "chapter-loop" and len(a) > 1:
        chapter_loop(a[1], int(a[2]) if len(a) > 2 else 1, int(a[3]) if len(a) > 3 else 2)
    else:
        print(__doc__)
