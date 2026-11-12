#!/usr/bin/env python3
"""
batch_upgrade_all_channel_audiobooks.py
======================================
ระบบยกระดับหน้าปกและชื่อคลิปทั้งช่อง YouTube (Midnight Tales)
- ค้นหาวิดีโอทั้งหมดที่ไม่มี Custom Thumbnail หรือชื่อยังไม่ได้ปรับให้ดึงดูด
- จับคู่ภาพปกจาก SecondBrain/05_Active_Projects/Covers/
- สร้าง High-CTR Thumbnail 1280x720 (Card Backdrop + Sukhumvit typography + Badge Pills)
- อัปโหลด Thumbnail ตรงเข้า YouTube ผ่าน YouTube Data API v3
- ปรับ Title & Tags ให้ติด SEO สวยงาม ไม่เกิน 95 ตัวอักษร
"""

import os
import sys
import re
import time
from typing import Dict, Any, Optional
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from googleapiclient.http import MediaFileUpload

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import youtube_stats

COVERS_DIR = os.path.join(ROOT, "SecondBrain", "05_Active_Projects", "Covers")
OUTPUT_DIR = os.path.join(ROOT, "scratch", "thumbnails")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# รายชื่อเฉพาะสำหรับวิดีโอที่ต้องปรับแต่งเป็นพิเศษ
SPECIFIC_CONFIGS = {
    "XLs5jJoFbOI": {
        "title_on_card": "แสงแห่งฤดูใบไม้ผลิ",
        "subtitle": "ในเมืองสีเทา (รวมครบทุกตอน)",
        "tagline": "ประกายความหวังท่ามกลางเงามืดของมหานคร",
        "new_title": "นิยายเสียง: แสงแห่งฤดูใบไม้ผลิในเมืองเทา (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "แสงแห่งฤดูใบไม้ผลิในเมืองเทา_Cover.jpg",
        "tags": ["นิยายเสียง", "แสงแห่งฤดูใบไม้ผลิในเมืองเทา", "นิยายดราม่า", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "WXxptSQWiuA": {
        "title_on_card": "แสงอัศวินในความมืด",
        "subtitle": "ตำนานผู้พิทักษ์ (รวมครบทุกตอน)",
        "tagline": "คมดาบแห่งความยุติธรรม ส่องสว่างท่ามกลางราตรีทมิฬ",
        "new_title": "นิยายเสียง: แสงอัศวินในความมืด (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "แสงอัศวินในความมืด_Cover.jpg",
        "tags": ["นิยายเสียง", "แสงอัศวินในความมืด", "นิยายแฟนตาซี", "อัศวิน", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "bgBF3F3FNB8": {
        "title_on_card": "เพลงกระบี่สะท้านฟ้า",
        "subtitle": "เหล่าผู้ไร้พันธนาการ (รวมครบทุกตอน)",
        "tagline": "วิถีกระบี่เด็ดเดี่ยว ท้าทายยุทธภพใต้หล้า",
        "new_title": "นิยายเสียง: เพลงกระบี่สะท้านฟ้า เหล่าผู้ไร้พันธนาการ (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "เหล่ามือกระบี่ไร้แม่เหล็ก_Cover.jpg",
        "tags": ["นิยายเสียง", "กำลังภายใน", "นิยายกำลังภายใน", "กระบี่", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "4cM5iELFUso": {
        "title_on_card": "เมื่อนางร้ายหมดรัก",
        "subtitle": "ท่านประธานก็เริ่มคลั่ง (รวมครบทุกตอน)",
        "tagline": "วันที่ฉันหันหลังให้ คือวันที่เขาแทบคลั่งตาย",
        "new_title": "นิยายเสียง: เมื่อนางร้ายหมดรัก ท่านประธานก็เริ่มคลั่ง (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "เมื่อนางร้ายหมดรัก_ท่านประธานก็เริ่มคลั่ง_Cover.jpg",
        "tags": ["นิยายเสียง", "เมื่อนางร้ายหมดรัก", "นางร้าย", "ท่านประธาน", "นิยายโรแมนติก", "นิยายเสียงก่อนนอน"]
    },
    "Xifoa9dfgoQ": {
        "title_on_card": "บทวิจารณ์อันตราย",
        "subtitle": "สตรีมมิ่งปั่นหัวมรณะ (รวมครบทุกตอน)",
        "tagline": "เบื้องหลังจอแก้วที่แลกด้วยชีวิต การตีแผ่ความลับสุดระทึก",
        "new_title": "นิยายเสียง: เน็ตฟิคปั่นหัว รวมบทวิจารณ์อันตราย (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "เน็ตฟิคปั่นหัว_รวมบทวิจารณ์อันตราย_Cover.jpg",
        "tags": ["นิยายเสียง", "เน็ตฟิคปั่นหัว", "ระทึกขวัญ", "สืบสวน", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "RGw0KYqBanY": {
        "title_on_card": "จอมทัพแห่งมิติ",
        "subtitle": "มาร์ชั่นผู้พิชิต (รวมครบทุกตอน)",
        "tagline": "พลังแห่งพันธสัญญาโบราณ สู่การกอบกู้บัลลังก์ต่างโลก",
        "new_title": "นิยายเสียง: เธอคือมาร์ชั่นผู้พิชิตดินแดน (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "เธอคือมาร์ชั่นผู้พิชิตด้วย_Succubus_เพียงสามตน_Cover.jpg",
        "tags": ["นิยายเสียง", "มาร์ชั่นผู้พิชิต", "แฟนตาซี", "ต่างโลก", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "5pAlRn6vogM": {
        "title_on_card": "เทพส่งเสริมความบันเทิง",
        "subtitle": "เซียนระบบบันเทิง (รวมครบทุกตอน)",
        "tagline": "จากคนธรรมดาสู่พระเจ้าแห่งวงการบันเทิงต่างโลก",
        "new_title": "นิยายเสียง: เทพส่งเสริมความบันเทิง (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "เทพส่งเสริมความบันเทิง_Cover.jpg",
        "tags": ["นิยายเสียง", "เทพส่งเสริมความบันเทิง", "ระบบ", "ตลกขบขัน", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "j2g99CpZUEo": {
        "title_on_card": "เจ้าชายหิมะน้ำแข็ง",
        "subtitle": "รักแรกแห่งทุ่งหญ้าสีขาว (รวมครบทุกตอน)",
        "tagline": "สายใยรักบริสุทธิ์ท่ามกลางลมหนาวอันเป็นนิรันดร์",
        "new_title": "นิยายเสียง: เจ้าชายหิมะน้ำแข็งแห่งทุ่งหญ้าสีขาว (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "เจ้าชายหิมะน้ำแข็งแห่งทุ่งหญ้าสีขาว_ปิ๊งรักไร้เดียงสา_Cover.jpg",
        "tags": ["นิยายเสียง", "เจ้าชายหิมะ", "โรแมนติก", "แฟนตาซี", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "EgNWhT7YR9A": {
        "title_on_card": "หายใจในช่องว่าง",
        "subtitle": "เธอคือลมหายใจของฉัน (รวมครบทุกตอน)",
        "tagline": "นิยายรักโรแมนติกแฟนตาซี อบอุ่นหัวใจยามค่ำคืน",
        "new_title": "นิยายเสียง: หายใจในช่องว่าง เธอคือลมหายใจของฉัน (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "หายใจในช่องว่าง_เธอคือลมหายใจของฉัน_Cover.jpg",
        "tags": ["นิยายเสียง", "หายใจในช่องว่าง", "นิยายรัก", "อบอุ่นหัวใจ", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "GqyIRz5cW8I": {
        "title_on_card": "หมอฟันเหนือธรรมชาติ",
        "subtitle": "คลินิกรักษาคนและภูต (รวมครบทุกตอน)",
        "tagline": "หัตถการเยียวยาฟันคนและวิญญาณ ปริศนาลี้ลับกลางเมืองหลวง",
        "new_title": "นิยายเสียง: หมอฟันยุคเหนือธรรมชาติ (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "หมอฟันยุคเหนือธรรมชาติ_Cover.jpg",
        "tags": ["นิยายเสียง", "หมอฟันยุคเหนือธรรมชาติ", "ลี้ลับ", "แฟนตาซี", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "4Ti4GKh6mXA": {
        "title_on_card": "สาวอัศวินในปราสาท",
        "subtitle": "เกียรติยศแห่งดาบ (รวมครบทุกตอน)",
        "tagline": "คำสาบานเพื่อปกป้อง และความลับในปราสาทโบราณ",
        "new_title": "นิยายเสียง: สาวอัศวินในปราสาท (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "สาวอัศวินในปราสาท_Cover.jpg",
        "tags": ["นิยายเสียง", "สาวอัศวินในปราสาท", "แฟนตาซี", "อัศวิน", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "Mp2zzJEyI9w": {
        "title_on_card": "สาวอภินิหารหัวใจเหล็ก",
        "subtitle": "พลังไซเบอร์พลิกโลก (รวมครบทุกตอน)",
        "tagline": "หัวใจที่ไม่มีวันยอมแพ้ การต่อสู้เพื่อความยุติธรรม",
        "new_title": "นิยายเสียง: สาวอภินิหารหัวใจเหล็ก (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "สาวอภินิหารหัวใจเหล็ก_Cover.jpg",
        "tags": ["นิยายเสียง", "สาวอภินิหารหัวใจเหล็ก", "ไซไฟ", "แอ็กชัน", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "XC93Gu6j8I4": {
        "title_on_card": "สมาคมภูติผีกวนประสาท",
        "subtitle": "รวมพลคนเห็นผี (รวมครบทุกตอน)",
        "tagline": "คอมเมดี้ลี้ลับสุดฮา เมื่อผีไม่ได้น่ากลัวอย่างที่คิด",
        "new_title": "นิยายเสียง: สมาคมภูติ์ผีกวนประสาท (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "สมาคมภูติ์ผีกวนประสาท_Cover.jpg",
        "tags": ["นิยายเสียง", "สมาคมภูติผี", "คอมเมดี้", "ผี", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "-KdOEn051j4": {
        "title_on_card": "สมาคมประกันภัยลี้ลับ",
        "subtitle": "เคลมประกันมิติพิศวง (รวมครบทุกตอน)",
        "tagline": "ประกันภัยที่คุ้มครองแม้กระทั่งความตายและคำสาป",
        "new_title": "นิยายเสียง: สมาคมประกันภัยลี้ลับ (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "สมาคมประกันภัยลี้ลับ_Cover.jpg",
        "tags": ["นิยายเสียง", "สมาคมประกันภัยลี้ลับ", "ลี้ลับ", "สืบสวน", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "crSeM2ZpRpY": {
        "title_on_card": "มหาเศรษฐียุค 90",
        "subtitle": "ระบบดัชนีวิเศษ (รวมครบทุกตอน)",
        "tagline": "ย้อนเวลากลับไปสร้างตัว ร่ำรวยข้ามยุคด้วยระบบอัจฉริยะ",
        "new_title": "นิยายเสียง: ย้อนเวลาไปเป็นมหาเศรษฐียุค 90 ระบบดัชนีวิเศษ (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "ย้อนเวลาไปเป็นมหาเศรษฐียุค_90_Cover.jpg",
        "tags": ["นิยายเสียง", "ย้อนเวลา", "ยุค 90", "มหาเศรษฐี", "สู้ชีวิต", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "nA2nRHgOxfI": {
        "title_on_card": "หนุ่มน้อยชิงบัลลังก์",
        "subtitle": "และเทพผู้พิทักษ์ (รวมครบทุกตอน)",
        "tagline": "เส้นทางกอบกู้ราชอาณาจักร การผจญภัยอันยิ่งใหญ่",
        "new_title": "นิยายเสียง: หนุ่มน้อยชิงบัลลังก์และเทพผู้พิทักษ์ (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "ราชอาณาจักรสองร้อยส่วน__เสด็จหนีวัยหนุ่มผู้หวังชิงบัลลังก์พร้อมทวยเทพหูหมาแห่งโลกภายนอก_Cover.jpg",
        "tags": ["นิยายเสียง", "ผจญภัย", "แฟนตาซี", "ชิงบัลลังก์", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "5PdJ8sI8Ct8": {
        "title_on_card": "รักกับเจ้าหญิงเพลย์บอย",
        "subtitle": "ความรักต้องห้ามในวังหลวง (รวมครบทุกตอน)",
        "tagline": "เมื่อหัวใจเต้นผิดจังหวะ ท่ามกลางกฎเกณฑ์อันเข้มงวด",
        "new_title": "นิยายเสียง: รักกับเจ้าหญิงเพลย์บอย (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "รักกับเจ้าหญิงเพลย์บอย_Cover.jpg",
        "tags": ["นิยายเสียง", "รักกับเจ้าหญิงเพลย์บอย", "โรแมนติก", "วังหลวง", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "sXRcrilfnCg": {
        "title_on_card": "ภารกิจสร้างตัว",
        "subtitle": "พลิกชะตากู้ตระกูล (รวมครบทุกตอน)",
        "tagline": "สู้ชีวิตจากจุดต่ำสุด สู่จุดสูงสุดของความสำเร็จ",
        "new_title": "นิยายเสียง: ภารกิจสร้างตัว พลิกชะตากู้ตระกูล (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "ภารกิจร้างตัว_Cover.jpg",
        "tags": ["นิยายเสียง", "ภารกิจสร้างตัว", "สู้ชีวิต", "สร้างตัว", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "8QBP8Me7zaI": {
        "title_on_card": "ฟาร์มสาวปีศาจรัก",
        "subtitle": "สโลว์ไลฟ์ต่างโลก (รวมครบทุกตอน)",
        "tagline": "ทำฟาร์มแสนสุขกับเหล่าสาวปีศาจ อบอุ่นหัวใจทุกคืนวัน",
        "new_title": "นิยายเสียง: ฟาร์มสาวปีศาจรัก ชีวิตสโลว์ไลฟ์ต่างโลก (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "ฟาร์มสาวปีศาจรัก_Cover.jpg",
        "tags": ["นิยายเสียง", "ฟาร์มสาวปีศาจรัก", "สโลว์ไลฟ์", "ต่างโลก", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "3qNBVI-AOWc": {
        "title_on_card": "ตะลุยดันเจียนวิเศษ",
        "subtitle": "พิชิตบอสมหาโหด (รวมครบทุกตอน)",
        "tagline": "ดาบเล่มเดียวฝ่าดงอสูร ปลดล็อกพลังไร้ขีดจำกัด",
        "new_title": "นิยายเสียง: ตะลุยดันเจียนวิเศษ พลิกชะตาพิชิตบอส (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "พลิกฟันดันเจียน_ทริปเปิลยูพ_Cover.jpg",
        "tags": ["นิยายเสียง", "ดันเจียน", "เกมเมอร์", "แฟนตาซี", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "0Vk2UGQ9QX4": {
        "title_on_card": "ผู้สาปแช่งไคเมร่า",
        "subtitle": "เกิดใหม่ในโลกเวทมนตร์ (รวมครบทุกตอน)",
        "tagline": "พลิกพลังคำสาปเป็นอาวุธ สู่จอมเวทผู้ไร้พ่าย",
        "new_title": "นิยายเสียง: ผู้สาปแช่งไคเมร่า เกิดใหม่ในโลกเวทมนตร์ (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "ผู้สาปแช่ง_Chimera_เกิดใหม่ในโลกเวทย์มนต์_Cover.jpg",
        "tags": ["นิยายเสียง", "ไคเมร่า", "เกิดใหม่", "เวทมนตร์", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "00xVUDjrilw": {
        "title_on_card": "นิมิตดวงดาวว่านหางแมว",
        "subtitle": "ความลับแห่งดวงดารา (รวมครบทุกตอน)",
        "tagline": "พลังพยากรณ์โบราณที่จะสั่นคลอนทั่วทั้งจักรวาล",
        "new_title": "นิยายเสียง: นิมิตดวงดาวว่านหางแมว (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "นิมิตดวงดาวว่านหางแมว_Cover.jpg",
        "tags": ["นิยายเสียง", "นิมิตดวงดาวว่านหางแมว", "แฟนตาซี", "เวทมนตร์", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "ri7R9MQOe_I": {
        "title_on_card": "นางฟ้าหัดร้าย นางมารหัดรัก",
        "subtitle": "รักสองขั้วหัวใจ (รวมครบทุกตอน)",
        "tagline": "เมื่อขั้วตรงข้ามมาบรรจบ ความรักจึงผลิบาน",
        "new_title": "นิยายเสียง: นางฟ้าหัดร้ายกับนางมารหัดรัก (รวมทุกตอนจบภาค) [ฟังต่อเนื่องก่อนนอน]",
        "cover_file": "นางฟ้าหัดร้ายกับนางมารหัดรัก_Cover.jpg",
        "tags": ["นิยายเสียง", "นางฟ้าหัดร้ายกับนางมารหัดรัก", "โรแมนติก", "แฟนตาซี", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    },
    "YpMdjON184w": {
        "title_on_card": "เกิดใหม่เป็นตัวเอก",
        "subtitle": "แต่ไม่อยากเด่น (รวมครบทุกตอน)",
        "tagline": "ขออยู่อย่างสงบ แต่โชคชะตาไม่เคยปรานี",
        "new_title": "นิยายเสียง: วนเกิดมาเป็นตัวเอกแต่ไม่อยากเด่น (รวมทุกตอนจบภาค) [ฟังก่อนนอน]",
        "cover_file": "วนเกิดมาเป็นตัวเอกแต่ไม่อยาก_Cover.jpg",
        "tags": ["นิยายเสียง", "เกิดใหม่", "ตลกขบขัน", "แฟนตาซี", "นิยายเสียงก่อนนอน", "Full Audiobook"]
    }
}


def find_cover_image(hint: str) -> Optional[str]:
    # 1. Exact path
    if os.path.isabs(hint) and os.path.exists(hint):
        return hint
    direct = os.path.join(COVERS_DIR, hint)
    if os.path.exists(direct):
        return direct

    # 2. Match in covers
    clean_hint = re.sub(r"[\s_:：]+", "", hint).replace("Cover.jpg", "").replace("Cover.png", "")
    all_files = [f for f in os.listdir(COVERS_DIR) if f.lower().endswith((".jpg", ".png", ".jpeg"))]
    # Filter out secondary suffixes
    primary = [f for f in all_files if not f.endswith("_captioned.jpg") and not f.endswith("_3x4.jpg") and not f.endswith("_tt.jpg")]

    for f in primary:
        clean_f = re.sub(r"[\s_:：]+", "", f).replace("Cover.jpg", "").replace("Cover.png", "")
        if clean_hint in clean_f or clean_f in clean_hint:
            return os.path.join(COVERS_DIR, f)

    # 3. Fuzzy chunk match
    for f in primary:
        clean_f = re.sub(r"[\s_:：]+", "", f)
        if len(clean_hint) >= 4 and clean_hint[:6] in clean_f:
            return os.path.join(COVERS_DIR, f)

    return None


def render_high_ctr_thumbnail(vid: str, title: str, subtitle: str, tagline: str, cover_path: str) -> str:
    width, height = 1280, 720
    orig = Image.open(cover_path).convert("RGBA")

    # 1. Blurred + Darkened Background
    bg = orig.resize((width, height)).filter(ImageFilter.GaussianBlur(28))
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 190))
    bg = Image.alpha_composite(bg, overlay)

    # 2. Cover card on left
    orig_ratio = orig.width / orig.height
    card_h = 600
    card_w = int(card_h * orig_ratio)
    cover_resized = orig.resize((card_w, card_h), Image.Resampling.LANCZOS)

    card_bg = Image.new("RGBA", (card_w + 12, card_h + 12), (255, 255, 255, 220))
    card_bg.paste(cover_resized, (6, 6))
    bg.paste(card_bg, (60, 60), card_bg)

    # 3. Typography on right
    draw = ImageDraw.Draw(bg)
    font_path = "/System/Library/Fonts/Supplemental/SukhumvitSet.ttc"

    # Font sizing based on title length
    t_len = len(title)
    t_size = 62 if t_len <= 14 else (52 if t_len <= 22 else 42)
    title_font = ImageFont.truetype(font_path, t_size, index=4)
    badge_font = ImageFont.truetype(font_path, 28, index=4)
    sub_font = ImageFont.truetype(font_path, 32, index=4)
    tag_font = ImageFont.truetype(font_path, 24, index=1)
    pill_font = ImageFont.truetype(font_path, 24, index=4)

    text_x = 60 + card_w + 45

    # Badges
    draw.rounded_rectangle([(text_x, 85), (text_x + 285, 138)], radius=10, fill=(245, 158, 11, 245))
    draw.text((text_x + 18, 95), "FULL AUDIOBOOK", fill=(0, 0, 0), font=badge_font)

    draw.rounded_rectangle([(text_x + 300, 85), (text_x + 510, 138)], radius=10, fill=(14, 165, 233, 240))
    draw.text((text_x + 320, 95), "รวมครบจบภาค", fill=(255, 255, 255), font=badge_font)

    # Title, Subtitle, Tagline
    draw.text((text_x, 175), title, fill=(255, 255, 255), font=title_font)
    draw.text((text_x, 265), subtitle, fill=(56, 189, 248), font=sub_font)
    draw.text((text_x, 335), tagline, fill=(226, 232, 240), font=tag_font)

    # Bottom pill badge
    draw.rounded_rectangle([(text_x, 520), (text_x + 470, 585)], radius=12, fill=(30, 41, 59, 240), outline=(56, 189, 248), width=2)
    draw.text((text_x + 35, 538), "รวมครบทุกตอน · ฟังยาวต่อเนื่องก่อนนอน", fill=(241, 245, 249), font=pill_font)

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_file = os.path.join(OUTPUT_DIR, f"{vid}_highctr.jpg")
    bg.convert("RGB").save(out_file, quality=95)
    return out_file


def run_batch_upgrade():
    print("=" * 65)
    print("🚀 เริ่มกระบวนการยกระดับหน้าปกและชื่อคลิปทั้งช่อง YouTube")
    print("=" * 65)

    yt = youtube_stats._yt()
    success_count = 0
    failed_count = 0

    for vid, cfg in SPECIFIC_CONFIGS.items():
        print(f"\n[+] กำลังดำเนินการ: {cfg['title_on_card']} ({vid})")
        cover_fp = find_cover_image(cfg["cover_file"])
        if not cover_fp or not os.path.exists(cover_fp):
            print(f"    ⚠️ ไม่พบไฟล์ปกสำหรับ: {cfg['cover_file']}")
            failed_count += 1
            continue

        try:
            # 1. สร้างภาพปก High-CTR
            thumb_path = render_high_ctr_thumbnail(
                vid=vid,
                title=cfg["title_on_card"],
                subtitle=cfg["subtitle"],
                tagline=cfg["tagline"],
                cover_path=cover_fp
            )
            print(f"    🎨 เจนเนอเรตภาพปกเรียบร้อย: {os.path.basename(thumb_path)}")

            # 2. อัปโหลดภาพปก
            media = MediaFileUpload(thumb_path, mimetype="image/jpeg")
            yt.thumbnails().set(videoId=vid, media_body=media).execute()
            print(f"    🚀 อัปโหลดหน้าปก Live บน YouTube สำเร็จ!")

            # 3. อัปเดต Title และ Tags
            res = yt.videos().list(part="snippet", id=vid).execute()
            if res.get("items"):
                snip = res["items"][0]["snippet"]
                clean_title = cfg["new_title"][:95]
                snip["title"] = clean_title
                snip["tags"] = cfg.get("tags", ["นิยายเสียง", "นิยายแฟนตาซี", "Full Audiobook", "นิยายเสียงก่อนนอน"])
                yt.videos().update(part="snippet", body={"id": vid, "snippet": snip}).execute()
                print(f"    📝 อัปเดตชื่อคลิปใหม่เรียบร้อย: {clean_title}")

            success_count += 1
            time.sleep(1.0)
        except Exception as e:
            print(f"    ❌ ข้อผิดพลาด: {e}")
            failed_count += 1

    print("\n" + "=" * 65)
    print(f"🎉 เสร็จสิ้นภารกิจ! สำเร็จ {success_count} คลิป | ล้มเหลว {failed_count} คลิป")
    print("=" * 65)


if __name__ == "__main__":
    run_batch_upgrade()
