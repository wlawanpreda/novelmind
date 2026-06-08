"""ScribbleHub scraper — ดึงนิยายยอดนิยมจาก series-ranking"""
import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Any

BASE = "https://www.scribblehub.com"
RANK_URL = "https://www.scribblehub.com/series-ranking/?sort=5&order=1"  # sort=5 ≈ favorites
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def _num(text: str) -> int:
    n = re.sub(r"[^\d]", "", text or "")
    return int(n) if n else 0


def fetch_scribblehub_novels(limit: int = 20) -> List[Dict[str, Any]]:
    """ดึงนิยายยอดนิยมจากหน้า series-ranking ของ ScribbleHub"""
    r = requests.get(RANK_URL, headers=HEADERS, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.content, "lxml")
    boxes = soup.select("div.search_main_box")
    novels = []
    for box in boxes[:limit]:
        title_el = box.select_one(".search_title a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        url = title_el.get("href", "")
        m = re.search(r"/series/(\d+)/", url)
        sid = m.group(1) if m else url

        synopsis = ""
        body = box.select_one(".search_body")
        if body:
            # ตัด "..." และลิงก์อ่านต่อออก
            synopsis = re.sub(r"\s+", " ", body.get_text(" ", strip=True))[:1500]

        genres = [g.get_text(strip=True) for g in box.select(".fic_genre")]

        # สถิติ (favorites, chapters, ratings, ...)
        favorites = chapters = views = 0
        rating = 0.0
        for st in box.select(".search_stats span, .mb_stat"):
            txt = st.get_text(" ", strip=True).lower()
            if "favorit" in txt:
                favorites = _num(txt)
            elif "chapter" in txt:
                chapters = _num(txt)
            elif "view" in txt:
                views = _num(txt)
        rate_el = box.select_one('[title*="Rating"], .mb_rate')
        if rate_el:
            rm = re.search(r"([\d.]+)", rate_el.get("title", "") or rate_el.get_text())
            if rm:
                try:
                    rating = float(rm.group(1))
                except ValueError:
                    pass

        novels.append({
            "source": "ScribbleHub",
            "id": sid,
            "title": title,
            "author": "Unknown (ScribbleHub)",
            "synopsis": synopsis,
            "genre": genres[0] if genres else "Fantasy",
            "tags": genres,
            "chapters": chapters,
            "length_chars": chapters * 2000,
            "url": url,
            "bookmarks": favorites,
            "rating": rating,
            "views": views,
            "last_updated": "",
        })
    return novels


if __name__ == "__main__":
    print("Testing ScribbleHub scraper...")
    for i, n in enumerate(fetch_scribblehub_novels(limit=3)):
        print(f"\n[{i+1}] {n['title']} (fav {n['bookmarks']}, ch {n['chapters']})")
        print(f"    genre: {', '.join(n['tags'][:4])}")
        print(f"    {n['synopsis'][:100]}...")
