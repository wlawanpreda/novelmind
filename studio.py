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


# อักษรจีน/ญี่ปุ่น/เกาหลีที่ LLM มักหลุดมาในบทเสียง — ต้องตัดทิ้ง
_NON_THAI_CJK = re.compile(r"[　-〿㐀-䶿一-鿿豈-﫿가-힯]")


def narration_script(title, ch=1):
    """สร้างบทเสียง 'ผู้บรรยายล้วน' ตรงจากบทไทย (ไม่ผ่าน LLM = ไม่มีทางหลุดภาษาอื่น/cue)
    ใช้กู้บทเสียงที่เพี้ยน (เช่น LLM drift เป็นจีน) ให้กลับมาเป็นไทยสะอาด อ่านได้จริง"""
    base = _match_base(title) or _slug(title)
    ch_fp = _find("05_Active_Projects/Chapters", f"{base}_Chapter_{int(ch):02d}.md")
    text = _read(ch_fp)
    if not text:
        return {"ok": False, "error": f"ไม่พบบทที่ {ch} ของ '{title}'"}
    # ล้าง: เครดิต/heading/markdown/CJK ที่หลุด
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith("#") or s.startswith(">"):
            continue
        if re.match(r"^(inspired by|source|แรงบันดาลใจ|ที่มา|คำโปรย|logline)\b", s, re.IGNORECASE):
            continue
        s = re.sub(r"[*_`>#]", "", s)              # markdown
        s = _NON_THAI_CJK.sub("", s).strip()        # อักษรจีน/เกาหลีที่หลุด
        if len(s) >= 2:
            lines.append(s)
    if not lines:
        return {"ok": False, "error": "บทว่าง/ไม่มีเนื้อไทย"}
    # แตกย่อหน้ายาวเป็นช่วง ~220 ตัว (ตามขอบเครื่องหมายวรรค) ให้ SRT ละเอียดขึ้น
    segs = []
    for para in lines:
        if len(para) <= 240:
            segs.append(para)
            continue
        buf = ""
        for part in re.split(r"(?<=[\.\!\?…”\"])\s+|(?<=[ฯๆ])\s+", para):
            if len(buf) + len(part) > 220 and buf:
                segs.append(buf.strip())
                buf = part
            else:
                buf = (buf + " " + part).strip()
        if buf.strip():
            segs.append(buf.strip())
    body = "# บทเสียง (ผู้บรรยายล้วน)\n\n" + "\n\n".join(segs) + "\n"
    fp = _save("Audio_Scripts", f"{base}_AudioScript_{int(ch):02d}.md", body)
    print(f"[narration] → {fp} ({len(segs)} ช่วง, {sum(len(s) for s in segs)} ตัวอักษรไทย)")
    return {"ok": True, "file": fp, "segments": len(segs)}


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
# 2. Chapter loop — เกลาบทหลายรูปแบบ (mode) + คำสั่งผู้ใช้ + AI วิจารณ์เอง
# ---------------------------------------------------------------------------
# แต่ละโหมด: review = AI วิจารณ์มุมไหน, rewrite = เขียนใหม่เน้นอะไร
REFINE_MODES = {
    "critique": {
        "label": "🧠 AI วิจารณ์เอง (3 มุมมอง)",
        "review": "คุณคือทีมวิจารณ์ 3 คน (นักอ่านสายมวลชน / บรรณาธิการ / นักการตลาด) "
                  "วิจารณ์บทนี้ตรงไปตรงมา ชี้จุดที่ควรปรับ 3-5 ข้อ พร้อมวิธีแก้ที่เป็นรูปธรรม",
        "rewrite": "เขียนบทนี้ใหม่ให้ดีขึ้นชัดเจนตามคำวิจารณ์ คงโครงเรื่อง/ตัวละคร/ความยาวใกล้เคียง",
    },
    "polish": {
        "label": "✨ เกลาสำนวนให้ลื่น",
        "review": "ชี้จุดสำนวนที่สะดุด ซ้ำคำ ประโยคพัง จังหวะไม่ลื่น คำฟุ่มเฟือย",
        "rewrite": "เกลาสำนวนให้คม ลื่นไหล สละสลวย แก้จุดที่สะดุด คงเนื้อหา/เหตุการณ์/ความยาวเดิม",
    },
    "concise": {
        "label": "✂️ กระชับ ตัดน้ำ",
        "review": "ชี้ส่วนที่ยืดเยื้อ ซ้ำซาก บรรยายเกินจำเป็น น้ำเยอะ",
        "rewrite": "ตัดส่วนเกิน กระชับ เข้มข้นขึ้น คงใจความและฉากสำคัญทั้งหมด (สั้นลงได้ ~15-25%)",
    },
    "dialogue": {
        "label": "💬 เพิ่ม/เกลาบทสนทนา",
        "review": "ชี้จุดที่บรรยายมากเกิน บทสนทนาน้อย/แข็ง/ไม่เป็นธรรมชาติ ตัวละครเสียงไม่ชัด",
        "rewrite": "เพิ่มบทสนทนาให้สมดุลกับบรรยาย เป็นธรรมชาติ มีเสียง/บุคลิกตัวละครชัด ลด monologue ภายในที่ยาว",
    },
    "audiobook": {
        "label": "🎧 ปรับให้เหมาะหนังสือเสียง",
        "review": "ชี้ stat-block/ตัวเลข/UI เกม/สัญลักษณ์ที่อ่านออกเสียงแล้วสะดุด และประโยคยาวซ้อนอนุประโยคที่ฟังเหนื่อย",
        "rewrite": "แปลงข้อความระบบ/ตัวเลข/UI เป็นประโยคที่อ่านออกเสียงลื่น ตัดสัญลักษณ์ที่อ่านไม่ได้ "
                   "(เช่น HP 5/80 → 'พลังชีวิตเหลือห้าจากแปดสิบ') จัดจังหวะประโยคให้ฟังสบาย คงเนื้อหาเดิม",
    },
    "vivid": {
        "label": "🌄 เพิ่มบรรยากาศ/อารมณ์",
        "review": "ชี้ฉากที่ขาดบรรยากาศ ขาด sensory detail หรืออารมณ์ตื้นเกินไป",
        "rewrite": "เพิ่มรายละเอียดประสาทสัมผัสและความลึกของอารมณ์ในจุดสำคัญ คงเหตุการณ์เดิม ไม่ยืดเยื้อเกิน",
    },
}


