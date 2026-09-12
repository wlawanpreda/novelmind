"""
quality_writing_engine.py — Advanced Novel Quality Engine & Organic Funnel
========================================================================

เสาหลัก 5 ประการของระบบผลิตนิยายคุณภาพสูง (Top-Tier Web Novel Engine):
1. The 3-Sentence Hook: เปิดฉากด้วยความขัดแย้ง (Conflict) หรือการกระทำ (Action) ทันที ห้ามเกริ่นสภาพอากาศ
2. Show, Don't Tell: ถ่ายทอดอารมณ์ผ่านภาษากายและปฏิกิริยาสรีรวิทยา ไม่สรุปอารมณ์ทื่อๆ
3. Distinct Character Voices: บทสนทนามีชีวิตชีวา น้ำเสียงและจังหวะพูดมีเอกลักษณ์เฉพาะตัว
4. Pacing & Cliffhanger Mastery: วางจุดหักมุม (Micro-Climax) และทิ้งปมค้างคา (Cliffhanger) ท้ายตอน
5. Zero AI Meta-talk: กรองคำฟุ่มเฟือยและภาษาเครื่องแปลออก 100%

Organic Funnel:
- ปล่อยอ่านฟรีทุกตอนเพื่อสะสมยอดเข้าชั้น (Add to Bookshelf) และยอดอ่านต่อเนื่อง
- ท้ายตอนทุกตอนมีบล็อก CTA ชวนไป "ฟังนิยายเสียงฟรีพร้อมดนตรีและซาวด์เอฟเฟกต์ บน YouTube: เงาพันจันทร์"
"""

import os
import re
from typing import Dict, Any, List, Optional

ORGANIC_END_NOTE_HTML = """
<div style="margin-top: 35px; padding: 18px 22px; background: linear-gradient(135deg, #fff5f5 0%, #fff0f5 100%); border-left: 5px solid #ff3366; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); font-family: 'Sarabun', sans-serif;">
    <p style="margin: 0 0 8px 0; font-size: 16px; color: #ff3366; font-weight: bold;">
        🎧 ฟังนิยายเสียงบรรยากาศสมจริง ฟรีบน YouTube!
    </p>
    <p style="margin: 0 0 10px 0; font-size: 14px; color: #444; line-height: 1.6;">
        ชอบเรื่องนี้และอยากฟังเวอร์ชันนิยายเสียงเต็มอารมณ์ มีเสียงพากย์พร้อมดนตรีประกอบและซาวด์เอฟเฟกต์จัดเต็ม? 
        แวะไปฟังฟรีได้ที่ช่อง YouTube: <strong>เงาพันจันทร์ (Panjan Audiobooks)</strong>
    </p>
    <p style="margin: 0; font-size: 13px; color: #777;">
        ❤️ เรื่องนี้เปิดให้อ่านฟรีจนจบ ฝากกดหัวใจ เพิ่มเข้าชั้น และคอมเมนต์เป็นกำลังใจให้นักเขียนด้วยนะคะ!
    </p>
</div>
"""

QUALITY_WRITING_SYSTEM_PROMPT = """คุณคือนักเขียนนิยายออนไลน์ระดับ Best-Seller ภาษาไทย และบรรณาธิการผู้เชี่ยวชาญการสร้างนิยายที่มียอดคนอ่านและผู้ติดตามหลักแสน

เป้าหมายของคุณ: เขียนเนื้อหาบทนิยายที่สนุก น่าติดตาม ชวนให้อ่านรวดเดียวจบ (Binge-Reading) โดยยึดหลักเกณฑ์ 5 ข้ออย่างเคร่งครัด:

1. [THE 3-SENTENCE HOOK]:
- 3 ประโยคแรกของทุกตอนต้องเปิดด้วย "Action", "Conflict", หรือ "Dialogue ที่ตึงเครียด" ทันที
- ห้ามเปิดด้วยการบรรยายดินฟ้าอากาศ ก้อนเมฆ หรือปรัชญาชีวิตเด็ดขาด

2. [SHOW, DON'T TELL]:
- ห้ามบอกตรงๆ เช่น 'เขาโกรธมาก' หรือ 'เธอเสียใจ'
- ให้บรรยายผ่านภาษากาย: สันกรามที่ขบแน่น, ปลายนิ้วที่จิกฝ่ามือ, ลมหายใจที่สะดุด, แววตาที่สั่นไหวแต่ไร้น้ำตา

3. [CHARACTER VOICE & TENSION]:
- ตัวละครแต่ละตัวต้องมีเอกลักษณ์ทางคำพูด การเว้นจังหวะ และไหวพริบ
- การปะทะคารมต้องกระชับ ไม่ประดิดประดอยเกินจริง เป็นธรรมชาติของภาษาพูดมนุษย์

4. [PACING & CLIFFHANGER]:
- มีจุดไคลแม็กซ์ย่อยกลางตอน และทิ้งระเบิดอารมณ์หรือคำถามใหญ่ไว้ในย่อหน้าสุดท้าย
- ผู้อ่านต้องรู้สึกว่า "ถ้าไม่กดอ่านตอนต่อไปคืนนี้นอนไม่หลับ"

5. [ZERO AI META-TALK]:
- ห้ามมีคำนำ คำลงท้าย หรือคำพูดของ AI เด็ดขาด ส่งคืนเฉพาะเนื้อหานิยายเท่านั้น
"""

