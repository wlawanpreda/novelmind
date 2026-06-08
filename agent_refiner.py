import os
import re
import sys
import json
from datetime import datetime
from llm_provider import generate, resolve_backend, _coerce_json

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ[key.strip()] = val.strip().strip('"').strip("'")

API_KEY = os.environ.get("GEMINI_API_KEY")
# GEMINI key required only if any refiner role still routes to gemini
if not API_KEY and "gemini" in {resolve_backend(r) for r in ("researcher", "writer", "editor")}:
    print("[!] ERROR: GEMINI_API_KEY is not set and a refiner role routes to gemini.")
    print("    Set GEMINI_API_KEY, or use LLM_BACKEND=local for a fully local run.")
    sys.exit(1)

# ----------------- System Prompts for Roles -----------------

SAFETY_GUIDELINE = """
[กฎความปลอดภัยที่สำคัญที่สุด]: ห้ามเขียนคำสยองขวัญสุดขั้ว ความรุนแรง เลือด การฆาตกรรม หรือรายละเอียดเกี่ยวกับศพ เพื่อป้องกันการถูกเซ็นเซอร์บนสื่อสังคมออนไลน์และตัวกรองของ AI 
ให้เลี่ยงไปเน้นการสร้างบรรยากาศลึกลับ (Mystery), โลกแฟนตาซี, มิติลี้ลับ, ระบบดันเจี้ยน, การทำงานเป็นสตรีมเมอร์ หรือความตื่นเต้นระทึกขวัญเชิงจิตวิทยาแบบ PG-13 ที่น่าสนใจและน่าติดตามสำหรับคนทุกวัยแทน
"""

RESEARCHER_PROMPT = f"""
คุณคือ "Viral Trend & Literary Researcher" หน้าที่ของคุณคือการวิเคราะห์เนื้อหานิยายและบทโปรโมตที่เขียนล่าสุด
วิจัยเปรียบเทียบกับพล็อตนิยายเว็บสตรีมดันเจี้ยนยอดนิยมในไทย (เช่น Dek-D, Dek-D Top, Fictionlog) และเทรนด์คลิปไวรัลบน TikTok/Shorts
วิเคราะห์จุดด้อย คีย์เวิร์ดที่ล้าสมัย หรือจุดที่ยังไม่สะดุดตาพอสำหรับดึงความสนใจคนดูใน 3 วินาทีแรก
และนำเสนอแนวทางการวิจัยเชิงลึก + แนะนำคำโปรย/พล็อตหักมุม (Hook) ที่ควรเพิ่มเข้าไป

{SAFETY_GUIDELINE}

ให้ผลลัพธ์การวิเคราะห์เป็น JSON รูปแบบนี้เท่านั้น:
{{
  "trend_analysis": "วิเคราะห์กระแสที่สอดคล้องกับพล็อตตอนนี้",
  "suggested_hooks": ["คำโปรย/ประโยคเปิดตัวที่หยุดคนดูได้ 3 วินาทีแรกบน TikTok 1", "คำโปรย 2"],
  "improvements_needed": "ประเด็นที่ต้องแก้ไขเพื่อให้งานโดนใจคนไทยและไวรัลในโซเชียล"
}}
"""

