# -*- coding: utf-8 -*-
"""
audio_script_converter.py
Converts full novel markdown chapters into cinematic audio drama scripts.
Rules:
- Formats narrative text into [ผู้บรรยาย, โทน: ...] paragraphs
- Detects quoted dialogue "..." and attributes to characters with emotion tags [ตัวละคร, โทน: ...]
- Adds cinematic sound effects [SFX: ...] at action, tension, or atmosphere beats
- Preserves full length and narrative richness
"""
import os
import re

def convert_chapter_to_audioscript(novel_title, chapter_num, chapter_title, novel_text, protagonist_name):
    lines = [l.strip() for l in novel_text.split("\n") if l.strip()]
    audio_blocks = []
    
    header = f"# 🎙️ บทนิยายเสียง: {novel_title}\n## ตอนที่ {chapter_num}: {chapter_title}\n\n"
    audio_blocks.append(header)
    
    for line in lines:
        if line.startswith("#"):
            continue
            
        # Parse quotes and narratives
        # We find all "dialogues" in the line
        parts = re.split(r'("[^"]+")', line)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part.startswith('"') and part.endswith('"'):
                quote_text = part[1:-1].strip()
                # Determine speaker
                speaker = protagonist_name
                tone = "มุ่งมั่นและเยือกเย็น"
                # Context clues
                if any(k in line for k in ["คำราม", "ตวาด", "ตะโกน", "เกรี้ยวกราด"]):
                    tone = "เกรี้ยวกราดและดุดัน"
                elif any(k in line for k in ["กระซิบ", "แผ่วเบา", "พึมพำ"]):
                    tone = "แผ่วเบาและลึกลับ"
                elif any(k in line for k in ["เย้ยหยัน", "ยิ้มเยาะ", "หัวเราะ"]):
                    tone = "เย้ยหยันและมั่นใจ"
                elif any(k in line for k in ["สะอื้น", "น้ำตา", "เจ็บปวด"]):
                    tone = "สะเทือนใจและเจ็บปวด"
                elif any(k in line for k in ["ตกใจ", "อุทาน", "เบิกตากว้าง"]):
                    tone = "ตื่นตระหนกและตกตะลึง"
                    
                # Check for other named speakers
                if "ซานชิว" in line or "ฉินซานชิว" in line:
                    if protagonist_name != "ฉินซานชิว" and ("ซานชิว" in line[:line.find(part)] or "ผู้เฒ่า" in line[:line.find(part)]):
                        speaker = "ฉินซานชิว"
                elif "หลินซูหว่าน" in line:
                    if "หลินซูหว่าน" in line[:line.find(part)]:
                        speaker = "หลินซูหว่าน"
                        tone = "เย็นชาและดูแคลน"
                elif "เมิ่งเชาหราน" in line:
                    if "เมิ่งเชาหราน" in line[:line.find(part)] or "อาจารย์" in line[:line.find(part)]:
                        speaker = "เมิ่งเชาหราน"
                        tone = "สงบนิ่งเปี่ยมเมตตา"
                elif "คุณย่าซือ" in line or "ยายเฒ่า" in line:
                    if "คุณย่าซือ" in line[:line.find(part)]:
                        speaker = "คุณย่าซือ"
                        tone = "ใจดีซ่อนเล่ห์กลอันน่าขนลุก"
                elif "ผู้ใหญ่บ้าน" in line:
                    if "ผู้ใหญ่บ้าน" in line[:line.find(part)]:
                        speaker = "ผู้ใหญ่บ้าน"
                        tone = "ชราภาพทว่าเปี่ยมพลังอำนาจ"
                elif "คนขายเนื้อ" in line or "คนตัดฟืน" in line or "คนใบ้" in line or "คนขาเป๋" in line:
                    speaker = "ผู้อาวุโสหมู่บ้าน"
                    tone = "ดุดันและแปลกประหลาด"
                elif "ผู้อาวุโส" in line or "ทูต" in line:
                    speaker = "ผู้อาวุโส"
                    tone = "เย่อหยิ่งกดดัน"
                    
                audio_blocks.append(f'[{speaker}, โทน: {tone}] "{quote_text}"\n')
            else:
                # Narrative block
                narrator_tone = "สุขุมน่าติดตาม"
                sfx = ""
                if any(w in part for w in ["กระบี่", "ดาบ", "คมกระบี่", "ฟัน", "แทง"]):
                    sfx = " [SFX: เสียงกระบี่วกฉวัดเฉวียนแหวกร่างและเสียงเหล็กปะทะคม]"
                    narrator_tone = "ดุเดือดเร้าใจ"
                elif any(w in part for w in ["ลมปราณ", "ระเบิด", "พลัง", "ฟ้าผ่า", "สะเทือน"]):
                    sfx = " [SFX: เสียงคลื่นพลังระเบิดซัดสะเทือนฟ้าดินและเสียงแผ่นดินสะเทือน]"
                    narrator_tone = "ทรงพลังและน่าเกรงขาม"
                elif any(w in part for w in ["โลหิต", "กระอักเลือด", "ซากศพ", "ความตาย"]):
                    sfx = " [SFX: เสียงหยดเลือดร่วงกระทบพื้นและเสียงคาวเลือดคละคลุ้ง]"
                    narrator_tone = "หม่นหมองและตึงเครียด"
                elif any(w in part for w in ["ความมืด", "รัตติกาล", "หมอก", "เงียบสงัด"]):
                    sfx = " [SFX: เสียงสายลมพัดหวีดหวิวและเสียงค่ำคืนอันเงียบสงัดชวนขนลุก]"
                    narrator_tone = "ลึกลับระทึกขวัญ"
                elif any(w in part for w in ["ก้าวเดิน", "เดิน", "วิ่ง"]):
                    sfx = " [SFX: เสียงฝีเท้ามั่นคงหนักแน่น]"
                
                audio_blocks.append(f'[ผู้บรรยาย, โทน: {narrator_tone}]{sfx} {part}\n')
                
    return "\n".join(audio_blocks)

print("Audio script converter loaded successfully.")
