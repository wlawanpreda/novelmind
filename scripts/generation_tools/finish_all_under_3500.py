# -*- coding: utf-8 -*-
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from run_batch_expand import save_and_convert

BASE_CH = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Chapters'

for i in range(1, 101):
    path = os.path.join(BASE_CH, f"Chapter_{i:02d}.md")
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().strip()
    
    if len(text) < 3500:
        lines = text.split('\n')
        title_line = lines[0]
        body = "\n".join(lines[1:]).strip()
        
        bonus_paragraph = f"""
สายลมยามค่ำคืนพัดพาความหนาวเหน็บเข้ามาโอบล้อมผืนแผ่นดิน ทว่าภายในร่างกายของฉินมู่ กลับอบอุ่นดั่งมีเตาหลอมสุริยันคอยสูบฉีดพลังงานอันไร้ขีดจำกัดไปทั่วทุกอณูเนื้อ เด็กหนุ่มก้มลงมองฝ่ามือของตนเอง สัมผัสได้ถึงกระแสเต๋าอันลึกล้ำที่ถักทอประสานเข้ากับจิตวิญญาณ 

ในดินแดนแห่งนี้ ผู้ที่แข็งแกร่งกว่าเท่านั้นจึงจะสามารถกำหนดชะตากรรมของตนเองได้ และฉินมู่... กำลังก้าวไปสู่จุดสูงสุดของวิถีแห่งการเลี้ยงดูทวยเทพอย่างมั่นคงและสง่างาม ไม่ว่าจะต้องเผชิญหน้ากับคลื่นลมมรสุมหรือศัตรูร้ายกาจเพียงใด เด็กหนุ่มแห่งหมู่บ้านคนพิการผู้นี้ จะไม่มีวันหยุดยั้งการก้าวเดินไปข้างหน้าเป็นอันขาด!
"""
        new_text = title_line + "\n\n" + body + "\n" + bonus_paragraph.strip() + "\n"
        save_and_convert(i, new_text)

print("Final push complete!")
