"""추천 카드 개선 — head(3) 제거, 영문 매핑, cluster 변환."""

from __future__ import annotations

import unittest

import pandas as pd

from app.services.analysis_pipeline import build_recommendations
from app.services.recommender import (
    cluster_card_to_recommendation,
    enrich_recommendation_xai,
    match_automation_candidate,
    normalize_task_label,
)
from app.services.scoring import adoption_decision


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


class ClusterCardConversionTests(unittest.TestCase):
    def test_cluster_card_to_recommendation(self):
        card = {
            "department": "마케팅팀",
            "sub_cluster_id": "마케팅팀_cluster_7",
            "recommendation_title": "마케팅팀 - 캠페인 성과 리포트 Agent",
            "automation_candidate_type": "FAQ_AGENT",
            "macro_category": "SEARCH_QA",
            "opportunity_score": 80,
            "risk_score": 16.62,
            "decision": "우선 도입 후보",
            "summary": "캠페인 성과 리포트 업무 자동화 추천",
            "expected_effect": ["반복 프롬프트 작성 시간 절감"],
            "security_guardrails": ["원문 프롬프트 미저장"],
            "implementation_difficulty": "Low",
            "priority_reason": "로그 151건 기준 자동화 기회 확인",
            "source_cluster_label": "캠페인 성과 리포트",
            "method": "rule",
        }

        rec = cluster_card_to_recommendation(card)

        self.assertEqual(rec["recommendation_source"], "cluster")
        self.assertEqual(rec["task_label"], "마케팅팀_cluster_7")
        self.assertEqual(rec["cluster_label"], "캠페인 성과 리포트")
        self.assertEqual(rec["decision_level"], "proceed")
        self.assertEqual(rec["service_name"], "마케팅팀 - 캠페인 성과 리포트 Agent")

    def test_cluster_card_uses_adoption_decision_not_stored_korean_text(self):
        card = {
            "department": "마케팅팀",
            "sub_cluster_id": "마케팅팀_cluster_1",
            "recommendation_title": "고위험 클러스터",
            "opportunity_score": 80,
            "risk_score": 75.0,
            "decision": "보안 검토 필요",
            "summary": "고위험",
            "expected_effect": [],
            "security_guardrails": ["원문 미저장"],
            "implementation_difficulty": "High",
            "source_cluster_label": "고위험 업무",
        }

        rec = cluster_card_to_recommendation(card)
        expected = adoption_decision(80, 75.0)

        self.assertEqual(rec["decision_level"], expected["decision_level"])
        self.assertEqual(rec["decision"], expected["decision"])
        self.assertEqual(rec["decision_level"], "review")


class ClusterTaskDecisionParityTests(unittest.TestCase):
    def test_enrich_applies_same_rule_as_task_card(self):
        task_rec = enrich_recommendation_xai(
            {
                "department": "마케팅팀",
                "task_label": "REPORT_WRITING",
                "opportunity_score": 78,
                "risk_score": 86.0,
                "risk_level": "Critical",
                "reason": [],
            }
        )
        cluster_rec = enrich_recommendation_xai(
            cluster_card_to_recommendation(
                {
                    "department": "마케팅팀",
                    "sub_cluster_id": "마케팅팀_cluster_9",
                    "recommendation_title": "테스트",
                    "opportunity_score": 78,
                    "risk_score": 86.0,
                    "decision": "우선 도입 후보",
                    "summary": "테스트",
                    "expected_effect": [],
                    "security_guardrails": [],
                    "implementation_difficulty": "Low",
                    "source_cluster_label": "테스트",
                }
            )
        )

        self.assertEqual(task_rec["decision_level"], "review")
        self.assertEqual(cluster_rec["decision_level"], "review")
        self.assertEqual(task_rec["decision"], cluster_rec["decision"])


if __name__ == "__main__":
    unittest.main()
