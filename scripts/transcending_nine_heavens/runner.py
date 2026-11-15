# -*- coding: utf-8 -*-
import os
import sys
import re

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_tools = os.path.join(current_dir, '..', 'generation_tools')
if parent_tools not in sys.path:
    sys.path.append(parent_tools)

from audio_script_converter import convert_chapter_to_audioscript

BASE_CH = 'SecondBrain/Full_Novel_Packs/02_Transcending_Nine_Heavens/Chapters'
BASE_AU = 'SecondBrain/Full_Novel_Packs/02_Transcending_Nine_Heavens/Audio_Scripts'

os.makedirs(BASE_CH, exist_ok=True)
os.makedirs(BASE_AU, exist_ok=True)

def save_and_convert(ch_num, prose):
    file_path = os.path.join(BASE_CH, f"Chapter_{ch_num:02d}.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(prose.strip() + "\n")
    
    first_line = prose.strip().split("\n")[0]
    title_match = re.search(r'# ตอนที่ \d+:\s*(.*)', first_line)
    ch_title = title_match.group(1).strip() if title_match else f"ตอนที่ {ch_num}"
    
    # Generate matching audio script
    audio_content = convert_chapter_to_audioscript(
        novel_title="ผงาดเก้าชั้นฟ้า (Transcending Nine Heavens - 傲世九重天)",
        chapter_num=ch_num,
        chapter_title=ch_title,
        novel_text=prose,
        protagonist_name="ฉู่หยาง"
    )
    
    au_path = os.path.join(BASE_AU, f"Chapter_{ch_num:02d}_AudioScript.md")
    with open(au_path, "w", encoding="utf-8") as f:
        f.write(audio_content.strip() + "\n")
        
    print(f"✅ Ch {ch_num:02d}: Novel {len(prose):,} chars | AudioScript {len(audio_content):,} chars")

if __name__ == '__main__':
    print("Runner initialized successfully.")