def append_organic_cta(chapter_html: str) -> str:
    """ผนวกท้ายบทด้วยบล็อก CTA สวยงาม เพื่อส่งต่อผู้อ่านไปเพิ่ม Watch Time บน YouTube ฟรี"""
    if "Panjan Audiobooks" in chapter_html or "เงาพันจันทร์" in chapter_html:
        return chapter_html
    return chapter_html.strip() + "\n\n" + ORGANIC_END_NOTE_HTML.strip()

def audit_chapter_quality(text: str) -> Dict[str, Any]:
    """ประเมินเนื้อหาบทนิยายตามเกณฑ์ Top-Tier 5 ด้าน"""
    lines = [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith('#')]
    score = 100
    feedback = []

    if not lines:
        return {"score": 0, "passed": False, "feedback": ["เนื้อหาว่างเปล่า"]}

    first_lines = " ".join(lines[:3])
    weather_words = ["ท้องฟ้า", "แสงแดด", "สายลมพัด", "ก้อนเมฆ", "ยามเช้าอันเงียบสงบ", "ในวันที่"]
    if any(w in first_lines for w in weather_words):
        score -= 15
        feedback.append("⚠️ เปิดตอนด้วยการบรรยายบรรยากาศ/อากาศ แนะนำให้เปิดด้วยเหตุการณ์หรือการกระทำทันที")

    tell_patterns = ["เขารู้สึกโกรธ", "เธอรู้สึกเศร้า", "เขารู้สึกตกใจ", "เธอดีใจมาก"]
    for p in tell_patterns:
        if p in text:
            score -= 10
            feedback.append(f"⚠️ พบการบอกอารมณ์ทื่อๆ ('{p}') แนะนำให้เปลี่ยนเป็นภาษากาย เช่น สันกรามขบแน่น หรือมือสั่น")

    clean_chars = len(re.sub(r'\s+', '', text))
    word_count = clean_chars // 4
    if word_count < 400:
        score -= 20
        feedback.append(f"⚠️ เนื้อหาค่อนข้างสั้น ({word_count} คำ) แนะนำขยายเป็น 600-1,200 คำ เพื่อความจุใจ")

    last_paragraph = lines[-1] if lines else ""
    if len(last_paragraph) < 15:
        score -= 10
        feedback.append("⚠️ ท้ายบทสั้นเกินไป ควรมีประโยคทิ้งปมที่ดึงดูดใจ")

    passed = score >= 80
    return {
        "score": max(0, score),
        "word_count": word_count,
        "passed": passed,
        "feedback": feedback if feedback else ["✅ ผ่านเกณฑ์คุณภาพระดับดีเยี่ยม พร้อมสร้าง Engagement"]
    }

if __name__ == "__main__":
    test_text = """
    "เซ็นซะ... แล้วชีวิตฉันกับนายจะไม่มีอะไรเกี่ยวข้องกันอีก!" 
    ณิชาเหวี่ยงซองเอกสารสีน้ำตาลลงบนโต๊ะไม้สักหรูหรา เสียงกระแทกดังสะท้อนก้องทั่วห้องทำงานส่วนตัวของประธานบริษัท
    
    รวีชะงัก สายตาที่เคยเต็มไปด้วยความเย่อหยิ่งเหลือบมองกระดาษสีขาวที่โผล่ออกมา 'หนังสือยินยอมหย่าขาด'
    สันกรามของเขาขบแน่นจนขึ้นรูปนูน ปลายนิ้วที่ถือปากกาหมึกซึมราคากว่าหกหลักสั่นสะท้านอย่างควบคุมไม่ได้
    
    "เธอคิดดีแล้วใช่ไหม?" เขาเปล่งเสียงแหบพร่า
    "ฉันคิดมาห้าปีแล้วค่ะท่านประธาน... และวันนี้ฉันฉลาดพอที่จะเดินออกมา" เธอส่งยิ้มบางเบาที่บาดลึกยิ่งกว่าใบมีด ก่อนจะหันหลังก้าวออกจากห้องโดยไม่แม้แต่จะหันกลับมามอง
    """
    res = audit_chapter_quality(test_text)
    print("Quality Audit Result:")
    print("Score:", res["score"])
    print("Passed:", res["passed"])
    print("Feedback:", res["feedback"])
