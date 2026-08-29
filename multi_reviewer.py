"""
multi_reviewer.py — Multi-Agent Editorial Review Board & Iteration Loop
========================================================================

คณะกรรมการรีวิว Multi-Persona 4 ด้าน + วงจรปรับปรุงซ้ำอย่างน้อย 3 รอบ (>= 3 rounds)
จนกว่าคุณภาพจะผ่านเกณฑ์ (Target Score >= 8.5/10) และมั่นใจก่อนเข้าสู่ขั้นตอนผลิตสื่อ

4 Personas:
  1. Plot & Hook Critic (ตรวจโครงเรื่อง, Plot hole, Hook เปิดตอน, จังหวะ Pacing)
  2. Emotional & Character Reader (ตรวจมิติอารมณ์, เคมีตัวละคร, ความอิน)
  3. Prose & Dialogue Editor (ตรวจภาษาไทย, สำนวน, คำเชื่อม, ตัด meta-talk)
  4. Voice & Cinematic Director (ตรวจจังหวะคำสำหรับเสียงพากย์ TTS, ช็อตภาพสำหรับคลิป)
"""
from __future__ import annotations

import os
import re
import json
import time
from typing import Dict, Any, List, Tuple
from llm_provider import generate

# โหลด .env
ROOT = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

NO_META = ("\n\n[สำคัญ] ส่งคืน 'เฉพาะผลการวิเคราะห์ตามรูปแบบ JSON' เท่านั้น "
           "ห้ามมีคำนำ คำทักทาย หรือคำลงท้ายใดๆ")

_META_MARK = ("ในฐานะ", "chief", "ข้าพเจ้า", "ผมขอ", "ผมจะ", "นี่คือผลลัพธ์", "นี่คือบท",
              "ยอดเยี่ยม", "ตามที่ท่าน", "ตามที่คุณ", "คำบัญชา", "เจียระไน",
              "ขอรับช่วง", "ด้วยความยินดี", "ผมได้", "ข้าพเจ้าได้", "หวังว่า", "เรียบร้อยแล้วครับ")


def strip_meta(text: str) -> str:
    """ตัด meta-talk ของ AI ที่หัว/ท้ายออก"""
    if not text:
        return text
    lines = text.split("\n")
    popped = 0
    while lines and popped < 8:
        s = lines[0].strip()
        if s == "" or s == "---" or any(m in s.lower() for m in _META_MARK):
            lines.pop(0)
            popped += 1
        else:
            break
    popped = 0
    while lines and popped < 5:
        s = lines[-1].strip()
        if s == "" or s == "---" or any(m in s.lower() for m in _META_MARK):
            lines.pop()
            popped += 1
        else:
            break
    return "\n".join(lines).strip()


def _parse_json_safe(raw_text: str, default: dict) -> dict:
    """Parse JSON อย่างปลอดภัย ทนต่อรูปแบบ markdown backticks"""
    if not raw_text:
        return default
    candidates = [
        raw_text,
        re.sub(r"^```json\s*|\s*```$", "", raw_text.strip(), flags=re.MULTILINE),
        re.sub(r"```[a-zA-Z]*", "", raw_text).replace("```", "").strip()
    ]
    m = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if m:
        candidates.append(m.group(0))
        
    for cand in candidates:
        try:
            val = json.loads(cand.strip())
            if isinstance(val, dict):
                return val
        except Exception:
            continue
    return default


# ===========================================================================
# 4 Persona Reviewers
# ===========================================================================

def review_plot_and_hook(title: str, chapter_text: str, outline: str = "", world: str = "") -> Dict[str, Any]:
    """Persona 1: Plot & Hook Critic (ตรวจพล็อต, จังหวะ, Hook และ Cliffhanger)"""
    prompt = f"""คุณคือ "Senior Plot & Hook Critic" ผู้เชี่ยวชาญด้านโครงสร้างนิยายระทึกขวัญ/แฟนตาซีออนไลน์
หน้าที่ของคุณคือวิเคราะห์โครงเรื่อง, Hook เปิดเรื่อง, ความสมเหตุสมผล, และ Cliffhanger ท้ายบท

ชื่อเรื่อง: {title}
บริบท/โครงเรื่องหลัก:
{outline[:2000]}

กฎของโลก/ระบบ:
{world[:1500]}

เนื้อหาบทนิยายที่ต้องตรวจ:
{chapter_text}

จงให้คะแนน (0.0 - 10.0) พร้อมวิเคราะห์ตามหัวข้อต่อไปนี้ในรูปแบบ JSON:
{{
  "score": 8.5,
  "hook_strength": "การเปิดเรื่องดึงดูดใจเพียงใด",
  "pacing_evaluation": "จังหวะการดำเนินเรื่อง อืดหรือเร็วเกินไปตรงไหน",
  "plot_holes": ["จุดขัดแย้ง 1", "จุดขัดแย้ง 2"],
  "cliffhanger_rating": "ความรู้สึกอยากอ่านตอนต่อไปท้ายบท",
  "critical_fixes": ["จุดที่ต้องแก้ไขทันทีเพื่อให้พล็อตแน่นขึ้น"]
}}
"""
    raw = generate(prompt + NO_META, role="analyzer", is_json=True)
    default = {
        "score": 7.5,
        "hook_strength": "เปิดเรื่องได้ดี",
        "pacing_evaluation": "จังหวะสม่ำเสมอ",
        "plot_holes": [],
        "cliffhanger_rating": "มีปมทิ้งท้าย",
        "critical_fixes": ["กระชับการบรรยายช่วงกลางบท"]
    }
    return _parse_json_safe(raw, default)


