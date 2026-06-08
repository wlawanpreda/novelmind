import os
import re
import json
import sys
import glob
from typing import Dict, Any, Tuple, List
from datetime import datetime
from llm_provider import generate, resolve_backend

# Load environment variables from .env file if it exists
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Setup Gemini API Key (required only if any writing stage routes to gemini)
API_KEY = os.environ.get("GEMINI_API_KEY")
_WRITER_ROLES = ("outline", "characters", "planner", "writer", "enhancer", "audio")
if not API_KEY and "gemini" in {resolve_backend(r) for r in _WRITER_ROLES}:
    print("[!] ERROR: GEMINI_API_KEY is not set and a writing stage routes to gemini.")
    print("    Set GEMINI_API_KEY, or use LLM_BACKEND=local for a fully local run.")
    sys.exit(1)

def parse_markdown_file(filepath: str) -> Tuple[Dict[str, Any], str]:
    """Parse Obsidian markdown file and separate frontmatter from body content."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    frontmatter = {}
    body = content
    
    # Match YAML frontmatter
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        
        # Simple YAML parser for key-value strings
        for line in yaml_text.splitlines():
            if ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                
                # Check for tags list
                if key == "tags":
                    frontmatter[key] = []
                elif line.startswith("  - ") and "tags" in frontmatter:
                    tag_val = line.replace("  - ", "").strip().strip('"').strip("'")
                    frontmatter["tags"].append(tag_val)
                else:
                    frontmatter[key] = val
                    
    return frontmatter, body

def update_markdown_file(filepath: str, frontmatter: Dict[str, Any], body: str):
    """Write back frontmatter and updated body to the markdown file."""
    yaml_lines = ["---"]
    for k, v in frontmatter.items():
        if k == "tags" and isinstance(v, list):
            yaml_lines.append("tags:")
            for tag in v:
                yaml_lines.append(f"  - {tag}")
        else:
            yaml_lines.append(f'{k}: "{v}"')
    yaml_lines.append("---\n")
    
    full_content = "\n".join(yaml_lines) + body
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(full_content)

# ----------------- ✍️ Multi-Stage Creative Writing Engine -----------------

# คำสั่งมาตรฐานต่อท้าย prompt: กัน AI พูดถึงตัวเอง/ใส่คำนำ-คำลงท้าย
NO_META = ("\n\n[สำคัญ] ส่งคืน 'เฉพาะเนื้อหา' เท่านั้น "
           "ห้ามมีคำนำ คำทักทาย การบรรยายบทบาทตัวเอง (เช่น 'ในฐานะ...', 'ผมขอ...', "
           "'นี่คือผลลัพธ์...') หรือคำลงท้ายใดๆ เริ่มที่เนื้อหาจริงทันที")

# วลีที่บ่งบอกว่าเป็น meta-talk ของ AI (ใช้ตัดทิ้งหัว/ท้าย)
_META_MARK = ("ในฐานะ", "chief", "ข้าพเจ้า", "ผมขอ", "ผมจะ", "นี่คือผลลัพธ์", "นี่คือบท",
              "นี่คือโครง", "ยอดเยี่ยม", "ตามที่ท่าน", "ตามที่คุณ", "คำบัญชา", "เจียระไน",
              "ขอรับช่วง", "ด้วยความยินดี", "ผมได้", "ข้าพเจ้าได้", "หวังว่า", "เรียบร้อยแล้วครับ")


def _tone_note() -> str:
    """โทนการเขียนที่ผู้ใช้กำหนดผ่าน ANSRE_TONE (เช่น 'ตลกเบาสมอง ภาษาง่ายๆ')"""
    t = os.environ.get("ANSRE_TONE", "").strip()
    return f"\n\n[โทน/สไตล์ที่ต้องการ — สำคัญมาก ให้ยึดเป็นหลัก] {t}" if t else ""


def strip_meta(text: str) -> str:
    """ตัด meta-talk ของ AI ที่หัว/ท้ายออก (เช่น 'ในฐานะ Chief Editor ข้าพเจ้า...')"""
    if not text:
        return text
    lines = text.split("\n")
    # ตัดหัว: ลบบรรทัดว่าง / meta / '---' เดี่ยวๆ (สูงสุด 8 บรรทัดแรก เพื่อความปลอดภัย)
    popped = 0
    while lines and popped < 8:
        s = lines[0].strip()
        if s == "" or s == "---" or any(m in s.lower() for m in _META_MARK):
            lines.pop(0)
            popped += 1
        else:
            break
    # ตัดท้าย: ลบบรรทัดว่าง / meta / '---' เดี่ยวๆ ท้ายไฟล์
    popped = 0
    while lines and popped < 5:
        s = lines[-1].strip()
        if s == "" or s == "---" or any(m in s.lower() for m in _META_MARK):
            lines.pop()
            popped += 1
        else:
            break
    return "\n".join(lines).strip()


def generate_content_safe(role: str, prompt: str, is_json: bool = False) -> str:
    """Generate content via the unified provider (gemini/local chosen by role).

    `role` is the writing stage name (outline/characters/planner/writer/enhancer/audio).
    Retries + safety settings are handled inside llm_provider.generate.
    """
    try:
        text = generate(prompt, role=role, is_json=is_json)
        if text:
            return text
    except Exception as e:  # noqa: BLE001
        print(f"[!] Exception during generation (role={role}): {e}")

    # Final fallback attempt with a softened, PG-13 instruction
    try:
        return generate(
            prompt + "\n[Note: Please generate safe PG-13 content without extreme elements]",
            role=role, is_json=is_json,
        ) or "Error: Generation returned empty result."
    except Exception as e:  # noqa: BLE001
        return f"Error: {str(e)}"

def run_stage_1_outline(title: str, analysis: str) -> str:
    """Stage 1: Outline Architect - Generates detailed 10-chapter master plan."""
    print("    [Stage 1] Outline Architect: Expanding concept into 10-chapter master plan...")
    prompt = f"""
