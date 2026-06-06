"""AI/ML detected_sensitive_types → Risk DB 플래그 어댑터 테스트."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from app.services import risk_service as risk_svc
from app.utils.sensitive_flags import sensitive_types_to_flags


class SensitiveTypesToFlagsTests(unittest.TestCase):
    def test_maps_pii_and_customer(self):
        flags = sensitive_types_to_flags(["EMAIL", "CUSTOMER_INFO"])
        self.assertTrue(flags["pii_detected"])
        self.assertTrue(flags["customer_detected"])
        self.assertFalse(flags["secret_detected"])
        self.assertTrue(flags["exposure_detected"])

    def test_maps_confidential_financial_legal_secret_hr(self):
        flags = sensitive_types_to_flags(
            [
                "INTERNAL_CONFIDENTIAL",
                "FINANCIAL_KEYWORD",
                "LEGAL_REVIEW",
                "OPENAI_API_KEY",
                "HR_SENSITIVE",
            ]
        )
        self.assertTrue(flags["confidential_detected"])
        self.assertTrue(flags["financial_detected"])
        self.assertTrue(flags["legal_detected"])
        self.assertTrue(flags["secret_detected"])
        self.assertTrue(flags["hr_detected"])

    def test_empty_types_no_flags(self):
        flags = sensitive_types_to_flags([])
        self.assertFalse(flags["pii_detected"])
        self.assertFalse(flags["exposure_detected"])

    def test_masked_status_sets_exposure_when_types_empty(self):
        flags = sensitive_types_to_flags([], masking_status="MASKED")
        self.assertTrue(flags["exposure_detected"])

    def test_flags_drive_risk_service_breakdown(self):
        logs = [
            SimpleNamespace(**sensitive_types_to_flags(["EMAIL", "INTERNAL_CONFIDENTIAL"])),
            SimpleNamespace(**sensitive_types_to_flags(["CUSTOMER_INFO", "OPENAI_API_KEY"])),
        ]

        breakdown = risk_svc.build_sensitive_breakdown(logs)  # type: ignore[arg-type]

        self.assertEqual(breakdown[0].count, 1)  # personal_info
        self.assertEqual(breakdown[1].count, 1)  # customer_info
        self.assertEqual(breakdown[2].count, 1)  # confidential
        self.assertEqual(breakdown[3].count, 1)  # source_code
        self.assertEqual(breakdown[4].count, 0)  # finance_legal


if __name__ == "__main__":
    unittest.main()
