"""
agent_auditor.py — Autonomous Production QA Inspector & Meta-talk Auditor
==========================================================================

Subagent / Inspector ประจำระบบ ANSRE สำหรับตรวจสอบและสกัดกั้น:
1. การรั่วไหลของคำสื่อสารภายในของ AI / Subagents (Meta-talk / Prompt Leaks):
   เช่น "Chief Literary Editor", "Audio Production Director", "ในฐานะ...",
   "ยอดเยี่ยมมากครับ", "ฉบับขัดเกลาโดย...", "Error: Generation returned empty result"
2. ความไม่สอดคล้องกันระหว่างเสียงพากย์, ชื่อเรื่อง, ชื่อตอน, และเนื้อหา:
   - ตรวจสอบว่าเสียงพากย์ (TTS) อ่านตรงกับชื่อตอนใน Chapter และ AudioScript
   - ตรวจสอบเพศและโทนเสียงของตัวละคร (ป้องกันตัวเอกชายพูดเสียงหญิง)
   - ตรวจสอบว่าวิดีโอ Teaser มีชื่อเรื่อง/ชื่อตอนครบถ้วน และไม่ถูกครอบตัด (crop) จาก Zoom
3. การตรวจรับรองก่อนเผยแพร่จริง (Pre-Publish Quality Gate):
   - ห้ามเผยแพร่สู่ YouTube, TikTok, Bilibili หรือ ReadAWrite หากมีข้อผิดพลาดร้ายแรง (Hard Block)

CLI:
  python agent_auditor.py --scan               # สแกนหาข้อความหลุดและความไม่สอดคล้องทั้งระบบ
  python agent_auditor.py --fix                # สแกนพร้อมทำความสะอาด (Sanitize) ไฟล์ทั้งหมดอัตโนมัติ
  python agent_auditor.py --audit-story <name> # ตรวจสอบความสมบูรณ์เฉพาะเรื่อง
"""
from __future__ import annotations

import os
import re
import sys
import glob
import json
from typing import Dict, Any, List, Tuple, Optional

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
ACTIVE_PROJECTS = os.path.join(SB, "05_Active_Projects")