def list_refine_modes():
    return [{"key": k, "label": v["label"]} for k, v in REFINE_MODES.items()]


def ab_variants(title):
    """สร้างตัวเลือก A/B/C ของ ชื่อเรื่อง/hook/ปก เพื่อนำไปทดสอบว่าแบบไหนปัง"""
    import json as _json
    base = _slug(title)
    outline = _read(_find("02_Concept_Extraction", f"{base}_Outline.md") or "")
    prompt = f"""คุณคือครีเอทีฟโฆษณา สร้างตัวเลือกทดสอบ A/B/C (3 แบบ แนวต่างกันชัด) สำหรับนิยายเรื่องนี้
เพื่อนำไปปล่อยเทียบว่าแบบไหนคนคลิก/ดูมากกว่า
เรื่อง: {title}
โครงเรื่องย่อ: {outline[:1600]}

ตอบ JSON เท่านั้น:
{{"variants": [
  {{"label": "A", "angle": "มุมขาย (เช่น ดราม่า/แอ็คชัน/ปริศนา)",
    "title": "ชื่อเรื่อง/คลิป", "hook": "ประโยค hook เปิด", "cover_concept": "ไอเดียปกสั้นๆ"}},
  {{"label": "B", ...}}, {{"label": "C", ...}}
]}}"""
    try:
        raw = generate(prompt, role="brainstorm", is_json=True, temperature=1.0)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        d = _json.loads(m.group(0) if m else raw)
    except Exception as e:
        return {"ok": False, "error": f"สร้างไม่ได้: {e}"}
    md = f"# 🔀 A/B Variants: {title}\n\n"
    for v in d.get("variants", []):
        md += (f"## ตัวเลือก {v.get('label','')} — {v.get('angle','')}\n"
               f"- **ชื่อ:** {v.get('title','')}\n"
               f"- **Hook:** {v.get('hook','')}\n"
               f"- **ไอเดียปก:** {v.get('cover_concept','')}\n\n")
    out = _save("AB_Tests", f"{base}_AB.md", md)
    print(f"[ab] {title} → {len(d.get('variants',[]))} ตัวเลือก → {out}")
    d["ok"] = True
    d["file"] = out
    return d


