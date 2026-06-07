import os
import re
import sys
import json
import time
import requests
from google import genai
from google.genai import types
from google.genai.errors import APIError

# 1. Configuration & Credentials
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("[!] ERROR: NOTION_TOKEN is not set.")
    sys.exit(1)

PARENT_PAGE_ID = "373d71ae-c6a9-805a-b8ac-d6a558d4943a"

# Load environment variables
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("[!] Error: GEMINI_API_KEY is not set.")
    sys.exit(1)

client = genai.Client(api_key=API_KEY)
MODEL_NAME = "gemini-2.5-flash"

# Notion API Headers
notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Helper to append blocks in chunks to prevent Notion API payload size limits
def append_blocks_to_page(page_id, blocks):
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

def parse_markdown_to_blocks(text):
    if not text:
        return []
    blocks = []
    lines = str(text).split("\n")
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            continue
        
        # Heading 1
        if line_strip.startswith("# "):
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": [{"type": "text", "text": {"content": line_strip.replace("# ", "")}}]
                }
            })
        # Heading 2
        elif line_strip.startswith("## "):
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": line_strip.replace("## ", "")}}]
                }
            })
        # Heading 3
        elif line_strip.startswith("### "):
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": [{"type": "text", "text": {"content": line_strip.replace("### ", "")}}]
                }
            })
        # Bullet list
        elif line_strip.startswith("* ") or line_strip.startswith("- "):
            clean_line = line_strip[2:].replace("**", "")
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": clean_line}}]
                }
            })
        else:
            # Paragraph
            clean_line = line_strip.replace("**", "")
            # Split long paragraphs if they exceed Notion's 2000 character limit
            if len(clean_line) > 1800:
                chunks = [clean_line[j:j+1800] for j in range(0, len(clean_line), 1800)]
                for chunk in chunks:
                    blocks.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": chunk}}]
                        }
                    })
            else:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": clean_line}}]
                    }
                })
    return blocks

# Set safety settings to allow creative writing
safety_settings = [
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HARASSMENT,
        threshold=types.HarmBlockThreshold.BLOCK_NONE,
    ),
    types.SafetySetting(
        category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
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
    safety_settings=safety_settings
)

def post_iteration_to_notion(iteration_num, title, concept, chapter_content, review, evaluation):
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"page_id": PARENT_PAGE_ID},
        "properties": {
            "title": {
                "title": [{"text": {"content": f"Iteration {iteration_num}/50: {title}"}}]
            }
        }
    }
    
    # Create the page with retries
    res = None
    for attempt in range(1, 4):
        try:
            res = requests.post(url, json=payload, headers=notion_headers)
            if res.status_code == 200:
                break
            else:
                print(f"    [!] Notion page creation failed (Attempt {attempt}/3): {res.text}")
        except Exception as e:
            print(f"    [!] Notion page creation error (Attempt {attempt}/3): {str(e)}")
        time.sleep(2)
        
    if not res or res.status_code != 200:
        print(f"[!] Failed to create Notion page after 3 attempts.")
        return None
    
    page_id = res.json().get("id")
    page_url = res.json().get("url")
    
    # Parse contents into block list
    content_blocks = []
    
    content_blocks.extend(parse_markdown_to_blocks(f"# Iteration {iteration_num}/50: {title}"))
    content_blocks.extend(parse_markdown_to_blocks(f"## 📌 Concept & Outline"))
    content_blocks.extend(parse_markdown_to_blocks(concept))
    
    content_blocks.extend(parse_markdown_to_blocks(f"## ✍️ Chapter 1 Draft"))
    content_blocks.extend(parse_markdown_to_blocks(chapter_content))
    
    content_blocks.extend(parse_markdown_to_blocks(f"## 🎙️ Sub-agents Review"))
    content_blocks.extend(parse_markdown_to_blocks(review))
    
    content_blocks.extend(parse_markdown_to_blocks(f"## 📊 Evaluation & Status"))
    content_blocks.extend(parse_markdown_to_blocks(f"**สถานะ:** {evaluation}"))
    
    # Upload blocks
    try:
        append_blocks_to_page(page_id, content_blocks)
    except Exception as e:
        print(f"    [!] Exception during blocks upload to page {page_id}: {str(e)}")
        
    return page_url

