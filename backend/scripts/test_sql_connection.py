"""Azure SQL 연결 및 upload_history 테이블 생성 테스트."""

from app.core.config import get_sql_settings
from app.db.sql import init_db, is_sql_ready
from app.services import upload_history_service as history_svc


def main() -> None:
    settings = get_sql_settings()
    if not settings.is_configured:
        print("FAIL: AZURE_SQL_CONNECTION_STRING 이 backend/.env 에 없습니다.")
        return

    print("1) SELECT 1 연결 테스트...")
    if not is_sql_ready():
        print("FAIL: DB 연결 실패. 방화벽(IP 허용)과 연결 문자열을 확인하세요.")
        return
    print("OK: DB 연결 성공")

    print("2) upload_history 테이블 생성...")
    if not init_db():
        print("FAIL: init_db 실패")
        return
    print("OK: 테이블 준비 완료")

    print("3) CRUD 스모크 테스트...")
    doc = history_svc.create_upload(filename="test_connection.csv", uploaded_by="test_script")
    history_svc.mark_processing(doc)
    history_svc.mark_completed(
        doc,
        summary={
            "total_logs": 1,
            "departments": 1,
            "total_tokens": 100,
            "total_cost": 1.0,
            "avg_risk_score": 10.0,
        },
        total_rows=1,
        valid_rows=1,
        invalid_rows=0,
        duration_ms=42,
    )

    loaded = history_svc.get_upload(doc.upload_id)
    if loaded is None or loaded.status != "completed":
        print("FAIL: 저장/조회 실패")
        return

    print(f"OK: upload_id={doc.upload_id} 저장·조회 성공")
    print(f"   이력 총 {history_svc.count_uploads()}건")


if __name__ == "__main__":
    main()