def caption_seo(title):
    """สร้างแคปชั่น+แฮชแท็ก+SEO ต่อคลิป (YouTube/TikTok) — ก่อนเผยแพร่"""
    import json as _json
    base = _slug(title)
    outline = _read(_find("02_Concept_Extraction", f"{base}_Outline.md") or "")
    prompt = f"""คุณคือนักการตลาดคอนเทนต์ไวรัล สร้างแคปชั่น+แฮชแท็กให้คลิป teaser นิยายเรื่องนี้ ให้ดึงคนคลิกสูงสุด
เรื่อง: {title}
โครงเรื่องย่อ: {outline[:1800]}

ตอบ JSON เท่านั้น:
{{
  "youtube_title": "ชื่อคลิป YouTube ดึงคลิก ไม่เกิน 60 ตัวอักษร",
  "youtube_desc": "คำบรรยาย YouTube 2-3 ย่อหน้า น่าสนใจ + call-to-action ให้กดติดตาม",
  "tiktok_caption": "แคปชั่น TikTok สั้น กระชับ มีอิโมจิ ชวนดูจนจบ",
  "hook_line": "ประโยคเปิดตรึงคนใน 3 วินาทีแรก",
  "hashtags": ["#แฮชแท็ก", "...10-12 อัน ผสมไทย+อังกฤษ ตรงกลุ่มนิยาย/แนวเรื่อง"]
}}"""
    try:
        raw = generate(prompt, role="researcher", is_json=True)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        d = _json.loads(m.group(0) if m else raw)
    except Exception as e:
        return {"ok": False, "error": f"สร้างไม่ได้: {e}"}
    md = f"""# 🏷️ Caption & SEO: {title}

## ▶️ YouTube
**ชื่อคลิป:** {d.get('youtube_title','')}

{d.get('youtube_desc','')}

## 🎵 TikTok
{d.get('tiktok_caption','')}

## 🪝 Hook (3 วิแรก)
{d.get('hook_line','')}

## #️⃣ Hashtags
{' '.join(d.get('hashtags', []))}
"""
    out = _save("Captions", f"{base}_Caption.md", md)
    print(f"[caption] {title} → {out}")
    d["ok"] = True
    d["file"] = out
    return d


