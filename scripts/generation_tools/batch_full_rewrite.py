# -*- coding: utf-8 -*-
"""
batch_full_rewrite.py
Rewrites compressed/short chapters into complete, rich full-length Thai web novel prose (>4,000 to 6,000+ characters),
preserving all authentic dialogues, internal monologues, vivid descriptions of martial techniques, Great Ruins atmosphere,
and Granny Si / Village Elders / Qin Mu dynamics without skipping or summarizing.
Then converts each chapter 1-to-1 to AudioScript with multi-voice tags & cinematic SFX.
"""
import os
import sys
import re

BASE_CH = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Chapters'
BASE_AU = 'SecondBrain/Full_Novel_Packs/03_Tales_of_Herding_Gods/Audio_Scripts'

from audio_script_converter import convert_chapter_to_audioscript

print("Audio script converter imported successfully.")