คุณคือ "Chief Outline Architect" ผู้แต่งโครงสร้างนิยายมืออาชีพ
วิเคราะห์แนวคิดนิยายเรื่อง: {title}
บทวิเคราะห์ความเหมาะสม:
{analysis}

จงขยายความและวางโครงเรื่องรายละเอียด 10 ตอนแรกสำหรับฉบับดัดแปลงสไตล์ไทยที่เป็น Original IP ใหม่ (ถูกกฎหมาย 100%)
ระบุหัวข้อประเด็นสำคัญ ปมความขัดแย้ง และจุดจบบทของแต่ละตอนเพื่อความตื่นเต้นดึงดูดใจ

ให้ผลลัพธ์เป็นข้อความ Markdown แบบเป็นสัดส่วน ประกอบด้วย:
1. ชื่อเรื่องภาษาไทยอย่างเป็นทางการ และคำโปรยสั้น (Logline)
2. แนวคิดแกนเรื่อง (Core Premise / World Building Rules)
3. รายละเอียดตอนที่ 1 ถึงตอนที่ 10 (อธิบายเนื้อหาและเป้าหมายตัวละครย่อยแต่ละตอนอย่างกระชับ)
"""
    return strip_meta(generate_content_safe("outline", prompt + _tone_note() + NO_META))

def run_stage_2_characters(title: str, outline: str) -> str:
    """Stage 2: Character Sculptor - Designs detailed character database."""
    print("    [Stage 2] Character Sculptor: Designing deep character profiles...")
    prompt = f"""
คุณคือ "Character Sculptor" ผู้เชี่ยวชาญด้านการออกแบบมิติตัวละครที่น่าจดจำ
อ้างอิงจากโครงเรื่องนิยายเรื่อง {title} ด้านล่างนี้:
{outline}

