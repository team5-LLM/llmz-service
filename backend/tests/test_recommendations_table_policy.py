"""recommendations 테이블 — deprecated snapshot 정책 (P2-A)."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from app.models.analysis_result_tables import DepartmentStatRow, RecommendationRow
from app.services.persistence_service import persist_analysis_result


class RecommendationsTablePolicyTests(unittest.TestCase):
    @patch("app.services.persistence_service.safe_session")
    def test_persist_skips_recommendation_row_insert(self, mock_safe_session):
        mock_session = MagicMock()
        mock_safe_session.return_value = mock_session

        result = {
            "department_stats": [
                {
                    "department": "마케팅팀",
                    "total_requests": 1,
                    "total_tokens": 10,
                    "total_cost": 1.0,
                    "user_count": 1,
                    "avg_risk_score": 10.0,
                    "risk_level": "Low",
                    "high_critical_ratio": 0.0,
                    "task_distribution": [],
                }
            ],
            "cluster_recommendations": [],
            "recommendations": [
                {
                    "department": "마케팅팀",
                    "task_label": "보고서 작성형",
                    "service_name": "테스트",
                    "expected_effect": "효과",
                    "difficulty": "하",
                    "required_resources": [],
                    "opportunity_score": 80,
                    "risk_score": 10.0,
                    "risk_level": "Low",
                    "decision": "도입 권장",
                    "decision_level": "proceed",
                    "decision_message": "ok",
                    "required_action": "none",
                    "reason": [],
                }
            ],
            "masked_logs": [],
        }

        self.assertTrue(persist_analysis_result("upload-test", result))

        added_types = {type(call.args[0]).__name__ for call in mock_session.add.call_args_list}
        self.assertIn("DepartmentStatRow", added_types)
        self.assertNotIn("RecommendationRow", added_types)

    @patch("app.services.persistence_service.safe_session")
    def test_persist_still_deletes_legacy_recommendation_rows(self, mock_safe_session):
        mock_session = MagicMock()
        mock_safe_session.return_value = mock_session

        persist_analysis_result("upload-test", {"masked_logs": []})

        queried_models = [call.args[0] for call in mock_session.query.call_args_list]
        self.assertIn(RecommendationRow, queried_models)


if __name__ == "__main__":
    unittest.main()
