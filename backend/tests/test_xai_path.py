"""P3 — XAI 경로 정책: BE recommender.enrich_recommendation_xai가 단일 진입점."""

from __future__ import annotations

import unittest

from app.services.recommender import enrich_recommendation_xai


class XaiPathPolicyTests(unittest.TestCase):
    def test_enrich_populates_api_xai_fields(self):
        rec = enrich_recommendation_xai(
            {
                "department": "마케팅팀",
                "task_label": "REPORT_WRITING",
                "opportunity_score": 85,
                "risk_score": 15,
                "risk_level": "Low",
                "reason": [
                    {
                        "factor": "업무 비중",
                        "value": 40,
                        "unit": "%",
                        "description": "부서 로그 중 해당 업무 비중",
                    },
                ],
            }
        )

        self.assertEqual(rec["decision_level"], "proceed")
        self.assertIsInstance(rec["xai_summary"], str)
        self.assertTrue(rec["xai_summary"])
        self.assertIsInstance(rec["key_evidence"], list)
        self.assertGreater(len(rec["key_evidence"]), 0)
        self.assertIsInstance(rec["decision_reason"], str)
        self.assertTrue(rec["decision_reason"])
        self.assertIn("보고서 작성형", rec["xai_summary"])


if __name__ == "__main__":
    unittest.main()
