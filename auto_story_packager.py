#!/usr/bin/env python3
"""
auto_story_packager.py — ระบบจัดแต่งแพ็กเกจจิ้งและคอนเซ็ปต์นิยายอัตโนมัติ (Creative Concept & Packaging Engine)

ความสามารถหลัก:
1. Copywriting Hook: สังเคราะห์คำโปรยดึงดูดสายตาตามหลักจิตวิทยาผู้อ่าน ReadAWrite (First 3 lines hook)
2. Character Chemistry Matrix: ออกแบบและจับคู่เคมีตัวละคร (เช่น Tsundere x Golden Retriever, ประธานสายคลั่ง x นางร้ายสุดสตรอง)
3. Curated Theme Song & OST: คัดเลือกเพลงธีมจาก YouTube พร้อมคำบรรยายอารมณ์เพลงที่เข้ากับธีมเรื่อง
4. Rich HTML Intro Builder: สร้างโค้ด HTML บทนำหน้านิยายที่พร้อมแสดงผลใน CKEditor บน ReadAWrite
5. Cover & Asset Matching: จับคู่ไฟล์ภาพปก 3:4 และข้อมูลโปรไฟล์ตัวละครในระบบอัตโนมัติ
"""

import os
import re
import glob
import json
from typing import Dict, Any, List, Optional, Tuple

ROOT = os.path.dirname(os.path.abspath(__file__))
COVERS_DIR = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Covers")

# คลังเพลงและบรรยากาศตามแนวเรื่อง (Genre-Based Theme Song Catalog)
GENRE_OST_CATALOG = {
    "romance_drama": {
        "title": "Sarah Salola - นะครับ (ได้ไหม) / Billkin - กีดกัน",
        "url": "https://www.youtube.com/watch?v=0kF_H1bJ8aQ",
        "desc": "เมโลดี้หวานอมขมกลืน ถ่ายทอดความรู้สึกของผู้ชายที่เพิ่งรู้ตัวว่ารักในวันที่สายเกินไป"
    },
    "romcom_fluffy": {
        "title": "Bow Maylada - แฟนผมน่ารัก / บอนซ์ - ฉลามชอบงับคุณ",
        "url": "https://www.youtube.com/watch?v=Fj-y5M7mH_A",
        "desc": "จังหวะเพลงสดใสน่ารัก ที่ฟังแล้วจะเผลอยิ้มตามไปกับความน่าเอ็นดูและความขี้อ้อนของตัวละคร"
    },
    "historical_family": {
        "title": "Acoustic Guzheng - Warm Memories / กู่เจิงทำนองอบอุ่น",
        "url": "https://www.youtube.com/watch?v=5qap5aO4i9A",
        "desc": "เสียงดนตรีบรรเลงพื้นบ้านยุค 70 แสนอบอุ่น ชวนให้นึกถึงกลิ่นอายข้าวสวยร้อนๆ และความผูกพันของครอบครัว"
    },
    "mystery_supernatural": {
        "title": "Dark Mystery Lo-fi / Three Man Down - ปรารถนาแห่งเงามืด",
        "url": "https://www.youtube.com/watch?v=jfKfPfyJRdk",
        "desc": "บีทลึกลับชวนค้นหา เหมาะสำหรับเปิดคลอขณะสืบสวนและเผชิญหน้ากับความลี้ลับเหนือธรรมชาติ"
    },
    "fantasy_sloth": {
        "title": "Relaxing Fantasy Tavern / Anime Chillhop Lounge",
        "url": "https://www.youtube.com/watch?v=5qap5aO4i9A",
        "desc": "เพลงบรรเลงแนวผจญภัยสโลว์ไลฟ์ สบายๆ ชิลล์ๆ สไตล์พระเอกสายขี้เกียจแต่พลังระดับมหาเทพ"
    },
    "action_scifi": {
        "title": "Cyberpunk Synthwave & Detective Tension",
        "url": "https://www.youtube.com/watch?v=4xDzrJKXOOY",
        "desc": "จังหวะซินธ์เวฟกระตุ้นอะดรีนาลีน เหมาะสำหรับฉากวิ่งแข่งกับเวลาและลูปมิติสุดระทึก"
    }
}


