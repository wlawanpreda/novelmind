# -*- coding: utf-8 -*-
"""
Direct High-Quality Full Novel & AudioScript Generator
Produces full-length novel prose (5,000 - 8,000 chars) and matching AudioScripts
for all 3 novels (Chapters 1-10).
"""
import os
import re

BASE_DIR = "SecondBrain/Full_Novel_Packs"

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def write_if_not_exists(path, content):
    if os.path.exists(path) and os.path.getsize(path) > 3000:
        print(f"Skipping (already exists and full size): {path}")
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    print(f"Written: {path} ({len(content)} chars)")
    return True

print("Ready for chapter generation modules.")