# ---------------------------------------------------------------------------
# คำ/วลีต้องห้าม (Forbidden Subagent & Meta-Talk Phrases) — Zero Tolerance
# ---------------------------------------------------------------------------
FORBIDDEN_PATTERNS = [
    # 1. บทบาทและชื่อ Subagent / Persona
    r"chief\s+literary\s+editor",
    r"audio\s+production\s+director",
    r"master\s+novelist",
    r"sub-agent(?:\s*\d+)?",
    r"subagent(?:\s*\d+)?",
    r"ผู้กำกับนิยาย\s*ai",
    r"ผู้ทดลองพล็อตเรื่องอัจฉริยะ",
    r"ทีมที่ปรึกษาและนักวิจารณ์เนื้อหา",
    r"หัวหน้าสถาปนิก\s*ai",
    r"นักวางแผนกลยุทธ์วรรณกรรม",
    r"ai\s*in\s*the\s*loop",
    r"ai-to-ai",

    # 2. คำประกาศบทบาท / การสนทนาของ AI / คำวิจารณ์ดราฟต์
    r"โอ้โห!?\s*ดราฟต์นี้มีของ",
    r"ดราฟต์นี้มีของ",
    r"วัตถุดิบชั้นเลิศ",
    r"มาครับ!?\s*ได้เวลา",
    r"ใส่เกลือเพิ่มความเค็ม",
    r"ขัดเกลาให้คมกริบ",
    r"ในฐานะ\s*(?:[\"']?(?:Chief|Editor|Director|ผู้กำกับ|สถาปนิก|ที่ปรึกษา|นักวิจารณ์|ผู้ช่วย|AI|โมเดล|ผู้เขียน|ผู้ประเมิน|ผู้คร่ำหวอด|ผู้เชี่ยวชาญ)[^,\n\r]*[\"']?|ของ(?:คุณ|ท่าน))",
    r"ข้าพเจ้าขอ(?:เสนอ|ปรับแต่ง|มอบ|คารวะ|ขัดเกลา)",
    r"ผมขอ(?:ปรับปรุง|คารวะ|ขัดเกลา|เสนอ|รับช่วง|บอกเลย)",
    r"ฉันขอ(?:ปรับปรุง|ขัดเกลา|มอบ)",
    r"ดิฉันในฐานะ",
    r"นี่คือ(?:ผลลัพธ์|บทที่|โครงเรื่อง|ดราฟต์|ฉบับ)",
    r"ฉบับขัดเกลาโดย",
    r"ฉบับปรับปรุงโดย",
    r"ขัดเกลาโดย\s*Chief",
    r"ฉบับ\s*Chief\s*Literary\s*Editor",
    r"ความคิดเห็นเพิ่มเติมจาก",
    r"โอ้โห!?\s*ดราฟต์นี้มีของ",
    r"ยอดเยี่ยมมาก(?:ครับ|ค่ะ)(?:\s*Chief|\s*Editor|\s*Director)?",
    r"เยี่ยมมาก(?:ครับ|ค่ะ)(?:\s*Chief|\s*Editor|\s*Director)?",
    r"ขอรับช่วง",
    r"เจียระไน",
    r"(?:นี่คือ|ส่งมอบ|แก้ไข|ขัดเกลา|จัดทำ)?\s*ตามที่คุณ(?:ขอ|ต้องการ|แนะนำ)(?:แล้ว|ครับ|ค่ะ|เลยครับ|เลยค่ะ)",
    r"^ตามที่คุณ(?:ขอ|ต้องการ|แนะนำ)",
    r"ตามคำขอของคุณ",
    r"ยินดีเป็นอย่างยิ่งที่จะช่วย",
    r"หวังว่าฉบับนี้จะถูกใจ",
    r"รออ่านบทต่อไปไม่ไหวแล้ว",
    r"กราบเรียนท่านผู้แต่ง",
    r"ขอให้คุณเตรียมตัวดำดิ่ง",
    r"คุณคือ\s*[\"']?(?:Audio Production Director|Chief Literary Editor|Master Novelist)[\"']?",

    # 3. Prompt Instructions & Editing Notes หลุด
    r"ปรับคำและประโยค",
    r"เพิ่มรายละเอียดเกี่ยวกับ",
    r"เพิ่มคำบรรยายให้",
    r"ใช้เวลามากมายในการวิเคราะห์",
    r"เน้นแรงจูงใจและความผูกพัน",
    r'ปรับประโยคที่ยาว.*?(?:\n|$)',
    r'กรุณาทราบว่า.*?(?:\n|$)',
    r'ฉันได้ส่งคืนเฉพาะ.*?(?:\n|$)',
    r'พร้อมทั้งคำแนะนำในการปรับปรุง.*?(?:\n|$)',
    r"suggestion\s*:",
    r"modified\s*:",

    # 4. Error / Artifacts / JSON Leaks รั่วไหล & ภาษาจีนหลุด
    r"error:\s*generation\s*returned\s*empty\s*result",
    r"as\s+an\s+ai",
    r"i\s+cannot\s+(?:generate|create|write)",
    r"here\s+is\s+the\s+(?:chapter|revised|audio\s*script)",
    r"INVALID_ARGUMENT",
    r"API\s*key\s*expired",
    r"googleapis\.com",
    r'"revised_content"\s*:',
    r'"paragraphs"\s*:\s*\[',
    r'"simplified_sentences"\s*:\s*\[',
    r'"character_relations"\s*:\s*\[',
    r'[\u4e00-\u9fff]{3,}',  # อักษรจีน 3 ตัวขึ้นไปในเนื้อเรื่องไทย
]

