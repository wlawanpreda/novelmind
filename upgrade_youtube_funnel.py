import os
import re
import json
import youtube_stats

ROOT = os.path.dirname(os.path.abspath(__file__))
SB = os.path.join(ROOT, "SecondBrain")

aid_map = {
    "ทะลุมิติไปเป็นคุณแม่ลูกแฝดยุค 70": "627d9707279484797acafaba010fcf69",
    "จากน้องสาวสู่พี่ใหญ่": "c9ba3d70c41e7b9e05e4d1110ec5b94e",
    "ผู้สาปแช่ง Chimera": "454f3980e21e630dc4891fa752796d58",
    "ฟาร์มสาวปีศาจรัก": "ac04dda030fae1380e3aa7ac52f66762",
    "ดวงจันทร์แห่งเวทมนตร์": "9e8c07991925a7993519a4d261fd6f2a",
    "วีรบุรุษสุดขี้เกียจแห่งโลกเวทย์มนต์": "f5d5ec2e430ab0bbade7b02be1beb149",
    "ยอดนักสืบสปีดรัน": "084947f5c23530e03094cc84bb1364b5",
    "สมาคมประกันภัยลี้ลับ": "f3624f7b4e09cde8fc524dff4f2fc4bd",
    "สาวอภินิหารหัวใจเหล็ก": "2ac4e08e36403cb46241714ff5758789",
    "กระจกเงาคนตาย": "e90bfef727e4730819e92444783d6850",
    "ร้านค้าเหนือโลก": "e90bfef727e4730819e92444783d6850",
    "รหัสลับใต้เงา": "86845b51bf2e8fd051a5518e76c95775",
    "ตื่นตามฝันนางพยากรณ์": "02efa2dd3eea0d584e8b815d78085966",
    "ตื่นขึ้นมาด้วยรอยยิ้ม": "1aeb1737a60e167ad499e1dd83c76057",
    "อุปสมบทในรักระหว่างพี่น้อง": "91ebfbe677e836f35774fb8c8c58c292",
    "กลิ่นหอมกู้วิกฤต": "a0d11c41bcfc9018a57e8cf9a0464bc9",
    "กอธาม": "34ee3ede15f2f9a77f7b84539bbd565a",
    "ดาบไร้พระเจ้า": "8bca736060616f7602daefdb056ebf63",
    "ปรมาจารย์สมาคมคนเดียว": "4271d4275c28b408dbed57de5e3cba51",
    "นักรบแสงผู้ล่วงลับ": "2dfa21a992dd4057bcff949041f9a0c6",
    "สถานีตำรวจกาววิญญาณ": "7bedcdb352b8fbec508ebc1f99b2601e",
    "เมื่อนางร้ายหมดรัก": "33e483f95428f693527c5d4843c7fef4",
    "รักกับเจ้าหญิงเพลย์บอย": "5738758aa9e2c5f89bcf6552d3a79187",
    "ย้ายมาอยู่บ้านปีศาจ": "2a364c2b01a394845dc7825556a8f0dd",
}

def find_aid_for_title(title: str) -> str:
    clean_t = re.sub(r"[\s_:：]+", "", title)
    for k, aid in aid_map.items():
        clean_k = re.sub(r"[\s_:：]+", "", k)
        if clean_k in clean_t:
            return aid
    return ""

def clean_text_no_underscore(text: str) -> str:
    # Replace underscore with space or colon depending on context
    t = text.replace("_", " ")
    t = re.sub(r"\s+", " ", t)
    return t.strip()

def run_audit(dry_run=True):
    yt = youtube_stats._yt()
    rows = youtube_stats.collect()
    stats = youtube_stats.fetch_stats(rows)
    stats.sort(key=lambda x: x['views'], reverse=True)

    print(f"Total videos to inspect: {len(stats)}")
    updated_count = 0

    for s in stats:
        vid = s['vid']
        try:
            resp = yt.videos().list(part='snippet', id=vid).execute()
            if not resp.get('items'):
                continue
            snippet = resp['items'][0]['snippet']
            curr_title = snippet['title']
            curr_desc = snippet['description']
            cat_id = snippet.get('categoryId', '24')
            tags = snippet.get('tags', [])

            aid = find_aid_for_title(curr_title)
            raw_url = f"https://www.readawrite.com/a/{aid}" if aid else ""

            # Check if needs modification:
            # 1. Has underscore `_`
            # 2. Missing top-line ReadAWrite CTA
            # 3. Truncated quotes in Shorts
            needs_update = False
            new_title = clean_text_no_underscore(curr_title)
            new_desc = clean_text_no_underscore(curr_desc)

            # Fix truncated quote at end of title
            if new_title.endswith(('"', "'", " “")):
                new_title = new_title.rstrip('"\' ')
            # If title has dangling quote before #Shorts
            new_title = re.sub(r'\|\s*["“][^#\n]{0,35}\s*#Shorts', '#Shorts', new_title).strip()

            # Upgrade Longform title
            if "รวม" in new_title and "ฟัง" not in new_title:
                candidate_title = f"{new_title} | ฟังยาวต่อเนื่องก่อนนอน [อ่านฟรี]"
                if len(candidate_title) <= 100:
                    new_title = candidate_title

            if new_title != curr_title:
                needs_update = True

            # Ensure ReadAWrite top-line link in description
            top_cta = f"👉 อ่านฟรีครบทุกตอนก่อนใครคลิก: {raw_url}\n❤️ ฝากกดหัวใจ + เพิ่มเข้าชั้นหนังสือใน ReadAWrite ด้วยนะครับ!\n\n" if raw_url else ""
            if raw_url and raw_url not in new_desc[:250]:
                new_desc = top_cta + new_desc
                needs_update = True

            # Also check if underscore was in desc
            if "_" in curr_desc:
                needs_update = True

            clean_tags = [clean_text_no_underscore(t) for t in tags if t]

            if needs_update:
                updated_count += 1
                print(f"\n[#{updated_count}] VID: {vid} (Views: {s['views']})")
                print(f"  OLD Title: {curr_title}")
                print(f"  NEW Title: {new_title}")
                print(f"  RAW URL: {raw_url or 'None'}")
                print(f"  Desc Top 120 chars: {new_desc[:120]}...")

                if not dry_run:
                    body = {
                        "id": vid,
                        "snippet": {
                            "title": new_title,
                            "description": new_desc,
                            "categoryId": cat_id,
                            "tags": clean_tags
                        }
                    }
                    yt.videos().update(part="snippet", body=body).execute()
                    print("  ✅ Updated on YouTube live!")
                    import time
                    time.sleep(0.5)
        except Exception as e:
            print(f"  ❌ Error on {vid}: {e}")

    print(f"\nAudit complete! {updated_count} videos identified for optimization.")

if __name__ == "__main__":
    import sys
    dry = "--apply" not in sys.argv
    print(f"Running mode: {'DRY RUN' if dry else 'LIVE APPLY'}")
    run_audit(dry_run=dry)
