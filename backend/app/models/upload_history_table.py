"""upload_history 테이블 SQLAlchemy ORM (Azure SQL)."""

from typing import Optional

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sql import Base


class UploadHistoryRow(Base):
    __tablename__ = "upload_history"
    __table_args__ = (Index("ix_upload_history_uploaded_at", "uploaded_at"),)

    upload_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    id: Mapped[str] = mapped_column(String(36), nullable=False)

    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    uploaded_at: Mapped[str] = mapped_column(String(40), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(128), nullable=False, default="anonymous")
    department_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="ALL")

    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    validation_errors_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    blob_path: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    blob_purged_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    status_history_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    summary_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