จงสร้างระบบฐานข้อมูลตัวละครที่ดัดแปลงเป็นบริบทไทยอย่างละเอียด ประกอบด้วย:
1. ตัวละครเอก (อคิน): ชื่อจริง นามสกุล อายุ ภูมิหลังการศึกษา ความสิ้นหวัง ความลับส่วนตัว จุดอ่อนร้ายแรง (Fatal Flaw) ความสามารถ และน้ำเสียงคำพูด
2. ตัวละครสมทบสำคัญ (เช่น วิญญาณ ผีเด็ก หรือเจ้าของแอปฯ)
3. ระบบความสัมพันธ์ (Character Dynamics/Conflict Matrix)
"""
    return strip_meta(generate_content_safe("characters", prompt + NO_META))

def run_stage_3_scene_planner(outline: str, characters: str) -> List[Dict[str, Any]]:
    """Stage 3: Scene Planner - Breaks down Chapter 1 into 4 logical beats."""
    print("    [Stage 3] Scene Planner: Breaking down Chapter 1 into 4 narrative beats...")
    prompt = f"""
คุณคือ "Screenwriter & Narrative Planner" ผู้เชี่ยวชาญการกำหนดฉาก
อ้างอิงจากโครงเรื่องนิยาย:
{outline}
และข้อมูลตัวละคร:
{characters}

จงแบ่งตอนที่ 1 (Chapter 1) ออกเป็น 4 ฉากย่อย (Beats) ที่มีเหตุผลและต่อเนื่องกัน เพื่อใช้เป็นแผนให้นักเขียนเขียนขยายความในขั้นตอนถัดไป
ให้ผลลัพธ์การวิเคราะห์เป็นรูปแบบ JSON เท่านั้น โดยมีโครงสร้างคีย์ดังนี้:
[
  {{
    "scene_number": "1",
    "setting": "สถานที่และบรรยากาศฉาก 1",
    "goal": "เป้าหมายตัวละครในฉากนี้",
    "action": "สิ่งที่เกิดขึ้นอย่างละเอียด",
    "climax": "จุดสำคัญหรืออารมณ์ฉากย่อยนี้"
  }},
  ... (รวมทั้งหมด 4 ฉาก)
]
"""
    res_text = generate_content_safe("planner", prompt, is_json=True)
    # ทน JSON ของ local model ที่อาจไม่ strict: coerce + fallback แทน crash
    for candidate in (res_text, re.sub(r"```json|```", "", res_text or "").strip()):
        try:
            data = json.loads(candidate)
            if isinstance(data, list) and data:
                return data
        except Exception:
            continue
    print("    [Stage 3] beats JSON ไม่ผ่าน — ใช้ fallback 4 ฉาก")
    return [{"scene_number": str(i + 1), "setting": f"ฉากที่ {i+1}", "goal": "เดินเรื่อง",
             "action": "เหตุการณ์ต่อเนื่องในตอน", "climax": "ปม/อารมณ์ของฉาก"} for i in range(4)]

def run_stage_4_scene_writer(title: str, scene_plan: Dict[str, str], prev_scenes_content: str, characters: str, world: str = "") -> str:
    """Stage 4: Draft Writer - Writes full detailed prose for a single scene."""
    scene_num = scene_plan.get("scene_number")
    print(f"    [Stage 4] Draft Writer: Writing detailed prose for Scene {scene_num}/4...")
    scene_words = int(os.environ.get("ANSRE_SCENE_WORDS", "450"))
    prompt = f"""
คุณคือ "Master Novelist" ผู้เชี่ยวชาญการแต่งนิยายพรรณนาภาษาไทยสละสลวยดึงดูดใจ
หน้าที่ของคุณคือแต่งเนื้อเรื่องฉากย่อยฉากนี้เพื่อประกอบเป็นนิยายตอนที่ 1 ของเรื่อง: {title}

กฎของโลก/ระบบในเรื่อง (ห้ามเขียนขัดแย้งกับสิ่งนี้เด็ดขาด):
{world[:2500]}

ข้อมูลตัวละครหลัก:
{characters}

เนื้อความฉากก่อนหน้านี้ (ถ้ามี):
{prev_scenes_content}

