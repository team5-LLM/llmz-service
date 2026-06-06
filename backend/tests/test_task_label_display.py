"""4단계 — 영문 category 한국어 표시 레이어."""

from __future__ import annotations

import unittest

from app.schemas.dashboard import TaskDistributionItem, TaskPriorityItem
from app.services.dashboard_service import _normalize_task_distribution
from app.services.recommender import (
    enrich_recommendation_xai,
    match_automation_candidate,
    normalize_task_label,
)
from app.utils.task_label_display import task_label_display


class TaskLabelDisplayUtilTests(unittest.TestCase):
    def test_normalize_english_category(self):
        self.assertEqual(normalize_task_label("REPORT_WRITING"), "보고서 작성형")

    def test_display_maps_english_category(self):
        self.assertEqual(task_label_display("CODE_GENERATION"), "코드 생성형")

    def test_korean_label_passthrough(self):
        self.assertEqual(task_label_display("보고서 작성형"), "보고서 작성형")


class TaskDistributionDisplayTests(unittest.TestCase):
    def test_normalize_task_distribution_adds_label_display(self):
        items = _normalize_task_distribution(
            [
                {"label": "REPORT_WRITING", "count": 3},
                {"label": "CODE_GENERATION", "count": 1},
            ]
        )

        self.assertEqual(len(items), 2)
        self.assertIsInstance(items[0], TaskDistributionItem)
        report = next(item for item in items if item.label == "REPORT_WRITING")
        self.assertEqual(report.label_display, "보고서 작성형")


class RecommendationDisplayTests(unittest.TestCase):
    def test_enrich_adds_task_label_display_for_english_category(self):
        rec = enrich_recommendation_xai(
            {
                "department": "마케팅팀",
                "task_label": "DOCUMENT_SUMMARY",
                "opportunity_score": 70,
                "risk_score": 20,
                "risk_level": "Low",
                "decision_level": "proceed",
                "reason": [],
            }
        )

        self.assertEqual(rec["task_label"], "DOCUMENT_SUMMARY")
        self.assertEqual(rec["task_label_display"], "문서 요약형")
        self.assertIn("문서 요약형", rec["xai_summary"])

    def test_automation_mapping_english_key(self):
        info = match_automation_candidate("SEARCH_QA")
        self.assertEqual(info["service_name"], "사내 지식검색 챗봇")


class TaskPriorityDisplayTests(unittest.TestCase):
    def test_task_priority_item_schema(self):
        item = TaskPriorityItem(
            task_label="DATA_ANALYSIS",
            task_label_display="데이터 분석형",
            count=5,
            ratio=50.0,
            opportunity_score=60,
            risk_score=25.0,
            risk_level="Low",
        )

        self.assertEqual(item.task_label_display, "데이터 분석형")


if __name__ == "__main__":
    unittest.main()