WRITER_PROMPT = f"""
คุณคือ "Master Viral Novelist & Social Copywriter" หน้าที่ของคุณคือการดัดแปลงและขยายความบทนิยายและเนื้อหาสำหรับใช้ลง Social Media ให้ดึงดูดใจสูงสุด
โดยเขียนเนื้อหาออกเป็น 2 ส่วนหลัก:
1. **โซเชียลทีเซอร์ฉบับขยี้อารมณ์ (Social Hook Script)**: บทสำหรับใช้ทำคลิปสั้นลง TikTok/Shorts (มีการระบุคำพูด ภาพประกอบประกอบฉาก และจุดหักมุม)
2. **ตอนที่ 1 ฉบับปรับปรุง (Refined Chapter 1 Intro)**: ย่อหน้าแรกๆ ของนิยาย (ประมาณ 500-800 คำ) ที่เขียนด้วยภาษาที่ทรงพลัง คมคาย สอดแทรกความตลก/ระทึกขวัญและปมลึกลับ

นำคำแนะนำจากบทวิจัยและการรีวิวของบรรณาธิการมาปรับปรุงเขียนใหม่ให้ดีขึ้นอย่างเห็นได้ชัดในทุกรอบ

{SAFETY_GUIDELINE}

ให้ผลลัพธ์เป็น JSON รูปแบบนี้เท่านั้น:
{{
  "social_hook_script": "บท TikTok/Shorts ที่มีฉากหักมุม คำพูด และภาพในคลิป เพื่อโปรโมตจริง",
  "refined_chapter_intro": "เนื้อหานิยายตอนแรกเฉพาะฉบับขยี้ปมความยาว 500-800 คำ ที่ดีที่สุด"
}}
"""

EDITOR_PROMPT = f"""
คุณคือ "Chief Literary Editor & Social Media Critic" หน้าที่ของคุณคือการตรวจชิ้นงานของนักเขียนอย่างละเอียดและให้คะแนน
ประเมินหัวข้อต่อไปนี้:
1. **Hook Strength (ความแรงของจุดหยุดสายตา 3 วินาทีแรก)** (1-100)
2. **Social Media Engagement Potential (ความน่าแชร์/คอมเมนต์/ติดตามต่อ)** (1-100)
3. **Pacing & Readability (ความลื่นไหล ภาษาไม่อืดอาดยืดเยื้อ)** (1-100)

วิจารณ์ชิ้นงานอย่างตรงไปตรงมา ชี้จุดที่ยังขัดใจ ภาษาที่ยังไม่ธรรมชาติ และคำนวณคะแนนเฉลี่ยรวม (Overall Score) 1-100

{SAFETY_GUIDELINE}

ให้ผลลัพธ์เป็น JSON รูปแบบนี้เท่านั้น:
{{
  "critique": "คำวิจารณ์อย่างละเอียด เจาะลึกจุดดีและจุดที่ต้องเกลา",
  "scores": {{
    "hook": 85,
    "engagement": 80,
    "pacing": 90
  }},
  "overall_score": 85
}}
"""

# ----------------- Helper Functions -----------------

def call_gemini(prompt: str, system_instruction: str, role: str = "default", is_retry: bool = False) -> dict:
    """Query the unified LLM provider (gemini/local by role) with JSON + self-healing safety retries.

    Name kept as call_gemini for backward-compat; backend is chosen by `role` via llm_provider.
    """
    if is_retry:
        # Tweak the prompt to be extremely safe, bypassing safety filters on retry
        prompt = f"[SAFETY RETRY - กรุณาเขียนและวิเคราะห์ด้วยโทนที่ปลอดภัยระดับครอบครัว PG-13 หลีกเลี่ยงความน่ากลัวรุนแรง ผี และเรื่องสยองขวัญทุกชนิด เปลี่ยนไปเน้นความแฟนตาซี มิติลี้ลับ และระบบสตรีมเมอร์สุดระทึกแทน!]\n{prompt}"

    try:
        raw = generate(prompt, role=role, is_json=True, system=system_instruction)
        if not raw or not raw.strip():
            if not is_retry:
                print("    [!] Empty response. Retrying with safe instructions...")
                return call_gemini(prompt, system_instruction, role, is_retry=True)
            print("    [!] Empty even on safe retry. Returning empty schema.")
            return {}
        return json.loads(_coerce_json(raw))
    except Exception as e:
        err_msg = str(e).lower()
        recoverable = any(k in err_msg for k in ("candidates", "blocked", "prohibited", "json", "expecting"))
        if recoverable and not is_retry:
            print("    [!] Generation/parse issue. Retrying with safe instructions...")
            return call_gemini(prompt, system_instruction, role, is_retry=True)
        if is_retry:
            print("    [!] Failed even on safe retry. Returning empty schema.")
            return {}
        raise e

