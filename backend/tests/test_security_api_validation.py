from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
TEST_CSV_PATH = os.getenv("TEST_CSV_PATH", "")


def api_url(path: str) -> str:
    return f"{API_BASE_URL}{path}"


def assert_ok(response: requests.Response) -> None:
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}\n"
        f"URL: {response.url}\n"
        f"Body: {response.text}"
    )


def has_key(data: Any, key_name: str) -> bool:
    """JSON 전체에서 특정 key가 존재하는지 재귀적으로 확인."""
    if isinstance(data, dict):
        if key_name in data:
            return True
        return any(has_key(value, key_name) for value in data.values())

    if isinstance(data, list):
        return any(has_key(item, key_name) for item in data)

    return False


def collect_values(data: Any, key_name: str) -> list[Any]:
    """JSON 전체에서 특정 key의 값을 모두 수집."""
    values: list[Any] = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key == key_name:
                values.append(value)
            values.extend(collect_values(value, key_name))

    elif isinstance(data, list):
        for item in data:
            values.extend(collect_values(item, key_name))

    return values


def get_items(data: Any) -> list[dict[str, Any]]:
    """
    응답이 list 형태이거나 {"items": [...]} 형태일 때 모두 처리.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        items = data.get("items", [])
        if isinstance(items, list):
            return items

    return []


def get_upload_id_from_upload_response(data: dict[str, Any]) -> str | None:
    """
    /api/upload 응답에서 upload_id 또는 upload_ids를 가져온다.
    """
    if data.get("upload_id"):
        return data["upload_id"]

    upload_ids = data.get("upload_ids")
    if isinstance(upload_ids, list) and upload_ids:
        return upload_ids[0]

    return None


def get_first_upload_id_from_history(data: Any) -> str | None:
    """
    /api/uploads/history 응답에서 첫 번째 upload_id를 가져온다.
    """
    items = get_items(data)
    if not items:
        return None

    first = items[0]
    return first.get("upload_id") or first.get("id")


def get_recommendation_items(data: Any) -> list[dict[str, Any]]:
    """
    /api/recommendations 응답이
    list 형태이거나 {"count": n, "recommendations": [...]} 형태일 때 모두 처리.
    """
    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        items = data.get("recommendations", [])
        if isinstance(items, list):
            return items

    return []


class SecurityApiValidationTests(unittest.TestCase):
    """운영/로컬 API E2E — API_BASE_URL 미응답 시 전체 skip."""

    @classmethod
    def setUpClass(cls) -> None:
        """API·DB·Storage 모두 ready일 때만 E2E 실행 (로컬 부분 기동 시 skip)."""
        try:
            response = requests.get(api_url("/api/health"), timeout=5)
            if response.status_code != 200:
                raise unittest.SkipTest(
                    f"API health check failed: status={response.status_code}"
                )
            data = response.json()
            db = data.get("db", {})
            storage = data.get("storage", {})
            if not db.get("ready"):
                raise unittest.SkipTest(
                    f"DB not ready: {db.get('message', 'unknown')}"
                )
            if not storage.get("ready"):
                raise unittest.SkipTest(
                    f"Storage not ready: {storage.get('message', 'unknown')}"
                )
        except requests.RequestException as exc:
            raise unittest.SkipTest(f"API unreachable at {API_BASE_URL}: {exc}") from exc

    def test_01_health_db_storage_ready(self) -> None:
        """DB / Storage 연결 검증."""
        response = requests.get(api_url("/api/health"), timeout=30)
        assert_ok(response)

        data = response.json()

        self.assertEqual(data.get("status"), "ok")

        db = data.get("db", {})
        storage = data.get("storage", {})

        self.assertTrue(db.get("configured"))
        self.assertTrue(db.get("ready"))
        self.assertEqual(db.get("message"), "connected")

        self.assertTrue(storage.get("configured"))
        self.assertTrue(storage.get("ready"))
        self.assertEqual(storage.get("message"), "connected")

    def test_02_original_prompt_discard_in_analyze_sample(self) -> None:
        """원문 폐기 검증 1: analyze-sample에 prompt_text 없음."""
        response = requests.get(api_url("/api/analyze-sample"), timeout=60)
        assert_ok(response)

        data = response.json()

        self.assertFalse(has_key(data, "prompt_text"))

        masked_prompts = collect_values(data, "masked_prompt")
        self.assertGreater(len(masked_prompts), 0)

        original_prompt_stored_values = collect_values(data, "original_prompt_stored")
        if original_prompt_stored_values:
            self.assertTrue(all(value is False for value in original_prompt_stored_values))

        discard_verified_values = collect_values(data, "original_discard_verified")
        if discard_verified_values:
            self.assertTrue(all(value is True for value in discard_verified_values))

    def test_03_original_prompt_discard_in_recommendations(self) -> None:
        """원문 폐기 검증 2: recommendations에 prompt_text 없음."""
        response = requests.get(api_url("/api/recommendations"), timeout=60)
        assert_ok(response)

        data = response.json()

        self.assertFalse(has_key(data, "prompt_text"))

    def test_04_latest_upload_linkage(self) -> None:
        """최신 업로드 연동 검증 (TEST_CSV_PATH 필요)."""
        if not TEST_CSV_PATH:
            self.skipTest("TEST_CSV_PATH가 .env에 설정되어 있지 않습니다.")

        csv_path = Path(TEST_CSV_PATH)

        if not csv_path.exists():
            self.skipTest(f"테스트 CSV 파일이 없습니다: {csv_path}")

        with csv_path.open("rb") as file:
            upload_response = requests.post(
                api_url("/api/upload"),
                files={"file": (csv_path.name, file, "text/csv")},
                timeout=180,
            )

        assert_ok(upload_response)

        upload_data = upload_response.json()

        self.assertIn(upload_data.get("status"), {"completed", "success", "ok"})

        upload_id = get_upload_id_from_upload_response(upload_data)
        self.assertIsNotNone(upload_id, f"upload_id를 찾을 수 없습니다: {upload_data}")

        history_response = requests.get(api_url("/api/uploads/history"), timeout=60)
        assert_ok(history_response)

        history_data = history_response.json()
        history_upload_id = get_first_upload_id_from_history(history_data)

        self.assertIsNotNone(history_upload_id)

        detail_response = requests.get(api_url(f"/api/uploads/{upload_id}"), timeout=60)
        assert_ok(detail_response)

        detail_data = detail_response.json()

        self.assertFalse(has_key(detail_data, "prompt_text"))

        if has_key(detail_data, "masked_prompt"):
            self.assertGreater(len(collect_values(detail_data, "masked_prompt")), 0)

        recommendations_response = requests.get(api_url("/api/recommendations"), timeout=60)
        assert_ok(recommendations_response)

        recommendation_data = recommendations_response.json()
        recommendations = get_recommendation_items(recommendation_data)

        self.assertGreater(len(recommendations), 0)

        first = recommendations[0]
        self.assertIn("department", first)
        self.assertIn("task_label", first)
        self.assertIn("opportunity_score", first)
        self.assertIn("risk_score", first)
        self.assertIn("decision", first)

    def test_05_recommendation_detail_and_decision(self) -> None:
        """추천 상세 및 Risk 기반 도입 판단 API 검증."""
        response = requests.get(api_url("/api/recommendations"), timeout=60)
        assert_ok(response)

        recommendation_data = response.json()
        recommendations = get_recommendation_items(recommendation_data)

        self.assertGreater(len(recommendations), 0)

        target = recommendations[0]
        department = target["department"]
        task_label = target["task_label"]

        detail_response = requests.get(
            api_url(f"/api/recommendations/{department}/{task_label}"),
            timeout=60,
        )
        assert_ok(detail_response)

        detail = detail_response.json()

        self.assertEqual(detail["department"], department)
        self.assertEqual(detail["task_label"], task_label)
        self.assertIn("reason", detail)
        self.assertIn("decision", detail)

        decision_response = requests.get(
            api_url(f"/api/recommendations/{department}/{task_label}/decision"),
            timeout=60,
        )
        assert_ok(decision_response)

        decision = decision_response.json()

        self.assertTrue("decision" in decision or "decision_level" in decision)

    def test_06_masking_rules_crud(self) -> None:
        """마스킹 규칙 CRUD 검증: GET → POST → PATCH → DELETE."""
        list_response = requests.get(api_url("/api/admin/masking-rules"), timeout=30)

        if list_response.status_code in {401, 403}:
            self.skipTest("마스킹 규칙 API는 인증/권한이 필요합니다.")

        assert_ok(list_response)

        create_payload = {
            "name": "unittest_email_masking_rule",
            "rule_type": "regex",
            "pattern": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+",
            "replacement": "[EMAIL]",
            "enabled": True,
            "description": "unittest에서 생성한 이메일 마스킹 규칙",
        }

        create_response = requests.post(
            api_url("/api/admin/masking-rules"),
            json=create_payload,
            timeout=30,
        )

        self.assertIn(create_response.status_code, {200, 201}, create_response.text)

        created = create_response.json()

        rule_id = created.get("rule_id") or created.get("id")

        self.assertIsNotNone(rule_id, f"rule_id를 찾을 수 없습니다: {created}")

        patch_payload = {
            "enabled": False,
            "description": "unittest에서 수정한 마스킹 규칙",
        }

        patch_response = requests.patch(
            api_url(f"/api/admin/masking-rules/{rule_id}"),
            json=patch_payload,
            timeout=30,
        )

        assert_ok(patch_response)

        patched = patch_response.json()

        if "enabled" in patched:
            self.assertFalse(patched["enabled"])

        delete_response = requests.delete(
            api_url(f"/api/admin/masking-rules/{rule_id}"),
            timeout=30,
        )

        self.assertIn(delete_response.status_code, {200, 204}, delete_response.text)

    def test_07_invalid_masking_rule_validation(self) -> None:
        """잘못된 정규식 입력 시 400 또는 422."""
        invalid_payload = {
            "name": "unittest_invalid_regex_rule",
            "rule_type": "regex",
            "pattern": r"[invalid-regex",
            "replacement": "[MASKED]",
            "enabled": True,
            "description": "잘못된 정규식 테스트",
        }

        response = requests.post(
            api_url("/api/admin/masking-rules"),
            json=invalid_payload,
            timeout=30,
        )

        if response.status_code in {401, 403}:
            self.skipTest("마스킹 규칙 API는 인증/권한이 필요합니다.")

        self.assertIn(
            response.status_code,
            {400, 422},
            (
                f"잘못된 정규식 입력 시 400 또는 422가 나와야 합니다.\n"
                f"status={response.status_code}\n"
                f"body={response.text}"
            ),
        )

    def test_08_embedding_access_policy(self) -> None:
        """FUNC-PROC-011 Embedding 접근 통제 정책 API 검증."""
        response = requests.get(api_url("/api/embedding/access-policy"), timeout=30)
        assert_ok(response)

        data = response.json()

        self.assertEqual(data.get("status"), "policy_defined")
        self.assertEqual(data.get("embedding_storage"), "not_persisted_in_p0_p1")

        allowed_roles = data.get("allowed_roles", [])
        self.assertIsInstance(allowed_roles, list)
        self.assertIn("admin", allowed_roles)
        self.assertIn("ml_engineer", allowed_roles)

        self.assertEqual(data.get("retention_days"), 30)

        restrictions = data.get("restrictions", [])
        self.assertIsInstance(restrictions, list)
        self.assertTrue(any("prompt_text" in item for item in restrictions))
        self.assertTrue(any("masked_prompt" in item for item in restrictions))

        future_extension = data.get("future_extension", [])
        self.assertIsInstance(future_extension, list)
        self.assertGreater(len(future_extension), 0)


if __name__ == "__main__":
    unittest.main()