def continuity_check(title):
    """ตรวจความต่อเนื่องข้ามตอน: ชื่อตัวละคร/กฎโลก/ตัวเลข/พล็อต ขัดกันไหม (แก้ปัญหาชื่อไม่ตรง)"""
    import json as _json
    base = _slug(title)
    outline = _read(_find("02_Concept_Extraction", f"{base}_Outline.md") or "")
    chars = _read(_find("04_Character_Database", f"{base}_Characters.md") or "")
    chapters = sorted(glob.glob(os.path.join(SB, "05_Active_Projects", "Chapters", f"{base}_Chapter_*.md")))
    if not chapters:
        return {"ok": False, "error": "ไม่พบบท"}
    joined = "\n\n".join(f"[ตอน {i+1}]\n{_read(c)[:3500]}" for i, c in enumerate(chapters))
    prompt = f"""คุณคือ Continuity Editor ตรวจความต่อเนื่องของนิยายข้ามตอน
หาจุดที่ "ขัดแย้งกันเอง" โดยเฉพาะ: ชื่อตัวละครไม่ตรงกันข้ามตอน/ไฟล์, กฎของโลก/ระบบขัดกัน,
ตัวเลข/สถานะไม่ต่อเนื่อง, เหตุการณ์ซ้ำ/ขัดกัน

โครงเรื่อง: {outline[:2000]}
ตัวละคร: {chars[:1500]}
บททั้งหมด (ช่วงต้นแต่ละตอน):
{joined[:9000]}

ตอบ JSON เท่านั้น:
{{"consistent": <true/false>, "score": <1-10>,
  "conflicts": ["จุดขัดแย้ง 1 (ระบุตอน)", "2"],
  "name_issues": ["ชื่อที่ไม่ตรง เช่น ตอน1 ใช้ X ตอน2 ใช้ Y"],
  "fix_suggestions": ["วิธีแก้ 1", "2"]}}"""
    try:
        from llm_provider import generate
        raw = generate(prompt, role="reviewer", is_json=True)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = _json.loads(m.group(0) if m else raw)
    except Exception as e:
        return {"ok": False, "error": f"ตรวจไม่ได้: {e}"}
    out = _save("Story_Bible", f"{base}_Continuity.md",
                f"# Continuity Check: {title}\n\n```json\n{_json.dumps(data, ensure_ascii=False, indent=2)}\n```\n")
    print(f"[continuity] {title}: score {data.get('score')}/10 · consistent={data.get('consistent')}")
    data["ok"] = True
    data["file"] = out
    return data


def auto_qa(title, ch=1):
    """Auto-QA: LLM ให้คะแนนคุณภาพบท (1-10) + ชี้จุดต้องแก้ + คำตัดสิน"""
    import json as _json
    ch_fp = _find("05_Active_Projects/Chapters", f"*{_slug(title)}*_Chapter_{int(ch):02d}.md")
    if not ch_fp:
        return {"ok": False, "error": f"ไม่พบบทที่ {ch}"}
    text = _read(ch_fp)
    prompt = f"""คุณคือบรรณาธิการนิยายไทยมืออาชีพ ตรวจคุณภาพบทนี้อย่างเข้มงวดเพื่อตัดสินว่าพร้อมเผยแพร่ไหม
ให้คะแนน 1-10 ในแต่ละด้าน แล้วสรุป

บท (ตอนที่ {ch}):
{text[:9000]}

ตอบ JSON เท่านั้น:
{{
  "prose": <1-10 สำนวน/ความลื่นไหล>,
  "engagement": <1-10 ความน่าติดตาม/hook>,
  "consistency": <1-10 ความสอดคล้องของกฎ/ชื่อ/ตัวเลข>,
  "audiobook": <1-10 เหมาะอ่านออกเสียง>,
  "overall": <1-10 รวม>,
  "verdict": "<ready=พร้อมปล่อย | revise=ควรแก้ก่อน | rewrite=ต้องเขียนใหม่>",
  "issues": ["จุดที่ต้องแก้ 1", "2", "3"],
  "strengths": ["จุดเด่น 1", "2"]
}}"""
    try:
        from llm_provider import generate
        raw = generate(prompt, role="reviewer", is_json=True)
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = _json.loads(m.group(0) if m else raw)
    except Exception as e:
        return {"ok": False, "error": f"QA ล้มเหลว: {e}"}
    print(f"[auto-qa] {title} ตอน {ch}: overall {data.get('overall')}/10 · {data.get('verdict')}")
    # บันทึกผล QA ลงไฟล์ให้ดูย้อนหลัง
    out = _save("QA_Reports", f"{_slug(title)}_QA_{int(ch):02d}.md",
                f"# QA: {title} ตอน {ch}\n\n```json\n{_json.dumps(data, ensure_ascii=False, indent=2)}\n```\n")
    data["ok"] = True
    data["file"] = out
    return data