def review_emotional_and_character(title: str, chapter_text: str, characters: str = "") -> Dict[str, Any]:
    """Persona 2: Emotional & Character Reader (ตรวจมิติอารมณ์, เคมีตัวละคร, ความอิน)"""
    prompt = f"""คุณคือ "Empathetic Character & Emotional Reader" นักอ่านสายอารมณ์และจิตวิทยาตัวละคร
หน้าที่ของคุณคือตรวจดูว่าตัวละครมีเลือดเนื้อ น่าเอาใจช่วย และสร้างความรู้สึกร่วม (Empathy) ให้ผู้อ่านได้จริงหรือไม่

ชื่อเรื่อง: {title}
ข้อมูลตัวละคร:
{characters[:2000]}

เนื้อหาบทนิยายที่ต้องตรวจ:
{chapter_text}

จงให้คะแนน (0.0 - 10.0) และวิเคราะห์ในรูปแบบ JSON:
{{
  "score": 8.0,
  "character_voice": "ความโดดเด่นและเป็นเอกลักษณ์ของเสียง/คำพูดตัวละคร",
  "emotional_resonance": "ฉากที่สร้างอารมณ์ร่วมได้ดีที่สุด",
  "flat_moments": ["จุดที่ตัวละครดูแบน ไร้อารมณ์ หรือการกระทำไม่สมเหตุสมผล"],
  "reader_empathy": "ระดับความผูกพันที่ผู้อ่านมีต่อตัวละครเอก",
  "critical_fixes": ["คำแนะนำเพิ่มมิติทางอารมณ์และแรงจูงใจ"]
}}
"""
    raw = generate(prompt + NO_META, role="reviewer", is_json=True)
    default = {
        "score": 7.5,
        "character_voice": "ตัวละครมีเอกลักษณ์ชัดเจน",
        "emotional_resonance": "สร้างความตึงเครียดได้ดี",
        "flat_moments": [],
        "reader_empathy": "น่าติดตาม",
        "critical_fixes": ["เพิ่มการบรรยายความรู้สึกภายในจิตใจของตัวละครเอก"]
    }
    return _parse_json_safe(raw, default)


def review_prose_and_dialogue(title: str, chapter_text: str) -> Dict[str, Any]:
    """Persona 3: Prose & Dialogue Editor (ตรวจภาษาไทย, ความสละสลวย, คำเชื่อม, สำนวน)"""
    prompt = f"""คุณคือ "Chief Literary & Thai Prose Editor" บรรณาธิการภาษาไทยมือฉมัง
หน้าที่ของคุณคือตรวจภาษา สำนวน บทสนทนา คำเชื่อม คำซ้ำ และตัดสำนวนแปลต่างประเทศที่ไม่เป็นธรรมชาติ

ชื่อเรื่อง: {title}
เนื้อหาบทนิยายที่ต้องตรวจ:
{chapter_text}

จงให้คะแนน (0.0 - 10.0) และวิเคราะห์ในรูปแบบ JSON:
{{
  "score": 8.2,
  "flow_and_rhythm": "ความลื่นไหลของสำนวนภาษาไทย",
  "dialogue_naturalness": "ความเป็นธรรมชาติของบทสนทนา (ไม่ลิเก ไม่แข็งทื่อ)",
  "awkward_phrases": ["วลีที่ฟังดูแปลกหรือแปลตรงตัว", "คำซ้ำซาก"],
  "meta_talk_detected": false,
  "critical_fixes": ["คำแนะนำในการเกลาประโยคและเลือกใช้คำ"]
}}
"""
    raw = generate(prompt + NO_META, role="editor", is_json=True)
    default = {
        "score": 8.0,
        "flow_and_rhythm": "ภาษาลื่นไหลดี",
        "dialogue_naturalness": "บทสนทนาเป็นธรรมชาติ",
        "awkward_phrases": [],
        "meta_talk_detected": False,
        "critical_fixes": ["เกลาคำเชื่อมให้สละสลวยขึ้น"]
    }
    return _parse_json_safe(raw, default)


