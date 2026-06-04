"""adoption_decision 3단계 판정 테스트"""

from __future__ import annotations

import unittest

from app.services.scoring import adoption_decision


class AdoptionDecisionTests(unittest.TestCase):
    def test_proceed_high_opportunity_low_risk(self):
        result = adoption_decision(78, 24.0)
        self.assertEqual(result["decision_level"], "proceed")
        self.assertEqual(result["decision"], "도입 권장")

    def test_review_high_opportunity_medium_risk(self):
        result = adoption_decision(78, 32.0)
        self.assertEqual(result["decision_level"], "review")
        self.assertEqual(result["decision"], "검토 후 추진")
        self.assertIn("기본 보안 조치", result["message"])

    def test_review_high_opportunity_high_risk(self):
        result = adoption_decision(78, 86.0)
        self.assertEqual(result["decision_level"], "review")
        self.assertIn("보안 검토", result["message"])

    def test_review_mid_opportunity(self):
        result = adoption_decision(60, 20.0)
        self.assertEqual(result["decision_level"], "review")
        self.assertIn("우선순위", result["message"])

    def test_low_priority(self):
        result = adoption_decision(40, 10.0)
        self.assertEqual(result["decision_level"], "low_priority")
        self.assertEqual(result["decision"], "우선순위 낮음")


if __name__ == "__main__":
    unittest.main()
