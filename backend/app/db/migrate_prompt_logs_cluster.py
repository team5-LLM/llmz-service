"""
prompt_logs.cluster_id · pattern_label 컬럼 추가 (기존 DB 마이그레이션).
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_COLUMNS = (
    ("cluster_id", "NVARCHAR(128)"),
    ("pattern_label", "NVARCHAR(128)"),
)


def _column_exists(engine: Engine, column: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT COL_LENGTH('prompt_logs', :column_name)"),
            {"column_name": column},
        ).fetchone()
    return row is not None and row[0] is not None


def migrate_prompt_logs_cluster(engine: Engine) -> int:
    """컬럼 없으면 ADD. 반환: 추가한 컬럼 수."""
    steps = 0
    for column, sql_type in _COLUMNS:
        if _column_exists(engine, column):
            continue
        with engine.begin() as conn:
            conn.execute(
                text(
                    f"""
                    ALTER TABLE prompt_logs
                    ADD [{column}] {sql_type} NULL
                    """
                )
            )
        steps += 1
        logger.info("prompt_logs.%s 컬럼 추가", column)
    return steps
