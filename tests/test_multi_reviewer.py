"""
test_multi_reviewer.py — Unit & Integration tests for Multi-Agent Review System
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import json

from multi_reviewer import (
    review_plot_and_hook,
    review_emotional_and_character,
    review_prose_and_dialogue,
    review_voice_and_cinematic,
    refine_chapter_prose,
    run_multi_agent_review_loop,
    _parse_json_safe,
    strip_meta
)
from discord_reporter import (
    send_review_summary_to_discord,
    send_media_and_publish_report
)

class TestMultiReviewer(unittest.TestCase):

    def test_parse_json_safe(self):
        default = {"score": 5.0}
        self.assertEqual(_parse_json_safe('{"score": 8.5}', default)["score"], 8.5)
        self.assertEqual(_parse_json_safe('```json\n{"score": 9.0}\n```', default)["score"], 9.0)
        self.assertEqual(_parse_json_safe('invalid json text', default)["score"], 5.0)

    def test_strip_meta(self):
        text = "ในฐานะ Chief Editor ข้าพเจ้าขอเสนอ\nเนื้อหานิยายตอนแรก\nเรียบร้อยแล้วครับ"
        cleaned = strip_meta(text)
        self.assertEqual(cleaned, "เนื้อหานิยายตอนแรก")

    @patch("multi_reviewer.generate")
    def test_personas_mocked(self, mock_gen):
        mock_gen.return_value = json.dumps({
            "score": 9.0,
            "hook_strength": "ทรงพลัง",
            "pacing_evaluation": "ดีเยี่ยม",
            "plot_holes": [],
            "cliffhanger_rating": "น่าติดตาม",
            "critical_fixes": []
        })
        res = review_plot_and_hook("ทดสอบ", "เนื้อหา")
        self.assertEqual(res["score"], 9.0)

        mock_gen.return_value = json.dumps({
            "score": 8.8,
            "character_voice": "ชัดเจน",
            "emotional_resonance": "ซึ้ง",
            "flat_moments": [],
            "reader_empathy": "สูง",
            "critical_fixes": []
        })
        res2 = review_emotional_and_character("ทดสอบ", "เนื้อหา")
        self.assertEqual(res2["score"], 8.8)

        mock_gen.return_value = json.dumps({
            "score": 8.7,
            "flow_and_rhythm": "ลื่นไหล",
            "dialogue_naturalness": "ดี",
            "awkward_phrases": [],
            "meta_talk_detected": False,
            "critical_fixes": []
        })
        res3 = review_prose_and_dialogue("ทดสอบ", "เนื้อหา")
        self.assertEqual(res3["score"], 8.7)

        mock_gen.return_value = json.dumps({
            "score": 9.2,
            "ear_friendly_score": "ฟังง่าย",
            "stumbling_blocks": [],
            "cinematic_visuals": ["ฉากเมืองหลวง"],
            "teaser_hook_quote": "คำคมเด็ด",
            "critical_fixes": []
        })
        res4 = review_voice_and_cinematic("ทดสอบ", "เนื้อหา")
        self.assertEqual(res4["score"], 9.2)

    @patch("multi_reviewer.generate")
    def test_multi_round_loop(self, mock_gen):
        # จำลองรอบที่ 1: คะแนน 7.5, รอบที่ 2: คะแนน 8.0, รอบที่ 3: คะแนน 9.0
        call_count = [0]
        def fake_generate(prompt, role="writer", is_json=False):
            if is_json:
                call_count[0] += 1
                score = 7.5 if call_count[0] <= 4 else (8.0 if call_count[0] <= 8 else 9.0)
                return json.dumps({
                    "score": score,
                    "hook_strength": "ดี",
                    "character_voice": "ดี",
                    "flow_and_rhythm": "ดี",
                    "ear_friendly_score": "ดี",
                    "critical_fixes": ["แก้จุดเล็กน้อย"],
                    "teaser_hook_quote": "Hook"
                })
            else:
                return "เนื้อหาบทที่ได้รับการปรับปรุงแล้วมากกว่า 350 ตัวอักษร " * 5

        mock_gen.side_effect = fake_generate
        final_text, report = run_multi_agent_review_loop(
            title="ทดสอบ",
            chapter_text="เนื้อหาเริ่มต้น",
            min_rounds=3,
            max_rounds=5,
            target_score=8.5,
            verbose=False
        )
        self.assertEqual(report["total_rounds"], 3)
        self.assertGreaterEqual(report["final_score"], 8.5)
        self.assertTrue(report["passed_quality_gate"])
        self.assertIn("เนื้อหาบทที่ได้รับการปรับปรุง", final_text)


class TestDiscordReporter(unittest.TestCase):

    @patch("discord_reporter.send_discord_message")
    def test_discord_reporting(self, mock_send):
        mock_send.return_value = True
        sample_card = {
            "total_rounds": 3,
            "initial_score": 7.5,
            "final_score": 9.0,
            "score_improvement": 1.5,
            "passed_quality_gate": True,
            "final_scores_breakdown": {"plot": 9.0, "character": 9.0, "prose": 9.0, "voice": 9.0},
            "teaser_hook_quote": "คำคม"
        }
        ok1 = send_review_summary_to_discord("ทดสอบ", 1, sample_card)
        self.assertTrue(ok1)

        ok2 = send_media_and_publish_report("ทดสอบ", 1, youtube_url="https://youtu.be/test1234")
        self.assertTrue(ok2)


if __name__ == "__main__":
    unittest.main()
