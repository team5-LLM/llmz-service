# 아래 스키마가 기존 app/schemas/log_schema.py에 없다면 추가하세요.
from typing import Optional
from pydantic import BaseModel, Field


class MaskingRuleCreate(BaseModel):
    """SCR-ADMIN-001 마스킹 규칙 생성 요청."""
    rule_type: str = Field(..., description="regex 또는 keyword")
    pattern: str
    replacement: str = "[MASKED]"
    category: str = "custom"
    enabled: bool = True


class MaskingRuleUpdate(BaseModel):
    """SCR-ADMIN-001 마스킹 규칙 수정 요청."""
    rule_type: Optional[str] = None
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None
