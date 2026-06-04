"""업로드 파일 내용 해시 (중복 파일 감지용)."""

from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    """파일 바이트 전체에 대한 SHA-256 hex (64자)."""
    return hashlib.sha256(data).hexdigest()
