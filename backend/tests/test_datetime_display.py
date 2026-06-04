"""datetime_display 단위 테스트."""

import unittest

from app.utils.datetime_display import format_datetime_kst


class FormatDatetimeKstTests(unittest.TestCase):
    def test_utc_iso_to_kst(self):
        # 2026-06-04 12:00:00 UTC → KST +9h
        out = format_datetime_kst("2026-06-04T12:00:00+00:00")
        self.assertEqual(out, "2026-06-04 21:00:00")

    def test_none_passthrough(self):
        self.assertIsNone(format_datetime_kst(None))

    def test_invalid_returns_original(self):
        self.assertEqual(format_datetime_kst("not-a-date"), "not-a-date")


if __name__ == "__main__":
    unittest.main()
