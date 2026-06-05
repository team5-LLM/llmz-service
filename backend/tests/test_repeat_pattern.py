"""SCR-DASH-003 — repeat_pattern_service·API 테스트"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.dashboard import DepartmentStatItem, TaskDistributionItem
from app.services.persistence_service import (
    _build_cluster_label_lookup,
    _cluster_fields_for_log,
)
from app.services.repeat_pattern_service import (
    PromptLogEntry,
    _row_to_entry,
    get_repeat_patterns,
    group_prompt_logs,
    summarize_department_patterns,
)
from app.utils.date_range import DateRange


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


class RepeatPatternPersistedRowTests(unittest.TestCase):
    def _prompt_log_row(self, **overrides):
        base = {
            "department": "마케팅팀",
            "task_label": "보고서 작성형",
            "masked_prompt": "주간 보고서 작성",
            "cluster_id": "마케팅팀_cluster_1",
            "pattern_label": "캠페인 성과 리포트",
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_row_to_entry_reads_cluster_id_from_persisted_row(self):
        row = self._prompt_log_row()
        entry = _row_to_entry(row)  # type: ignore[arg-type]

        self.assertEqual(entry.cluster_id, "마케팅팀_cluster_1")
        self.assertEqual(entry.pattern_label, "캠페인 성과 리포트")

    def test_group_from_db_rows_uses_cluster_mode(self):
        rows = [
            self._prompt_log_row(masked_prompt="프롬프트 A"),
            self._prompt_log_row(masked_prompt="프롬프트 B"),
        ]
        entries = [_row_to_entry(row) for row in rows]  # type: ignore[arg-type]
        groups, method = group_prompt_logs(entries, method="cluster")

        self.assertEqual(method, "cluster")
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0].count, 2)
        self.assertEqual(groups[0].cluster_id, "마케팅팀_cluster_1")
        self.assertEqual(groups[0].label, "캠페인 성과 리포트")
        self.assertTrue(groups[0].pattern_key.startswith("c-"))

    def test_cluster_fields_for_log_maps_sub_cluster_id_and_profile_label(self):
        lookup = _build_cluster_label_lookup(
            {
                "cluster_profiles": [
                    {
                        "department": "마케팅팀",
                        "sub_cluster_id": "마케팅팀_cluster_7",
                        "cluster_label": "캠페인 성과 리포트",
                    }
                ]
            }
        )
        cluster_id, pattern_label = _cluster_fields_for_log(
            {
                "department": "마케팅팀",
                "sub_cluster_id": "마케팅팀_cluster_7",
            },
            label_lookup=lookup,
        )

        self.assertEqual(cluster_id, "마케팅팀_cluster_7")
        self.assertEqual(pattern_label, "캠페인 성과 리포트")

    @patch("app.services.repeat_pattern_service.dashboard_svc.fetch_prompt_log_rows_in_range")
    @patch("app.services.repeat_pattern_service.dashboard_svc.get_dashboard_departments")
    def test_get_repeat_patterns_cluster_method_from_db_rows(
        self,
        mock_departments,
        mock_fetch_logs,
    ):
        mock_departments.return_value = [
            DepartmentStatItem(
                department="마케팅팀",
                total_requests=2,
                total_tokens=100,
                total_cost=10.0,
                user_count=2,
                avg_risk_score=12.0,
                risk_level="Low",
                high_critical_ratio=0.0,
                task_distribution=[
                    TaskDistributionItem(
                        label="보고서 작성형",
                        label_display="보고서 작성형",
                        count=2,
                        ratio=1.0,
                    )
                ],
            )
        ]
        mock_fetch_logs.return_value = [
            self._prompt_log_row(masked_prompt="A"),
            self._prompt_log_row(masked_prompt="B"),
        ]

        result = get_repeat_patterns(
            DateRange(from_date="2026-05-01", to_date="2026-05-31"),
            method="cluster",
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result["analysis_method"], "cluster")
        marketing = next(
            item for item in result["departments"] if item["department"] == "마케팅팀"
        )
        self.assertTrue(marketing["patterns"])
        self.assertEqual(marketing["patterns"][0]["cluster_id"], "마케팅팀_cluster_1")
        self.assertEqual(marketing["patterns"][0]["label"], "캠페인 성과 리포트")


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
