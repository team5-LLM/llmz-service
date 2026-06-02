"""
기존 VARCHAR 컬럼 → NVARCHAR 마이그레이션.

SQLAlchemy String/Text 가 SQL Server 에 VARCHAR 를 생성한 경우,
한글 부서명이 '???' 로 저장되어 department_stats UNIQUE 제약 위반이 발생한다.

분석 결과 3테이블(department_stats, recommendations, prompt_logs)은
데이터가 없으면 DROP 후 Unicode ORM 으로 재생성한다.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.db.sql import Base

logger = logging.getLogger(__name__)

_ANALYSIS_TABLES = ("prompt_logs", "recommendations", "department_stats")


def _column_type(engine: Engine, table: str, column: str) -> str | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT t.name
                FROM sys.columns c
                JOIN sys.types t ON c.user_type_id = t.user_type_id
                WHERE c.object_id = OBJECT_ID(:table_name)
                  AND c.name = :column_name
                """
            ),
            {"table_name": table, "column_name": column},
        ).fetchone()
    return row[0].lower() if row else None


def _table_exists(engine: Engine, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT OBJECT_ID(:table_name)"),
            {"table_name": table},
        ).fetchone()
    return row is not None and row[0] is not None


def _needs_analysis_table_recreate(engine: Engine) -> bool:
    if not _table_exists(engine, "department_stats"):
        return False
    col_type = _column_type(engine, "department_stats", "department")
    return col_type is not None and col_type not in {"nvarchar", "nchar", "ntext"}


def _recreate_analysis_result_tables(engine: Engine) -> None:
    from app.models.analysis_result_tables import (  # noqa: F401
        DepartmentStatRow,
        PromptLogRow,
        RecommendationRow,
    )

    with engine.begin() as conn:
        for table in _ANALYSIS_TABLES:
            conn.execute(text(f"DROP TABLE IF EXISTS [{table}]"))

    tables = [
        DepartmentStatRow.__table__,
        RecommendationRow.__table__,
        PromptLogRow.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    logger.info("분석 결과 테이블 재생성 완료 (NVARCHAR): %s", ", ".join(_ANALYSIS_TABLES))


def migrate_varchar_to_nvarchar(engine: Engine) -> int:
    """
    VARCHAR → NVARCHAR 마이그레이션.
    반환값: 수행한 마이그레이션 단계 수 (0 또는 1).
    """
    if not _needs_analysis_table_recreate(engine):
        logger.info("department_stats 가 이미 NVARCHAR — 분석 테이블 마이그레이션 skip")
        return 0

    _recreate_analysis_result_tables(engine)
    return 1
