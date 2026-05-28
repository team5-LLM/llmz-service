from pathlib import Path
import pandas as pd
from app.schemas.log_schema import validate_columns

def load_and_validate_csv(csv_path: str | Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        df = pd.read_csv(csv_path, encoding="utf-8")

    valid, missing = validate_columns(list(df.columns))
    if not valid:
        raise ValueError(f"CSV 필수 컬럼이 누락되었습니다: {missing}")

    for col in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["prompt_text"] = df["prompt_text"].fillna("").astype(str)
    df["department"] = df["department"].fillna("미분류").astype(str)
    df["user_hash"] = df["user_hash"].fillna("unknown_user").astype(str)
    df["model"] = df["model"].fillna("unknown_model").astype(str)
    return df
