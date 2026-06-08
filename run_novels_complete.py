"""
run_novels_complete.py
======================
Master script: เขียน 3 เรื่องให้จบ + รีวิว + เขียนใหม่ 1 รอบ

เรื่องที่รัน:
  1. สถานีตำรวจกาววิญญาณ  → บทที่ 5-16 (คดีที่ 2, 3, 4)
  2. สมาคมประกันภัยลี้ลับ  → บทที่ 5-16 (คดีที่ 2, 3, 4)
  3. วินดี้ นักสืบหลงทิศ     → บทที่ 1-10 (จากต้นจนจบ)

Pipeline ต่อบท:
  A. Beat planning (4 scenes JSON)
  B. Scene-by-scene writing (4 scenes × ~700 words)
  C. Prose polishing
  D. Sub-agents review (3 reviewers)
  E. Rewrite pass (1 round based on review)
  F. Notion sync + local save
"""

import os
import re
import sys
import json
import time
import requests
from llm_provider import generate

# ─── ENV & CREDENTIALS ────────────────────────────────────────────────────────
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
    print("[!] WARNING: GEMINI_API_KEY not set — relying on local LLM backend (LLM_BACKEND=local|hybrid).")

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("[!] ERROR: NOTION_TOKEN is not set.")
    sys.exit(1)

PARENT_PAGE_ID = "373d71ae-c6a9-805a-b8ac-d6a558d4943a"

notion_headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}

# ─── LLM HELPER (routed via llm_provider: gemini/local by role) ───────────────
def call_gemini(prompt: str, role: str = "writer", is_json: bool = False) -> str:
    try:
        text = generate(prompt, role=role, is_json=is_json)
        return text if text else "ERROR: empty result"
    except Exception as e:
        print(f"    [!] LLM error (role={role}): {e}")
        return f"ERROR: {e}"

# ─── NOTION HELPERS ───────────────────────────────────────────────────────────
def md_to_blocks(text: str) -> list:
    if not text:
        return []
    blocks = []
    for line in text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if s.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": s[2:]}}]}})
        elif s.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": s[3:]}}]}})
        elif s.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": s[4:]}}]}})
        elif s.startswith("* ") or s.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": s[2:].replace("**", "")}}]}})
        else:
            clean = s.replace("**", "")
            for chunk in [clean[i:i+1800] for i in range(0, len(clean), 1800)]:
                blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]}})
    return blocks

def append_blocks(page_id: str, blocks: list):
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    for i in range(0, len(blocks), 50):
        chunk = blocks[i:i+50]
        for attempt in range(1, 4):
            try:
                res = requests.patch(url, json={"children": chunk}, headers=notion_headers)
                if res.status_code == 200:
                    break
                print(f"    [!] Notion append failed (attempt {attempt}/3): {res.text[:200]}")
            except Exception as e:
                print(f"    [!] Notion error (attempt {attempt}/3): {e}")
            time.sleep(2)

def create_notion_page(parent_id: str, title: str, content: str) -> str | None:
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
    }
    for attempt in range(1, 4):
        try:
            res = requests.post(url, json=payload, headers=notion_headers)
            if res.status_code == 200:
                page_id = res.json()["id"]
                page_url = res.json()["url"]
                append_blocks(page_id, md_to_blocks(content))
                return page_url
            print(f"    [!] Page creation failed (attempt {attempt}/3): {res.text[:200]}")
        except Exception as e:
            print(f"    [!] Notion error (attempt {attempt}/3): {e}")
        time.sleep(2)
    return None

def create_notion_subpage(parent_id: str, title: str) -> str:
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": {"page_id": parent_id},
        "properties": {"title": {"title": [{"text": {"content": title}}]}},
    }
    try:
        res = requests.post(url, json=payload, headers=notion_headers)
        if res.status_code == 200:
            sub_id = res.json()["id"]
            print(f"    [Notion] Sub-page created: {title}")
            return sub_id
        print(f"    [!] Sub-page creation failed: {res.text[:200]}")
    except Exception as e:
        print(f"    [!] Notion sub-page error: {e}")
    return parent_id

