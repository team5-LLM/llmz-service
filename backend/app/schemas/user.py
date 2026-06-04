"""현재 사용자 프로필 API 스키마"""

from typing import Literal

from pydantic import BaseModel


class UserProfileResponse(BaseModel):
    """GET /api/users/me — 단일 관리자 모드 고정값
    """

    user_id: str
    display_name: str
    role: Literal["admin"]
    department: str
    logged_in_at: str
