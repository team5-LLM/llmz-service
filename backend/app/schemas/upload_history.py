"""SCR-INPUT-004 - 업로드 이력 조회 API의 응답 스키마"""

from typing import List, Optional

from pydantic import BaseModel

from app.models.upload_history import StatusEvent, UploadSummary


# Upload History Item Model
class UploadHistoryItem(BaseModel):
    """이력 리스트 1행"""

    upload_id: str
    filename: str
    uploaded_at: str
    uploaded_by: str
    status: str

    total_rows: int
    valid_rows: int
    invalid_rows: int

    duration_ms: Optional[int] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    summary: Optional[UploadSummary] = None


# Upload History List Response Model
class UploadHistoryListResponse(BaseModel):
    """SCR-INPUT-004 list 응답"""

    items: List[UploadHistoryItem]
    total: int
    limit: int
    skip: int


# Upload History Detail Response Model
class UploadHistoryDetailResponse(BaseModel):
    """단일 업로드 상세 (status_history 포함)"""

    upload_id: str
    filename: str
    uploaded_at: str
    uploaded_by: str
    department_scope: str

    total_rows: int
    valid_rows: int
    invalid_rows: int

    status: str
    status_history: List[StatusEvent]

    duration_ms: Optional[int] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None
    summary: Optional[UploadSummary] = None
    blob_path: Optional[str] = None
    blob_purged_at: Optional[str] = None