# ─── WRITING PIPELINE ─────────────────────────────────────────────────────────
def step_a_beat_plan(novel_title: str, outline: str, characters: str,
                     ch_num: int, ch_title: str, ch_desc: str) -> list:
    """Generate 4-scene beat plan as JSON."""
    prompt = f"""คุณคือ "Narrative Planner" ผู้วางแผนฉากนิยายแนวตลก-สืบสวน
อ้างอิงจากโครงเรื่องนิยายเรื่อง '{novel_title}':
{outline}

ข้อมูลตัวละคร:
{characters}

เป้าหมายของบทที่ {ch_num}: {ch_title}
{ch_desc}

จงแบ่งบทที่ {ch_num} ออกเป็น 4 ฉากย่อย (Beats) ที่ต่อเนื่อง มีมุกตลก สืบสวน และจบด้วย Cliffhanger
ให้ผลลัพธ์เป็น JSON อาร์เรย์ 4 อิลิเมนต์ดังนี้:
[
  {{
    "scene_number": "1",
    "setting": "สถานที่และบรรยากาศ",
    "goal": "เป้าหมายตัวละคร",
    "action": "เหตุการณ์ที่เกิดขึ้นอย่างละเอียด",
    "climax": "จุดตบมุกหรือจุดสำคัญ"
  }},
  ...
]"""
    raw = call_gemini(prompt, role="planner", is_json=True)
    try:
        return json.loads(raw)
    except Exception:
        # strip markdown fences if any
        raw2 = re.sub(r"```json|```", "", raw).strip()
        try:
            return json.loads(raw2)
        except Exception as e:
            print(f"    [!] Beat JSON parse failed: {e}. Using fallback single scene.")
            return [{"scene_number": str(i+1), "setting": f"ฉากที่ {i+1}", "goal": ch_desc,
                     "action": ch_desc, "climax": "ปิดบทด้วยความฮา"} for i in range(4)]

def step_b_write_scene(novel_title: str, characters: str, ch_num: int, ch_title: str,
                       scene_plan: dict, prev_content: str) -> str:
    """Write one scene (~700 words)."""
    scene_num = scene_plan.get("scene_number", "?")
    prompt = f"""คุณคือ "Master Comedy Novelist" ผู้แต่งนิยายแนวตลกขบขัน-สืบสวน ภาษาไทยอ่านง่าย ลื่นไหล
หน้าที่ของคุณคือแต่งเนื้อเรื่องฉากย่อยนี้เป็นส่วนหนึ่งของบทที่ {ch_num}: {ch_title}
นิยายเรื่อง: {novel_title}

ข้อมูลตัวละคร:
{characters}

เนื้อความฉากก่อนหน้า (ถ้ามี):
{prev_content[-3000:] if prev_content else "(ยังไม่มี)"}

แผนฉากที่ {scene_num}:
- สถานที่: {scene_plan.get("setting")}
- เป้าหมาย: {scene_plan.get("goal")}
- เหตุการณ์: {scene_plan.get("action")}
- จุดสำคัญ: {scene_plan.get("climax")}

คำแนะนำ:
1. เขียนพรรณนาอย่างลงลึก บรรยายบรรยากาศ บทสนทนา และอารมณ์ตัวละครให้ชัดเจน
2. ใส่มุกตลกแบบไทยๆ เป็นธรรมชาติ ชิงไหวชิงพริบ
3. เป้าหมายความยาว 700-900 คำสำหรับฉากนี้
4. ใช้ภาษาไทยสละสลวย อ่านง่าย ลื่นไหล"""
    return call_gemini(prompt, role="writer")

def step_c_polish(novel_title: str, ch_num: int, ch_title: str, draft: str) -> str:
    """Polish the compiled chapter draft."""
    prompt = f"""คุณคือ "Chief Literary Editor" บรรณาธิการนิยายไทยตลก-สืบสวน
นี่คือดราฟต์บทที่ {ch_num}: {ch_title} ของนิยายเรื่อง '{novel_title}':
{draft}

กรุณาขัดเกลา:
1. เพิ่มจังหวะตบมุกให้คมและฮายิ่งขึ้น
2. ปรับภาษาให้ลื่นไหล ไม่ซ้ำซาก
3. ปิดท้ายบทด้วย Cliffhanger ที่ชวนติดตาม
4. ห้ามย่อหรือลบรายละเอียดสำคัญ
ส่งคืนเฉพาะเนื้อหาบทที่ขัดเกลาแล้ว ไม่ต้องมีคำอธิบายเพิ่มเติม"""
    return call_gemini(prompt, role="enhancer")

