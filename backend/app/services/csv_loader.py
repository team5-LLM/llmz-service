from pathlib import Path

import pandas as pd

from app.schemas.log_schema import validate_columns


class CsvValidationError(ValueError):
    """CSV 스키마/파싱 검증 실패 — upload_history.validation_errors 로 기록."""

    def __init__(self, errors: list[str], *, row_index: int = 0):
        self.errors = errors
        self.row_index = row_index
        message = "; ".join(errors)
        super().__init__(message)


def load_and_validate_csv(csv_path: str | Path) -> pd.DataFrame:
    try:
        df = pd.read_csv(csv_path, encoding="utf-8-sig")
    except UnicodeDecodeError:
        try:
            df = pd.read_csv(csv_path, encoding="utf-8")
        except pd.errors.EmptyDataError:
            raise CsvValidationError(["CSV 파일이 비어 있습니다."]) from None
        except Exception as exc:
            raise CsvValidationError([f"CSV 파싱 실패: {exc}"]) from exc
    except pd.errors.EmptyDataError:
        raise CsvValidationError(["CSV 파일이 비어 있습니다."]) from None
    except Exception as exc:
        raise CsvValidationError([f"CSV 파싱 실패: {exc}"]) from exc

    if df.empty:
        raise CsvValidationError(["CSV에 데이터 행이 없습니다."])

    valid, missing = validate_columns(list(df.columns))
    if not valid:
        raise CsvValidationError([f"필수 컬럼 누락: {', '.join(missing)}"])

    for col in ["input_tokens", "output_tokens", "total_tokens", "cost"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df["prompt_text"] = df["prompt_text"].fillna("").astype(str)
    df["department"] = df["department"].fillna("미분류").astype(str)
    df["user_hash"] = df["user_hash"].fillna("unknown_user").astype(str)
    df["model"] = df["model"].fillna("unknown_model").astype(str)
    return df