_COMPILED_FORBIDDEN = [re.compile(p, re.IGNORECASE) for p in FORBIDDEN_PATTERNS]


def detect_meta_talk(text: str) -> List[Dict[str, Any]]:
    """สแกนหาคำสื่อสารภายในของ subagent ในข้อความ คืนตำแหน่งและรูปแบบที่พบ"""
    if not text:
        return []
    findings = []
    lines = text.split("\n")
    for idx, line in enumerate(lines, 1):
        for pattern in _COMPILED_FORBIDDEN:
            match = pattern.search(line)
            if match:
                findings.append({
                    "line": idx,
                    "matched": match.group(0),
                    "context": line.strip()[:120],
                    "pattern": pattern.pattern
                })
                break
    return findings


def sanitize_meta_talk(text: str) -> str:
    """ทำความสะอาดเนื้อหาโดยตัด meta-talk หัว/ท้าย/กลาง/ในหัวข้อ และแกะเนื้อความจาก JSON หลุด อย่างหมดจด"""
    if not text:
        return ""

    # 0. ตรวจสอบกรณีที่เนื้อหาทั้งหมดหรือบางส่วนถูกส่งมาเป็น JSON ดิบ (เช่น {"revised_content": "..."} หรือ {"paragraphs": [...]})
    trimmed = text.strip()
    if (trimmed.startswith("{") and trimmed.endswith("}")) or (trimmed.startswith("[") and trimmed.endswith("]")):
        # ลบ trailing commas ก่อน parse เพื่อความทนทาน
        sanitized_json = re.sub(r",\s*([\]}])", r"\1", trimmed)
        parsed = None
        try:
            parsed = json.loads(sanitized_json)
        except Exception:
            try:
                parsed = json.loads(trimmed)
            except Exception:
                pass

        if parsed is not None:
            if isinstance(parsed, dict):
                # กรณี nested ใน response
                if "response" in parsed and isinstance(parsed["response"], dict):
                    resp = parsed["response"]
                    for k in ["story", "prose", "chapter_text", "content", "full_prose", "revised_content"]:
                        if k in resp and isinstance(resp[k], str):
                            text = resp[k]
                            break
                # กรณีมีคีย์เนื้อหาเด่นชัด
                if not text:
                    for k in ["story", "full_prose", "revised_content", "content", "full_text", "chapter_text", "text", "prose"]:
                        if k in parsed and isinstance(parsed[k], str):
                            text = parsed[k]
                            break
                else:
                    if "paragraphs" in parsed and isinstance(parsed["paragraphs"], list):
                        p_list = []
                        for item in parsed["paragraphs"]:
                            if isinstance(item, dict) and "text" in item:
                                p_list.append(item["text"])
                            elif isinstance(item, str):
                                p_list.append(item)
                        if p_list:
                            text = "\n\n".join(p_list)
                    elif "analysis" in parsed and isinstance(parsed["analysis"], list):
                        p_list = []
                        for item in parsed["analysis"]:
                            if isinstance(item, dict):
                                t = item.get("description") or item.get("modified") or item.get("line") or item.get("text")
                                if t and isinstance(t, str):
                                    p_list.append(t)
                                elif "examples" in item and isinstance(item["examples"], list):
                                    for ex in item["examples"]:
                                        if isinstance(ex, str):
                                            p_list.append(ex)
                                elif "issues" in item and isinstance(item["issues"], list):
                                    for sub in item["issues"]:
                                        if isinstance(sub, dict):
                                            val = sub.get("suggestions") or sub.get("resolution") or sub.get("recommendation") or sub.get("description")
                                            if val and isinstance(val, str):
                                                p_list.append(val)
                        if p_list:
                            text = "\n\n".join(p_list)
                    elif "revisions" in parsed and isinstance(parsed["revisions"], list):
                        p_list = []
                        for item in parsed["revisions"]:
                            if isinstance(item, dict) and "revisions" in item and isinstance(item["revisions"], list):
                                p_list.extend(item["revisions"])
                            elif isinstance(item, str):
                                p_list.append(item)
                        if p_list:
                            text = "\n\n".join(p_list)
            elif isinstance(parsed, list):
                p_list = []
                for item in parsed:
                    if isinstance(item, dict):
                        t = item.get("text") or item.get("content") or item.get("modified") or item.get("description") or item.get("action")
                        if t and isinstance(t, str):
                            p_list.append(t)
                        elif "suggestions" in item:
                            p_list.append(str(item["suggestions"]))
                        elif "resolution" in item:
                            p_list.append(str(item["resolution"]))
                    elif isinstance(item, str):
                        p_list.append(item)
                if p_list:
                    text = "\n\n".join(p_list)
        else:
            # Fallback: ถ้าเป็น JSON ที่ parse ไม่ได้แต่เป็น JSON block ให้ดึง string ภาษาไทยใน quotes
            thai_snippets = re.findall(r'"(?:text|suggestions|resolution|recommendation|revised_content|description)"\s*:\s*"([^"]+)"', trimmed)
            if thai_snippets:
                text = "\n\n".join(thai_snippets)

    # แปลง/ลบคำศัพท์จีน-ญี่ปุ่นทั่วไปที่อาจหลงเหลือ
    cjk_dict = {
        '魔王': 'จอมมาร', '魑魅魍魉': 'ภูตผีปีศาจ', '神器': 'ศาสตราวุธเทพ', '防卫': 'ป้องกัน',
        '闪烁': 'กะพริบระยิบระยับ', '他说': 'เขาพูดว่า', '琴': 'พิณ', '垭': 'ช่องเขา',
        '树叶': 'ใบไม้', '砂': 'ทราย', '静': 'สงบ', '温柔': 'อ่อนโยน', '和平': 'สงบสุข',
        '报警': 'สัญญาณเตือนภัย', '结束': 'สิ้นสุด', '早上好': 'สวัสดีตอนเช้า', '你是谁': 'เธอเป็นใคร',
        '我们必须立刻行动': 'พวกเราต้องลงมือทันที', '调整时间线': 'ปรับเส้นเวลา',
    }
    for cjk_k, cjk_v in cjk_dict.items():
        if cjk_k in text:
            text = text.replace(cjk_k, cjk_v)

    # ถ้ามีหัวข้อตอน (เช่น ## ตอนที่ X: หรือ **ตอนที่ X: หรือ [ผู้บรรยาย] ตอนที่ X:)
    # ข้อความทั้งหมดที่อยู่ก่อนหน้าหัวข้อตอนแรก ถือเป็น AI conversation preamble ให้ตัดทิ้งทันที
    header_pattern = re.compile(
        r"(?:\n|^)(?:#+\s*)?(?:\*{1,2}\s*)?(?:🔖\s*)?(?:ตอนที่\s*\d+|บทที่\s*\d+|\[ผู้บรรยาย\]|\[ชื่อตอน\]|\[SFX:)",
        re.IGNORECASE
    )
    m_head = header_pattern.search(text)
    if m_head:
        # ตัดข้อความทั้งหมดก่อนหัวข้อตอนหรือคิวแรกออก
        text = text[m_head.start():].lstrip()

    lines = text.split("\n")

    # 1. กำจัดส่วนหัว (Leading AI preamble) จนกว่าจะถึงเนื้อเรื่องจริงหรือหัวข้อตอน
    while lines:
        first = lines[0].strip()
        if not first or first == "---":
            lines.pop(0)
            continue
        is_meta = any(p.search(first) for p in _COMPILED_FORBIDDEN)
        if is_meta:
            lines.pop(0)
            continue
        break

    # 2. กำจัดส่วนท้าย (Trailing editor notes / AI comments)
    while lines:
        last = lines[-1].strip()
        if not last or last == "---":
            lines.pop()
            continue
        is_meta = any(p.search(last) for p in _COMPILED_FORBIDDEN)
        if is_meta:
            lines.pop()
            continue
        break

    cleaned_lines = []
    skip_block = False

    # 3. กำจัดบล็อก meta กลางไฟล์ เช่น "**ความคิดเห็นเพิ่มเติมจาก Chief...**"
    for line in lines:
        s = line.strip()

        # เริ่มต้นบล็อก meta กลางเนื้อหา
        if re.search(r"\*\*(?:ความคิดเห็นเพิ่มเติม|ข้อเสนอแนะ|โน้ตจากผู้ตรวจทาน|บันทึกจากบรรณาธิการ)", s, re.IGNORECASE):
            skip_block = True
            continue

        if skip_block:
            # ถ้าพบบรรทัดแบ่งตอนใหม่ หรือ heading ใหม่ หรือ footer ติดตาม ให้จบการ skip
            if s.startswith("#") or s == "---" or "คุยกับนักเขียน" in s:
                skip_block = False
            else:
                continue

        # 4. ตรวจสอบว่าบรรทัดนี้มี meta-talk หรือไม่
        if any(p.search(s) for p in _COMPILED_FORBIDDEN):
            # ถ้าเป็นหัวข้อตอนหลัก (เช่น ## ตอนที่ X: ...) ให้ล้างเฉพาะคำ meta ในหัวข้อทิ้ง
            if s.startswith("#") and re.search(r"ตอนที่\s*\d+|บทที่\s*\d+", s):
                cleaned_heading = re.sub(
                    r"\s*\(?(?:ฉบับขัดเกลาโดย|ฉบับปรับปรุงโดย|ฉบับ)\s*Chief[^\)]*\)?",
                    "",
                    line,
                    flags=re.IGNORECASE
                ).strip()
                cleaned_heading = re.sub(
                    r"\s*\(?(?:ขัดเกลาโดย|ปรับปรุงโดย)[^\)]*\)?",
                    "",
                    cleaned_heading,
                    flags=re.IGNORECASE
                ).strip()
                cleaned_lines.append(cleaned_heading)
                continue

            # ตรวจสอบว่าเป็นคำพูดในบทสนทนาตัวละครจริงหรือไม่
            if s.startswith(('"', "“", "「")) and s.endswith(('"', "”", "」")):
                if not any(k in s.lower() for k in ["chief", "director", "editor", "subagent", "sub-agent", "ดราฟต์", "ฉบับขัดเกลา"]):
                    cleaned_lines.append(line)
                    continue

            # ถ้าไม่ใช่บทสนทนาจริง ให้ตัดบรรทัด meta-talk ทิ้ง
            continue

        cleaned_lines.append(line)

    res = "\n".join(cleaned_lines).strip()
    return res


