# -*- coding: utf-8 -*-
"""
mass_full_expander.py
Fully expands chapters 21 to 100 in batches into rich, detailed, full prose (>3,500 - 5,000+ chars),
honoring the real Chinese original plot points of 《牧神记》 (Tales of Herding Gods):
- Village Elders' secret arts (Butcher knife, Cripple speed, Deaf painting, Blind eyes, Apothecary poisons/medicine, Granny Si demonic arts, Village Chief sword skill)
- Imperial Preceptor (延康国师) reforms, Little Fox Hu Ling'er, Princess Ling Yuxiu, Heavenly Devil Cult (天魔教) Little Cult Master duties, Sun Guardian ship, Imperial College entrance exams, etc.
- Multi-voice dialogues, dynamic combats, philosophical breakthroughs.
- Converts 1-to-1 to AudioScript with sound effects and character tones.
"""
import os
import sys
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

from run_batch_expand import save_and_convert

BASE_CH = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Chapters'

def get_current_content(ch_num):
    path = os.path.join(BASE_CH, f"Chapter_{ch_num:02d}.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""

print("Mass full expander initialized.")
