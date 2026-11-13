# -*- coding: utf-8 -*-
from run_batch_expand import save_and_convert
from expand_batch_1 import chapters_data

for ch_num, prose in chapters_data.items():
    save_and_convert(ch_num, prose)

print("Batch 1 (Ch 4, 5, 7, 9) applied successfully!")
