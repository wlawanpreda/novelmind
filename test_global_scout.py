"""
test_global_scout.py — Unit & Integration tests for Global Playwright Scout
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import json
import shutil
import tempfile

from global_scout import (
    sanitize_filename,
    localize_and_adapt_concept,
    save_to_scouting_pool,
    notify_discord_global_discoveries
)

class TestGlobalScout(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.pool_dir = os.path.join(self.test_dir, "01_Scouting_Pool")
        os.makedirs(self.pool_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("The Solo Hunter: ตอนที่ 1!"), "The_Solo_Hunter_ตอนที่_1")
        self.assertEqual(sanitize_filename("ยอดนักสืบวิญญาณ"), "ยอดนักสืบวิญญาณ")

    @patch("llm_provider.generate")
    def test_localize_and_adapt_concept(self, mock_gen):
        mock_gen.return_value = json.dumps({
            "thai_working_title": "สมาคมกำจัดวิญญาณคนเดียว",
            "core_trope": "ระบบสมาคมและเกตมอนสเตอร์",
            "novelty_hook": "อัญเชิญวีรชนโบราณมาเป็นลูกทีม",
            "thai_adaptation_strategy": "ปรับฉากเป็นคอนโดร้างและไซต์ก่อสร้างในกรุงเทพฯ",
            "market_fit_score": 9.0,
            "recommended_tone": "ระทึกขวัญเอาชีวิตรอด"
        })
        novel_sample = {
            "country": "KR",
            "source": "Novelpia",
            "title": "탑을 오르는 1인 길드",
            "genre": "Hunter / Tower",
            "synopsis": "เรื่องย่อเกาหลี"
        }
        concept = localize_and_adapt_concept(novel_sample)
        self.assertEqual(concept["thai_working_title"], "สมาคมกำจัดวิญญาณคนเดียว")
        self.assertEqual(concept["market_fit_score"], 9.0)

    @patch("global_scout.SCOUTING_POOL")
    def test_save_to_scouting_pool(self, mock_pool):
        mock_pool.__str__ = lambda x: self.pool_dir
        novel = {
            "id": "12345",
            "source": "RoyalRoad",
            "country": "US",
            "title": "Dungeon Crawler Carl",
            "genre": "LitRPG",
            "rank": 1,
            "url": "https://www.royalroad.com/fiction/12345",
            "synopsis": "A man and his cat enter a global dungeon crawl.",
            "tags": ["LitRPG", "Dungeon"]
        }
        concept = {
            "thai_working_title": "ดันเจี้ยนวันสิ้นโลกกับแมวพูดได้",
            "core_trope": "วันสิ้นโลกและดันเจี้ยนเซอร์ไววัล",
            "novelty_hook": "คู่หูแมวขาวปากแซ่บ",
            "thai_adaptation_strategy": "เปลี่ยนเป็นตึกร้างใจกลางสยาม",
            "market_fit_score": 9.2,
            "recommended_tone": "ตลกหน้าตายผสมระทึกขวัญ"
        }
        with patch("global_scout.SCOUTING_POOL", self.pool_dir):
            fp = save_to_scouting_pool(novel, concept)
            self.assertTrue(os.path.exists(fp))
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('thai_working_title: "ดันเจี้ยนวันสิ้นโลกกับแมวพูดได้"', content)
            self.assertIn('country: "US"', content)
            self.assertIn('status: "Analyzed"', content)

    @patch("discord_reporter.send_discord_message")
    def test_notify_discord_global_discoveries(self, mock_discord):
        mock_discord.return_value = True
        discoveries = [{
            "country": "JP",
            "source": "Syosetu",
            "original_title": "Isekai Gourmet",
            "thai_title": "เปิดร้านส้มตำในต่างโลก",
            "trope": "ทำอาหารข้ามมิติ",
            "score": 8.8,
            "rank": 1
        }]
        notify_discord_global_discoveries(discoveries)
        self.assertTrue(mock_discord.called)

if __name__ == "__main__":
    unittest.main()