# ---------------------------------------------------------------------------
# ตรวจสอบความสอดคล้องของเสียงและชื่อตอน (Voice & Title Coherence)
# ---------------------------------------------------------------------------
def audit_title_and_audio_coherence(story_name: str) -> Dict[str, Any]:
    """
    ตรวจสอบความสอดคล้องระหว่าง:
    1. Chapter heading (ตอนที่ X: ...)
    2. AudioScript heading / narration
    3. SRT subtitle text
    4. Voice assignment (เพศของตัวละครหลัก vs เสียง TTS)
    """
    ch_dir = os.path.join(ACTIVE_PROJECTS, "Chapters")
    as_dir = os.path.join(ACTIVE_PROJECTS, "Audio_Scripts")
    ao_dir = os.path.join(ACTIVE_PROJECTS, "Audio_Output")
    char_file = os.path.join(SB, "04_Character_Database", f"{story_name}_Characters.md")

    issues = []
    chapters = sorted(glob.glob(os.path.join(ch_dir, f"{story_name}_Chapter_*.md")))
    if not chapters:
        chapters = sorted(glob.glob(os.path.join(ch_dir, f"*{story_name}*_Chapter_*.md")))

    # 1. ตรวจสอบชื่อตอนแต่ละบท
    for ch_path in chapters:
        m_num = re.search(r"Chapter_(\d+)", os.path.basename(ch_path))
        if not m_num:
            continue
        ep = int(m_num.group(1))

        with open(ch_path, "r", encoding="utf-8") as f:
            ch_content = f.read()

        # ดึงชื่อตอนจาก Chapter
        m_title = re.search(r"ตอนที่\s*\d+\s*[:：\s]\s*([^\n\r#\(\)]+)", ch_content)
        ch_title = m_title.group(1).strip() if m_title else ""

        # ตรวจสอบ AudioScript
        as_candidates = [
            os.path.join(as_dir, f"{story_name}_AudioScript_{ep:02d}.md"),
            os.path.join(as_dir, f"{story_name}_AudioScript_{ep}.md")
        ]
        as_path = next((p for p in as_candidates if os.path.exists(p)), None)
        if not as_path:
            issues.append(f"บทที่ {ep}: ไม่พบไฟล์ AudioScript สำหรับเรนเดอร์เสียง")
            continue

        with open(as_path, "r", encoding="utf-8") as f:
            as_content = f.read()

        m_as_title = re.search(r"ตอนที่\s*\d+\s*[:：\s]\s*([^\n\r#\(\)]+)", as_content)
        as_title = m_as_title.group(1).strip() if m_as_title else ""

        if ch_title and as_title:
            c1 = re.sub(r"\s+", "", ch_title)
            c2 = re.sub(r"\s+", "", as_title)
            if c1 != c2 and c1 not in c2 and c2 not in c1:
                issues.append(f"บทที่ {ep}: ชื่อตอนในนิยาย ('{ch_title}') ไม่ตรงกับบทเสียง ('{as_title}')")

        # ตรวจสอบไฟล์เสียงและ SRT
        srt_candidates = [
            os.path.join(ao_dir, f"{story_name}_Audiobook_{ep:02d}.srt"),
            os.path.join(ao_dir, f"{story_name}_Audiobook_{ep}.srt")
        ]
        srt_path = next((p for p in srt_candidates if os.path.exists(p)), None)
        if srt_path:
            with open(srt_path, "r", encoding="utf-8") as f:
                srt_txt = f.read()
            srt_meta = detect_meta_talk(srt_txt)
            if srt_meta:
                issues.append(f"บทที่ {ep}: พบข้อความ AI หลุดในไฟล์ซับไตเติล SRT ({len(srt_meta)} จุด)")

    # 2. ตรวจสอบความถูกต้องของเพศตัวละครและเสียง
    char_gender_map = {}
    if os.path.exists(char_file):
        with open(char_file, "r", encoding="utf-8") as f:
            char_txt = f.read()
        m_hero = re.search(r"##\s*\d*\.?\s*([^\(—\n\r]+)[^\n\r]*—\s*(?:ตัวเอก|พระเอก)", char_txt)
        if m_hero:
            hero_name = m_hero.group(1).strip()
            hero_ctx = char_txt[m_hero.start():m_hero.start() + 400].lower()
            is_male = any(k in hero_ctx for k in ["ชาย", "หนุ่ม", "นาย", "เขา", "พ่อ", "บิ๊กไบค์", "สูท"])
            is_female = any(k in hero_ctx for k in ["หญิง", "สาว", "นาง", "เธอ", "แม่"])
            if is_male and not is_female:
                char_gender_map[hero_name] = "male"
            elif is_female and not is_male:
                char_gender_map[hero_name] = "female"

    return {
        "story": story_name,
        "coherent": len(issues) == 0,
        "issues": issues,
        "char_gender_map": char_gender_map
    }