def run_loop(second_brain_dir: str, max_iterations: int = 50):
    # Find active chapters and outlines to use as starting seed
    chapters_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Chapters")
    outlines_dir = os.path.join(second_brain_dir, "02_Concept_Extraction")
    
    chapter_files = [f for f in os.listdir(chapters_dir) if f.endswith(".md") and "รานคาเหนอโลก" in f]
    outline_files = [f for f in os.listdir(outlines_dir) if f.endswith(".md") and "รานคาเหนอโลก" in f]
    
    if not chapter_files or not outline_files:
        print("[!] Cannot find generated chapter or outline for 'ร้านค้าเหนือโลก'")
        sys.exit(1)
        
    chapter_path = os.path.join(chapters_dir, chapter_files[0])
    outline_path = os.path.join(outlines_dir, outline_files[0])
    
    with open(chapter_path, "r", encoding="utf-8") as f:
        initial_chapter = f.read()
        
    with open(outline_path, "r", encoding="utf-8") as f:
        initial_outline = f.read()
        
    print(f"[*] Loaded initial chapter ({len(initial_chapter)} chars) and outline ({len(initial_outline)} chars).")
    
    # Target directory for iteration logs
    drafts_dir = os.path.join(second_brain_dir, "05_Active_Projects", "Draft_Iterations")
    os.makedirs(drafts_dir, exist_ok=True)
    
    # Initialize state
    current_social_script = "ไม่มีบทตั้งต้น"
    current_chapter_intro = initial_chapter[:3000] # Take first 3000 chars as seed
    last_critique = "นี่คือรอบเริ่มต้น รันวิจัยเพื่อหาจุดบกพร่องและสร้างสรรค์บทเขียนที่ดีที่สุด"
    last_research = {}
    best_score = 0
    consecutive_no_improve = 0
    
    print(f"[*] Starting Multi-Agent Refinement Loop. Goal: Score >= 95. Max iterations: {max_iterations}")
    
    for i in range(1, max_iterations + 1):
        print(f"\n================ ITERATION {i}/{max_iterations} ================")
        
        # Step 1: Researcher Analyzes & Researches
        print("[*] 1. Researcher: Analyzing trends and hooks...")
        research_prompt = f"""
วิเคราะห์นิยายและบทโปรโมตโซเชียลล่าสุดดังนี้:
1. นิยายตอนแรก:
{current_chapter_intro}

2. บท TikTok/Shorts ล่าสุด:
{current_social_script}

3. คำวิจารณ์รอบล่าสุด:
{last_critique}
"""
        try:
            research_res = call_gemini(research_prompt, RESEARCHER_PROMPT, role="researcher")
            last_research = research_res
            print(f"[+] Suggested Hook: \"{research_res.get('suggested_hooks', ['N/A'])[0]}\"")
        except Exception as e:
            print(f"[!] Researcher failed: {e}. Skipping to next step.")
            
        # Step 2: Writer Rewrites & Refines
        print("[*] 2. Writer: Rewriting copy & chapter intro...")
        writer_prompt = f"""
ปรับปรุงบทเขียนโดยอ้างอิงข้อมูลนี้:
1. การวิเคราะห์เทรนด์และ Hook ที่แนะนำ:
{json.dumps(last_research, ensure_ascii=False, indent=2)}

2. คำวิจารณ์ครั้งล่าสุด:
{last_critique}

3. นิยายตอนแรกฉบับเดิม:
{current_chapter_intro}

4. บท TikTok/Shorts ฉบับเดิม:
{current_social_script}
"""
        try:
            writer_res = call_gemini(writer_prompt, WRITER_PROMPT, role="writer")
            current_social_script = writer_res.get("social_hook_script", current_social_script)
            current_chapter_intro = writer_res.get("refined_chapter_intro", current_chapter_intro)
            print("[+] Writer completed rewriting.")
        except Exception as e:
            print(f"[!] Writer failed: {e}.")
            
        # Step 3: Editor Critiques & Scores
        print("[*] 3. Editor: Critiquing and scoring...")
        editor_prompt = f"""
ตรวจและให้คะแนนชิ้นงานที่เพิ่งแก้ไขล่าสุดนี้:
1. บท TikTok/Shorts:
{current_social_script}

2. ตอนที่ 1 ฉบับปรับปรุงใหม่:
{current_chapter_intro}
"""
        try:
            editor_res = call_gemini(editor_prompt, EDITOR_PROMPT, role="editor")
            last_critique = editor_res.get("critique", "")
            score = editor_res.get("overall_score", 0)
            scores = editor_res.get("scores", {})
            print(f"[+] Overall Score: {score}/100 (Hook: {scores.get('hook', 0)}, Engagement: {scores.get('engagement', 0)}, Pacing: {scores.get('pacing', 0)})")
        except Exception as e:
            print(f"[!] Editor failed: {e}.")
            score = 0
            
        # Save Iteration Details
        iteration_data = {
            "iteration": i,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "research": last_research,
            "social_hook_script": current_social_script,
            "refined_chapter_intro": current_chapter_intro,
            "editor_critique": last_critique,
            "score": score
        }
        
        iter_file = os.path.join(drafts_dir, f"iteration_{i:02d}.json")
        with open(iter_file, "w", encoding="utf-8") as f:
            json.dump(iteration_data, f, ensure_ascii=False, indent=4)
            
        # Track improvements
        if score > best_score:
            print(f"[🎉] Improved Score from {best_score} to {score}!")
            best_score = score
            consecutive_no_improve = 0
            
            # Save the best version to main active projects file
            best_file = os.path.join(second_brain_dir, "05_Active_Projects", "viral_social_package.md")
            best_content = f"""# 🚀 Viral Social Package: ร้านค้าเหนือโลก
*ปรับปรุงผ่านกระบวนการจำลอง AI Multi-Agent Loop รอบที่ {i} (คะแนนบรรณาธิการ: {score}/100)*
*วิเคราะห์และพัฒนาเมื่อ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

---

## 🎬 1. บทวิดีโอโปรโมตคลิปสั้น (Viral TikTok / Shorts Script)
{current_social_script}

---

## 📖 2. บทนิยายตอนที่ 1 ฉบับปรับปรุงปมไวรัล (Refined Chapter 1 Hook)
{current_chapter_intro}

---

## 🧐 3. คำวิจารณ์ล่าสุดจากบรรณาธิการ (Latest Editorial Review)
{last_critique}
"""
            with open(best_file, "w", encoding="utf-8") as f:
                f.write(best_content)
        else:
            consecutive_no_improve += 1
            print(f"[~] No improvement in score. Best: {best_score}. Consecutive without improvement: {consecutive_no_improve}")
            
        # Early stopping rules to conserve API and time if score is extremely high
        if score >= 97:
            print(f"[✨] Editor score reached target ({score}/100). Auto-terminating early.")
            break
        if consecutive_no_improve >= 8 and i >= 15:
            print("[*] Score stabilized and did not improve for 8 consecutive rounds after 15 iterations. Terminating.")
            break
            
    print(f"\n[+] Multi-Agent loop finished. Best Score: {best_score}/100. Best package saved to: SecondBrain/05_Active_Projects/viral_social_package.md")

if __name__ == "__main__":
    second_brain_path = "./SecondBrain"
    max_iters = 50
    if len(sys.argv) > 1:
        second_brain_path = sys.argv[1]
    if len(sys.argv) > 2:
        try:
            max_iters = int(sys.argv[2])
        except ValueError:
            pass
        
    run_loop(second_brain_path, max_iterations=max_iters)
