import os
import re
import sys
import json
import time
import requests
from google import genai
from google.genai import types

# Load environment variables
env_path = ".env"
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("[!] ERROR: GEMINI_API_KEY is not set.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-2.5-flash"

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("[!] ERROR: NOTION_TOKEN is not set.")
    sys.exit(1)

PARENT_PAGE_ID = "373d71ae-c6a9-805a-b8ac-d6a558d4943a"

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

safety_settings = [
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
    types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
]

def generate_content_safe(prompt: str, is_json: bool = False) -> str:
    current_config = types.GenerateContentConfig(
        safety_settings=safety_settings,
        response_mime_type="application/json" if is_json else "text/plain"
    )
    for attempt in range(1, 4):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=current_config
            )
            if response.text:
                return response.text
            print(f"[!] Warning: Empty result (attempt {attempt}/3). Retrying...")
            time.sleep(2)
        except Exception as e:
            print(f"[!] Exception (attempt {attempt}/3): {e}")
            time.sleep(2)
    # Final fallback
    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt + "\n[Note: Please generate safe PG-13 content without extreme elements]",
            config=current_config
        )
        return response.text or "Error: Generation returned empty result."
    except Exception as e:
        return f"Error: {str(e)}"

# Notion Block Parser
def parse_markdown_to_blocks(text):
    if not text:
        return []
    blocks = []
    lines = str(text).split("\n")
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        
        if line_strip.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {"rich_text": [{"type": "text", "text": {"content": line_strip.replace("# ", "")}}]}
            })
        elif line_strip.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"type": "text", "text": {"content": line_strip.replace("## ", "")}}]}
            })
        elif line_strip.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {"rich_text": [{"type": "text", "text": {"content": line_strip.replace("### ", "")}}]}
            })
        elif line_strip.startswith("* ") or line_strip.startswith("- "):
            clean_line = line_strip[2:].replace("**", "")
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": clean_line}}]}
            })
        else:
            clean_line = line_strip.replace("**", "")
            if len(clean_line) > 1800:
                chunks = [clean_line[i:i+1800] for i in range(0, len(clean_line), 1800)]
                for chunk in chunks:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}
                    })
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"type": "text", "text": {"content": clean_line}}]}
                })
    return blocks

def append_blocks_in_chunks(page_id, blocks):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    chunk_size = 50
    for i in range(0, len(blocks), chunk_size):
        chunk = blocks[i:i+chunk_size]
        payload = {"children": chunk}
        for attempt in range(1, 4):
            try:
                res = requests.patch(url, json=payload, headers=notion_headers)
                if res.status_code == 200:
                    break
                else:
                    print(f"    [!] Failed to append blocks chunk (Attempt {attempt}/3): {res.text}")
            except Exception as e:
                print(f"    [!] Error appending blocks chunk (Attempt {attempt}/3): {str(e)}")
            time.sleep(2)

def create_notion_subpage(parent_page_id, title):
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"page_id": parent_page_id},
        "properties": {
            "title": {
                "title": [{"text": {"content": title}}]
            }
        }
    }
    try:
        res = requests.post(url, json=payload, headers=notion_headers)
        if res.status_code == 200:
            subpage_id = res.json().get("id")
            subpage_url = res.json().get("url")
            print(f"[*] Created sub-page on Notion successfully! Title: {title} | URL: {subpage_url}")
            return subpage_id
        else:
            print(f"[!] FAILED to create sub-page: {res.text}")
            return parent_page_id
    except Exception as e:
        print(f"[!] ERROR creating sub-page: {e}")
        return parent_page_id

def publish_to_notion(title, content, parent_id):
    url = "https://api.notion.com/v1/pages"
    blocks = parse_markdown_to_blocks(content)
    
    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {
                "title": [{"text": {"content": title}}]
            }
        }
    }
    
    try:
        res = requests.post(url, json=payload, headers=notion_headers)
        if res.status_code == 200:
            page_id = res.json().get("id")
            page_url = res.json().get("url")
            print(f"    [Notion] Page created successfully! URL: {page_url}")
            append_blocks_in_chunks(page_id, blocks)
            return page_url
        else:
            print(f"    [Notion] FAILED to create page: {res.text}")
            return None
    except Exception as e:
        print(f"    [Notion] ERROR publishing: {e}")
        return None

