import requests
from bs4 import BeautifulSoup
import re
from typing import List, Dict, Any, Optional

BASE_URL = "https://www.royalroad.com"
LIST_URL = "https://www.royalroad.com/fictions/active-popular"

def parse_stat_value(text: str) -> int:
    """Helper to convert stats like '24,009 Followers' or '14,947,211 Views' to integer."""
    clean_text = re.sub(r'[^\d]', '', text)
    return int(clean_text) if clean_text else 0

def fetch_royalroad_novels(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Fetch and parse the active popular fictions list from Royal Road.
    
    :param limit: Maximum number of fictions to return
    :return: List of fiction metadata dictionaries
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(LIST_URL, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'lxml')
        items = soup.find_all('div', class_='fiction-list-item')
        
        novels = []
        for item in items[:limit]:
            # Extract title and link
            title_el = item.find('h2', class_='fiction-title')
            if not title_el:
                continue
                
            link_el = title_el.find('a')
            title = link_el.text.strip() if link_el else ""
            relative_url = link_el.get('href') if link_el else ""
            full_url = BASE_URL + relative_url if relative_url else ""
            
            # Extract ID from relative url: /fiction/107917/sky-pride -> 107917
            fiction_id = ""
            match = re.search(r'/fiction/(\d+)/', relative_url)
            if match:
                fiction_id = match.group(1)
                
            # Extract cover image
            img_el = item.find('img')
            cover_url = img_el.get('src') if img_el else ""
            if cover_url and cover_url.startswith('/'):
                cover_url = BASE_URL + cover_url
                
            # Extract tags
            tags = []
            tag_els = item.find_all('a', class_='fiction-tag')
            for tag in tag_els:
                tags.append(tag.text.strip())
                
            # Extract stats (Followers, Rating, Pages, Views, Chapters, Last Updated)
            followers = 0
            rating = 0.0
            pages = 0
            views = 0
            chapters = 0
            last_updated = ""
            
            stats_div = item.find('div', class_='stats')
            if stats_div:
                # Followers
                fol_div = stats_div.find('i', class_='fa-users')
                if fol_div and fol_div.find_next('span'):
                    followers = parse_stat_value(fol_div.find_next('span').text)
                    
                # Rating
                rate_div = stats_div.find('div', attrs={'aria-label': True})
                if rate_div:
                    aria_label = rate_div.get('aria-label', '')
                    # e.g., "Rating: 4.81 out of 5"
                    rate_match = re.search(r'Rating:\s*([\d\.]+)', aria_label)
                    if rate_match:
                        rating = float(rate_match.group(1))
                        
                # Pages
                page_div = stats_div.find('i', class_='fa-book')
                if page_div and page_div.find_next('span'):
                    pages = parse_stat_value(page_div.find_next('span').text)
                    
                # Views
                view_div = stats_div.find('i', class_='fa-eye')
                if view_div and view_div.find_next('span'):
                    views = parse_stat_value(view_div.find_next('span').text)
                    
                # Chapters
                chap_div = stats_div.find('i', class_='fa-list')
                if chap_div and chap_div.find_next('span'):
                    chapters = parse_stat_value(chap_div.find_next('span').text)
                    
                # Last Updated
                time_el = stats_div.find('time')
                if time_el:
                    last_updated = time_el.get('datetime', '')
                    
            # Extract description/synopsis
            desc_div = item.find('div', id=lambda x: x and x.startswith('description-'))
            synopsis = ""
            if desc_div:
                paragraphs = desc_div.find_all('p')
                synopsis = "\n\n".join([p.text.strip() for p in paragraphs if p.text.strip()])
                
            novel_info = {
                "source": "Royal Road",
                "id": fiction_id,
                "title": title,
                "author": "Unknown (Royal Road)",
                "synopsis": synopsis,
                "genre": tags[0] if tags else "Fantasy",
                "tags": tags,
                "chapters": chapters,
                "length_chars": pages * 250,  # rough approximation for pages to chars
                "url": full_url,
                "cover_url": cover_url,
                "bookmarks": followers, # Use followers as bookmarks metric
                "rating": rating,
                "views": views,
                "last_updated": last_updated
            }
            novels.append(novel_info)
            
        return novels
    except Exception as e:
        print(f"Error scraping Royal Road: {e}")
        return []

if __name__ == "__main__":
    print("Scraping active popular novels from Royal Road...")
    test_novels = fetch_royalroad_novels(limit=3)
    for idx, n in enumerate(test_novels):
        print(f"\n[{idx+1}] {n['title']} (Rating: {n['rating']})")
        print(f"Tags: {', '.join(n['tags'])}")
        print(f"URL: {n['url']}")
        print(f"Chapters: {n['chapters']} | Followers: {n['bookmarks']}")
        print(f"Synopsis: {n['synopsis'][:100]}...")
