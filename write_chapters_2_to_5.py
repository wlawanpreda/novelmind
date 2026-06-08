import os
import re
import sys
import json
import time
import requests
from datetime import datetime
from llm_provider import generate

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
    print("[!] WARNING: GEMINI_API_KEY not set — relying on local LLM backend (LLM_BACKEND=local|hybrid).")


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



def generate_content_safe(prompt: str, is_json: bool = False, role: str = "default") -> str:
    """Routed through the unified LLM provider (gemini/local by role); see llm_provider.py."""
    try:
        text = generate(prompt, role=role, is_json=is_json)
        if text:
            return text
    except Exception as e:
        print(f"[!] Exception during generation: {e}")
    try:
        softened = prompt + "\n[Note: Please generate safe PG-13 content without extreme elements]"
        return generate(softened, role=role, is_json=is_json) or "Error: Generation returned empty result."
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
        
        # Check for Headings
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

def publish_to_notion(title, content):
    url = "https://api.notion.com/v1/pages"
    blocks = parse_markdown_to_blocks(content)
    
    # We pass the title and the first few blocks in the page creation request
    payload = {
        "parent": {"page_id": PARENT_PAGE_ID},
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
            
            # Now append all content blocks to the page
            append_blocks_in_chunks(page_id, blocks)
            return page_url
        else:
            print(f"    [Notion] FAILED to create page: {res.text}")
            return None
    except Exception as e:
        print(f"    [Notion] ERROR publishing: {e}")
        return None

def main():
    outline_path = "SecondBrain/02_Concept_Extraction/รหสลบใตเงา_บทเพลงแหงกาลเวลา_Outline.md"
    chars_path = "SecondBrain/04_Character_Database/รหสลบใตเงา_บทเพลงแหงกาลเวลา_Characters.md"
    
    if not os.path.exists(outline_path) or not os.path.exists(chars_path):
        print("[!] ERROR: Outline or Characters DB files not found.")
        sys.exit(1)
        
    with open(outline_path, "r", encoding="utf-8") as f:
        outline_content = f.read()
        
    with open(chars_path, "r", encoding="utf-8") as f:
        characters_content = f.read()

    print("[*] Loaded Outline and Character Database successfully.")
    
    chapter_details = {
        2: {
            "title": "เศษเสี้ยวแห่งอดีต",
            "desc": "ทีมรอดชีวิตจากการตกกระแทกแต่กระจัดกระจาย โซล (อคิน) ฟื้นขึ้นมาท่ามกลางสภาพแวดล้อมที่เวลาบิดเบี้ยว เห็นภาพซ้อนของอดีตและอนาคต เขากับบลู (ชล) และไอริส (อัญ) พยายามรวมกลุ่มกัน การเดินทางเต็มไปด้วยเหตุการณ์ประวัติศาสตร์ที่ซ้ำรอย, ภาพหลอนของผู้คนและเหตุการณ์ในอดีต โซลต้องใช้พลัง 'บิดผัน' ของเขาเพื่อนำทางและช่วยบลู/ไอริสจากอันตรายจากเวลาที่บิดเบือน เช่น สะพานที่หายไปแล้วปรากฏขึ้นใหม่"
        },
        3: {
            "title": "รหัสแห่งเซนธาเรีย",
            "desc": "ทีมเริ่มต้นการเดินทางสู่ใจกลางดาวตามเบาะแสของไอริส (อัญ) บลู (ชล) พยายามสร้างอุปกรณ์วิเคราะห์คลื่นเวลาที่ช่วยให้โซลควบคุมและระบุตำแหน่งของพลัง 'บิดผัน' ได้ดีขึ้น พวกเขาต้องไขปริศนาทางโบราณคดีที่เกี่ยวข้องกับ 'แก่นมรดก' ซึ่งถูกซ่อนอยู่ในซากปรักหักพังของเมืองโบราณที่ปรากฏสลับไปมาตามเวลา ไอริสพบว่า 'แก่นมรดก' บนเซนธาเรียมีการทำงานที่แตกต่างจากที่เคยถูกบันทึกไว้ในตำนาน"
        },
        4: {
            "title": "เสียงกระซิบจากอดีต",
            "desc": "ทีมพยายามฝ่าด่าน 'เงาปริศนา' เข้าไปในโครงสร้าง โซล (อคิน) ต้องใช้พลัง 'บิดผัน' เพื่อ 'มองเห็น' ช่องโหว่ในมิติของเงามืดและสร้างทางผ่านที่ปลอดภัย ภายในโครงสร้าง พวกเขาพบข้อมูลที่บอกเล่าถึงการทดลองโบราณที่ผิดพลาดซึ่งเกี่ยวข้องกับการควบคุมเวลา ซึ่งอาจเป็นสาเหตุของการล่มสลายของเวลาและกำเนิด 'เงาปริศนา'"
        },
        5: {
            "title": "วงกตแห่งกาล",
            "desc": "ทีมต้องเดินทางผ่านเขาวงกตขนาดใหญ่ที่เต็มไปด้วยกับดักเวลาและภาพลวงตา โซลฟื้นขึ้นมาพร้อมความกังวลเกี่ยวกับเสียงกระซิบและภาพที่เขาเห็น ไอริส (อัญ) ใช้ความรู้ทางโบราณคดีและตำนานในการนำทาง, บลู (ชล) ใช้เทคโนโลยีในการระบุและทำลายกับดักที่เกี่ยวข้องกับเวลา โซลเรียนรู้การใช้พลัง 'บิดผัน' เพื่อแก้ไขเส้นทางเวลาเล็กๆ น้อยๆ ได้อย่างแม่นยำขึ้น"
        }
    }

    # Setup directories
    chapters_dir = "SecondBrain/05_Active_Projects/Chapters"
    audio_scripts_dir = "SecondBrain/05_Active_Projects/Audio_Scripts"
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(audio_scripts_dir, exist_ok=True)

    for ch_num in range(2, 6):
        title = chapter_details[ch_num]["title"]
        desc = chapter_details[ch_num]["desc"]
        
        print(f"\n==================== WRITING CHAPTER {ch_num}: {title} ====================")
        
        # Step A: Beat breakdown
        print(f"[*] Step A: Planning 4 scenes for Chapter {ch_num}...")
        beat_prompt = f"""คุณคือ "Screenwriter & Narrative Planner" ผู้เชี่ยวชาญการกำหนดฉากย่อย
อ้างอิงจากแผนภาพรวม 10 ตอน:
{outline_content}

ข้อมูลตัวละครหลัก:
{characters_content}

นี่คือเป้าหมายของตอนที่ {ch_num}: {title}
{desc}

จงแบ่งบทที่ {ch_num} ออกเป็น 4 ฉากย่อย (Beats) ที่ต่อเนื่องและชิงไหวชิงพริบ
ให้ผลลัพธ์การวิเคราะห์เป็นรูปแบบ JSON เท่านั้น โดยมีโครงสร้างคีย์ดังนี้:
[
  {{
    "scene_number": "1",
    "setting": "สถานที่และบรรยากาศฉาก 1",
    "goal": "เป้าหมายตัวละครในฉากนี้",
    "action": "สิ่งที่เกิดขึ้นอย่างละเอียดเพื่อแสดงความฉลาดของตัวเอกและการดำเนินเรื่อง",
    "climax": "จุดสำคัญหรืออารมณ์ฉากย่อยนี้"
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
คุณคือ "Master Novelist" ผู้เชี่ยวชาญการแต่งนิยายพรรณนาภาษาไทยอ่านง่าย เข้าใจง่าย กระชับ และสนุกสนาน
หน้าที่ของคุณคือแต่งเนื้อเรื่องฉากย่อยนี้เพื่อประกอบเป็นตอนที่ {ch_num}: {title} ของนิยายเรื่อง เงามิติผัน: รหัสบรรเลงกาล (Inspired by Ciphered Shadows)

ข้อมูลตัวละครหลัก:
{characters_content}

เนื้อความฉากก่อนหน้านี้ในบท (ถ้ามี):
{prev_scenes_content}

---
แผนการเขียนฉากที่ {scene_num} นี้:
- สถานที่/บรรยากาศ: {scene_plan.get("setting")}
- เป้าหมาย: {scene_plan.get("goal")}
- ลำดับเหตุการณ์: {scene_plan.get("action")}
- จุดสำคัญ/ความรู้สึกหลัก: {scene_plan.get("climax")}

คำแนะนำการแต่ง:
1. เขียนบรรยายโดยใช้ภาษาที่เข้าใจง่าย ไม่ซับซ้อน อ่านง่ายลื่นไหล กระชับ ดำเนินเรื่องคึกคักรวดเร็ว
2. โฟกัสไปที่ความฉลาดและเล่ห์เหลี่ยมชั้นเชิง (มีเหลี่ยม) ของตัวเอก (อคิน/โซล) และการประสานงานของทีม (ชล, อัญ)
3. ใส่บทสนทนาโต้ตอบที่สมจริงสะท้อนอารมณ์ คาแรกเตอร์ตัวละคร และมีความฉลาดชิงไหวชิงพริบ
4. แต่งให้มีความยาวและรายละเอียดที่สมจริงที่สุด (เป้าหมาย 600-800 คำสำหรับฉากนี้)
"""
            scene_content = generate_content_safe(write_prompt)
            chapter_scenes.append(scene_content)
            prev_scenes_content += f"\n\n--- [ฉากที่ {idx+1}] ---\n\n" + scene_content
            time.sleep(1)

        compiled_draft = "\n\n".join(chapter_scenes)
        
        # Step C: Prose Polishing (Stage 5)
        print(f"[*] Step C: Polishing Chapter {ch_num} Prose...")
        polish_prompt = f"""
คุณคือ "Chief Literary Editor" ผู้แต่งและบรรณาธิการภาษาไทยอ่านง่าย
นี่คือดราฟต์นิยายบทที่ {ch_num}: {title}
{compiled_draft}

กรุณาปรับแต่งขัดเกลาบทนี้ โดย:
1. ใช้ภาษาที่เข้าใจง่าย ไม่ซับซ้อน อ่านง่ายลื่นไหล เป็นมิตรกับผู้อ่านทั่วไป หลีกเลี่ยงศัพท์ยากหรือวรรณศิลป์ที่ซับซ้อนเกินจำเป็น
2. รักษาจังหวะการเล่าเรื่อง (Pacing) ให้ตื่นเต้น กระชับ ชิงไหวชิงพริบ
3. ปรับจังหวะปิดท้ายบท (Cliffhanger) ให้น่าติดตาม ทิ้งปมให้ชวนอ่านบทถัดไปทันที
"""
        final_chapter = generate_content_safe(polish_prompt)
        
        # Step D: Audio Script Adapter (Stage 6)
        print(f"[*] Step D: Generating Chapter {ch_num} Audio Script...")
        audio_prompt = f"""
คุณคือ "Audio Production Director" ผู้กำกับนิยายเสียง
จงแปลงนิยายตอนที่ {ch_num}: {title} ด้านล่างนี้ ให้กลายเป็นบทนิยายเสียงพากย์ (Audio Script):
{final_chapter}

ระบุผู้พูดและน้ำเสียงในวงเล็บเหลี่ยมให้ชัดเจน เช่น [อคิน, โทน: แฝงรอยยิ้มเจ้าเล่ห์] และระบุคิวเสียงเอฟเฟกต์ (SFX) เช่น [SFX: เสียงเข็มนาฬิกาเดินถี่ๆ]
"""
        final_audio_script = generate_content_safe(audio_prompt)
        
        # Step E: Save locally
        chapter_file_path = os.path.join(chapters_dir, f"รหสลบใตเงา_บทเพลงแหงกาลเวลา_Chapter_{ch_num:02d}.md")
        with open(chapter_file_path, "w", encoding="utf-8") as f:
            f.write(final_chapter)
        print(f"[+] Saved Chapter {ch_num} locally to: {chapter_file_path}")
        
        audio_file_path = os.path.join(audio_scripts_dir, f"รหสลบใตเงา_บทเพลงแหงกาลเวลา_AudioScript_{ch_num:02d}.md")
        with open(audio_file_path, "w", encoding="utf-8") as f:
            f.write(final_audio_script)
        print(f"[+] Saved Audio Script {ch_num} locally to: {audio_file_path}")
        
        # Step F: Publish to Notion
        print(f"[*] Step F: Syncing Chapter {ch_num} to Notion...")
        notion_title = f"เงามิติผัน: รหัสบรรเลงกาล - บทที่ {ch_num}: {title}"
        notion_url = publish_to_notion(notion_title, final_chapter)
        if notion_url:
            print(f"[+] Sync successful! Page URL: {notion_url}")
            
        time.sleep(2)

if __name__ == "__main__":
    main()