# Helper to call Gemini with retries and exponential backoff
def call_gemini_with_retry(prompt, retry_config=config, max_retries=5):
    delay = 5
    for attempt in range(1, max_retries + 1):
        try:
            res = client.models.generate_content(
                model=MODEL_NAME,
                contents=prompt,
                config=retry_config
            )
            return res
        except Exception as e:
            print(f"    [!] API call failed (Attempt {attempt}/{max_retries}): {str(e)}")
            if attempt == max_retries:
                raise e
            print(f"    [!] Waiting {delay} seconds before retry...")
            time.sleep(delay)
            delay *= 2

# Helper to parse backup markdown files for resuming
def parse_backup_file(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    markers = [
        ("concept", r"^## Concept\s*$", re.MULTILINE),
        ("chapter", r"^## Chapter 1\s*$", re.MULTILINE),
        ("review", r"^## Review\s*$", re.MULTILINE),
        ("evaluation", r"^## Evaluation\s*$", re.MULTILINE),
    ]
    
    positions = {}
    for name, pattern, flags in markers:
        match = re.search(pattern, content, flags)
        if match:
            positions[name] = match.end()
            
    concept = ""
    chapter = ""
    review = ""
    evaluation = ""
    
    if "concept" in positions:
        match = re.search(r"^## Chapter 1\s*$", content, re.MULTILINE)
        end_pos = match.start() if match else len(content)
        concept = content[positions["concept"]:end_pos].strip()
        
    if "chapter" in positions:
        match = re.search(r"^## Review\s*$", content, re.MULTILINE)
        end_pos = match.start() if match else len(content)
        chapter = content[positions["chapter"]:end_pos].strip()
        
    if "review" in positions:
        match = re.search(r"^## Evaluation\s*$", content, re.MULTILINE)
        end_pos = match.start() if match else len(content)
        review = content[positions["review"]:end_pos].strip()
        
    if "evaluation" in positions:
        evaluation = content[positions["evaluation"]:].strip()
            
    return concept, chapter, review, evaluation

# 2. Main Iteration Loop
def run_loop():
    backup_dir = "SecondBrain/05_Active_Projects/Draft_Iterations"
    os.makedirs(backup_dir, exist_ok=True)
    
    # Auto-detect existing iterations
    start_iteration = 1
    current_concept = """**แนวคิดเริ่มต้น**: การย้อนเวลาพริกแพลงเหลี่ยมจัด
- แนวเรื่อง: ย้อนเวลา ชิงไหวชิงพริบ ไซไฟ-แฟนตาซี (Time-Travel / Sci-Fi / Fantasy / Thriller)
- ตัวละครเอก: เก่ง ฉลาดเป็นกรด พลิกแพลงเก่ง มีเล่ห์เหลี่ยมและชั้นเชิงแพรวพราว ไม่ยอมจำนนต่อโชคชะตา
- จุดขายหลัก (Hook): ตัวเอกย้อนเวลากลับมาพร้อมกับสมอง ความรู้ และเล่ห์เหลี่ยมที่จะต้อนคู่ปรับหรือระบบย้อนเวลาให้จนมุม"""
    
    last_review = "เริ่มรอบแรก ร่างพล็อตและขยายเนื้อหาเกี่ยวกับการย้อนเวลาและตัวเอกมีเหลี่ยม"
    evaluation = "เริ่มต้นรอบปรับปรุง"
    
    for i in range(1, 51):
        backup_file = os.path.join(backup_dir, f"Iteration_{i:02d}_Draft.md")
        if os.path.exists(backup_file):
            start_iteration = i + 1
            try:
                current_concept, _, last_review, evaluation = parse_backup_file(backup_file)
            except Exception:
                pass
                
    if start_iteration > 50:
        print("[*] All 50 iterations are already completed!")
        return

    print(f"[*] Starting/Resuming the 50 Iterations Novel Refinement Process from Iteration {start_iteration}...")
    
    for i in range(start_iteration, 51):
        print(f"\n==================== ITERATION {i}/50 ====================")
        
        # Step 1: Brainstorm & Concept
        print("[*] Step 1: Generating/Refining Concept & Outline...")
        concept_prompt = f"""คุณคือ "ผู้กำกับนิยาย AI และผู้ทดลองพล็อตเรื่องอัจฉริยะ" มีหน้าที่สร้างสรรค์พล็อตและบทแรกอย่างไร้ขีดจำกัด เป้าหมายคือรันลูปพัฒนาไอเดียต่อเนื่อง 50 รอบ (Iterations) และบันทึกผลลง Notion

ข้อมูลรอบก่อนเพื่อประเมินความต่อเนื่องหรือการปรับเปลี่ยน:
- โครงเรื่องรอบก่อน: {current_concept}
- คำวิจารณ์รอบก่อน: {last_review}
- การประเมินล่าสุด: {evaluation}

# ขั้นตอนในแต่ละรอบ:
1. ปลดล็อกจินตนาการ: คิดพล็อตและแนวเรื่องใหม่แกะกล่อง (ห้ามยึดติดกับแนวเดิม ชื่อเรื่อง หรือชื่อตัวละครเดิม เว้นแต่รอบก่อนหน้าจะทำได้ดีและต้องการต่อยอด) เปิดรับทุกแนวทางไม่ว่าจะเป็นไซไฟ แฟนตาซี สืบสวน หรือโรแมนซ์ แต่เน้นไปที่แนวเกี่ยวกับการย้อนเวลา ตัวเอกเก่ง พริกแพลง มีเหลี่ยม และควรใช้ภาษาที่เข้าใจง่าย ไม่ซับซ้อน ดำเนินเรื่องรวดเร็วและอ่านง่ายลื่นไหล
2. ร่างบทเปิด: เขียนบทที่ 1 (Chapter 1) ของพล็อตนั้นทันทีเพื่อทดสอบความน่าสนใจ
3. จำลองกลุ่มวิจารณ์: ส่งต่อให้ Sub-agents ประเมินในหลายมุมมอง
4. ประเมินผลลัพธ์: ตรวจสอบว่าไอเดียนี้มีศักยภาพไปต่อได้ไหม หรือควรเปลี่ยนทิศทางไปลองแนวอื่นในรอบถัดไปเพื่อค้นหาความเป็นไปได้ใหม่ๆ
5. บันทึก Notion: ส่งข้อมูล (รอบที่, แนวเรื่อง/พล็อตย่อ, เนื้อหาบทแรก, คะแนนคอมเมนต์, และทิศทางพัฒนาต่อ) เข้า Notion Database
6. ควบคุมลูป: อัปเดตตัวนับรอบ (รอบปัจจุบัน: {i}/50) แล้วเริ่มลูปถัดไปทันทีโดยโฟกัสที่การสร้างสรรค์สิ่งใหม่

# รูปแบบ Output:
สรุปผลเป็น Text Block หรือหัวข้อต่อไปนี้อย่างละเอียด:
1. เรื่อง: [ชื่อเรื่องภาษาไทยและภาษาอังกฤษ]
2. แนวเรื่อง (Genre): [ระบุแนวเรื่อง ย้อนเวลา/ชิงไหวชิงพริบ]
3. พล็อตย่อ (Synopsis) และจุดขายหลัก (Hook): [อธิบายพล็อตและชั้นเชิงเหลี่ยมคมของตัวเอก]"""
        
        # We increase temperature to 1.0 for creative brainstorming
        concept_config = types.GenerateContentConfig(
            safety_settings=safety_settings,
            temperature=1.0
        )
        concept_res = call_gemini_with_retry(concept_prompt, retry_config=concept_config)
        current_concept = concept_res.text or "Concept Blocked"
        print("    [Done] Concept generated.")
        
        # Step 2: Draft Chapter 1
        print("[*] Step 2: Drafting Chapter 1...")
        draft_prompt = f"""คุณคือ "ผู้กำกับนิยาย AI และผู้ทดลองพล็อตเรื่องอัจฉริยะ"
หน้าที่ของคุณคือร่างบทเปิด: เขียนบทที่ 1 (Chapter 1) ของพล็อตนั้นทันทีเพื่อทดสอบความน่าสนใจ

พล็อตและโครงเรื่องล่าสุด:
{current_concept}

กรุณาเขียนบทประพันธ์บทที่ 1 ภาษาไทย โดยใช้คำที่เข้าใจง่าย ไม่ซับซ้อน อ่านง่ายลื่นไหล กระชับ ชัดเจน และดึงดูดความสนใจผู้อ่านอย่างรวดเร็ว โดยเน้นภาษาที่เป็นมิตรกับคนอ่านทั่วไป หลีกเลี่ยงคำศัพท์ที่ยากหรือซับซ้อนเกินจำเป็น และแสดงให้เห็นความฉลาดเล่ห์เหลี่ยมของตัวเอกตั้งแต่บทแรก"""
        
        draft_res = call_gemini_with_retry(draft_prompt)
        current_chapter = draft_res.text or "Draft Blocked"
        print("    [Done] Chapter 1 drafted.")
        
        # Step 3: Sub-agents Review
        print("[*] Step 3: Getting Sub-agents Review...")
        review_prompt = f"""คุณคือทีมที่ปรึกษาและนักวิจารณ์เนื้อหา จงร่วมกันวิเคราะห์ "พล็อตและบทที่ 1" ที่ได้รับอย่างตรงไปตรงมาเพื่อหาจุดแข็งและโอกาสในการขยายไอเดียใน 3 มุมมอง:
1. [นักสร้างสรรค์/ผู้เชี่ยวชาญพล็อต]: ประเมินความสดใหม่ ความแหวกแนว และไอเดียนี้สามารถแตกแขนงหรือพลิกแพลงไปในทิศทางไหนได้อีกบ้าง
2. [นักการตลาด/คนอ่านสายแมส]: วิเคราะห์จุดขายหลัก (Hook) ว่าดึงดูดพอที่จะเปลี่ยนคนดูขาจรให้กลายเป็นแฟนคลับได้ไหม
3. [ผู้เชี่ยวชาญด้านมิติเนื้อหา]: เช็กความสมจริงของโลกในนิยาย (World-building) และเสน่ห์ดึงดูดของตัวละครหลัก

# รูปแบบ Output:
สรุปคอมเมนต์สั้นกระชับเป็นข้อๆ ให้คะแนนศักยภาพ (เต็ม 10) พร้อมสรุปคำแนะนำชัดเจนว่า "พล็อตนี้ควรพัฒนาต่อยอดในทิศทางใด" หรือ "ควรเปลี่ยนไปลองไอเดียใหม่อื่นๆ ที่น่าสนใจกว่า"

ข้อมูลที่ต้องประเมิน:
- โครงเรื่อง: {current_concept}
- บทที่ 1: {current_chapter}"""
        
        review_res = call_gemini_with_retry(review_prompt)
        last_review = review_res.text or "Review Blocked"
        print("    [Done] Review completed.")
        
        # Step 4: Evaluation
        print("[*] Step 4: Evaluating Status...")
        eval_prompt = f"""วิเคราะห์บทวิจารณ์ด้านล่างนี้ และสรุปผลออกมาสั้นๆ 1 บรรทัด ว่าเป็นคำแนะนำแบบใด เช่น "ผ่าน พัฒนาต่อยอดในทิศทาง..." หรือ "ควรเปลี่ยนไปลองไอเดียใหม่อื่นๆ ที่น่าสนใจกว่า"

บทวิจารณ์:
{last_review}"""
        
        eval_res = call_gemini_with_retry(eval_prompt)
        evaluation = eval_res.text.strip() if eval_res.text else "ควรเปลี่ยนไปลองไอเดียใหม่อื่นๆ"
        print(f"    [Done] Evaluation status: {evaluation}")
        
        # Step 5: Notion Sync
        print("[*] Step 5: Syncing to Notion...")
        title_match = re.search(r"เรื่อง:\s*(.*)", current_concept)
        title = title_match.group(1).strip() if title_match else "การย้อนเวลาพริกแพลงเหลี่ยมจัด"
        title = title.replace("**", "").replace("*", "").strip()
        if len(title) > 50:
            title = title[:47] + "..."
            
        page_url = post_iteration_to_notion(i, title, current_concept, current_chapter, last_review, evaluation)
        if page_url:
            print(f"    [Done] Sync successful! Page URL: {page_url}")
        else:
            print("    [!] Sync failed but continuing the loop...")
            
        # Write local backup of current iteration
        backup_file = os.path.join(backup_dir, f"Iteration_{i:02d}_Draft.md")
        with open(backup_file, "w", encoding="utf-8") as bf:
            bf.write(f"# Iteration {i}/50\n\n## Concept\n{current_concept}\n\n## Chapter 1\n{current_chapter}\n\n## Review\n{last_review}\n\n## Evaluation\n{evaluation}\n")
        print(f"    [Done] Local backup written to {backup_file}")
        
        # Quick delay to prevent API ratelimits
        time.sleep(2)

if __name__ == "__main__":
    run_loop()
