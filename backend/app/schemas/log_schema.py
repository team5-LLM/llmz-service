import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

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
    rule_type: Literal["regex", "keyword"] = Field(..., description="regex 또는 keyword")
    pattern: str
    replacement: str = "[MASKED]"
    category: str = "custom"
    enabled: bool = True

    @model_validator(mode="after")
    def validate_regex_pattern(self):
        """
        rule_type이 regex인 경우 pattern이 유효한 정규식인지 검증한다.
        잘못된 정규식이면 FastAPI가 422 Validation Error를 반환한다.
        """
        if self.rule_type == "regex":
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {exc}")
        return self


class MaskingRuleUpdate(BaseModel):
    """SCR-ADMIN-001 마스킹 규칙 수정 요청."""
    rule_type: Optional[Literal["regex", "keyword"]] = None
    pattern: Optional[str] = None
    replacement: Optional[str] = None
    category: Optional[str] = None
    enabled: Optional[bool] = None

    @model_validator(mode="after")
    def validate_regex_pattern(self):
        """
        수정 요청에서 rule_type이 regex이고 pattern이 함께 들어온 경우
        pattern이 유효한 정규식인지 검증한다.
        """
        if self.rule_type == "regex" and self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"Invalid regex pattern: {exc}")
        return self