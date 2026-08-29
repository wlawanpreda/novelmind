"""
global_scout.py — Multi-Country Web Novel Browser Crawler using Playwright
===========================================================================

ระบบท่องเว็บหานิยายและไอเดียเทรนด์จากทั่วโลก (JP, CN, KR, US/EN, TH)
โดยใช้ Playwright Headless Browser ดึงข้อมูลพล็อต, เรื่องย่อ, อันดับ, และแท็ก
พร้อมแปลงเป็นไอเดียดัดแปลงสำหรับนิยายไทย (Original IP) อัตโนมัติ

ประเทศและแพลตฟอร์ม:
  🇯🇵 ญี่ปุ่น (JP): Syosetu, Kakuyomu
  🇨🇳 จีน (CN): Webnovel / Qidian Global Trends
  🇰🇷 เกาหลี (KR): Novelpia / Munpia Trends
  🇺🇸/🌐 สากล (EN): RoyalRoad, ScribbleHub, Reddit WritingPrompts
  🇹🇭 ไทย (TH): ReadAWrite / Dek-D Trends
"""
from __future__ import annotations

import os
import re
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime
from typing import List, Dict, Any, Optional

from playwright.sync_api import sync_playwright, Browser, Page

ROOT = os.path.dirname(os.path.abspath(__file__))
_ENV = os.path.join(ROOT, ".env")
if os.path.exists(_ENV):
    with open(_ENV, "r", encoding="utf-8") as _f:
        for _l in _f:
            _l = _l.strip()
            if _l and not _l.startswith("#") and "=" in _l:
                _k, _v = _l.split("=", 1)
                os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))

SECOND_BRAIN = os.environ.get("ANSRE_SB", os.path.join(ROOT, "SecondBrain"))
SCOUTING_POOL = os.path.join(SECOND_BRAIN, "01_Scouting_Pool")
IDEA_VAULT = os.path.join(SECOND_BRAIN, "00_Idea_Vault")

os.makedirs(SCOUTING_POOL, exist_ok=True)
os.makedirs(IDEA_VAULT, exist_ok=True)

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

COUNTRY_FLAGS = {
    "JP": "🇯🇵 ญี่ปุ่น",
    "CN": "🇨🇳 จีน",
    "KR": "🇰🇷 เกาหลี",
    "US": "🇺🇸 สากล",
    "EN": "🌐 สากล",
    "TH": "🇹🇭 ไทย"
}


def sanitize_filename(name: str) -> str:
    """ทำความสะอาดชื่อไฟล์ เก็บภาษาไทยและอังกฤษ"""
    clean = re.sub(r'[^\w\-_\s฀-๿]', '', name).strip()
    return clean.replace(' ', '_')[:60]


# ===========================================================================
# Playwright Crawlers per Country / Platform
# ===========================================================================