---
แผนการเขียนฉากที่ {scene_num} นี้:
- สถานที่/บรรยากาศ: {scene_plan.get("setting")}
- เป้าหมาย: {scene_plan.get("goal")}
- ลำดับเหตุการณ์: {scene_plan.get("action")}
- จุดสำคัญ/ความรู้สึกหลัก: {scene_plan.get("climax")}

คำแนะนำการแต่ง:
1. เขียนพรรณนาฉากอย่างลงลึกและสมจริงทางประสาทสัมผัส บรรยายบรรยากาศ แสง เงา เสียง กลิ่น และความรู้สึกทางกายภาพให้ผู้เขียนเห็นภาพชัดเจน
2. หลีกเลี่ยงสำนวนภาษาแปลกๆ หรือแปลตรงตัวจากต่างประเทศ ใช้สำนวนและภาษาไทยที่สละสลวย เป็นธรรมชาติ ลื่นไหล เข้ากับบริบทไทย
3. ใส่บทสนทนาโต้ตอบที่สมจริงสะท้อนอารมณ์ นัยยะ และลักษณะนิสัยเฉพาะของตัวละคร ห้ามสรุปความเด็ดขาด
4. เน้นอารมณ์ความตึงเครียด ความหวาดกลัว ความหวัง หรือความขัดแย้งภายในจิตใจของตัวละครเอกให้ลึกซึ้ง
5. แต่งให้กระชับ ลื่นไหล ได้อารมณ์ ความยาวประมาณ {scene_words} คำ (ห้ามยืดเยื้อ ห้ามน้ำท่วมทุ่ง)
6. ต้องสอดคล้องกับกฎของโลก/ระบบและฉากก่อนหน้า ไม่ขัดแย้งตัวเลข/สถานะใดๆ
"""
    return strip_meta(generate_content_safe("writer", prompt + _tone_note() + NO_META))

def run_stage_5_prose_enhancer(title: str, full_draft: str, characters: str, world: str = "") -> str:
    """Stage 5: Prose Enhancer - Polishes the compiled chapter, refines vocabulary and cliffhanger."""
    print("    [Stage 5] Editorial Prose Enhancer: Polishing vocabulary and Cliffhanger...")
    prompt = f"""
คุณคือ "Chief Literary Editor" ผู้เชี่ยวชาญด้านการขัดเกลาภาษานิยายออนไลน์ให้กลายเป็นผลงานระทึกขวัญระดับพรีเมียม
นี่คือดราฟต์ตอนแรกของนิยายเรื่อง {title}:
{full_draft}

กฎของโลก/ระบบในเรื่อง (ใช้ตรวจความสอดคล้อง ห้ามให้เนื้อหาขัดแย้งกับกฎหรือตัวเลข/สถานะ):
{world[:2500]}

ข้อมูลตัวละคร:
{characters}

กรุณาปรับแต่งขัดเกลาภาษานิยายตอนแรกนี้ โดย:
1. ขัดเกลาสำนวนพรรณนาให้สละสลวย มีวรรณศิลป์ ทรงพลัง และเห็นภาพเด่นชัด
2. ปรับจังหวะการเล่าเรื่อง (Pacing) บทสนทนา และการตัดบทให้กระชับ ลื่นไหล
3. ตรวจสำนวนสะกดคำและไวยากรณ์ไทย และ "แก้จุดที่ขัดแย้งกับกฎของระบบ/ตัวเลข/สถานะ" ให้ถูกต้อง
4. ปรับ Cliffhanger ปิดท้ายตอนให้ทิ้งปริศนาชวนอ่านต่อ
5. **ห้ามขยายความยาว** — รักษาความยาวใกล้เคียงดราฟต์เดิม เน้นเกลาให้คมขึ้น ไม่ใช่เพิ่มคำ
"""
    return strip_meta(generate_content_safe("enhancer", prompt + _tone_note() + NO_META))

def _chunk_text(text: str, size: int = 3000):
    """แบ่งข้อความเป็นท่อน ~size ตัวอักษร โดยตัดที่ขอบย่อหน้า (กัน audio output ทะลุ token limit)"""
    paras = text.split("\n\n")
    chunks, cur = [], ""
    for p in paras:
        if len(cur) + len(p) > size and cur:
            chunks.append(cur)
            cur = p
        else:
            cur += ("\n\n" if cur else "") + p
    if cur.strip():
        chunks.append(cur)
    return chunks or [text]


def run_stage_6_audio_script(title: str, final_chapter: str) -> str:
    """Stage 6: Audio Script Adapter — แปลงเป็นบทเสียงทีละท่อน (กัน output ยาวเกิน token limit)"""
    print("    [Stage 6] Audio Script Adapter: Generating audio production script...")
    rules = """กฎการเขียนบทเสียง:
