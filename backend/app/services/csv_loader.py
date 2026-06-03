from pathlib import Path
import pandas as pd

from app.schemas.log_schema import REQUIRED_COLUMNS, validate_columns


class CsvValidationError(Exception):
    """CSV 유효성 검증 실패 시 사용하는 커스텀 예외"""

    def __init__(self, message: str, row_index: int | None = None, errors: list | None = None):
        super().__init__(message)
        self.row_index = row_index
        self.errors = errors or []


def inspect_csv(csv_path: str | Path) -> dict:
    """
    CSV 스키마 검증 결과를 반환합니다.
    """
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8")

    valid, missing = validate_columns(list(df.columns))

    validation_errors = []
    if missing:
        validation_errors.append({
            "type": "missing_columns",
            "message": "CSV 필수 컬럼이 누락되었습니다.",
            "missing_columns": missing,
        })

    return {
        "valid": valid,
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "required_columns": REQUIRED_COLUMNS,
        "validation_errors": validation_errors,
    }


def load_and_validate_csv(csv_path: str | Path) -> pd.DataFrame:
    """
    CSV를 읽고 필수 컬럼과 숫자 컬럼을 검증합니다.
    """
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8")

    valid, missing = validate_columns(list(df.columns))
    if not valid:
        raise CsvValidationError(
            message=f"CSV 필수 컬럼이 누락되었습니다: {missing}",
            row_index=None,
            errors=[
                {
                    "type": "missing_columns",
                    "missing_columns": missing,
                }
            ],
        )

    numeric_cols = ["input_tokens", "output_tokens", "total_tokens", "cost"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["prompt_text"] = df["prompt_text"].fillna("").astype(str)
    df["department"] = df["department"].fillna("미분류").astype(str)
    df["user_hash"] = df["user_hash"].fillna("unknown_user").astype(str)
    df["model"] = df["model"].fillna("unknown_model").astype(str)

    return df