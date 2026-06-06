"""추천 카드 개선 — head(3) 제거, 영문 매핑, decision 정규화."""

from __future__ import annotations

import unittest

import pandas as pd

from app.services.analysis_pipeline import build_recommendations
from app.services.recommender import (
    enrich_recommendation_xai,
    match_automation_candidate,
    normalize_task_label,
)


class BuildRecommendationsNoCapTests(unittest.TestCase):
    def test_returns_all_task_types_per_department(self):
        adf = pd.DataFrame(
            [
                {"department": "마케팅팀", "task_label": "보고서 작성형", "cost": 10, "user_hash": "u1", "risk_score": 20},
                {"department": "마케팅팀", "task_label": "문서 요약형", "cost": 8, "user_hash": "u2", "risk_score": 15},
                {"department": "마케팅팀", "task_label": "코드 생성형", "cost": 6, "user_hash": "u3", "risk_score": 10},
                {"department": "마케팅팀", "task_label": "데이터 분석형", "cost": 4, "user_hash": "u4", "risk_score": 12},
                {"department": "마케팅팀", "task_label": "기타", "cost": 2, "user_hash": "u5", "risk_score": 5},
            ]
        )

        result = build_recommendations(adf)
        marketing = [item for item in result if item["department"] == "마케팅팀"]

        self.assertEqual(len(marketing), 4)
        self.assertTrue(all(item["task_label"] != "기타" for item in marketing))


class TaskLabelMappingTests(unittest.TestCase):
    def test_normalize_english_category(self):
        self.assertEqual(normalize_task_label("REPORT_WRITING"), "보고서 작성형")

    def test_match_automation_candidate_english_key(self):
        info = match_automation_candidate("CODE_GENERATION")
        self.assertEqual(info["service_name"], "개발 생산성 Copilot")


class EnrichDecisionTests(unittest.TestCase):
    def test_enrich_applies_adoption_decision(self):
        rec = enrich_recommendation_xai(
            {
                "department": "마케팅팀",
                "task_label": "REPORT_WRITING",
                "opportunity_score": 78,
                "risk_score": 86.0,
                "risk_level": "Critical",
                "reason": [],
            }
        )

        self.assertEqual(rec["decision_level"], "review")


if __name__ == "__main__":
    unittest.main()
