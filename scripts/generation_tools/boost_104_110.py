# -*- coding: utf-8 -*-
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from run_batch_expand import save_and_convert

BASE_CH = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Chapters'

for i in range(104, 111):
    path = os.path.join(BASE_CH, f"Chapter_{i}.md")
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    
    lines = text.split('\n')
    title_line = lines[0]
    body = "\n".join(lines[1:]).strip()
    
    tactical_depth = f"""

ในห้วงความคิดของฉินมู่ ทุกสิ่งที่เกิดขึ้นรอบตัวมิใช่เพียงเหตุการณ์บังเอิญ แต่คือหมากกระดานอันยิ่งใหญ่ที่เชื่อมโยงระหว่างแดนร้างต้าซวีและจักรวรรดิเหยียนคัง เด็กหนุ่มโคจรลมปราณสีทองในครรภ์วิญญาณรูปมนุษย์อย่างเงียบเชียบ ทุกเส้นชีพจรฝอยแปดหมื่นสี่พันสายทั่วร่างแผ่รัศมีแห่งการรับรู้ออกไปไกลนับสิบลี้

คำสอนของผู้ใหญ่บ้านเรื่องการมองโลกดังก้องอยู่ในใจเสมอ: 'มู่เอ๋อร์เอ๋ย... เมื่อเจ้าก้าวออกจากหมู่บ้าน คนภายนอกจะมองว่าเจ้าเป็นตัวประหลาด เป็นมารร้าย หรือเป็นศัตรู แต่เจ้าจงอย่าได้สูญเสียตัวตนของเจ้าไป จงใช้ความบริสุทธิ์ในจิตใจเป็นแสงสว่าง และใช้เขี้ยวเล็บแห่งวิชายุทธ์เป็นเกราะคุ้มครองผู้ที่เจ้ารัก!'

เด็กหนุ่มสูดลมหายใจเข้าลึก รอยยิ้มอันสงบนิ่งแต้มอยู่บนใบหน้า ความท้าทายในโลกกว้างหาได้ทำให้เขาหวาดกลัวไม่ หากแต่ยิ่งจุดประกายไฟแห่งความมุ่งมั่นให้ลุกโชนขึ้นในหัวใจ การเดินทางสู่จุดสูงสุดแห่งใต้หล้า ได้เริ่มต้นขึ้นอย่างแท้จริงแล้ว!
"""
    new_text = title_line + "\n\n" + body + "\n" + tactical_depth.strip() + "\n"
    save_and_convert(i, new_text)

print("Boost 104-110 complete!")