def review_voice_and_cinematic(title: str, chapter_text: str) -> Dict[str, Any]:
    """Persona 4: Voice & Cinematic Director (ตรวจความพร้อมสำหรับเสียงพากย์ TTS & วิดีโอ Teaser)"""
    prompt = f"""คุณคือ "Cinematic & Audiobook Director" ผู้กำกับการพากย์เสียงและภาพยนตร์สั้น
หน้าที่ของคุณคือตรวจว่าบทนี้เมื่อนำไปอ่านออกเสียง (TTS) ฟังเข้าใจง่ายหรือไม่ และมีภาพที่นำไปทำวิดีโอ Teaser เด่นชัดหรือไม่

ชื่อเรื่อง: {title}
เนื้อหาบทนิยายที่ต้องตรวจ:
{chapter_text}

จงให้คะแนน (0.0 - 10.0) และวิเคราะห์ในรูปแบบ JSON:
{{
  "score": 8.5,
  "ear_friendly_score": "ระดับความเข้าใจง่ายเมื่อฟังผ่านเสียง (ห้ามมีประโยคซ้อนยาวเกินไป)",
  "stumbling_blocks": ["คำหรือประโยคที่ระบบอ่านเสียงอาจสะดุดหรือออกเสียงเพี้ยน"],
  "cinematic_visuals": ["ฉากที่เด่นชัดเหมาะนำไปสร้างภาพปกและวิดีโอ Teaser"],
  "teaser_hook_quote": "ประโยคเด็ด (Punchline/Hook) ที่เหมาะใส่ในคลิป Teaser สั้น 15-30 วินาที",
  "critical_fixes": ["คำแนะนำปรับแต่งให้เหมาะกับการฟังและการทำวิดีโอ"]
}}
"""
    raw = generate(prompt + NO_META, role="audio", is_json=True)
    default = {
        "score": 8.0,
        "ear_friendly_score": "ฟังเข้าใจง่าย ประโยคกระชับ",
        "stumbling_blocks": [],
        "cinematic_visuals": ["ฉากเปิดตัวละครในบรรยากาศตึงเครียด"],
        "teaser_hook_quote": "ถ้าคุณรู้ว่าความตายกำลังนับถอยหลัง คุณจะเลือกวิ่งหนีหรือหันหน้าสู้?",
        "critical_fixes": ["แบ่งวรรคประโยคยาวให้เป็นท่อนสั้นสำหรับการหายใจพากย์เสียง"]
    }
    return _parse_json_safe(raw, default)


# ===========================================================================
# Refiner / Writer Improvement
# ===========================================================================