def detect_genre(title: str, premise: str = "") -> str:
    """ตรวจจับแนวเรื่องจากชื่อเรื่องและเรื่องย่อ"""
    text = f"{title} {premise}".lower()
    if any(k in text for k in ["นางร้าย", "ประธาน", "คลั่งรัก", "หมดรัก", "หย่า", "แก้แค้น", "ดราม่า"]):
        return "romance_drama"
    elif any(k in text for k in ["ฟาร์ม", "เจ้าหญิง", "เพลย์บอย", "ซัคคิวบัส", "ฮาเร็ม", "สาวปีศาจ", "รัก"]):
        return "romcom_fluffy"
    elif any(k in text for k in ["ยุค 70", "ยุค 80", "คุณแม่", "ลูกแฝด", "ซูเปอร์มาร์เก็ต", "ข้ามมิติ", "โบราณ"]):
        return "historical_family"
    elif any(k in text for k in ["ประกันภัย", "กระจกเงา", "คนตาย", "สืบสวน", "วิญญาณ", "ผี", "ลี้ลับ"]):
        return "mystery_supernatural"
    elif any(k in text for k in ["ขี้เกียจ", "เทพทรู", "เวทย์มนต์", "จอมเวท", "สโลว์ไลฟ์", "อัศวิน"]):
        return "fantasy_sloth"
    elif any(k in text for k in ["สปีดรัน", "นักสืบ", "ไซไฟ", "ลูป", "เวลา", "เกม"]):
        return "action_scifi"
    return "romcom_fluffy"


def find_cover_image(title: str) -> Optional[str]:
    """ค้นหาไฟล์ภาพปกที่ตรงกับชื่อเรื่องใน Covers directory"""
    sub_titles = [title]
    if ":" in title:
        sub_titles.extend(title.split(":"))
    if " " in title:
        sub_titles.append(title.split()[0])
        
    for sub in sub_titles:
        clean_title = re.sub(r'[:\s_-]+', '_', sub).strip('_')
        patterns = [
            f"{clean_title}_Cover_3x4.jpg",
            f"{clean_title}_Cover.jpg",
            f"{clean_title}_Cover_captioned.jpg",
            f"{clean_title}.jpg",
            f"{clean_title}.png"
        ]
        for pat in patterns:
            path = os.path.join(COVERS_DIR, pat)
            if os.path.exists(path):
                return path

    # Fuzzy match ค้นหาชื่อที่มีคำสำคัญ
    for sub in sub_titles:
        clean_title = re.sub(r'[:\s_-]+', '_', sub).strip('_')
        key = clean_title.split('_')[0]
        if len(key) >= 3:
            for f in glob.glob(os.path.join(COVERS_DIR, f"*{key}*.jpg")):
                return f
    return None


def build_heartflutter_hook(title: str, premise: str = "") -> Tuple[str, str]:
    """
    สร้างคำโปรยแบบ Hook 3 บรรทัดตามหลัก ReadAWrite Conversion
    คืนค่า (headline_tag, synopsis_body)
    """
    genre = detect_genre(title, premise)
    
    if genre == "romance_drama":
        tag = "[อ่านฟรีฟินจนตับสั่น!]"
        dialogue = '"ถ้าเธอคิดจะเดินออกไปจากชีวิตฉัน... ก็เตรียมตัวรับผลที่ตามมาได้เลย!"'
        body = f"ในวันที่เธอตัดสินใจปล่อยมือและหันหลังให้ความรักที่ไร้ค่า ชายผู้เย็นชาและเคยมองข้ามเธอกลับกลายเป็นคนคลั่งรักที่ยอมทำทุกวิถีทางเพื่อรั้งเธอไว้ข้างกาย"
    elif genre == "romcom_fluffy":
        tag = "[อ่านฟรีฟินจิกหมอน!]"
        dialogue = '"นี่นาย... คิดจะหนีเสน่ห์ของฉันพ้นจริงๆ เหรอจ๊ะ?"'
        body = f"เมื่อหนุ่มธรรมดาต้องมารับมือกับสาวสวยสายรุกสุดขี้แกล้ง ที่ขยันหยอดความหวานและป่วนหัวใจจนแทบละลายทุกวัน ความสัมพันธ์สุดป่วนชวนใจเต้นตึกตักจึงเริ่มต้นขึ้น!"
    elif genre == "historical_family":
        tag = "[อ่านฟรีฟีลกู๊ด อบอุ่นหัวใจ!]"
        dialogue = '"แม่สัญญา... ชาตินี้ลูกทั้งสองจะไม่ต้องอดอยากอีกต่อไป!"'
        body = f"ทะลุมิติมาอยู่ในร่างคุณแม่ลูกแฝดยุคข้าวยากหมากแพง แต่โชคดีที่มีมิติซูเปอร์มาร์เก็ตลับติดตัวมาด้วย! งานนี้เตรียมพบกับมหกรรมการสร้างตัว เลี้ยงลูก และปราบตัวร้ายให้อยู่หมัด"
    elif genre == "mystery_supernatural":
        tag = "[ลุ้นระทึก พลิกปมเกินคาดเดา!]"
        dialogue = '"สัญญานี้ไม่ได้เซ็นด้วยหมึก... แต่แลกด้วยวิญญาณ!"'
        body = f"เมื่อเบื้องหลังความตายและอุบัติเหตุปริศนามีเรื่องราวลี้ลับซ่อนอยู่ การสืบสวนและประเมินสินไหมที่เดิมพันด้วยชะตากรรมของคนเป็นและวิญญาณจึงเริ่มขึ้น"
    elif genre == "fantasy_sloth":
        tag = "[อ่านฟรีสายชิลล์ พระเอกเทพทรู!]"
        dialogue = '"ปลุกฉันทำไม... กองทัพศัตรูแสนตน เดี๋ยวฉันกลิ้งตัวทับทีเดียวก็เรียบแล้ว คร่อก..."'
        body = f"เมื่อเด็กหนุ่มผู้แสนขี้เกียจได้รับพรสวรรค์เวทมนตร์ระดับไร้เทียมทาน มหกรรมการกู้โลกแบบไม่ต้องลุกจากเตียงนอนที่ศัตรูต้องหลั่งน้ำตาเพราะแพ้คนละเมอ!"
    else:
        tag = "[ลุ้นระทึก สนุกจนวางไม่ลง!]"
        dialogue = '"เหลือเวลาอีกแค่ 3 นาที... ก่อนที่ทุกอย่างจะระเบิด!"'
        body = f"การเดินทางและภารกิจสุดท้าทายที่ต้องใช้ไหวพริบ ความกล้าหาญ และการตัดสินใจในเสี้ยววินาทีเพื่อเอาชีวิตรอดและก้าวสู่จุดสูงสุด"

    full_synopsis = f'{tag} {dialogue}\n\n{body}'
    return tag, full_synopsis


