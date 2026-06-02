"""users/me API 테스트"""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from app.main import app


class UserMeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_users_me_fixed_admin(self):
        resp = self.client.get("/api/users/me")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["user_id"], "anonymous-admin")
        self.assertEqual(body["display_name"], "관리자")
        self.assertEqual(body["role"], "admin")
        self.assertEqual(body["department"], "ALL")
        self.assertIn("logged_in_at", body)


if __name__ == "__main__":
    unittest.main()
