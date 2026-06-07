import os
import re
import json
import sys
import glob
from typing import Dict, Any, Tuple, List
from datetime import datetime
from google import genai
from google.genai import types

# Load environment variables from .env file if it exists
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

# Setup Gemini API Key
API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("[!] ERROR: GEMINI_API_KEY is not set.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)

# Setup Writing Mode
WRITING_MODE = os.environ.get("WRITING_MODE", "premium").lower()

def get_model(stage: str) -> str:
    """Return model name based on stage and WRITING_MODE config."""
    if WRITING_MODE == "master":
        return "gemini-2.5-pro"
    elif WRITING_MODE == "premium":
        if stage in ["writer", "enhancer"]:
            return "gemini-2.5-pro"
        return "gemini-2.5-flash"
    else: # draft
        return "gemini-2.5-flash"

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

def generate_content_safe(model: str, prompt: str, is_json: bool = False) -> str:
    """Helper to generate content from Gemini with safety checks disabled to prevent None responses."""
    safety_settings = [
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
        types.SafetySetting(
            category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
            threshold=types.HarmBlockThreshold.BLOCK_NONE,
        ),
    ]
    
    config = types.GenerateContentConfig(
        safety_settings=safety_settings,
        response_mime_type="application/json" if is_json else "text/plain"
    )
    
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            if response.text:
                return response.text
            
            print(f"[!] Warning: Gemini returned empty text (Attempt {attempt}/3). Retrying with simple adjustment...")
            time.sleep(2)
        except Exception as e:
            print(f"[!] Exception during generation (Attempt {attempt}/3): {e}")
            time.sleep(2)
            
    # Final fallback attempt with simplified instruction
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt + "\n[Note: Please generate safe PG-13 content without extreme elements]",
            config=config
        )
        return response.text or "Error: Generation returned empty result."
    except Exception as e:
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
    return generate_content_safe(get_model("outline"), prompt)

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
    return generate_content_safe(get_model("characters"), prompt)

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
    res_text = generate_content_safe(get_model("planner"), prompt, is_json=True)
    return json.loads(res_text)

def run_stage_4_scene_writer(title: str, scene_plan: Dict[str, str], prev_scenes_content: str, characters: str) -> str:
    """Stage 4: Draft Writer - Writes full detailed prose for a single scene."""
    scene_num = scene_plan.get("scene_number")
    print(f"    [Stage 4] Draft Writer: Writing detailed prose for Scene {scene_num}/4...")
    prompt = f"""
คุณคือ "Master Novelist" ผู้เชี่ยวชาญการแต่งนิยายพรรณนาภาษาไทยสละสลวยดึงดูดใจ
หน้าที่ของคุณคือแต่งเนื้อเรื่องฉากย่อยฉากนี้เพื่อประกอบเป็นนิยายตอนที่ 1 ของเรื่อง: {title}

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
5. แต่งฉากนี้ให้ออกมาละเอียดประณีตและยาวที่สุดเพื่อสร้างอารมณ์ร่วม (เป้าหมาย 600-800 คำสำหรับฉากนี้)
"""
    return generate_content_safe(get_model("writer"), prompt)

