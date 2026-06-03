from typing import Optional
from pydantic import BaseModel, Field

REQUIRED_COLUMNS = [
    "log_id",
    "department",
    "user_hash",
    "prompt_text",
    "model",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost",
    "created_at",
]


def validate_columns(columns: list[str]) -> tuple[bool, list[str]]:
    """CSV 필수 컬럼 검증."""
    missing = [col for col in REQUIRED_COLUMNS if col not in columns]
    return len(missing) == 0, missing


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
