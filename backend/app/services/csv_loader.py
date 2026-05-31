from pathlib import Path
import pandas as pd

from app.schemas.log_schema import REQUIRED_COLUMNS, validate_columns


def inspect_csv(csv_path: str | Path) -> dict:
    """
    SCR-INPUT-001 CSV 로그 업로드 중 스키마 검증 담당.
    누락 컬럼이 있으면 validation_errors를 반환합니다.
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
    CSV를 읽고 필수 컬럼과 숫자 컬럼을 정리합니다.
    """
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8")

    valid, missing = validate_columns(list(df.columns))
    if not valid:
        raise ValueError(f"CSV 필수 컬럼이 누락되었습니다: {missing}")

    numeric_cols = ["input_tokens", "output_tokens", "total_tokens", "cost"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["prompt_text"] = df["prompt_text"].fillna("").astype(str)
    df["department"] = df["department"].fillna("미분류").astype(str)
    df["user_hash"] = df["user_hash"].fillna("unknown_user").astype(str)
    df["model"] = df["model"].fillna("unknown_model").astype(str)

    return df
