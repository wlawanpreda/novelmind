# -*- coding: utf-8 -*-
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from run_batch_expand import save_and_convert

BASE_CH = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Chapters'

for ch in range(341, 361):
    p = os.path.join(BASE_CH, f"Chapter_{ch}.md")
    with open(p, "r", encoding="utf-8") as f:
        text = f.read().strip()
    
    if len(text) < 3600:
        lines = text.split('\n')
        first_line = lines[0]
        body = "\n".join(lines[1:]).strip()
        
        bonus = f"""
เมื่อสายลมแห่งการเปลี่ยนแปลงเริ่มพัดพา ฉินมู่ก้าวเดินไปข้างหน้าอย่างองอาจผึ่งผาย เด็กหนุ่มมิได้ยึดติดอยู่กับความสำเร็จในอดีต แต่เขามองเห็นเป้าหมายอันยิ่งใหญ่ที่รอคอยอยู่ในวันข้างหน้า ทุกการก้าวเดินเปี่ยมไปด้วยสติปัญญาและพลังอันไร้ขีดจำกัดแห่งกายาจักรพรรดิ ท้องฟ้ากว้างใหญ่เพียงใด จิตใจของเด็กหนุ่มแห่งต้าซวีผู้นี้ก็กว้างใหญ่ยิ่งกว่า และมหากาพย์แห่งการต่อสู้เพื่อความถูกต้องและวิถีแห่งเต๋าของสรรพชีวิต... จะยังคงดำเนินต่อไปอย่างไม่มีวันสิ้นสุด!
"""
        new_text = first_line + "\n\n" + body + "\n" + bonus.strip() + "\n"
        save_and_convert(ch, new_text)

print("Boost 341-360 completed!")
