import requests
from typing import List, Dict, Any, Optional

# Syosetu (Narou) Genre Mappings
GENRE_MAP = {
    101: "異世界〔恋愛〕 (Otherworld Romance)",
    102: "現実世界〔恋愛〕 (Real World Romance)",
    201: "ハイファンタジー〔ファンタジー〕 (High Fantasy)",
    202: "ローファンタジー〔ファンタジー〕 (Low Fantasy)",
    301: "純文学〔文芸〕 (Pure Literature)",
    302: "ヒューマンドラマ〔文芸〕 (Human Drama)",
    303: "歴史〔文芸〕 (Historical)",
    304: "推理〔文芸〕 (Mystery/Detective)",
    305: "ホラー〔文芸〕 (Horror)",
    306: "アクション〔文芸〕 (Action)",
    307: "コメディー〔文芸〕 (Comedy)",
    401: "VRゲーム〔SF〕 (VR Game)",
    402: "宇宙〔SF〕 (Space Sci-Fi)",
    403: "空想科学〔SF〕 (Sci-Fi Fantasy)",
    404: "パニック〔SF〕 (Panic/Disaster)",
    9901: "童話〔その他〕 (Fairy Tale)",
    9902: "詩〔その他〕 (Poetry)",
    9903: "エッセイ〔その他〕 (Essay)",
    9904: "リプレイ〔その他〕 (Replay)",
    9999: "その他〔その他〕 (Other)",
    9801: "ノンジャンル〔ノンジャンル〕 (Non-genre)"
}

API_URL = "https://api.syosetu.com/novelapi/api/"

def fetch_syosetu_novels(
    limit: int = 20,
    genre: Optional[str] = None,
    order: str = "weekly_point",
    min_length: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Fetch novels from Syosetu (Narou) using the official API.
    
    :param limit: Number of novels to fetch (1-500)
    :param genre: Genre code or multiple codes separated by hyphen (e.g. "201-202")
    :param order: Sort order (new, favnovelcnt, reviewcnt, daily_point, weekly_point, monthly_point, quarter_point, yearly_point)
    :param min_length: Minimum character count
    :return: List of novel metadata dictionaries
    """
    params = {
        "out": "json",
        "lim": limit,
        "order": order
    }
    
    if genre:
        params["genre"] = genre
    if min_length:
        params["minlen"] = min_length
        
    headers = {
        "User-Agent": "ANSRE-Scouting-Engine/1.0"
    }
    
    try:
        response = requests.get(API_URL, params=params, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # The first element is always {"allcount": ...}
        if not data or len(data) <= 1:
            return []
            
        novels = []
        for item in data[1:]:
            genre_code = item.get("genre")
            genre_name = GENRE_MAP.get(genre_code, f"Unknown ({genre_code})")
            
            # Map standard structure
            novel_info = {
                "source": "Syosetu",
                "id": item.get("ncode"),
                "title": item.get("title"),
                "author": item.get("writer"),
                "synopsis": item.get("story"),
                "genre": genre_name,
                "genre_code": genre_code,
                "tags": item.get("keyword", "").split(),
                "chapters": item.get("general_all_no"),
                "length_chars": item.get("length"),
                "url": f"https://ncode.syosetu.com/{item.get('ncode').lower()}/",
                "bookmarks": item.get("fav_novel_cnt"),
                "reviews": item.get("review_cnt"),
                "global_points": item.get("global_point"),
                "daily_points": item.get("daily_point"),
                "weekly_points": item.get("weekly_points") or item.get("weekly_point"),
                "monthly_points": item.get("monthly_points") or item.get("monthly_point"),
                "last_updated": item.get("novelupdated_at"),
                "first_uploaded": item.get("general_firstup")
            }
            novels.append(novel_info)
            
        return novels
    except Exception as e:
        print(f"Error fetching from Syosetu API: {e}")
        return []

if __name__ == "__main__":
    # Test fetch
    print("Fetching test novels from Syosetu...")
    test_novels = fetch_syosetu_novels(limit=3, order="weekly_point")
    for idx, n in enumerate(test_novels):
        print(f"\n[{idx+1}] {n['title']} by {n['author']}")
        print(f"Genre: {n['genre']}")
        print(f"URL: {n['url']}")
        print(f"Weekly Points: {n['weekly_points']} | Bookmarks: {n['bookmarks']}")
        print(f"Synopsis: {n['synopsis'][:100]}...")