def step_d_review(novel_title: str, ch_num: int, ch_title: str, chapter: str) -> str:
    """3-reviewer sub-agents review."""
    prompt = f"""คุณคือทีมนักวิจารณ์นิยาย 3 คน จงร่วมกันวิจารณ์บทที่ {ch_num}: {ch_title}
ของนิยายเรื่อง '{novel_title}' ดังนี้:

เนื้อหา:
{chapter[:8000]}

วิจารณ์ใน 3 มุมมอง:
1. [นักอ่านสายมวลชน]: ความสนุก ความฮา จุดดึงดูด และสิ่งที่ทำให้รู้สึกเบื่อ
2. [บรรณาธิการ]: โครงสร้างการเล่าเรื่อง จังหวะ Pacing และความสอดคล้องของตัวละคร
3. [นักการตลาดเนื้อหา]: จุดขาย Viral Potential และสิ่งที่ควรเน้นให้มากขึ้น

สรุปคะแนน (เต็ม 10) และข้อเสนอแนะ 3-5 ข้อที่ชัดเจนสำหรับการเขียนใหม่ (Rewrite Pass)"""
    return call_gemini(prompt, role="reviewer")

def step_e_rewrite(novel_title: str, ch_num: int, ch_title: str,
                   chapter: str, review: str) -> str:
    """Rewrite the chapter based on review feedback."""
    prompt = f"""คุณคือ "Master Rewriter" ผู้เชี่ยวชาญการเขียนใหม่ตาม feedback
นิยายเรื่อง: '{novel_title}' บทที่ {ch_num}: {ch_title}

บทต้นฉบับ:
{chapter[:8000]}

ข้อเสนอแนะจากทีมวิจารณ์:
{review[:3000]}

จงเขียนบทนี้ใหม่ 1 รอบโดย:
1. นำ feedback ทุกข้อมาปรับปรุงอย่างครบถ้วน
2. รักษาโครงเรื่องและเหตุการณ์หลักไว้ครบ
3. เพิ่มความสนุก ความฮา และความดึงดูดให้มากขึ้น
4. Cliffhanger ท้ายบทต้องทรงพลังกว่าเดิม
ส่งคืนเฉพาะเนื้อหาบทที่เขียนใหม่แล้ว"""
    return call_gemini(prompt, role="writer")

# ─── CHAPTER PROCESSOR ────────────────────────────────────────────────────────
def process_chapter(novel_title: str, novel_key: str, outline: str, characters: str,
                    ch_num: int, ch_title: str, ch_desc: str,
                    notion_parent_id: str, chapters_dir: str, reviews_dir: str) -> bool:
    """
    Full pipeline for one chapter:
    A→B→C→D→E→save+notion
    Returns True if successful.
    """
    # Check if already done (local file exists = done)
    final_path = os.path.join(chapters_dir, f"{novel_key}_Chapter_{ch_num:02d}_Final.md")
    if os.path.exists(final_path):
        print(f"    [Skip] Chapter {ch_num} already done: {final_path}")
        return True

    print(f"\n{'='*60}")
    print(f"[📖] {novel_title} — บทที่ {ch_num}: {ch_title}")
    print(f"{'='*60}")

    # A: Beat plan
    print("[A] Planning 4 scenes...")
    scene_plans = step_a_beat_plan(novel_title, outline, characters, ch_num, ch_title, ch_desc)
    time.sleep(1)

    # B: Write scenes
    chapter_scenes = []
    prev_content = ""
    for idx, sp in enumerate(scene_plans):
        print(f"[B] Writing scene {idx+1}/4...")
        scene_text = step_b_write_scene(novel_title, characters, ch_num, ch_title, sp, prev_content)
        chapter_scenes.append(scene_text)
        prev_content += f"\n\n--- ฉากที่ {idx+1} ---\n\n{scene_text}"
        time.sleep(1)

    compiled_draft = "\n\n".join(chapter_scenes)

    # C: Polish
    print("[C] Polishing draft...")
    polished = step_c_polish(novel_title, ch_num, ch_title, compiled_draft)
    time.sleep(1)

    # D: Review
    print("[D] Getting 3-reviewer review...")
    review_text = step_d_review(novel_title, ch_num, ch_title, polished)
    time.sleep(1)

    # E: Rewrite
    print("[E] Rewriting based on review...")
    final_chapter = step_e_rewrite(novel_title, ch_num, ch_title, polished, review_text)
    time.sleep(1)

    # Save locally: draft, review, final
    draft_path = os.path.join(chapters_dir, f"{novel_key}_Chapter_{ch_num:02d}_Draft.md")
    review_path = os.path.join(reviews_dir, f"{novel_key}_Chapter_{ch_num:02d}_Review.md")

    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(f"# {novel_title} — บทที่ {ch_num}: {ch_title}\n\n(Draft after polish)\n\n{polished}")
    with open(review_path, "w", encoding="utf-8") as f:
        f.write(f"# Review: {novel_title} — บทที่ {ch_num}\n\n{review_text}")
    with open(final_path, "w", encoding="utf-8") as f:
        f.write(f"# {novel_title}\n## บทที่ {ch_num}: {ch_title}\n\n{final_chapter}")

    print(f"[+] Saved Final: {final_path}")

    # Notion sync
    print("[F] Syncing to Notion...")
    notion_title = f"{novel_title} — บทที่ {ch_num}: {ch_title}"
    full_notion_content = (
        f"# {novel_title}\n## บทที่ {ch_num}: {ch_title}\n\n"
        f"---\n\n{final_chapter}\n\n"
        f"---\n\n## 🎙️ บทวิจารณ์\n\n{review_text}"
    )
    page_url = create_notion_page(notion_parent_id, notion_title, full_notion_content)
    if page_url:
        print(f"[+] Notion: {page_url}")
    else:
        print("[!] Notion sync failed, continuing...")

    time.sleep(2)
    return True

