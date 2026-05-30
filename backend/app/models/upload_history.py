"""
SCR-INPUT-004 - upload_history Pydantic 문서 모델

저장소: Azure SQL Database (테이블 upload_history)

상태 흐름 (현재 동기 구현):
    pending → processing → completed | failed

향후 비동기/큐 처리 도입 시 다음 상태 추가 예정:
    masking | classifying | scoring
"""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class UploadStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    MASKING = "masking"
    CLASSIFYING = "classifying"
    SCORING = "scoring"
    COMPLETED = "completed"
    FAILED = "failed"


def _now_iso() -> str:
    """ISO-8601 UTC 타임스탬프."""
    return datetime.now(timezone.utc).isoformat()


class StatusEvent(BaseModel):
    status: UploadStatus
    at: str = Field(default_factory=_now_iso)
    message: Optional[str] = None


class ValidationErrorItem(BaseModel):
    row_index: int
    errors: List[str]


class UploadSummary(BaseModel):
    """analysis_pipeline.analyze_csv_file() 결과의 summary 부분."""

    total_logs: int = 0
    departments: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    avg_risk_score: float = 0.0


class UploadHistoryDoc(BaseModel):
    """upload_history 테이블 1 row."""

    model_config = ConfigDict(use_enum_values=True)

    id: str = Field(default_factory=lambda: str(uuid4()))
    upload_id: str = Field(default_factory=lambda: str(uuid4()))

    filename: str
    uploaded_at: str = Field(default_factory=_now_iso)
    uploaded_by: str = "anonymous"
    department_scope: str = "ALL"

    total_rows: int = 0
    valid_rows: int = 0
    invalid_rows: int = 0
    validation_errors: List[ValidationErrorItem] = Field(default_factory=list)

    blob_path: Optional[str] = None
    blob_purged_at: Optional[str] = None

    status: UploadStatus = UploadStatus.PENDING
    status_history: List[StatusEvent] = Field(default_factory=list)
    error_message: Optional[str] = None

    summary: Optional[UploadSummary] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None

    def push_status(self, status: UploadStatus, message: Optional[str] = None) -> None:
        """상태 갱신 + status_history append."""
        self.status = status
        self.status_history.append(StatusEvent(status=status, message=message))
