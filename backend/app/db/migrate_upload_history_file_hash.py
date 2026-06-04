"""
upload_history.file_content_sha256 컬럼 추가 (기존 DB 마이그레이션).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_COLUMN = "file_content_sha256"
_INDEX = "ix_upload_history_file_sha256"


def _column_exists(engine: Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT COL_LENGTH('upload_history', 'file_content_sha256')")
        ).fetchone()
    return row is not None and row[0] is not None


def _index_exists(engine: Engine) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT 1
                FROM sys.indexes
                WHERE name = :index_name
                  AND object_id = OBJECT_ID('upload_history')
                """
            ),
            {"index_name": _INDEX},
        ).fetchone()
    return row is not None


def migrate_upload_history_file_hash(engine: Engine) -> int:
    """컬럼·인덱스 없으면 추가. 반환: 수행한 단계 수 (0~2)."""
    steps = 0
    if not _column_exists(engine):
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    ALTER TABLE upload_history
                    ADD [{_COLUMN}] NVARCHAR(64) NULL
                    """
                )
            )
        steps += 1
        logger.info("upload_history.%s 컬럼 추가", _COLUMN)

    if not _index_exists(engine):
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    CREATE INDEX [{_INDEX}]
                    ON upload_history ([{_COLUMN}])
                    WHERE [{_COLUMN}] IS NOT NULL
                    """
                )
            )
        steps += 1
        logger.info("upload_history 인덱스 %s 생성", _INDEX)

    return steps
