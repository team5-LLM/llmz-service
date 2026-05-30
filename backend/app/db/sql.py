"""
Azure SQL Database + SQLAlchemy 연결 헬퍼

환경변수: AZURE_SQL_CONNECTION_STRING (backend/.env)
"""

from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import OdbcDriverMissingError, get_sql_settings, require_odbc_driver

logger = logging.getLogger(__name__)


class SqlUnavailableError(RuntimeError):
    """SQL 연결 문자열 미설정 또는 초기화 실패."""


class Base(DeclarativeBase):
    pass


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker[Session]] = None


def is_sql_configured() -> bool:
    return get_sql_settings().is_configured


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    settings = get_sql_settings()
    if not settings.is_configured:
        raise SqlUnavailableError(
            "AZURE_SQL_CONNECTION_STRING 이 설정되지 않았습니다. "
            "backend/.env (또는 App Service 환경변수) 를 확인하세요."
        )

    _engine = create_engine(
        settings.connection_string,
        pool_pre_ping=True,
        pool_recycle=1800,
    )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionLocal


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """트랜잭션 경계. 실패 시 rollback."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def safe_session() -> Optional[Session]:
    """SQL 미설정 시 None. 호출자가 graceful skip 가능."""
    if not is_sql_configured():
        return None
    try:
        return get_session_factory()()
    except SqlUnavailableError:
        return None
    except Exception:
        return None


def _ping_database(retries: int = 3, delay_seconds: float = 8.0) -> None:
    """Serverless DB auto-pause 해제 등을 위해 재시도."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
            return
        except SQLAlchemyError as exc:
            last_error = exc
            logger.warning(
                "DB 연결 재시도 (%s/%s): %s",
                attempt,
                retries,
                exc,
            )
            if attempt < retries:
                time.sleep(delay_seconds)

    if last_error is not None:
        raise last_error


def init_db() -> bool:
    """테이블이 없으면 생성. 미설정/연결 실패 시 False."""
    if not is_sql_configured():
        return False

    try:
        from app.models.upload_history_table import UploadHistoryRow  # noqa: F401

        _ping_database()
        Base.metadata.create_all(get_engine())
        return True
    except Exception as exc:
        logger.error("init_db 실패: %s", exc)
        return False


def is_sql_ready() -> bool:
    """헬스체크용 — env + ODBC 드라이버 + 실제 SELECT 1."""
    if not is_sql_configured():
        return False
    try:
        require_odbc_driver()
        _ping_database(retries=2, delay_seconds=5.0)
        return True
    except Exception:
        return False


def sql_status() -> dict:
    """헬스체크 상세 — 팀 디버깅용."""
    configured = is_sql_configured()
    if not configured:
        return {
            "configured": False,
            "odbc_driver": None,
            "ready": False,
            "message": "AZURE_SQL_CONNECTION_STRING 미설정",
        }

    try:
        driver = require_odbc_driver()
        ready = False
        message = "연결 대기"
        try:
            _ping_database(retries=2, delay_seconds=5.0)
            ready = True
            message = "connected"
        except Exception as exc:
            message = str(exc)

        return {
            "configured": True,
            "odbc_driver": driver,
            "ready": ready,
            "message": message,
        }
    except OdbcDriverMissingError as exc:
        return {
            "configured": True,
            "odbc_driver": None,
            "ready": False,
            "message": str(exc),
        }
