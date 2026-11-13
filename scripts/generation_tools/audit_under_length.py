# -*- coding: utf-8 -*-
import os

base_ch = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Chapters'
files = [f for f in os.listdir(base_ch) if f.startswith('Chapter_') and f.endswith('.md')]
files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))

target_under = []
for f in files:
    path = os.path.join(base_ch, f)
    with open(path, 'r', encoding='utf-8') as fl:
        text = fl.read()
        cnt = len(text)
        num = int(f.split('_')[1].split('.')[0])
        first_line = text.split('\n')[0].strip()
        if cnt < 3500:
            target_under.append((num, cnt, first_line))

print(f"Total under 3,500 chars: {len(target_under)} chapters")
for num, cnt, title in target_under:
    print(f"Ch {num:3d} ({cnt:4d} chars): {title}")