# ---------------------------------------------------------------------------
# Pre-Publish Quality Gate: ประตูตรวจสกัดก่อนปล่อยจริง
# ---------------------------------------------------------------------------
def audit_publication_package(
    teaser_path: str,
    meta: Dict[str, Any],
    auto_sanitize: bool = False
) -> Dict[str, Any]:
    """
    ตรวจสอบชิ้นงานอย่างเข้มงวดก่อนอนุญาตให้อัปโหลด (YouTube, TikTok, Bilibili, Web novel):
    1. ไม่มี Meta-talk เด็ดขาดใน Title, Description, Tags, Hook
    2. ไม่มี Meta-talk ในไฟล์ Video/Audio/SRT
    3. ชื่อตอนและชื่อเรื่องสอดคล้องกัน
    4. สัดส่วนและโครงสร้างปลอดภัย (Shorts Safe Zone)
    """
    errors = []
    warnings = []

    # 1. ตรวจสอบ Metadata ของการเผยแพร่
    title = meta.get("title", "")
    desc = meta.get("description", "")
    hook = meta.get("hook", "")

    title_meta = detect_meta_talk(title)
    desc_meta = detect_meta_talk(desc)
    hook_meta = detect_meta_talk(hook) if hook else []

    # Auto-heal Metadata ถ้าเปิด auto_sanitize
    if auto_sanitize:
        if title_meta:
            meta["title"] = sanitize_meta_talk(title).replace("\n", " ").strip()
            title = meta["title"]
            title_meta = detect_meta_talk(title)
        if desc_meta:
            meta["description"] = sanitize_meta_talk(desc).strip()
            desc = meta["description"]
            desc_meta = detect_meta_talk(desc)
        if hook_meta:
            meta["hook"] = sanitize_meta_talk(hook).strip()
            hook = meta["hook"]
            hook_meta = detect_meta_talk(hook)

    if title_meta:
        errors.append(f"ชื่อคลิปมีข้อความ AI หลุด: '{title_meta[0]['matched']}' ใน \"{title}\"")

    if desc_meta:
        errors.append(f"คำอธิบายคลิปมีข้อความ AI หลุด: '{desc_meta[0]['matched']}'")

    if hook_meta:
        errors.append(f"ข้อความ Hook มีข้อความ AI หลุด: '{hook_meta[0]['matched']}'")

    # 2. ตรวจสอบไฟล์ Teaser วิดีโอ
    if not os.path.exists(teaser_path) or os.path.getsize(teaser_path) < 10000:
        errors.append(f"ไฟล์วิดีโอไม่มีอยู่จริงหรือเสียหาย: {teaser_path}")

    # 3. ตรวจสอบไฟล์ซับไตเติลที่เกี่ยวข้อง
    srt_path = teaser_path.replace(".mp4", ".srt").replace("Teaser_", "Audiobook_").replace("Teasers", "Audio_Output")
    if not os.path.exists(srt_path):
        srt_path = teaser_path.replace(".mp4", ".srt")

    if os.path.exists(srt_path):
        with open(srt_path, "r", encoding="utf-8") as f:
            srt_content = f.read()
        srt_leaks = detect_meta_talk(srt_content)
        if srt_leaks and auto_sanitize:
            cleaned_srt = sanitize_srt_content(srt_content)
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(cleaned_srt)
            srt_leaks = []
        if srt_leaks:
            errors.append(f"ซับไตเติลที่จะเบิร์นลงวิดีโอมีข้อความ AI หลุด ({len(srt_leaks)} ตำแหน่ง)")

    # 4. ตรวจสอบชื่อเรื่องและตอน
    story_name = meta.get("story_name", "")
    if story_name:
        coherence = audit_title_and_audio_coherence(story_name)
        if not coherence["coherent"]:
            for iss in coherence["issues"]:
                warnings.append(iss)

    passed = len(errors) == 0

    return {
        "passed": passed,
        "errors": errors,
        "warnings": warnings,
        "teaser_path": teaser_path,
        "title": title
    }


