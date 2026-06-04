"""SCR-DASH-003 — repeat_pattern_service·API 테스트"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.services.repeat_pattern_service import (
    PromptLogEntry,
    group_prompt_logs,
    summarize_department_patterns,
)


class RepeatPatternAnalyzerTests(unittest.TestCase):
    def test_heuristic_groups_identical_prompts(self):
        logs = [
            PromptLogEntry("마케팅팀", "보고서 작성형", "주간  보고서  작성"),
            PromptLogEntry("마케팅팀", "보고서 작성형", "주간 보고서 작성"),
            PromptLogEntry("마케팅팀", "코드 생성형", "Python 함수 만들어줘"),
        ]
        groups, method = group_prompt_logs(logs, method="heuristic")
        self.assertEqual(method, "heuristic")
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].count, 2)
        self.assertTrue(groups[0].pattern_key.startswith("h-"))
        self.assertIsNone(groups[0].cluster_id)

    def test_cluster_groups_by_cluster_id(self):
        logs = [
            PromptLogEntry(
                "마케팅팀",
                "보고서 작성형",
                "프롬프트 A",
                cluster_id="cl-001",
                pattern_label="캠페인 보고서",
            ),
            PromptLogEntry(
                "마케팅팀",
                "보고서 작성형",
                "프롬프트 B",
                cluster_id="cl-001",
                pattern_label="캠페인 보고서",
            ),
            PromptLogEntry(
                "마케팅팀",
                "보고서 작성형",
                "다른 업무",
                cluster_id="cl-002",
            ),
        ]
        groups, method = group_prompt_logs(logs, method="cluster")
        self.assertEqual(method, "cluster")
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0].count, 2)
        self.assertEqual(groups[0].label, "캠페인 보고서")
        self.assertEqual(groups[0].cluster_id, "cl-001")
        self.assertTrue(groups[0].pattern_key.startswith("c-"))

    def test_auto_mixed_when_partial_cluster_ids(self):
        logs = [
            PromptLogEntry("마케팅팀", "보고서 작성형", "동일", cluster_id="cl-1"),
            PromptLogEntry("마케팅팀", "보고서 작성형", "동일", cluster_id="cl-1"),
            PromptLogEntry("마케팅팀", "코드 생성형", "유니크 프롬프트"),
        ]
        groups, method = group_prompt_logs(logs, method="auto")
        self.assertEqual(method, "mixed")
        self.assertEqual(len(groups), 2)

    def test_repeat_ratio_summary(self):
        groups, _ = group_prompt_logs(
            [
                PromptLogEntry("마케팅팀", "보고서 작성형", "반복"),
                PromptLogEntry("마케팅팀", "보고서 작성형", "반복"),
                PromptLogEntry("마케팅팀", "보고서 작성형", "반복"),
                PromptLogEntry("마케팅팀", "코드 생성형", "한번"),
            ],
            method="heuristic",
        )
        summary = summarize_department_patterns(
            "마케팅팀",
            groups,
            min_pattern_count=2,
            total_requests=4,
        )
        self.assertEqual(summary["repeat_requests"], 3)
        self.assertEqual(summary["repeat_ratio"], 75.0)
        self.assertTrue(summary["patterns"][0]["is_repeat"])


class RepeatPatternApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_repeat_patterns_list(self):
        resp = self.client.get("/api/dashboard/repeat-patterns?month=2026-05")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("departments", body)
        self.assertIn("analysis_method", body)
        self.assertIn("min_pattern_count", body)

    def test_department_repeat_patterns_not_found(self):
        resp = self.client.get(
            "/api/dashboard/departments/없는부서/repeat-patterns?month=2026-05"
        )
        self.assertEqual(resp.status_code, 404)

    def test_invalid_method_422(self):
        resp = self.client.get(
            "/api/dashboard/repeat-patterns?month=2026-05&method=embedding"
        )
        self.assertEqual(resp.status_code, 422)

    def test_invalid_min_pattern_count_422(self):
        resp = self.client.get(
            "/api/dashboard/repeat-patterns?month=2026-05&min_pattern_count=1"
        )
        self.assertEqual(resp.status_code, 422)

    def test_department_repeat_patterns_shape(self):
        resp = self.client.get(
            "/api/dashboard/departments/마케팅팀/repeat-patterns?month=2026-05"
        )
        if resp.status_code == 404:
            return
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["department"], "마케팅팀")
        self.assertIn("repeat_ratio", body)
        self.assertIn("patterns", body)


if __name__ == "__main__":
    unittest.main()