def chapter_loop(title, ch=1, rounds=2, mode="critique", note=""):
    import shutil
    _, chars, _ = _project_files(title)
    ch_fp = _find("05_Active_Projects/Chapters", f"*{_slug(title)}*_Chapter_{int(ch):02d}.md")
    if not ch_fp:
        return {"ok": False, "error": f"ไม่พบบทที่ {ch} ของ '{title}'"}
    spec = REFINE_MODES.get(mode, REFINE_MODES["critique"])
    text = _read(ch_fp)
    characters = _read(chars)
    note = (note or "").strip()
    note_block = (f"\n\n📌 คำสั่ง/เป้าหมายเพิ่มเติมจากผู้ใช้ (สำคัญที่สุด ทำตามนี้ก่อน):\n{note}\n") if note else ""
    min_chars = max(int(len(text) * 0.4), 800)   # กันผลลัพธ์สั้นผิดปกติ (LLM ล่ม)

    # สำรองบทเดิมก่อนเขียนทับ (เก็บประวัติเวอร์ชันสะสม + .bak ล่าสุด)
    try:
        shutil.copy(ch_fp, ch_fp + ".bak")
        import versions
        versions.snapshot(ch_fp, f"ก่อนเกลา-{mode}")
    except Exception:
        pass

    print(f"[chapter-loop] โหมด: {spec['label']} · ตอน {ch} · {rounds} รอบ"
          + (f" · มีคำสั่งผู้ใช้" if note else ""))
    from agent_writer import strip_meta, NO_META, generate_content_safe
    history = []
    for r in range(1, rounds + 1):
        print(f"\n===== CHAPTER LOOP รอบ {r}/{rounds} ({mode}) =====")
        review = generate(
            f"""{spec['review']}{note_block}
บท:
{text[:8000]}""", role="reviewer")
        print(f"[วิจารณ์] {review[:240]}")
        new = strip_meta(generate_content_safe("enhancer",
            f"""{spec['rewrite']}{note_block}
ข้อมูลตัวละคร (คงให้ตรง):
{characters[:1500]}

บทเดิม:
{text[:8000]}

คำวิจารณ์ (แก้ตามนี้):
{review}""" + NO_META))
        if len(new) < min_chars:
            print(f"[!] รอบ {r}: ผลลัพธ์สั้นผิดปกติ ({len(new)}<{min_chars}) — ข้ามรอบนี้ กันบทพัง")
            history.append({"round": r, "review": review, "chars": len(text), "skipped": True})
            continue
        text = new
        history.append({"round": r, "review": review, "chars": len(text)})
        print(f"[เขียนใหม่] {len(text)} ตัวอักษร")

    with open(ch_fp, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"[chapter-loop] เสร็จ {rounds} รอบ ({spec['label']}) บันทึกแล้ว (สำรองเดิมที่ .bak)")
    return {"ok": True, "mode": mode, "rounds": history, "chars": len(text)}


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
        chapter_loop(a[1], int(a[2]) if len(a) > 2 else 1, int(a[3]) if len(a) > 3 else 2,
                     a[4] if len(a) > 4 else "critique", a[5] if len(a) > 5 else "")
    elif cmd == "auto-qa" and len(a) > 1:
        import json as _j
        print(_j.dumps(auto_qa(a[1], int(a[2]) if len(a) > 2 else 1), ensure_ascii=False, indent=2))
    elif cmd == "continuity" and len(a) > 1:
        import json as _j
        print(_j.dumps(continuity_check(a[1]), ensure_ascii=False, indent=2))
    elif cmd == "caption" and len(a) > 1:
        import json as _j
        print(_j.dumps(caption_seo(a[1]), ensure_ascii=False, indent=2))
    elif cmd == "abtest" and len(a) > 1:
        import json as _j
        print(_j.dumps(ab_variants(a[1]), ensure_ascii=False, indent=2))
    else:
        print(__doc__)