def generate_story_package(title: str, premise: str = "", raw_characters: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
    """
    สร้างและจัดชุดแพ็กเกจจิ้งของเรื่องแบบครบวงจร:
    - Cover Path
    - Synopsis
    - Characters Matrix
    - Curated Theme Song
    - Rich Intro HTML
    """
    genre = detect_genre(title, premise)
    tag, synopsis = build_heartflutter_hook(title, premise)
    cover_file = find_cover_image(title)
    ost_info = GENRE_OST_CATALOG.get(genre, GENRE_OST_CATALOG["romcom_fluffy"])

    # ตัวละครเริ่มต้นถ้าไม่ได้ระบุ
    characters = raw_characters or [
        ("ตัวเอกหลัก", "ผู้นำเรื่องที่มีเสน่ห์เฉพาะตัว มุ่งมั่นและเปี่ยมด้วยไหวพริบ"),
        ("คู่ปรับ / คู่ใจ", "บุคคลสำคัญที่เข้ามาสั่นคลอนหัวใจและสร้างความเปลี่ยนแปลงครั้งใหญ่"),
        ("ผู้ช่วยคู่ใจ", "เพื่อนร่วมทางสุดป่วนที่คอยสร้างรอยยิ้มและช่วยเหลือในยามคับขัน")
    ]

    # สร้าง Rich HTML สำหรับนำไปแปะใน ReadAWrite Intro Box
    intro_html = f"""<p><strong>[ยินดีต้อนรับสู่นิยาย {title}]</strong></p>

<p>{synopsis.replace(chr(10), '<br>')}</p>

<hr>
<p><strong>🔥 เคมีตัวละครที่ชวนติดตาม (Character Chemistry & Dynamics):</strong></p>
<ul>
"""
    for name, role in characters:
        intro_html += f"  <li><strong>{name}:</strong> {role}</li>\n"
    intro_html += f"""</ul>

<p><strong>🎵 เพลงธีมประจำเรื่อง (Theme Song &amp; OST):</strong><br>
🎧 แนะนำเปิดคลอเพิ่มระดับความฟินและอารมณ์ร่วม:<br>
🔗 <a href="{ost_info['url']}" target="_blank" rel="noopener noreferrer"><strong>[YouTube] {ost_info['title']} (คลิกเพื่อฟัง)</strong></a><br>
<em>"{ost_info['desc']}"</em></p>

<p><strong>✨ สิทธิพิเศษผู้อ่าน:</strong> อัปเดตตอนใหม่อย่างต่อเนื่องตาม Golden Hours อ่านฟรี สบายใจ ไร้ดราม่าค้างคา!</p>"""

    return {
        "title": title,
        "genre": genre,
        "headline_tag": tag,
        "synopsis": synopsis,
        "cover_path": cover_file,
        "characters": characters,
        "ost": ost_info,
        "intro_html": intro_html
    }


if __name__ == "__main__":
    sample_titles = [
        "เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง",
        "ฟาร์มสาวปีศาจรัก",
        "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์",
        "สมาคมประกันภัยลี้ลับ"
    ]
    print("🎨 [Story Packager] ทดสอบการสังเคราะห์แพ็กเกจจิ้ง:")
    for t in sample_titles:
        pkg = generate_story_package(t)
        print(f"\n📚 เรื่อง: {pkg['title']}")
        print(f"   • แนว: {pkg['genre']}")
        print(f"   • ภาพปก: {os.path.basename(pkg['cover_path']) if pkg['cover_path'] else 'ไม่พบ (พร้อม generate)'}")
        print(f"   • เพลง OST: {pkg['ost']['title']}")
        print(f"   • คำโปรย: {pkg['synopsis'][:80]}...")