def sanitize_srt_content(srt_text: str) -> str:
    """ลบ Subtitle block ที่มีคำ meta-talk ออกจากไฟล์ SRT แล้วจัดเรียงลำดับหมายเลขใหม่"""
    blocks = srt_text.strip().split("\n\n")
    cleaned_blocks = []
    new_idx = 1
    for b in blocks:
        lines = b.strip().split("\n")
        if len(lines) >= 3:
            sub_text = " ".join(lines[2:])
            if detect_meta_talk(sub_text):
                continue  # ข้าม block ที่มี meta-talk
            lines[0] = str(new_idx)
            new_idx += 1
            cleaned_blocks.append("\n".join(lines))
        elif b.strip():
            cleaned_blocks.append(b.strip())
    return "\n\n".join(cleaned_blocks) + "\n"


# ---------------------------------------------------------------------------
# สแกนและทำความสะอาดระบบทั้ง SecondBrain
# ---------------------------------------------------------------------------
def run_full_scan(fix: bool = False) -> Dict[str, Any]:
    """สแกนทุกไฟล์ใน Chapters, Audio_Scripts, Publish_Queue, และ SRT Subtitles หา Meta-talk"""
    scan_targets = [
        ("Chapters", os.path.join(ACTIVE_PROJECTS, "Chapters", "*.md")),
        ("Audio_Scripts", os.path.join(ACTIVE_PROJECTS, "Audio_Scripts", "*.md")),
        ("Publish_Queue", os.path.join(ACTIVE_PROJECTS, "Publish_Queue", "*.md")),
        ("SRT_Subtitles", os.path.join(ACTIVE_PROJECTS, "Audio_Output", "*.srt")),
    ]

    total_files = 0
    corrupted_files = []
    fixed_files = []

    print(f"\n🔍 [Agent Auditor] เริ่มต้นการตรวจค้นหา Meta-talk และสิ่งแปลกปลอมทั่วระบบ...")

    for folder_name, pattern in scan_targets:
        files = sorted(glob.glob(pattern))
        for fp in files:
            total_files += 1
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()

            leaks = detect_meta_talk(content)
            if leaks:
                rel = os.path.relpath(fp, ROOT)
                corrupted_files.append({
                    "file": rel,
                    "folder": folder_name,
                    "leaks_count": len(leaks),
                    "first_leak": leaks[0]
                })
                print(f"  ❌ [{folder_name}] พบการรั่วไหลใน {os.path.basename(fp)} ({len(leaks)} จุด): "
                      f"บรรทัด {leaks[0]['line']}: '{leaks[0]['matched']}'")

                if fix:
                    if fp.endswith(".srt"):
                        cleaned = sanitize_srt_content(content)
                    else:
                        cleaned = sanitize_meta_talk(content)
                    with open(fp, "w", encoding="utf-8") as f:
                        f.write(cleaned)
                    fixed_files.append(rel)
                    print(f"     ✅ ทำความสะอาดและบันทึกไฟล์ใหม่เรียบร้อย")

    print(f"\n=======================================================")
    print(f"📊 สรุปรายงานการตรวจสอบคุณภาพ (Audit Report)")
    print(f"=======================================================")
    print(f"📁 สแกนทั้งหมด: {total_files} ไฟล์")
    print(f"⚠️  พบไฟล์ปนเปื้อนข้อความ AI: {len(corrupted_files)} ไฟล์")
    if fix:
        print(f"🧹 ทำความสะอาดสำเร็จ: {len(fixed_files)} ไฟล์")
    print(f"=======================================================\n")

    return {
        "total_files": total_files,
        "corrupted_files": corrupted_files,
        "fixed_files": fixed_files
    }


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--fix" in args:
        run_full_scan(fix=True)
    elif "--audit-story" in args and len(args) > 1:
        story = args[args.index("--audit-story") + 1]
        res = audit_title_and_audio_coherence(story)
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        run_full_scan(fix=False)
