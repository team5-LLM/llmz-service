"""
환경변수 로더
환경변수: .env.example 참고해서 .env 파일 작성해야 함

운영에서는 App Service 환경변수 / Azure Key Vault로 주입되며,
로컬에서는 backend/.env (gitignore 처리됨) 에서 읽는다.
"""

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_ROOT / ".env", override=False)

ODBC_DRIVER_INSTALL_URL = (
    "https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server"
)

_REQUIRED_ODBC_DRIVERS = (
    "ODBC Driver 18 for SQL Server",
    "ODBC Driver 17 for SQL Server",
)


class OdbcDriverMissingError(RuntimeError):
    """팀 공통 전제: ODBC Driver 17/18 미설치."""


def list_installed_odbc_drivers() -> list[str]:
    try:
        import pyodbc
    except ImportError:
        return []
    return list(pyodbc.drivers())


def pick_odbc_driver() -> str | None:
    installed = list_installed_odbc_drivers()
    for name in _REQUIRED_ODBC_DRIVERS:
        if name in installed:
            return name
    return None


def require_odbc_driver() -> str:
    driver = pick_odbc_driver()
    if driver:
        return driver
    installed = list_installed_odbc_drivers()
    raise OdbcDriverMissingError(
        "ODBC Driver 18 for SQL Server (또는 17) 설치가 필요합니다.\n"
        f"  설치: {ODBC_DRIVER_INSTALL_URL}\n"
        f"  현재 PC에 등록된 드라이버: {installed or '(없음)'}\n"
        "  Windows: msodbcsql.msi x64 설치 후 터미널 재시작"
    )


def _apply_odbc_driver(raw: str, driver: str) -> str:
    encoded_driver = quote(driver, safe="")
    if "driver=" in raw.lower():
        return re.sub(r"driver=[^&]+", f"driver={encoded_driver}", raw, flags=re.IGNORECASE)
    separator = "&" if "?" in raw else "?"
    return f"{raw}{separator}driver={encoded_driver}&Encrypt=yes&TrustServerCertificate=no"


def resolve_connection_string(raw: str) -> str:
    """pyodbc + ODBC Driver 17/18 기준으로 연결 문자열 보정."""
    if not raw:
        return raw

    if not raw.startswith("mssql+pyodbc://"):
        raise ValueError(
            "AZURE_SQL_CONNECTION_STRING 은 mssql+pyodbc:// 로 시작해야 합니다. "
            ".env.example 을 참고하세요."
        )

    driver = require_odbc_driver()
    return _apply_odbc_driver(raw, driver)


@dataclass(frozen=True)
class SqlSettings:
    connection_string: str

    @property
    def is_configured(self) -> bool:
        return bool(self.connection_string)


@lru_cache
def get_sql_settings() -> SqlSettings:
    raw = os.getenv("AZURE_SQL_CONNECTION_STRING", "").strip()
    if not raw:
        return SqlSettings(connection_string="")
    return SqlSettings(connection_string=resolve_connection_string(raw))
