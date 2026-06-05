"""build_recommendations · split_analysis_result_by_month 테스트"""

from __future__ import annotations

import unittest

import pandas as pd

from app.services.analysis_pipeline import (
    build_recommendations,
    build_analysis_result_from_logs,
    split_analysis_result_by_month,
)


class BuildRecommendationsTests(unittest.TestCase):
    def test_returns_all_task_types_per_department_not_top_three(self):
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


class SplitAnalysisByMonthTests(unittest.TestCase):
    def test_split_analysis_result_by_month(self):
        logs = [
            {
                "log_id": 1,
                "department": "마케팅팀",
                "user_hash": "u1",
                "model": "gpt-4o-mini",
                "input_tokens": 10.0,
                "output_tokens": 5.0,
                "total_tokens": 15.0,
                "cost": 1.0,
                "created_at": "2026-04-15 10:00:00",
                "masked_prompt": "a",
                "task_label": "보고서 작성형",
                "risk_score": 10,
                "risk_level": "Low",
                "original_prompt_stored": False,
                "original_discard_verified": True,
                "discard_verification_message": "ok",
            },
            {
                "log_id": 2,
                "department": "마케팅팀",
                "user_hash": "u2",
                "model": "gpt-4o-mini",
                "input_tokens": 10.0,
                "output_tokens": 5.0,
                "total_tokens": 15.0,
                "cost": 2.0,
                "created_at": "2026-05-01 09:00:00",
                "masked_prompt": "b",
                "task_label": "문서 요약형",
                "risk_score": 20,
                "risk_level": "Low",
                "original_prompt_stored": False,
                "original_discard_verified": True,
                "discard_verification_message": "ok",
            },
        ]
        result = build_analysis_result_from_logs(logs)
        monthly = split_analysis_result_by_month(result)

        self.assertEqual(list(monthly.keys()), ["2026-04", "2026-05"])
        self.assertEqual(monthly["2026-04"]["summary"]["total_logs"], 1)
        self.assertEqual(monthly["2026-05"]["summary"]["total_logs"], 1)

    def test_split_preserves_cluster_recommendations_per_month(self):
        logs = [
            {
                "log_id": 1,
                "department": "마케팅팀",
                "user_hash": "u1",
                "model": "gpt-4o-mini",
                "input_tokens": 10.0,
                "output_tokens": 5.0,
                "total_tokens": 15.0,
                "cost": 1.0,
                "created_at": "2026-04-15 10:00:00",
                "masked_prompt": "a",
                "task_label": "보고서 작성형",
                "risk_score": 10,
                "risk_level": "Low",
                "sub_cluster_id": "마케팅팀_cluster_1",
                "original_prompt_stored": False,
                "original_discard_verified": True,
                "discard_verification_message": "ok",
            },
            {
                "log_id": 2,
                "department": "마케팅팀",
                "user_hash": "u2",
                "model": "gpt-4o-mini",
                "input_tokens": 10.0,
                "output_tokens": 5.0,
                "total_tokens": 15.0,
                "cost": 2.0,
                "created_at": "2026-05-01 09:00:00",
                "masked_prompt": "b",
                "task_label": "문서 요약형",
                "risk_score": 20,
                "risk_level": "Low",
                "sub_cluster_id": "마케팅팀_cluster_2",
                "original_prompt_stored": False,
                "original_discard_verified": True,
                "discard_verification_message": "ok",
            },
        ]
        cluster_card = {
            "department": "마케팅팀",
            "sub_cluster_id": "마케팅팀_cluster_1",
            "recommendation_title": "보고서 자동화",
            "automation_candidate_type": "REPORT_BOT",
            "macro_category": "REPORT_WRITING",
            "opportunity_score": 80,
            "risk_score": 10.0,
            "decision": "도입 권장",
            "summary": "반복 보고서 업무",
            "expected_effect": ["시간 절감"],
            "security_guardrails": ["마스킹 유지"],
            "implementation_difficulty": "Low",
            "priority_reason": "빈도 높음",
            "source_cluster_label": "보고서 클러스터",
            "method": "rule",
        }
        cluster_profile = {
            "department": "마케팅팀",
            "sub_cluster_id": "마케팅팀_cluster_2",
            "cluster_label": "문서 요약 클러스터",
            "log_count": 1,
        }
        full_result = {
            **build_analysis_result_from_logs(logs),
            "masked_logs": logs,
            "cluster_recommendations": [
                cluster_card,
                {**cluster_card, "sub_cluster_id": "마케팅팀_cluster_2", "recommendation_title": "요약 자동화"},
            ],
            "cluster_profiles": [cluster_profile],
        }

        monthly = split_analysis_result_by_month(full_result)

        self.assertEqual(len(monthly["2026-04"]["cluster_recommendations"]), 1)
        self.assertEqual(
            monthly["2026-04"]["cluster_recommendations"][0]["sub_cluster_id"],
            "마케팅팀_cluster_1",
        )
        self.assertEqual(len(monthly["2026-05"]["cluster_recommendations"]), 1)
        self.assertEqual(
            monthly["2026-05"]["cluster_recommendations"][0]["sub_cluster_id"],
            "마케팅팀_cluster_2",
        )
        self.assertEqual(len(monthly["2026-04"]["cluster_profiles"]), 0)
        self.assertEqual(len(monthly["2026-05"]["cluster_profiles"]), 1)
        self.assertEqual(monthly["2026-04"]["summary"]["recommendation_count"], 1)
        self.assertEqual(monthly["2026-05"]["summary"]["recommendation_count"], 1)


if __name__ == "__main__":
    unittest.main()
