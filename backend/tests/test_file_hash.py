import unittest

from app.utils.file_hash import sha256_hex


class FileHashTests(unittest.TestCase):
    def test_sha256_hex_deterministic(self):
        data = b"log_id,department\n1,test\n"
        self.assertEqual(len(sha256_hex(data)), 64)
        self.assertEqual(sha256_hex(data), sha256_hex(data))

    def test_sha256_hex_differs_by_content(self):
        self.assertNotEqual(sha256_hex(b"a"), sha256_hex(b"b"))


if __name__ == "__main__":
    unittest.main()