def run_stage_5_prose_enhancer(title: str, full_draft: str, characters: str) -> str:
    """Stage 5: Prose Enhancer - Polishes the compiled chapter, refines vocabulary and cliffhanger."""
    print("    [Stage 5] Editorial Prose Enhancer: Polishing vocabulary and Cliffhanger...")
    prompt = f"""
คุณคือ "Chief Literary Editor" ผู้เชี่ยวชาญด้านการขัดเกลาภาษานิยายออนไลน์ให้กลายเป็นผลงานระทึกขวัญระดับพรีเมียม
นี่คือดราฟต์ตอนแรกของนิยายเรื่อง {title}:
{full_draft}

ข้อมูลตัวละคร:
{characters}

กรุณาปรับแต่งขัดเกลาภาษานิยายตอนแรกนี้ โดย:
1. ขัดเกลาสำนวนพรรณนาให้สละสลวย มีวรรณศิลป์ ทรงพลัง และเห็นภาพเด่นชัด
2. ปรับแต่งจังหวะการเล่าเรื่อง (Pacing) บทสนทนา และการตัดบทให้กระชับ ลื่นไหล ไม่ยืดเยื้อหรือเร่งเร้าจนเสียอารมณ์
3. ตรวจสอบสำนวนสะกดคำและไวยากรณ์ไทย ปรับการเปรียบเปรยและการแปลให้เป็นบริบทไทยที่ลึกซึ้ง
4. ปรับจังหวะปิดท้ายตอน (Cliffhanger) ให้น่าติดตาม ดึงดูด และทิ้งปริศนาชวนให้ผู้อ่านต้องการอ่านตอนต่อไปทันที
5. ห้ามลบรายละเอียดสำคัญหรือย่อเนื้อหาที่สร้างอารมณ์ร่วมออก
"""
    return generate_content_safe(get_model("enhancer"), prompt)

def run_stage_6_audio_script(title: str, final_chapter: str) -> str:
    """Stage 6: Audio Script Adapter - Formats chapter into an audio production script."""
    print("    [Stage 6] Audio Script Adapter: Generating audio production script...")
    prompt = f"""
คุณคือ "Audio Production Director" ผู้กำกับละครวิทยุและนิยายเสียง
จงแปลงนิยายตอนแรกของเรื่อง {title} ด้านล่างนี้ ให้กลายเป็นบทนิยายเสียงพากย์ (Audio Script) สำหรับการผลิตเสียง MP3:
{final_chapter}

กฎการเขียนบทเสียง:
1. ระบุผู้พูดและน้ำเสียงในวงเล็บเหลี่ยมให้ชัดเจน เช่น:
   [ผู้บรรยาย, โทน: หม่นหมอง, สิ้นหวัง]
   [อคิน, โทน: ตะโกนอย่างเดือดดาล]
   [ระบบ, โทน: เสียงสังเคราะห์เย็นชา]
2. ระบุคิวเสียงเอฟเฟกต์ (SFX) ในบรรทัดแยกหรือแทรกในบทพูด เช่น:
   [SFX: เสียงกระดาษขยำทิ้งและเสียงถอนหายใจ]
   [SFX: เสียงแจ้งเตือนโทรศัพท์สั่นสะเทือนถี่ๆ]
3. ดัดแปลงเนื้อหาเล็กน้อยให้เหมาะสมกับการฟัง แต่ยังคงรักษาโครงเรื่องและความน่าตื่นเต้นไว้ทั้งหมด
"""
    return generate_content_safe(get_model("audio"), prompt)

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
                scene_content = run_stage_4_scene_writer(novel_title, scene_plan, prev_scenes_content, characters)
                chapter_scenes.append(scene_content)
                # Append to memory of prev scenes
                prev_scenes_content += f"\n\n--- [ฉากที่ {idx+1}] ---\n\n" + scene_content
                
            compiled_draft = "\n\n".join(chapter_scenes)
            
            # Stage 5: Editor Polishing & Enhancements
            final_chapter = run_stage_5_prose_enhancer(novel_title, compiled_draft, characters)
            
            # Stage 6: Audio Script Formatting
            final_audio_script = run_stage_6_audio_script(novel_title, final_chapter)
            
            # Save files to Second Brain structure
            active_projects_dir = os.path.join(second_brain_dir, "05_Active_Projects")
            chapters_dir = os.path.join(active_projects_dir, "Chapters")
            audio_scripts_dir = os.path.join(active_projects_dir, "Audio_Scripts")
            
            os.makedirs(chapters_dir, exist_ok=True)
            os.makedirs(audio_scripts_dir, exist_ok=True)
            
            clean_title = re.sub(r'[^\w\-_\s]', '', thai_title)
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