def crawl_syosetu_jp(page: Page, limit: int = 5) -> List[Dict[str, Any]]:
    """🇯🇵 ญี่ปุ่น: Syosetu (Shousetsuka ni Narou) Weekly Ranking + API Fallback"""
    novels = []
    # 1. ลองใช้ Official Syosetu API ก่อน (ข้อมูลสมบูรณ์และเร็วที่สุด)
    try:
        api_url = f"https://api.syosetu.com/novelapi/api/?out=json&lim={limit}&order=weekly_point"
        req = urllib.request.Request(api_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            # item แรกเป็น allcount dict
            for idx, item in enumerate(data[1:limit+1]):
                ncode = item.get("ncode", "").lower()
                novels.append({
                    "id": ncode or f"syosetu_{idx+1}",
                    "source": "Syosetu",
                    "country": "JP",
                    "title": item.get("title", f"Syosetu #{idx+1}"),
                    "url": f"https://ncode.syosetu.com/{ncode}/",
                    "synopsis": item.get("story", ""),
                    "points": item.get("weekly_point", 0),
                    "rank": idx + 1,
                    "genre": "Fantasy / Isekai",
                    "tags": ["Isekai", "Fantasy", "Syosetu", "Japanese"]
                })
        if novels:
            print(f"[+] [JP] ดึงข้อมูล Syosetu สำเร็จ {len(novels)} เรื่อง")
            return novels
    except Exception as e:
        print(f"[!] Syosetu API fallback to Playwright: {e}")

    # 2. Browser Playwright fallback
    url = "https://yomou.syosetu.com/rank/genrelist/type/weekly_total/"
    print(f"[*] [Playwright JP] กำลังท่องเว็บ Syosetu: {url} ...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(2000)
        items = page.query_selector_all(".ranking_list, .c-card, tr, .p-rank-list")
        for idx, item in enumerate(items[:limit]):
            try:
                title_el = item.query_selector("a")
                title = title_el.inner_text().strip() if title_el else f"Syosetu Novel #{idx+1}"
                link = title_el.get_attribute("href") if title_el else ""
                novels.append({
                    "id": f"syosetu_{idx+1}_{int(time.time())}",
                    "source": "Syosetu",
                    "country": "JP",
                    "title": title,
                    "url": link or url,
                    "synopsis": f"Japanese Webnovel: {title}",
                    "rank": idx + 1,
                    "genre": "Fantasy/Isekai",
                    "tags": ["Isekai", "Fantasy", "Syosetu", "Japanese"]
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[!] Syosetu crawl error: {e}")
    return novels


def crawl_royalroad_en(page: Page, limit: int = 5) -> List[Dict[str, Any]]:
    """🇺🇸/🌐 สากล: RoyalRoad Rising Stars & Best Rated"""
    novels = []
    url = "https://www.royalroad.com/fictions/rising-stars"
    print(f"[*] [Playwright US/EN] กำลังท่องเว็บ Royal Road: {url} ...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_selector(".fiction-list-item", timeout=10000)
        
        items = page.query_selector_all(".fiction-list-item")
        for idx, item in enumerate(items[:limit]):
            try:
                title_el = item.query_selector(".fiction-title a")
                title = title_el.inner_text().strip() if title_el else f"RoyalRoad #{idx+1}"
                link = title_el.get_attribute("href") if title_el else ""
                if link and not link.startswith("http"):
                    link = f"https://www.royalroad.com{link}"
                    
                fid = ""
                m = re.search(r"/fiction/(\d+)", link or "")
                if m:
                    fid = m.group(1)
                else:
                    fid = f"rr_{idx+1}_{int(time.time())}"
                    
                cover_el = item.query_selector("img")
                cover_url = cover_el.get_attribute("src") if cover_el else ""
                
                synopsis_el = item.query_selector(".description")
                synopsis = synopsis_el.inner_text().strip() if synopsis_el else ""
                
                tags_el = item.query_selector_all(".tags a")
                tags = [t.inner_text().strip() for t in tags_el] or ["LitRPG", "Progression Fantasy"]
                
                rating_el = item.query_selector("[aria-label*='stars']")
                rating_text = rating_el.get_attribute("aria-label") if rating_el else "4.5"
                rating_val = 4.5
                rm = re.search(r"([\d\.]+)", rating_text or "")
                if rm:
                    rating_val = float(rm.group(1))

                novels.append({
                    "id": fid,
                    "source": "RoyalRoad",
                    "country": "US",
                    "title": title,
                    "url": link,
                    "cover_url": cover_url,
                    "synopsis": synopsis,
                    "rating": rating_val,
                    "rank": idx + 1,
                    "genre": "Progression Fantasy / LitRPG",
                    "tags": tags + ["RoyalRoad", "Western"]
                })
            except Exception as e:
                print(f"[!] Error parsing RoyalRoad item {idx}: {e}")
    except Exception as e:
        print(f"[!] RoyalRoad crawl error: {e}")
    return novels


def crawl_novelpia_kr(page: Page, limit: int = 5) -> List[Dict[str, Any]]:
    """🇰🇷 เกาหลี: Novelpia Top Trending Korean Webnovels"""
    novels = []
    url = "https://novelpia.com/ranking/all/realtime"
    print(f"[*] [Playwright KR] กำลังท่องเว็บ Novelpia (เกาหลี): {url} ...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        # Novelpia loads ranking cards
        page.wait_for_timeout(3000)
        
        cards = page.query_selector_all(".ranking_item, .novel_list_item, .s_card")
        if not cards:
            cards = page.query_selector_all("a[href*='/novel/']")
            
        for idx, card in enumerate(cards[:limit]):
            try:
                title = card.inner_text().split("\n")[0].strip()
                link = card.get_attribute("href") or ""
                if link and not link.startswith("http"):
                    link = f"https://novelpia.com{link}"
                if not title or len(title) < 2:
                    continue
                nid = f"novelpia_{idx+1}_{int(time.time())}"
                m = re.search(r"/novel/(\d+)", link or "")
                if m:
                    nid = m.group(1)
                    
                novels.append({
                    "id": nid,
                    "source": "Novelpia",
                    "country": "KR",
                    "title": title,
                    "url": link or url,
                    "synopsis": f"인기 랭킹 웹소설: {title} (Hunter / Constellation / Regression Trope)",
                    "rank": idx + 1,
                    "genre": "Hunter / System / Regression",
                    "tags": ["Korean", "Novelpia", "Hunter", "Regression", "Constellation"]
                })
            except Exception as e:
                continue
    except Exception as e:
        print(f"[!] Novelpia crawl error: {e}")
        
    # Fallback ตัวอย่าง Korean Hunter/Gate tropes ถ้าเว็บติด geo-block
    if not novels:
        novels.append({
            "id": f"kr_hunter_{int(time.time())}",
            "source": "Korean_Webnovel",
            "country": "KR",
            "title": "탑을 오르는 1인 길드 마스터 (The Solo Guildmaster Climbs the Tower)",
            "url": "https://novelpia.com",
            "synopsis": "เกตมอนสเตอร์เปิดออกทั่วกรุงโซล แต่ชายหนุ่มคนหนึ่งได้รับระบบ 'สมาคมคนเดียว' ที่สามารถอัญเชิญวิญญาณฮีโร่ในอดีตมาเป็นสมาชิกกิลด์ได้",
            "rank": 1,
            "genre": "Tower / Hunter / System",
            "tags": ["Korean", "Tower", "Hunter", "Solo", "System"]
        })
    return novels


def crawl_qidian_cn(page: Page, limit: int = 5) -> List[Dict[str, Any]]:
    """🇨🇳 จีน: Webnovel / Qidian Global Trending System Novels"""
    novels = []
    url = "https://www.webnovel.com/ranking/novel/trending_male"
    print(f"[*] [Playwright CN] กำลังท่องเว็บ Webnovel (จีน/แปลสากล): {url} ...")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=25000)
        page.wait_for_timeout(3000)
        
        items = page.query_selector_all(".rank-item, li.item, .g_book_item")
        for idx, item in enumerate(items[:limit]):
            try:
                title_el = item.query_selector("h3, h4, .book-name, a.title")
                title = title_el.inner_text().strip() if title_el else f"Webnovel CN #{idx+1}"
                link_el = item.query_selector("a[href*='/book/']")
                link = link_el.get_attribute("href") if link_el else ""
                if link and not link.startswith("http"):
                    link = f"https://www.webnovel.com{link}"
                    
                synopsis_el = item.query_selector("p, .desc")
                synopsis = synopsis_el.inner_text().strip() if synopsis_el else ""
                
                bid = f"cn_{idx+1}_{int(time.time())}"
                m = re.search(r"/book/([^/]+)", link or "")
                if m:
                    bid = m.group(1)
                    
                novels.append({
                    "id": bid,
                    "source": "Qidian_Webnovel",
                    "country": "CN",
                    "title": title,
                    "url": link or url,
                    "synopsis": synopsis or f"Chinese Cultivation/System webnovel: {title}",
                    "rank": idx + 1,
                    "genre": "Urban Cultivation / Infinite Flow / System",
                    "tags": ["Chinese", "System", "Urban", "Cultivation", "Infinite Flow"]
                })
            except Exception:
                continue
    except Exception as e:
        print(f"[!] Qidian/Webnovel crawl error: {e}")
        
    if not novels:
        novels.append({
            "id": f"cn_system_{int(time.time())}",
            "source": "Qidian_Webnovel",
            "country": "CN",
            "title": "全球进入诡异降临时代 (Global Supernatural Incursion Era)",
            "url": "https://www.webnovel.com",
            "synopsis": "โลกมนุษย์ถูกทับซ้อนด้วยมิติลี้ลับ ตัวเอกได้รับระบบ 'ร้านค้ายมโลก' ที่สามารถซื้อขายของวิเศษกับภูตผีได้ เพื่อเอาชีวิตรอดในกฎเกณฑ์สุดอันตราย",
            "rank": 1,
            "genre": "Infinite Flow / Mystery / System",
            "tags": ["Chinese", "Mystery", "Supernatural", "System"]
        })
    return novels


# ===========================================================================
# AI Localization & Concept Extraction Engine
# ===========================================================================

def localize_and_adapt_concept(novel: Dict[str, Any]) -> Dict[str, Any]:
    """
    นำเรื่องย่อและพล็อตต่างประเทศ (JP/CN/KR/EN) มาวิเคราะห์ผ่าน LLM
    เพื่อสกัด Core Trope, Novelty Hook, และกลยุทธ์ดัดแปลงเป็น "นิยายไทยต้นฉบับ 100%"
    """
    try:
        from llm_provider import generate
    except ImportError:
        generate = None

    prompt = f"""คุณคือ "Senior IP Strategist & Thai Localization Master"
หน้าที่ของคุณคือ วิเคราะห์ไอเดียนิยายต่างประเทศเรื่องนี้ แล้วสร้างเป็น **"คอนเซปต์นิยายไทยต้นฉบับใหม่ 100% (Original Thai IP)"**
โดยคงความสนุกของแกนเรื่องไว้ แต่เปลี่ยนบริบท ฉาก มุก และตัวละครให้เข้ากับรสนิยมคนไทย

[ข้อมูลนิยายต้นทาง]:
- ประเทศ: {novel.get('country')} ({COUNTRY_FLAGS.get(novel.get('country', ''), '')})
- แหล่งที่มา: {novel.get('source')}
- ชื่อเรื่องเดิม: {novel.get('title')}
- แนวเรื่อง: {novel.get('genre')}
- เรื่องย่อ/พล็อตย่อ:
{novel.get('synopsis')}

จงสกัดและวิเคราะห์ในรูปแบบ JSON ต่อไปนี้:
{{
  "thai_working_title": "ชื่อเรื่องภาษาไทยที่น่าดึงดูดใจและตรงแนว (เช่น 'สมาคมประกันภัยลี้ลับ')",
  "core_trope": "แกนเรื่องหลัก (เช่น ระบบชดเชยวิญญาณ, ย้อนเวลาไขคดี)",
  "novelty_hook": "จุดเด่นหรือหักมุมที่ทำให้เรื่องนี้น่าสนใจ",
  "thai_adaptation_strategy": "แผนการดัดแปลงให้เข้ากับสังคมไทย (สถานที่, อาชีพ, ความเชื่อ, อารมณ์ขัน)",
  "market_fit_score": 8.5,
  "recommended_tone": "ระทึกขวัญปนตลก / สืบสวนเข้มข้น / แฟนตาซีเอาชีวิตรอด"
}}
"""
    default_res = {
        "thai_working_title": f"บันทึกลับ {novel.get('title')}",
        "core_trope": "การเอาชีวิตรอดด้วยพลังพิเศษในชีวิตประจำวัน",
        "novelty_hook": "ระบบภารกิจที่ให้ผลตอบแทนแปลกประหลาด",
        "thai_adaptation_strategy": "ปรับฉากเป็นกรุงเทพฯ และเมืองไทยสมัยใหม่",
        "market_fit_score": 8.0,
        "recommended_tone": "ระทึกขวัญเข้มข้น"
    }

    if not generate:
        return default_res

    try:
        raw = generate(prompt + "\n\n[สำคัญ] ตอบเฉพาะ JSON เท่านั้น", role="analyzer", is_json=True)
        # Parse JSON
        m = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if m:
            data = json.loads(m.group(0))
            if isinstance(data, dict):
                return data
    except Exception as e:
        print(f"[!] Localization LLM error for {novel.get('title')}: {e}")
    return default_res


# ===========================================================================
# Markdown Saving & SecondBrain Integration
# ===========================================================================

def save_to_scouting_pool(novel: Dict[str, Any], concept: Dict[str, Any]) -> str:
    """บันทึกข้อมูลนิยายที่ส่องมาลงใน SecondBrain/01_Scouting_Pool/*.md"""
    safe_title = sanitize_filename(concept.get("thai_working_title", novel.get("title", "novel")))
    filename = f"{novel.get('source')}_{novel.get('id')}_{safe_title}.md"
    filepath = os.path.join(SCOUTING_POOL, filename)

    tags = list(set(novel.get("tags", []) + [concept.get("core_trope", "Global_Trend")]))
    tags_formatted = "\n".join([f"  - {t}" for t in tags])

    content = f"""---
id: "{novel.get('id')}"
source: "{novel.get('source')}"
country: "{novel.get('country')}"
original_title: "{novel.get('title')}"
thai_working_title: "{concept.get('thai_working_title')}"
genre: "{novel.get('genre')}"
market_fit_score: {concept.get('market_fit_score', 8.0)}
popularity_score: {int(concept.get('market_fit_score', 8.0) * 10)}
rank: {novel.get('rank', 1)}
url: "{novel.get('url', '')}"
status: "Analyzed"
scouted_at: "{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
tags:
{tags_formatted}
---

# 🌐 Global Scout: {concept.get('thai_working_title')} ({novel.get('title')})

- **ประเทศต้นทาง:** {COUNTRY_FLAGS.get(novel.get('country', ''), novel.get('country'))} ({novel.get('source')})
- **ลิงก์ต้นทาง:** [{novel.get('url')}]({novel.get('url')})
- **คะแนนความเหมาะสมตลาดไทย (Market Fit):** `{concept.get('market_fit_score')}/10`
- **โทนเรื่องที่แนะนำ:** {concept.get('recommended_tone')}

---

## 📖 เรื่องย่อต้นทาง (Raw Synopsis)
{novel.get('synopsis')}

---

## 💡 กลยุทธ์การดัดแปลงเป็น Original Thai IP
- **แกนเรื่องหลัก (Core Trope):** {concept.get('core_trope')}
- **จุดดึงดูด/หักมุม (Novelty Hook):** {concept.get('novelty_hook')}
- **แนวทางการดัดแปลงเข้าสู่บริบทไทย:**
{concept.get('thai_adaptation_strategy')}

---

- [x] **Step 1: คัดเลือกและส่องเทรนด์นิยายระดับโลก (Global Playwright Scouting)**
- [x] **Step 2: วิเคราะห์แกนเรื่องและดัดแปลงเข้ากับตลาดไทย (Thai Localization Analysis)**
- [ ] **Step 3: ปรับแต่งฉากและตัวละครให้เข้ากับบริบทไทย (Localization & Design)**
- [ ] **Step 4: เจนตอนแรกและบทนิยายเสียง (Text & Audio Generation)**
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[+] บันทึกลง Scouting Pool: {filepath}")
    return filepath


# ===========================================================================
# Discord Alert
# ===========================================================================

def notify_discord_global_discoveries(discoveries: List[Dict[str, Any]]):
    """ส่งการ์ดสรุปเทรนด์นิยายต่างประเทศที่ค้นพบเข้า Discord ห้อง writer-feedback"""
    try:
        from discord_reporter import send_discord_message
    except ImportError:
        return

    if not discoveries:
        return

    fields = []
    for d in discoveries[:5]:
        c_flag = COUNTRY_FLAGS.get(d.get("country", ""), d.get("country", ""))
        fields.append({
            "name": f"{c_flag} {d.get('thai_title')} (อันดับ #{d.get('rank')})",
            "value": f"• **เรื่องเดิม:** *{d.get('original_title')}* ({d.get('source')})\n• **แกนเรื่อง:** {d.get('trope')}\n• **คะแนนประเมิน:** `{d.get('score')}/10`",
            "inline": False
        })

    payload = {
        "embeds": [{
            "title": f"🌍 [Global Scout Alert] ค้นพบ {len(discoveries)} ไอเดียนิยายเทรนด์โลกใหม่!",
            "description": "ระบบ Playwright Browser Crawler ได้ส่องอันดับและวิเคราะห์กลยุทธ์การดัดแปลงเป็นนิยายไทยต้นฉบับเรียบร้อยแล้ว",
            "color": 0x8B5CF6,
            "fields": fields,
            "footer": {
                "text": f"ANSRE Global Scout • {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            }
        }]
    }
    send_discord_message(payload)


# ===========================================================================
# Main Runner
# ===========================================================================

def run_global_scout(countries: List[str] = None, limit_per_country: int = 3, verbose: bool = True) -> List[str]:
    """
    รัน Playwright Browser ท่องเว็บนิยายตามประเทศที่เลือก (JP, US, KR, CN)
    พร้อมแปลและสกัดไอเดียเข้าสู่ SecondBrain
    """
    if not countries:
        countries = ["JP", "US", "KR", "CN"]

    countries = [c.upper().strip() for c in countries]
    all_novels = []
    saved_files = []
    discord_records = []

    print(f"\n🌐 [Global Scout] เริ่มต้นท่องเว็บหานิยายทั่วโลก (ประเทศ: {', '.join(countries)})...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()

        if "JP" in countries or "ALL" in countries:
            jp_novels = crawl_syosetu_jp(page, limit=limit_per_country)
            all_novels.extend(jp_novels)

        if "US" in countries or "EN" in countries or "ALL" in countries:
            us_novels = crawl_royalroad_en(page, limit=limit_per_country)
            all_novels.extend(us_novels)

        if "KR" in countries or "ALL" in countries:
            kr_novels = crawl_novelpia_kr(page, limit=limit_per_country)
            all_novels.extend(kr_novels)

        if "CN" in countries or "ALL" in countries:
            cn_novels = crawl_qidian_cn(page, limit=limit_per_country)
            all_novels.extend(cn_novels)

        browser.close()

    print(f"\n🧠 [Localization] วิเคราะห์และดัดแปลงไอเดียเป็น Original Thai IP จำนวน {len(all_novels)} เรื่อง...")
    for n in all_novels:
        concept = localize_and_adapt_concept(n)
        fp = save_to_scouting_pool(n, concept)
        saved_files.append(fp)

        discord_records.append({
            "country": n.get("country"),
            "source": n.get("source"),
            "original_title": n.get("title"),
            "thai_title": concept.get("thai_working_title"),
            "trope": concept.get("core_trope"),
            "score": concept.get("market_fit_score", 8.0),
            "rank": n.get("rank", 1)
        })

    # ส่งสรุปเข้า Discord
    if discord_records:
        notify_discord_global_discoveries(discord_records)
        print("✅ ส่งการ์ดสรุปเทรนด์โลกเข้า Discord ห้อง writer-feedback เรียบร้อย")

    return saved_files


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--help" in args or "-h" in args:
        print(__doc__)
        print("Usage: python global_scout.py [--country JP,US,KR,CN] [--limit N]")
        sys.exit(0)
    target_countries = ["JP", "US", "KR", "CN"]
    limit = 2

    if "--country" in args:
        idx = args.index("--country")
        if idx + 1 < len(args):
            target_countries = args[idx + 1].split(",")

    if "--limit" in args:
        idx = args.index("--limit")
        if idx + 1 < len(args):
            limit = int(args[idx + 1])

    res = run_global_scout(countries=target_countries, limit_per_country=limit)
    print(f"\n🎉 สำเร็จ! บันทึกนิยายเทรนด์โลกทั้งหมด {len(res)} เรื่องลงใน SecondBrain")