def main():
    outline_path = "SecondBrain/02_Concept_Extraction/สมาคมประกันภัยลี้ลับ_Outline.md"
    chars_path = "SecondBrain/04_Character_Database/สมาคมประกันภัยลี้ลับ_Characters.md"
    
    if not os.path.exists(outline_path) or not os.path.exists(chars_path):
        print("[!] ERROR: Outline or Characters DB files not found.")
        sys.exit(1)
        
    with open(outline_path, "r", encoding="utf-8") as f:
        outline_content = f.read()
        
    with open(chars_path, "r", encoding="utf-8") as f:
        characters_content = f.read()

    print("[*] Loaded Outline and Character Database successfully.")
    
    print("[*] Creating dedicated folder for the novel on Notion...")
    insurance_parent_page_id = create_notion_subpage(PARENT_PAGE_ID, "สมาคมประกันภัยลี้ลับ: แผนกเคลมกรรม")
    
    chapter_details = {
        1: {
            "title": "เกิดอุบัติกรรมลี้ลับ",
            "desc": "ลูกค้ารายใหญ่ยื่นใบเคลมประกัน อ้างว่าโดนผีเจ้าที่ผลักตกบันไดบ้านทรงไทยโบราณจนขาหัก เรียกค่ารักษา 2 แสนบาท เอกผู้เป็นหัวหน้าฝ่ายประเมินความเสียหายจอมเหนียว และจิ๊บนักศึกษาฝึกงานขวัญอ่อน ต้องเดินทางไปตรวจสอบที่เกิดเหตุกลางดึก"
        },
        2: {
            "title": "ชันสูตรความชัน",
            "desc": "เอกตรวจสอบบันไดอย่างละเอียด วัดสโลปมุมความลาดเอียงเพื่อประเมินความน่าจะเป็นทางสถิติของแรงโน้มถ่วง ขณะที่จิ๊บร้องกรี๊ดคอหอยแทบแตกเพราะวิญญาณเจ้าที่โบราณสวมชฎาปรากฏตัวชี้นิ้วข่มขู่ เอกหงัดสัญญากรมธรรม์ข้อกฎหมายโต้เถียงกับผีเจ้าที่เรื่องขอบเขตภัยพิบัติอย่างหน้าตาย"
        },
        3: {
            "title": "จับโป๊ะผีจับขา",
            "desc": "อาจารย์เดช วิศวกรอาคมประจำบริษัทมาร่วมตรวจสอบ นำเครื่องตรวจวัดแรงสั่นสะเทือนวิญญาณมาสแกน พบว่าแรงถีบที่แท้จริงไม่สอดคล้องกับพลังงานของผีเจ้าที่ แต่กลับไปเจอคราบน้ำมันมะพร้าวทาอยู่ตรงเหลี่ยมมุมของบันได แผนตบตาเพื่อเอาเงินเคลมประกันเริ่มแดงโร่"
        },
        4: {
            "title": "ใบปฏิเสธสินไหมวิญญาณ",
            "desc": "ฉากเคลียร์บิลกลางดึก เอกจัดประชุมร่วมระหว่างลูกค้าจอมโกง ผีเจ้าที่ และบริษัทประกัน ผีสารภาพว่าไม่ได้ผลักแต่แค่อยากเขกหัวเพราะลูกค้ามาฉี่ใส่ศาล เอกยื่นเอกสารปฏิเสธการเคลมสินไหม (Claim Denial Form) แสนรัก และช่วยไกล่เกลี่ยขอโทษเจ้าที่โดยการซื้อน้ำแดงถวายแทน"
        }
    }

    chapters_dir = "SecondBrain/05_Active_Projects/Chapters"
    audio_scripts_dir = "SecondBrain/05_Active_Projects/Audio_Scripts"
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(audio_scripts_dir, exist_ok=True)

    for ch_num in range(1, 5):
        title = chapter_details[ch_num]["title"]
        desc = chapter_details[ch_num]["desc"]
        
        print(f"\n==================== WRITING CHAPTER {ch_num}: {title} ====================")
        
        # Step A: Beat breakdown
        print(f"[*] Step A: Planning 4 scenes for Chapter {ch_num}...")
        beat_prompt = f"""คุณคือ "Screenwriter & Comedy Narrative Planner" ผู้เชี่ยวชาญการเขียนบทย่อยแนวเสียดสีระบบสำนักงานผสมมุกตลกกาว ๆ
อ้างอิงจากแผนภาพรวมของนิยายตลกเรื่อง 'สมาคมประกันภัยลี้ลับ':
{outline_content}

ข้อมูลตัวละครหลัก:
{characters_content}

นี่คือเป้าหมายของบทที่ {ch_num}: {title}
{desc}

จงแบ่งบทที่ {ch_num} ออกเป็น 4 ฉากย่อย (Beats) ที่ต่อเนื่อง ชิงไหวชิงพริบ และแฝงความเสียดสีพนักงานออฟฟิศปะทะความกาวลี้ลับ
ให้ผลลัพธ์การวิเคราะห์เป็นรูปแบบ JSON เท่านั้น โดยมีโครงสร้างคีย์ดังนี้:
[
  {{
    "scene_number": "1",
    "setting": "สถานที่และบรรยากาศฉาก 1",
    "goal": "เป้าหมายตัวละครในฉากนี้",
    "action": "สิ่งที่เกิดขึ้นอย่างละเอียดเพื่อแสดงความฮา การจับผิด และความเค็มของผู้ประเมินภัย",
    "climax": "จุดสำคัญหรือจุดตบมุกของฉากย่อยนี้"
  }},
  ... (รวมทั้งหมด 4 ฉาก)
]
"""
        try:
            beat_res = generate_content_safe(beat_prompt, is_json=True)
            scene_plans = json.loads(beat_res)
        except Exception as e:
            print(f"[!] Error parsing scenes JSON, trying again: {e}")
            time.sleep(2)
            beat_res = generate_content_safe(beat_prompt, is_json=True)
            scene_plans = json.loads(beat_res)
            
        # Step B: Scene-by-scene writing
        chapter_scenes = []
        prev_scenes_content = ""
        
        for idx, scene_plan in enumerate(scene_plans):
            scene_num = scene_plan.get("scene_number")
            print(f"[*] Step B: Writing Chapter {ch_num} Scene {scene_num}/4...")
            
            write_prompt = f"""
คุณคือ "Master Comedy Novelist" ผู้เชี่ยวชาญการแต่งนิยายแนวตลกขบขัน เสียดสีการทำงานออฟฟิศ ภาษาไทยอ่านง่าย ลื่นไหล ดำเนินเรื่องรวดเร็วและตบมุกตลกเป็นธรรมชาติ
หน้าที่ของคุณคือแต่งเนื้อเรื่องฉากย่อยนี้เพื่อประกอบเป็นตอนที่ {ch_num}: {title} ของนิยายเรื่อง สมาคมประกันภัยลี้ลับ: แผนกเคลมกรรม

ข้อมูลตัวละครหลัก:
{characters_content}

เนื้อความฉากก่อนหน้านี้ในบท (ถ้ามี):
{prev_scenes_content}

---
แผนการเขียนฉากที่ {scene_num} นี้:
- สถานที่/บรรยากาศ: {scene_plan.get("setting")}
- เป้าหมาย: {scene_plan.get("goal")}
- ลำดับเหตุการณ์: {scene_plan.get("action")}
- จุดสำคัญ/จุดตบมุกหลัก: {scene_plan.get("climax")}

คำแนะนำการแต่ง:
1. เขียนบรรยายให้อ่านง่าย กระชับ ดำเนินเรื่องคึกคักรวดเร็ว
2. โฟกัสความขัดแย้งของตัวละคร: คุณเอก (หัวหน้าเคลมประกันเค็มจัดสุดเหตุผล) ปะทะ จิ๊บ (เด็กฝึกงานผู้ช่วยที่กลัวผีจนสติแตก) และผี/คนโกงประกัน
3. ใส่บทสนทนาโต้ตอบที่มีการตบมุกตลกขบขันเสียดสีงานบริการลูกค้า มีการชิงไหวชิงพริบ
4. แต่งให้มีความยาวและรายละเอียดที่สมจริง (เป้าหมาย 600-800 คำสำหรับฉากนี้)
"""
            scene_content = generate_content_safe(write_prompt)
            chapter_scenes.append(scene_content)
            prev_scenes_content += f"\n\n--- [ฉากที่ {idx+1}] ---\n\n" + scene_content
            time.sleep(1)

        compiled_draft = "\n\n".join(chapter_scenes)
        
        # Step C: Prose Polishing (Stage 5)
        print(f"[*] Step C: Polishing Chapter {ch_num} Prose...")
        polish_prompt = f"""
คุณคือ "Chief Literary Editor" ผู้แต่งและบรรณาธิการภาษาไทยตลกขบขันและอ่านง่าย
นี่คือดราฟต์นิยายบทที่ {ch_num}: {title}
{compiled_draft}

กรุณาปรับแต่งขัดเกลาบทนี้ โดย:
1. ใช้ภาษาที่เข้าใจง่าย ไม่ซับซ้อน อ่านง่ายลื่นไหล เพิ่มจังหวะคอมเมดี้/ตบมุกให้คมและฮายิ่งขึ้น
2. รักษาจังหวะการเล่าเรื่อง (Pacing) ให้ตื่นเต้น กระชับ
3. ปรับจังหวะปิดท้ายบท (Cliffhanger) ให้น่าติดตาม ทิ้งปมให้ชวนฮาและชวนอ่านบทถัดไปทันที
"""
        final_chapter = generate_content_safe(polish_prompt)
        
        # Step D: Audio Script Adapter (Stage 6)
        print(f"[*] Step D: Generating Chapter {ch_num} Audio Script...")
        audio_prompt = f"""
คุณคือ "Audio Production Director" ผู้กำกับนิยายเสียงแนวคอมเมดี้สนุกสนาน
จงแปลงนิยายตอนที่ {ch_num}: {title} ด้านล่างนี้ ให้กลายเป็นบทนิยายเสียงพากย์ (Audio Script):
{final_chapter}

ระบุผู้พูดและน้ำเสียงในวงเล็บเหลี่ยมให้ชัดเจน เช่น [คุณเอก, โทน: ตรวจสอบแบบใจเย็นจอมเค็ม] และระบุคิวเสียงเอฟเฟกต์ (SFX) เช่น [SFX: เสียงกดเครื่องคิดเลขรัวๆ]
"""
        final_audio_script = generate_content_safe(audio_prompt)
        
        # Step E: Save locally
        chapter_file_path = os.path.join(chapters_dir, f"สมาคมประกันภัยลี้ลับ_Chapter_{ch_num:02d}.md")
        with open(chapter_file_path, "w", encoding="utf-8") as f:
            f.write(final_chapter)
        print(f"[+] Saved Chapter {ch_num} locally to: {chapter_file_path}")
        
        audio_file_path = os.path.join(audio_scripts_dir, f"สมาคมประกันภัยลี้ลับ_AudioScript_{ch_num:02d}.md")
        with open(audio_file_path, "w", encoding="utf-8") as f:
            f.write(final_audio_script)
        print(f"[+] Saved Audio Script {ch_num} locally to: {audio_file_path}")
        
        # Step F: Publish to Notion
        print(f"[*] Step F: Syncing Chapter {ch_num} to Notion...")
        notion_title = f"สมาคมประกันภัยลี้ลับ - บทที่ {ch_num}: {title}"
        notion_url = publish_to_notion(notion_title, final_chapter, insurance_parent_page_id)
        if notion_url:
            print(f"[+] Sync successful! Page URL: {notion_url}")
            
        time.sleep(2)

if __name__ == "__main__":
    main()
