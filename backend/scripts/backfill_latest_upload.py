"""최신 completed 업로드에 분석 결과를 persist (NVARCHAR 수정 후 backfill)."""
from pathlib import Path

from sqlalchemy import func, select

from app.db.sql import safe_session
from app.models.analysis_result_tables import DepartmentStatRow
from app.models.upload_history_table import UploadHistoryRow
from app.services.analysis_pipeline import analyze_csv_file
from app.services.persistence_service import persist_analysis_result


def main() -> None:
    sample = Path(__file__).resolve().parents[2] / "data-sample" / "sample_llm_logs.csv"
    result = analyze_csv_file(sample)

    session = safe_session()
    if session is None:
        raise RuntimeError("SQL 미설정")

    upload_id = session.scalar(
        select(UploadHistoryRow.upload_id)
        .where(UploadHistoryRow.status == "completed")
        .order_by(UploadHistoryRow.uploaded_at.desc())
        .limit(1)
    )
    if not upload_id:
        raise RuntimeError("completed 업로드 없음")

    ok = persist_analysis_result(upload_id, result)
    count = session.scalar(
        select(func.count())
        .select_from(DepartmentStatRow)
        .where(DepartmentStatRow.upload_id == upload_id)
    )
    session.close()

    print("upload_id:", upload_id)
    print("persist ok:", ok)
    print("department_stats rows:", count)


if __name__ == "__main__":
    main()
