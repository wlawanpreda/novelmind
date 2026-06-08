import os
import json
import sys
import glob
from typing import Dict, Any, Tuple
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

# Setup Gemini API Key
API_KEY = os.environ.get("GEMINI_API_KEY")

def parse_markdown_file(filepath: str) -> Tuple[Dict[str, Any], str]:
    """Parse Obsidian markdown file and separate frontmatter from body content."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    frontmatter = {}
    body = content
    
    # Match YAML frontmatter
    import re
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        body = match.group(2)
        
        # Simple YAML parser for key-value strings
        for line in yaml_text.splitlines():
            # tag list item (ขึ้นต้น "- " ไม่มี ":") — ต้องเช็คก่อน เพราะไม่มี colon
            if re.match(r"^\s+-\s", line) and isinstance(frontmatter.get("tags"), list):
                frontmatter["tags"].append(line.strip()[2:].strip().strip('"').strip("'"))
            elif ":" in line:
                key, val = line.split(":", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                if key == "tags":
                    frontmatter[key] = []
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

def _extract_json(raw: str) -> Dict[str, Any]:
    """ดึง JSON ออกจากผลลัพธ์ LLM อย่างทนทาน — กัน ```json fence / ข้อความนำหน้า (local backend ชอบห่อ)"""
    import re as _re
    s = (raw or "").strip()
    # ลอกรั้วโค้ด ```json ... ```
    m = _re.search(r"```(?:json)?\s*(.+?)\s*```", s, _re.DOTALL)
    if m:
        s = m.group(1).strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    # fallback: เก็บตั้งแต่ { แรกถึง } ท้ายสุด
    i, j = s.find("{"), s.rfind("}")
    if i != -1 and j != -1 and j > i:
        return json.loads(s[i:j + 1])
    raise ValueError("ไม่พบ JSON ในผลลัพธ์")


def analyze_novel_with_ai(frontmatter: Dict[str, Any], body: str) -> Dict[str, Any]:
    """Send novel data to Gemini to perform translation, market fit analysis and localization suggestion in JSON format."""
    prompt = f"""
คุณคือ "Chief AI Architect & Literary Strategist" ผู้เชี่ยวชาญด้านการวิเคราะห์ตลาดนิยายออนไลน์ระดับสากลและผู้เชี่ยวชาญด้าน Creative Localization

หน้าที่ของคุณคือการวิเคราะห์เนื้อหานิยายดิบที่ดึงมาได้นี้ แล้วทำการแปลสกัดเนื้อหา วิเคราะห์ความคุ้มค่าเชิงธุรกิจสำหรับตลาดไทย และนำเสนอแนวทางการดัดแปลง/ดึงจุดเด่น (Inspired Concept) ที่ถูกกฎหมายและถูกจริตคนไทย

ข้อมูลนิยายดิบ:
- ชื่อเรื่อง: {frontmatter.get('title')}
- แหล่งที่มา: {frontmatter.get('source')}
- หมวดหมู่: {frontmatter.get('genre')}
- ผู้เขียน: {frontmatter.get('author')}
- 📊 สัญญาณความนิยม (สำคัญ — ใช้วิเคราะห์ว่าทำไมเรื่องนี้ปัง):
  คะแนนความนิยม {frontmatter.get('popularity_score','?')}/100 (อันดับ #{frontmatter.get('rank','?')}) ·
  เรตติ้ง {frontmatter.get('rating','?')} · ยอดวิว {frontmatter.get('views','?')} ·
  ผู้ติดตาม {frontmatter.get('bookmarks','?')} · รีวิว {frontmatter.get('reviews','?')} ·
  points {frontmatter.get('points','?')} · {frontmatter.get('chapters','?')} ตอน
- เรื่องย่อ/เนื้อหาดิบ:
{body}

วิเคราะห์โดยใช้ "ตัวเลขความนิยม" เป็นหลักฐานว่าอะไรทำให้เรื่องนี้ประสบความสำเร็จ
ให้ผลลัพธ์ JSON เท่านั้น:
{{
  "thai_working_titles": ["ชื่อภาษาไทยที่น่าดึงดูดใจ 1", "ชื่อภาษาไทยที่น่าดึงดูดใจ 2"],
  "localized_synopsis": "เรื่องย่อภาษาไทยที่เกลาสำนวนสละสลวยน่าติดตาม",
  "market_fit_score": 9,
  "market_fit_reasoning": "วิเคราะห์โอกาสและความนิยมของผู้อ่านไทยต่อพล็อตแนวนี้",
  "core_tropes": ["แนวพล็อตเด่น 1", "แนวพล็อตเด่น 2", "สูตรสำเร็จที่ดึงดูด"],
  "standout_points": ["จุดเด่นที่ทำให้เรื่องนี้ปัง/ติดอันดับ (อิงตัวเลข+เนื้อหา) 1", "2", "3"],
  "viral_hooks": ["hook/จุดที่ตรึงคนอ่านในฉากแรกๆ 1", "2"],
  "adapt_strategy": "วิธีดึงจุดเด่นเหล่านี้ไปใช้กับนิยายไทยเรื่องต่อไปของเราอย่างเป็นรูปธรรม (ห้ามลอก ให้เอาแก่นความสำเร็จมาปรับ)",
  "inspired_concept": "แนวทางสร้างเป็น Original IP ใหม่ที่ถูกกฎหมายและโดนใจคนไทย"
}}
"""
    # routed through the unified provider: role "analyzer" -> local (Mac mini) in hybrid mode
    raw = generate(prompt, role="analyzer", is_json=True)

    try:
        return _extract_json(raw)
    except Exception as e:
        print(f"[!] Error parsing JSON response: {raw[:500]}")
        raise e

def process_scouting_pool(second_brain_dir: str, limit: int = 0):
    """Scan the scouting pool for 'Scouted' novels and process them.

    วิเคราะห์เรื่อง 'นิยมสูงสุดก่อน' (popularity_score) — เรื่องเด่นได้คิวก่อน
    limit: ถ้า >0 วิเคราะห์แค่ N เรื่องเด่นสุดในรอบนี้ (คุมเวลา/ค่าใช้จ่าย)
    """
    scouting_pool_dir = os.path.join(second_brain_dir, "01_Scouting_Pool")
    md_files = glob.glob(os.path.join(scouting_pool_dir, "*.md"))

    # คัดเฉพาะ 'Scouted' แล้วเรียงตามคะแนนความนิยม (มาก→น้อย) ให้เรื่องเด่นได้คิวก่อน
    def _score(fp):
        try:
            fm, _ = parse_markdown_file(fp)
            if fm.get("status") != "Scouted":
                return None
            return float(fm.get("popularity_score") or 0)
        except Exception:
            return None
    queue = [(s, fp) for fp in md_files if (s := _score(fp)) is not None]
    queue.sort(key=lambda x: x[0], reverse=True)
    if limit and limit > 0:
        queue = queue[:limit]

    print(f"[*] Scouting Pool: {len(md_files)} ไฟล์ · รอวิเคราะห์ {len(queue)} เรื่อง"
          + (f" (จำกัด {limit} เด่นสุด)" if limit else "") + " — เรียงตามความนิยม")

    processed_count = 0
    for _score_val, filepath in queue:
        try:
            frontmatter, body = parse_markdown_file(filepath)

            # Only process if status is 'Scouted' (re-check; อาจถูกแก้ระหว่างรอบ)
            if frontmatter.get("status") != "Scouted":
                continue

            print(f"\n[*] Processing: {frontmatter.get('title')} ({frontmatter.get('source')}) "
                  f"· นิยม {frontmatter.get('popularity_score','?')}/100...")
            
            # Run AI Analysis (JSON)
            analysis = analyze_novel_with_ai(frontmatter, body)
            
            # Format analysis as beautiful markdown to write back to the file
            thai_titles_str = "\n".join([f"1. **{t}**" for t in analysis.get("thai_working_titles", [])])
            tropes_str = "\n".join([f"- **{t}**" for t in analysis.get("core_tropes", [])])
            standout_str = "\n".join([f"- ⭐ {t}" for t in analysis.get("standout_points", [])])
            hooks_str = "\n".join([f"- 🪝 {t}" for t in analysis.get("viral_hooks", [])])

            ai_analysis_md = f"""
## 🇹🇭 บทวิเคราะห์ภาษาไทย (AI Literary Analysis)

### 1. ชื่อเรื่องภาษาไทยที่แนะนำ (Thai Working Titles)
{thai_titles_str}

### 2. เรื่องย่อฉบับปรับปรุงบริบทไทย (Localized Synopsis)
{analysis.get("localized_synopsis")}

### 3. การประเมินตลาดและความคุ้มค่าเชิงพาณิชย์ (Market Viability)
- **คะแนนความเหมาะสมของตลาด (Market Fit Score):** `{analysis.get("market_fit_score")}/10`
- **บทวิเคราะห์ความต้องการเชิงลึก:**
  {analysis.get("market_fit_reasoning")}

### 4. แกนพล็อตเด่นที่ต้องสกัด (Core Tropes & Hooks)
{tropes_str}

### 5. ⭐ จุดเด่นที่ทำให้เรื่องนี้ปัง (Standout Points)
{standout_str}

### 6. 🪝 Hook ที่ตรึงคนอ่าน (Viral Hooks)
{hooks_str}

### 7. 🎯 วิธีเอามาปรับใช้กับเรื่องต่อไปของเรา (Adapt Strategy)
{analysis.get("adapt_strategy", "")}

### 8. แนวทางการสร้างเรื่องใหม่ (Inspired Concept & Localization)
{analysis.get("inspired_concept")}
"""
            
            # Form updated body
            new_body = f"""
# {frontmatter.get('title')}

## 📖 ข้อมูลพื้นฐาน (Basic Info)
- **แหล่งที่มา:** [{frontmatter.get('source')}]({frontmatter.get('url')})
- **ผู้เขียน:** {frontmatter.get('author')}
- **หมวดหมู่:** {frontmatter.get('genre')}
- **จำนวนตอนสะสม:** {frontmatter.get('chapters')} ตอน
- **ยอดบุ๊กมาร์ก/ผู้ติดตาม:** {frontmatter.get('bookmarks', 0)}
- **อัปเดตล่าสุด:** {frontmatter.get('last_updated')}

---
{ai_analysis_md}
---

## 🛠️ ขั้นตอนถัดไปในระบบ ANSRE (ANSRE Pipeline Status)
- [x] **Step 1: ตรวจสอบลิขสิทธิ์ในไทยเบื้องต้น (Copyright Check)**
- [x] **Step 2: สกัดแก่นเรื่องและจุดดึงดูดใจ (Core Concept Extraction)**
- [ ] **Step 3: ปรับแต่งฉากและตัวละครให้เข้ากับบริบทไทย (Localization & Design)**
- [ ] **Step 4: เจนตอนแรกและบทนิยายเสียง (Text & Audio Generation)**
"""
            
            # Update status and parameters
            frontmatter["status"] = "Analyzed"
            
            titles = analysis.get("thai_working_titles", [])
            if titles:
                frontmatter["thai_working_title"] = titles[0]
            frontmatter["market_fit_score"] = analysis.get("market_fit_score", "0")
                
            # Save updated file
            update_markdown_file(filepath, frontmatter, new_body)
            print(f"[+] Successfully analyzed and updated: {filepath}")
            processed_count += 1
            
        except Exception as e:
            print(f"[!] Error processing {filepath}: {e}")
            
    print(f"\n[+] Analysis batch completed. Processed {processed_count} files.")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="ANSRE analyzer — วิเคราะห์เรื่องเด่นก่อน")
    ap.add_argument("second_brain_path", nargs="?", default="./SecondBrain",
                    help="โฟลเดอร์ Second Brain (default: ./SecondBrain)")
    ap.add_argument("--limit", type=int, default=0,
                    help="วิเคราะห์แค่ N เรื่องเด่นสุดในรอบนี้ (0=ทั้งหมด)")
    a = ap.parse_args()

    # gemini key required only if the analyzer role actually routes to gemini
    if resolve_backend("analyzer") == "gemini" and not API_KEY:
        print("[!] ERROR: GEMINI_API_KEY is not set and analyzer routes to gemini.")
        print("    Set GEMINI_API_KEY, or use a local backend (LLM_BACKEND=local|hybrid).")
        sys.exit(1)

    print(f"[*] Analyzer backend = {resolve_backend('analyzer')}")
    process_scouting_pool(a.second_brain_path, limit=a.limit)