# ─── NOVEL DEFINITIONS ────────────────────────────────────────────────────────
def get_novels_config() -> list:
    base = "SecondBrain"
    outlines_dir = f"{base}/02_Concept_Extraction"
    chars_dir = f"{base}/04_Character_Database"

    # ── 1. สถานีตำรวจกาววิญญาณ ───────────────────────────────────────────────
    sod_chapters = {
        5:  ("โจรกรรมข้อมูลวิญญาณ",     "แฮกเกอร์ร่างทรงโจรกรรมข้อมูลวิญญาณคนตาย บุกบ้านเพื่อขโมยสูตรเสน่ห์โบราณ ผู้กองบัตสืบเส้นทางจากกุมารทอง GPS"),
        6:  ("Wi-Fi Hacker กุมารทอง",    "กุมารทองของจ่าดวงถูกแฮกจนส่งสัญญาณเพี้ยน ส่งผิดตำแหน่งพิกัดเจ้าที่ต่างๆ ทั่วกรุง ผู้กองบัตต้องแก้ไขก่อนเกิดหายนะสายมู"),
        7:  ("ยันต์ไวรัสดิจิทัล",        "ไวรัสที่ฝังในข้อมูลวิญญาณเริ่มแพร่กระจาย กินสัญญาณ Wi-Fi ทำให้ผีทั่วกรุงเทพออกอาละวาดเพราะสับสนพิกัด"),
        8:  ("ปิดคดีด้วยยันต์ Patch",    "อาจารย์คงเขียนโปรแกรม Patch ล้างไวรัส จ่าดวงสวดคาถา Deploy บนเซิร์ฟเวอร์วิญญาณ คดีสำเร็จพร้อม Cliffhanger คดีถัดไป"),
        9:  ("ฆาตกรรมในเมตาเวิร์ส",     "มีคนตายจริงในโลกแห่งความจริงหลังถูกฆ่าในเมตาเวิร์ส ผู้กองบัตต้องสวม VR Headset เพื่อสอบปากคำพยานดิจิทัล"),
        10: ("อาการ VR ป่วน",            "ผู้กองบัตใส่แว่น VR แล้วเมาคลื่น อ้วกพุ่งกลางโลกเสมือน แต่กลับค้นพบหลักฐานสำคัญโดยบังเอิญระหว่างสะลึมสะลือ"),
        11: ("ผู้ต้องสงสัยน่องไก่พูดได้", "ฆาตกรตัวจริงปรากฏตัวเป็นน่องไก่ทอดสุดฮาที่มีปัญญาประดิษฐ์ฝังอยู่ภายใน ผู้กองบัตต้องสอบปากคำน่องไก่อย่างจริงจัง"),
        12: ("ปิดคดีเมตาเวิร์ส",         "จับกุมผู้อยู่เบื้องหลังที่ใช้เมตาเวิร์สเป็นสถานที่ก่ออาชญากรรม ผู้กองบัตใช้ Nokia 3310 ตัดสัญญาณระบบ VR ของคนร้าย"),
        13: ("ฆาตกรรีวิวส้ม 1 ดาว",     "ร้านอาหารชื่อดังถูกรีวิวสังหาร เจ้าของร้านมาแจ้งความว่ามีแก๊งรีวิว 1 ดาวมาขู่กรรโชก ผู้กองบัตต้องแฝงตัวเป็นนักชิม"),
        14: ("ปฏิบัติการนักชิมลับ",      "ผู้กองบัตแฝงตัวรีวิวร้านอาหารล่อซื้อแก๊งรีวิวมืออาชีพ จ่าดวงปลอมเป็นบล็อกเกอร์สายมูอาหาร"),
        15: ("จับแอดมินมืออาชีพ",       "เผยตัวตนแอดมินเพจรีวิวที่อยู่เบื้องหลังแก๊งกรรโชก พร้อมหลักฐานดิจิทัลที่จ่าดวงหาได้จากกุมารทอง GPS"),
        16: ("ปิดคดีรีวิวส้มและตอนจบ",  "คดีทั้งหมดถูกปิด ผู้กองบัตได้รับคำชม แต่ทรมานจิตใจเพราะร้านอาหารที่แฝงตัวอยู่เลิกให้ส่วนลดกะเพรา"),
    }

    # ── 2. สมาคมประกันภัยลี้ลับ ──────────────────────────────────────────────
    ins_chapters = {
        5:  ("ผีสิงเครื่องจักรโรงงาน",  "โรงงานเคลมประกันว่าผีสิงเครื่องจักรทำให้ผลิตสินค้าพัง เอกและจิ๊บไปตรวจสอบพบเครื่องจักรทำงานผิดปกติจริงๆ"),
        6:  ("วิศวกรหรือผีวิศวกร",       "อาจารย์เดชวิเคราะห์พบว่าผีเป็นวิศวกรที่เสียชีวิตในโรงงานแต่ยังอยากทำงาน ยังซ่อมเครื่องจักรอยู่แต่ทำพัง"),
        7:  ("ปรึกษาผีวิศวกร",           "เอกเจรจาต่อรองกับผีวิศวกรให้หยุดซ่อมและเซ็นเอกสารยินยอมปฏิเสธสินไหม แต่ผีขอรับสวัสดิการบำนาญก่อน"),
        8:  ("ปิดคดีโรงงาน",             "เอกออกใบปฏิเสธสินไหม แต่ต้องเพิ่มเงื่อนไขพิเศษ: บริษัทต้องจัดพิธีส่งผีวิศวกรขึ้นสวรรค์ด้วยค่าใช้จ่ายตัวเอง"),
        9:  ("คุณไสยระเบิดไฟไหม้บ้าน", "บ้านลูกค้าไฟไหม้จากพิธีกรรมไสยศาสตร์ผิดพลาด เคลมประกันอัคคีภัย เอกต้องพิสูจน์ว่าไฟมาจากเจตนาหรืออุบัติเหตุไสยศาสตร์"),
        10: ("อาจารย์ไสยศาสตร์พยาน",    "เอกเชิญนักไสยศาสตร์มาเป็นพยานผู้เชี่ยวชาญ แต่กลับระเบิดความขัดแย้งระหว่างสำนักไสยศาสตร์ต่างๆ ในห้องประชุม"),
        11: ("สารวัตรไสยศาสตร์",         "อาจารย์เดชเปิดเผยว่ามีพิธีกรรมผิดกฎหมายไสยศาสตร์ที่ทำให้ไฟไหม้ เอกต้องตัดสินใจระหว่างกฎหมายกับไสยศาสตร์"),
        12: ("ปิดคดีคุณไสย",             "เอกออกเงื่อนไขพิเศษให้เคลมได้เฉพาะส่วนที่ไม่ได้มาจากพิธีกรรมโดยตรง จิ๊บเป็นพยานว่าได้ยินผีคาถาสวดก่อนไฟไหม้"),
        13: ("ประกันชีวิตผี",             "ผีคนหนึ่งเดินมาสมัครประกันชีวิต อ้างว่าตัวเองยังมีชีวิตอยู่เพียงแค่ไม่มีร่างกาย เอกต้องหาทางปฏิเสธตามกรมธรรม์"),
        14: ("กรมธรรม์ผีมาตรา 7",        "เอกพบว่ากรมธรรม์มี 'มาตรา 7' ที่คลุมเครือเรื่องสถานะการมีชีวิต อาจารย์เดชถกเถียงทางกฎหมายกับผีอย่างจริงจัง"),
        15: ("ศาลไสยศาสตร์",             "คดีขึ้นสู่ 'ศาลไสยศาสตร์' สถาบันพิสดารที่ตัดสินคดีเกี่ยวกับสิ่งเหนือธรรมชาติ เอกต้องแก้ต่างในนามบริษัทประกัน"),
        16: ("ปิดคดีประกันผีและตอนจบ",  "ศาลตัดสินว่าผีไม่มีสิทธิ์ทำประกัน เอกชนะคดีแต่ได้ชื่อเสียงว่าเป็น 'ผู้เชี่ยวชาญประกันภัยผี' ลูกค้าผีแห่มาสมัครเพิ่ม"),
    }

    # ── 3. วินดี้ นักสืบหลงทิศ ───────────────────────────────────────────────
    # บทที่ 1-4 มีต้นฉบับแล้วใน novel_draft.md แต่ยังไม่สมบูรณ์
    # เริ่มจาก 2 เพื่อ finish story arc ให้ครบ 10 บท
    windy_chapters = {
        2:  ("รหัสลับในถังขยะ",          "เนยใช้ OCR วิเคราะห์โน้ตปริศนาจากถังขยะ ได้เบาะแสเวลา สถานที่ และรหัสผ่าน PIZZA123 ทีมต้องรีบไปก่อนเที่ยง"),
        3:  ("บุกตรอกหลังร้าน",          "วินดี้นำทีมบุกตรอกหลังร้านแต่หลงทิศ บังเอิญพบผู้ต้องสงสัยคนแรกที่แต่งตัวเป็นนินจาพิซซ่าขี่สกู๊ตเตอร์ไฟฟ้า"),
        4:  ("จิลลี่ขัดขวาง",            "ยอดนักสืบจิลลี่ปรากฏตัวอ้างว่ารับคดีนี้ก่อนแล้ว เกิดการแข่งขันสืบหาหลักฐาน วินดี้โชคดีค้นพบเบาะแสสำคัญโดยพลัดตกตู้แช่แข็ง"),
        5:  ("สูตรลับแปดเหลี่ยม",        "ทีมวินดี้ถอดรหัสสูตรลับที่ซ่อนอยู่ในแป้งพิซซ่าตัวอย่าง เนยใช้ AI วิเคราะห์ส่วนผสมพบว่ามีสารลับที่ทำให้ติดพิซซ่าหน้าสับปะรด"),
        6:  ("สมาคมต่อต้านสับปะรด",      "เผยโฉมตัวร้ายที่แท้จริงคือ 'สมาคมต่อต้านสับปะรดบนอาหารโลก' ซึ่งจิลลี่เป็นสมาชิกชั้นนำ ทำให้จิลลี่กลายเป็นผู้ต้องสงสัย"),
        7:  ("วินดี้ถูกลักพาตัว",         "วินดี้โดนสมาคมต่อต้านสับปะรดลักพาตัวไปยัง 'ห้องปลอดสับปะรด' เนยและจิลลี่ต้องร่วมมือกันตามหา"),
        8:  ("เนยและจิลลี่บังคับทีม",    "เนยใช้ทักษะ AI ติดตาม GPS มือถือวินดี้ขณะที่จิลลี่ใช้เครือข่ายข่าวกรองของตัวเอง ทั้งสองขัดแย้งแต่ต้องร่วมมือ"),
        9:  ("บุกกอบกู้สูตรและวินดี้",    "บุกรังลับสมาคม วินดี้ช่วยตัวเองได้โดยบังเอิญหลงทิศออกนอกห้องขัง เนยเจาะระบบดึงสูตรลับกลับคืน"),
        10: ("ไขคดีและบทสรุป",           "วินดี้แถลงปิดคดีอย่างผิดฝาผิดตัวแต่ได้ผลถูกต้อง ส่งสูตรลับคืนเจ้าของ จิลลี่กลับใจออกจากสมาคม เนยได้พิซซ่าฟรีตลอดชีพ"),
    }

    novels = [
        {
            "key":   "สถานตรวจกาววญญาณ",
            "title": "สถานีตำรวจกาววิญญาณ: แผนกคดีไม่ปกติ",
            "outline_path": f"{outlines_dir}/สถานีตำรวจกาววิญญาณ_Outline.md",
            "chars_path":   f"{chars_dir}/สถานีตำรวจกาววิญญาณ_Characters.md",
            "chapters": sod_chapters,
            "notion_title": "สถานีตำรวจกาววิญญาณ — เล่มสมบูรณ์",
        },
        {
            "key":   "สมาคมประกนภยลลบ",
            "title": "สมาคมประกันภัยลี้ลับ: แผนกเคลมกรรม",
            "outline_path": f"{outlines_dir}/สมาคมประกันภัยลี้ลับ_Outline.md",
            "chars_path":   f"{chars_dir}/สมาคมประกันภัยลี้ลับ_Characters.md",
            "chapters": ins_chapters,
            "notion_title": "สมาคมประกันภัยลี้ลับ — เล่มสมบูรณ์",
        },
        {
            "key":   "วนดนกสบหลงทศ",
            "title": "วินดี้ นักสืบหลงทิศ กับ คดีพิซซ่าหน้าสับปะรดกู้โลก",
            "outline_path": None,   # ใช้ novel_draft.md แทน
            "chars_path":   None,   # ใช้ novel_draft.md แทน
            "chapters": windy_chapters,
            "notion_title": "วินดี้ นักสืบหลงทิศ — เล่มสมบูรณ์",
        },
    ]
    return novels

# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    chapters_dir = "SecondBrain/05_Active_Projects/Chapters"
    reviews_dir  = "SecondBrain/05_Active_Projects/Reviews"
    os.makedirs(chapters_dir, exist_ok=True)
    os.makedirs(reviews_dir,  exist_ok=True)

    novels = get_novels_config()

    print("\n" + "="*60)
    print(" 📚  NOVEL COMPLETION + REVIEW LOOP")
    print(" เรื่อง: สถานตรวจฯ / ประกันภัยลี้ลับ / วินดี้")
    print("="*60)

    for novel in novels:
        title       = novel["title"]
        key         = novel["key"]
        outline_p   = novel["outline_path"]
        chars_p     = novel["chars_path"]
        chapters    = novel["chapters"]
        notion_ttl  = novel["notion_title"]

        print(f"\n\n{'#'*60}")
        print(f"# 📖 Starting: {title}")
        print(f"{'#'*60}")

        # Load outline & characters
        if outline_p and os.path.exists(outline_p):
            with open(outline_p, "r", encoding="utf-8") as f:
                outline = f.read()
        else:
            # Windy: use novel_draft.md as outline
            windy_draft_path = "novel_draft.md"
            if os.path.exists(windy_draft_path):
                with open(windy_draft_path, "r", encoding="utf-8") as f:
                    outline = f.read()
            else:
                outline = f"นิยายแนวตลก-สืบสวนเรื่อง {title}"

        if chars_p and os.path.exists(chars_p):
            with open(chars_p, "r", encoding="utf-8") as f:
                characters = f.read()
        else:
            # Windy: extract character section from novel_draft.md
            characters = outline[:3000]  # first section has character profiles

        # Create Notion parent page for this novel
        print(f"[Notion] Creating parent page for: {title}")
        notion_parent = create_notion_subpage(PARENT_PAGE_ID, notion_ttl)

        # Process each chapter
        total = len(chapters)
        for idx, (ch_num, (ch_title, ch_desc)) in enumerate(chapters.items(), 1):
            print(f"\n[{idx}/{total}] บทที่ {ch_num}: {ch_title}")
            ok = process_chapter(
                novel_title=title,
                novel_key=key,
                outline=outline,
                characters=characters,
                ch_num=ch_num,
                ch_title=ch_title,
                ch_desc=ch_desc,
                notion_parent_id=notion_parent,
                chapters_dir=chapters_dir,
                reviews_dir=reviews_dir,
            )
            if not ok:
                print(f"[!] Chapter {ch_num} failed, skipping...")

        print(f"\n[✅] {title} — เขียนครบแล้ว!")

    print("\n\n" + "="*60)
    print(" 🎉  ALL NOVELS COMPLETE!")
    print("="*60)

if __name__ == "__main__":
    main()