def refine_chapter_prose(
    title: str,
    current_text: str,
    round_num: int,
    critique_bundle: Dict[str, Any],
    outline: str = "",
    characters: str = "",
    world: str = ""
) -> str:
    """สั่งให้ Refiner Agent เขียนแก้บทตามคอมเมนต์ของ Reviewer ทั้ง 4 ท่าน"""
    plot_fixes = "\n- ".join(critique_bundle.get("plot", {}).get("critical_fixes", []))
    char_fixes = "\n- ".join(critique_bundle.get("character", {}).get("critical_fixes", []))
    prose_fixes = "\n- ".join(critique_bundle.get("prose", {}).get("critical_fixes", []))
    voice_fixes = "\n- ".join(critique_bundle.get("voice", {}).get("critical_fixes", []))
    
    awkward = ", ".join(critique_bundle.get("prose", {}).get("awkward_phrases", []))
    stumbling = ", ".join(critique_bundle.get("voice", {}).get("stumbling_blocks", []))

    prompt = f"""คุณคือ "Master Novelist & Chief Revision Editor" นักเขียนและผู้ปรับปรุงนิยายระดับพรีเมียม
หน้าที่ของคุณคือ **ปรับปรุงและเขียนยกระดับเนื้อหานิยายเรื่อง '{title}' (รอบปรับปรุงที่ {round_num})**
โดยแก้ไขตามข้อติติงและคำแนะนำจากคณะกรรมการรีวิว 4 ด้านอย่างเคร่งครัด

---
[เนื้อหาเดิมก่อนปรับปรุง]:
{current_text}

---
[ข้อติติงและคำแนะนำจากคณะกรรมการรีวิวที่ต้องแก้ให้หมด]:
1. ด้านโครงเรื่อง & Hook:
- {plot_fixes or 'รักษาความกระชับและปมทิ้งท้าย'}

2. ด้านอารมณ์ & มิติตัวละคร:
- {char_fixes or 'เน้นอารมณ์ความรู้สึกภายในของตัวละครให้เด่นชัด'}

3. ด้านภาษาไทย & สำนวน:
- {prose_fixes or 'ขัดเกลาสำนวนให้สละสลวยเป็นธรรมชาติ'}
{f'*(โปรดแก้คำ/วลีที่ไม่ลื่นไหลเหล่านี้: {awkward})*' if awkward else ''}

4. ด้านจังหวะการอ่านออกเสียง (Audiobook Friendly):
- {voice_fixes or 'จัดจังหวะประโยคให้กระชับ ชัดเจน ฟังง่าย'}
{f'*(โปรดปรับแก้ประโยคสะดุดเหล่านี้: {stumbling})*' if stumbling else ''}

---
[ข้อกำหนดในการส่งมอบ]:
1. ส่งคืน **เนื้อหานิยายฉบับปรับปรุงเต็มบท (Full Prose)** ที่สละสลวย สมบูรณ์แบบ ลื่นไหล ตื่นเต้น
2. ห้ามมีข้อความทักทาย ห้ามมีคำนำคำลงท้าย ห้ามมีสรุปสิ่งที่แก้ เริ่มต้นที่เนื้อหานิยายทันที
3. รักษาความยาวให้เหมาะสม ไม่สั้นเกินไปและไม่ยืดเยื้อ
"""
    refined = generate(prompt + NO_META, role="writer")
    return strip_meta(refined) or current_text


# ===========================================================================
# Multi-Round Editorial Iteration Loop Engine
# ===========================================================================

