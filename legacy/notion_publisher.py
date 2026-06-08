import os
import re
import requests
import json

# Setup Notion connection
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("[!] ERROR: NOTION_TOKEN is not set.")
    sys.exit(1)

PARENT_PAGE_ID = "373d71ae-c6a9-805a-b8ac-d6a558d4943a"

headers = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

# Read Markdown file
filepath = "SecondBrain/05_Active_Projects/Chapters/กระจกเงาคนตาย_Chapter_01.md"

if not os.path.exists(filepath):
    print(f"Error: File {filepath} not found.")
    exit(1)

with open(filepath, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Parse Markdown lines into Notion blocks
blocks = []
page_title = "บทที่ 1"

for line in lines:
    line_strip = line.strip()
    if not line_strip:
        continue
    
    # Check for Headings
    if line_strip.startswith("## "):
        title_content = line_strip.replace("## ", "")
        page_title = title_content
        blocks.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": title_content}
                }]
            }
        })
    elif line_strip.startswith("### "):
        blocks.append({
            "object": "block",
            "type": "heading_3",
            "heading_3": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": line_strip.replace("### ", "")}
                }]
            }
        })
    elif line_strip.startswith("* "):
        # Bullet list item
        content = line_strip.replace("* ", "")
        # Clean bold markers **
        content = content.replace("**", "")
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{
                    "type": "text",
                    "text": {"content": content}
                }]
            }
        })
    else:
        # Standard paragraph. Clean bold markers **
        content = line_strip.replace("**", "")
        # Chunk text if it exceeds Notion limit (2000 chars)
        if len(content) > 1800:
            chunks = [content[i:i+1800] for i in range(0, len(content), 1800)]
            for chunk in chunks:
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{
                            "type": "text",
                            "text": {"content": chunk}
                        }]
                    }
                })
        else:
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": [{
                        "type": "text",
                        "text": {"content": content}
                    }]
                }
            })

# Create the Page in Notion
url = "https://api.notion.com/v1/pages"
payload = {
    "parent": {"page_id": PARENT_PAGE_ID},
    "properties": {
        "title": {
            "title": [{
                "text": {"content": page_title}
            }]
        }
    },
    "children": blocks
}

print(f"[*] Publishing '{page_title}' to Notion parent page ID '{PARENT_PAGE_ID}'...")

try:
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 200:
        page_url = response.json().get("url")
        print(f"SUCCESS: Page created successfully!")
        print(f"Notion URL: {page_url}")
    else:
        print(f"FAILED status_code={response.status_code}")
        print(response.text)
except Exception as e:
    print(f"ERROR: {str(e)}")
