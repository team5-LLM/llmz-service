"""build_recommendations — 부서별 추천 전체 반환 테스트"""

from __future__ import annotations

import unittest

import pandas as pd

from app.services.analysis_pipeline import build_recommendations


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


if __name__ == "__main__":
    unittest.main()