1. ระบุผู้พูดและน้ำเสียงในวงเล็บเหลี่ยม เช่น [ผู้บรรยาย, โทน: หม่นหมอง] / [ระบบ, โทน: เย็นชา]
2. ระบุคิวเสียง [SFX: ...] แทรกได้
3. คงโครงเรื่องและอารมณ์ไว้ครบ ส่งคืนเฉพาะบทเสียง"""
    chunks = _chunk_text(final_chapter, 3000)
    parts = []
    for i, chunk in enumerate(chunks):
        print(f"        audio chunk {i+1}/{len(chunks)}...")
        prompt = (f"คุณคือ Audio Production Director แปลงเนื้อนิยายเรื่อง {title} "
                  f"(ท่อนที่ {i+1}/{len(chunks)}) ให้เป็นบทนิยายเสียงพากย์:\n{chunk}\n\n{rules}")
        seg = strip_meta(generate_content_safe("audio", prompt + NO_META))
        if seg and not seg.startswith("Error:"):
            parts.append(seg)
    return "\n\n".join(parts) if parts else "[ไม่สามารถสร้างบทเสียงได้]"

# ----------------- Main Orchestration Loop -----------------

def process_analyzed_novels(second_brain_dir: str):
    """Scan the pool for 'Analyzed' novels and execute the 6-stage writing pipeline."""
    scouting_pool_dir = os.path.join(second_brain_dir, "01_Scouting_Pool")
    md_files = glob.glob(os.path.join(scouting_pool_dir, "*.md"))
    
    print(f"[*] Scanning {len(md_files)} files in Scouting Pool for recreation...")
    
    processed_count = 0
    for filepath in md_files:
        try:
            frontmatter, body = parse_markdown_file(filepath)
            
            if frontmatter.get("status") != "Analyzed":
                continue
                
            novel_title = frontmatter.get('title')
            thai_title = frontmatter.get('thai_working_title', 'Recreation')
            print(f"\n[🚀] Starting Multi-Stage Writing pipeline for: '{thai_title}' (Inspired by '{novel_title}')...")
            
            # Stage 1: Detailed Outline Creation
            outline = run_stage_1_outline(novel_title, body)
            
            # Stage 2: Character Database Design
            characters = run_stage_2_characters(novel_title, outline)
            
            # Stage 3: Chapter 1 Beat planning
            scene_plans = run_stage_3_scene_planner(outline, characters)
            
            # Stage 4: Scene-by-scene iterative writing (Ensures length & depth)
            chapter_scenes = []
            prev_scenes_content = ""
            for idx, scene_plan in enumerate(scene_plans):
                scene_content = run_stage_4_scene_writer(novel_title, scene_plan, prev_scenes_content, characters, world=outline)
                chapter_scenes.append(scene_content)
                # Append to memory of prev scenes
                prev_scenes_content += f"\n\n--- [ฉากที่ {idx+1}] ---\n\n" + scene_content

            compiled_draft = "\n\n".join(chapter_scenes)

            # Stage 5: Editor Polishing & Enhancements
            final_chapter = run_stage_5_prose_enhancer(novel_title, compiled_draft, characters, world=outline)
            
            # Stage 6: Audio Script Formatting
            final_audio_script = run_stage_6_audio_script(novel_title, final_chapter)
            
            # Save files to Second Brain structure
            active_projects_dir = os.path.join(second_brain_dir, "05_Active_Projects")
            chapters_dir = os.path.join(active_projects_dir, "Chapters")
            audio_scripts_dir = os.path.join(active_projects_dir, "Audio_Scripts")
            
            os.makedirs(chapters_dir, exist_ok=True)
            os.makedirs(audio_scripts_dir, exist_ok=True)
            
            # เก็บอักษรไทย (รวมสระ/วรรณยุกต์ U+0E00–U+0E7F) ไม่ให้ถูกตัดทิ้ง
            clean_title = re.sub(r'[^\w\-_\s฀-๿]', '', thai_title)
            clean_title = clean_title.strip().replace(' ', '_')
            
            # Save Outline
            outline_path = os.path.join(second_brain_dir, "02_Concept_Extraction", f"{clean_title}_Outline.md")
            with open(outline_path, "w", encoding="utf-8") as f:
                f.write(f"# Outline & Concept: {thai_title}\n\nInspired by: {novel_title} ({frontmatter.get('source')})\n\n" + outline)
            print(f"[+] Saved Outline to: {outline_path}")
            
            # Save Characters DB
            chars_path = os.path.join(second_brain_dir, "04_Character_Database", f"{clean_title}_Characters.md")
            with open(chars_path, "w", encoding="utf-8") as f:
                f.write(f"# Characters Database: {thai_title}\n\n" + characters)
            print(f"[+] Saved Characters DB to: {chars_path}")
            
            # Save Chapter 1
            chapter_path = os.path.join(chapters_dir, f"{clean_title}_Chapter_01.md")
            with open(chapter_path, "w", encoding="utf-8") as f:
                f.write(final_chapter)
            print(f"[+] Saved Chapter 1 Draft to: {chapter_path}")
            
            # Save Audio Script
            audio_path = os.path.join(audio_scripts_dir, f"{clean_title}_AudioScript_01.md")
            with open(audio_path, "w", encoding="utf-8") as f:
                f.write(final_audio_script)
            print(f"[+] Saved Audio Script to: {audio_path}")
            
            # Update source file status to Processed
            frontmatter["status"] = "Processed"
            frontmatter["recreation_title"] = thai_title
            frontmatter["recreation_date"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            frontmatter["recreation_outline_ref"] = f"[[{clean_title}_Outline]]"
            frontmatter["recreation_chars_ref"] = f"[[{clean_title}_Characters]]"
            
            # Append log in original md body
            body_append = f"\n\n## 🚀 ผลงานสร้างสรรค์ใหม่ (Re-creation Output)\n- **โครงร่างและบทนิยายเสียงถูกสร้างด้วยระบบ Multi-Stage Engine:** {thai_title}\n- **ไฟล์พล็อต:** [[{clean_title}_Outline]]\n- **ไฟล์ตัวละคร:** [[{clean_title}_Characters]]\n- **ไฟล์ตอนแรก:** [[{clean_title}_Chapter_01]]\n- **ไฟล์บทนิยายเสียงตอนแรก:** [[{clean_title}_AudioScript_01]]\n"
            
            body = re.sub(r"- \[ \] \*\*Step 3:.*", "- [x] **Step 3: ปรับแต่งฉากและตัวละครให้เข้ากับบริบทไทย (Localization & Design)**", body)
            body = re.sub(r"- \[ \] \*\*Step 4:.*", "- [x] **Step 4: เจนตอนแรกและบทนิยายเสียง (Text & Audio Generation)**", body)
            body += body_append
            
            update_markdown_file(filepath, frontmatter, body)
            print(f"[+] Successfully finished recreation pipeline for: {filepath}")
            processed_count += 1
            
        except Exception as e:
            print(f"[!] Error recreating {filepath}: {e}")
            
    print(f"\n[+] Multi-Stage writing batch completed. Processed {processed_count} files.")

if __name__ == "__main__":
    second_brain_path = "./SecondBrain"
    if len(sys.argv) > 1:
        second_brain_path = sys.argv[1]
        
    process_analyzed_novels(second_brain_path)