def run_multi_agent_review_loop(
    title: str,
    chapter_text: str,
    outline: str = "",
    characters: str = "",
    world: str = "",
    min_rounds: int = 3,
    max_rounds: int = 5,
    target_score: float = 8.5,
    verbose: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """
    รันลูปรวม Reviewer 4 คน + Refiner อย่างน้อย min_rounds รอบ (ค่าเริ่มต้น 3 รอบ)
    จนกว่าคะแนนรวมเฉลี่ย >= target_score (หรือครบ max_rounds)
    
    คืนค่า: (final_chapter_text, scorecard_report)
    """
    current_text = chapter_text
    round_history = []
    
    if verbose:
        print(f"\n🎭 [Multi-Agent Review Board] เริ่มต้นกระบวนการรีวิวและปรับปรุง '{title}'")
        print(f"   เกณฑ์: วนซ้ำอย่างน้อย {min_rounds} รอบ | เป้าหมายคะแนน >= {target_score}/10")

    for r in range(1, max_rounds + 1):
        if verbose:
            print(f"\n--- 🔄 รอบที่ {r}/{max_rounds} ---")
            print("   1) Plot & Hook Critic กำลังตรวจโครงเรื่อง...")
        plot_eval = review_plot_and_hook(title, current_text, outline, world)
        
        if verbose:
            print("   2) Emotional Reader กำลังตรวจมิติตัวละคร...")
        char_eval = review_emotional_and_character(title, current_text, characters)
        
        if verbose:
            print("   3) Prose Editor กำลังตรวจภาษาไทยและสำนวน...")
        prose_eval = review_prose_and_dialogue(title, current_text)
        
        if verbose:
            print("   4) Cinematic Director กำลังตรวจจังหวะเสียงพากย์และช็อตวิดีโอ...")
        voice_eval = review_voice_and_cinematic(title, current_text)
        
        s_plot = float(plot_eval.get("score", 7.5))
        s_char = float(char_eval.get("score", 7.5))
        s_prose = float(prose_eval.get("score", 7.5))
        s_voice = float(voice_eval.get("score", 7.5))
        
        composite_score = round((s_plot * 0.30) + (s_char * 0.25) + (s_prose * 0.25) + (s_voice * 0.20), 2)
        
        round_data = {
            "round": r,
            "composite_score": composite_score,
            "scores": {
                "plot": s_plot,
                "character": s_char,
                "prose": s_prose,
                "voice": s_voice
            },
            "evaluations": {
                "plot": plot_eval,
                "character": char_eval,
                "prose": prose_eval,
                "voice": voice_eval
            }
        }
        round_history.append(round_data)
        
        if verbose:
            print(f"   📊 ผลคะแนนรอบที่ {r}: รวม = {composite_score}/10 (พล็อต: {s_plot}, ตัวละคร: {s_char}, ภาษา: {s_prose}, เสียง: {s_voice})")

        is_last_round = (r >= max_rounds)
        passed_criteria = (r >= min_rounds and composite_score >= target_score)
        
        if passed_criteria:
            if verbose:
                print(f"   ✅ ผ่านเกณฑ์คุณภาพแล้วในรอบที่ {r}! (คะแนน {composite_score} >= {target_score} และทำซ้ำครบ {r} รอบ)")
            break
        elif is_last_round:
            if verbose:
                print(f"   ⚠️ ครบจำนวนรอบสูงสุด ({max_rounds} รอบ) — สรุปเนื้อหาฉบับสมบูรณ์ที่สุด")
            break
        else:
            if verbose:
                need_reason = f"ยังไม่ครบขั้นต่ำ {min_rounds} รอบ" if r < min_rounds else f"คะแนน {composite_score} ยังไม่ถึง {target_score}"
                print(f"   ✍️ สั่งการ Refiner Agent ปรับปรุงเนื้อหาต่อ ({need_reason})...")
            
            critique_bundle = {
                "plot": plot_eval,
                "character": char_eval,
                "prose": prose_eval,
                "voice": voice_eval
            }
            new_text = refine_chapter_prose(
                title=title,
                current_text=current_text,
                round_num=r + 1,
                critique_bundle=critique_bundle,
                outline=outline,
                characters=characters,
                world=world
            )
            if new_text and len(new_text.strip()) > 50:
                current_text = new_text

    initial_score = round_history[0]["composite_score"]
    final_score = round_history[-1]["composite_score"]
    improvement = round(final_score - initial_score, 2)
    
    scorecard_report = {
        "title": title,
        "total_rounds": len(round_history),
        "initial_score": initial_score,
        "final_score": final_score,
        "score_improvement": improvement,
        "passed_quality_gate": final_score >= target_score,
        "final_scores_breakdown": round_history[-1]["scores"],
        "teaser_hook_quote": round_history[-1]["evaluations"]["voice"].get("teaser_hook_quote", ""),
        "cinematic_visuals": round_history[-1]["evaluations"]["voice"].get("cinematic_visuals", []),
        "history": round_history
    }
    
    return current_text, scorecard_report


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    
    # ถ้ามี argument ให้ดึงไฟล์บทนิยายมารีวิว หรือใช้บททดสอบ
    sample_text = """
เข็มนาฬิกาดิจิทัลบนข้อมือของอคินกระพริบเป็นแสงสีเลือด ตัวเลข 00:03:00 กำลังนับถอยหลังลงอย่างไม่ปรานี
ในห้องใต้ดินที่อับชื้น กลิ่นสนิมและควันไฟลอยคละคลุ้งไปทั่ว เขาต้องเลือกระหว่างการถอดรหัสกล่องนิรภัย หรือวิ่งหนีเอาชีวิตรอด
เสียงกระซิบประหลาดดังขึ้นข้างหู 'ถ้าเจ้าไขรหัสไม่ได้ วิญญาณของเจ้าจะถูกริบเป็นค่าปรับ'
อคินกัดฟันแน่น ปลายนิ้วสัมผัสแป้นพิมพ์โลหะเย็นเฉียบ ร่างกายสั่นสะท้านด้วยความกลัวแต่ดวงตากลับลุกโชนด้วยความมุ่งมั่น
    """
    target_title = "ยอดนักสืบสปีดรัน"
    
    if args:
        target_title = args[0]
        # ลองหาไฟล์ chapter
        matching = [f for f in os.listdir(os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Chapters")) if target_title in f]
        if matching:
            with open(os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Chapters", matching[0]), "r", encoding="utf-8") as f:
                sample_text = f.read()

    print(f"[*] เริ่มทดสอบ Multi-Agent Review บน '{target_title}'...")
    polished, report = run_multi_agent_review_loop(
        title=target_title,
        chapter_text=sample_text,
        min_rounds=3,
        max_rounds=3,
        target_score=8.5,
        verbose=True
    )
    print("\n--- 📋 สรุปผลคะแนนจาก Multi-Agent Review Board ---")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    
    try:
        from discord_reporter import send_review_summary_to_discord
        send_review_summary_to_discord(target_title, 1, report)
        print("✅ ส่งผลรีวิวเข้า Discord ห้อง writer-feedback เรียบร้อย")
    except Exception as e:
        print(f"⚠️ Discord error: {e}")
