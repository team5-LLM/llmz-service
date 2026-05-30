import logging
import time
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.db.sql import init_db, is_sql_configured, sql_status
from app.services import upload_history_service as history_svc
from app.services.analysis_pipeline import analyze_csv_file
from app.services.recommender import build_recommendation_detail
from app.schemas.upload_history import (
    UploadHistoryDetailResponse,
    UploadHistoryItem,
    UploadHistoryListResponse,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if is_sql_configured():
        if init_db():
            logger.info("Azure SQL 초기화 완료")
        else:
            logger.warning(
                "Azure SQL 초기화 실패 — 분석 API는 동작하지만 upload_history 저장은 skip 됩니다."
            )
    yield


# FastAPI 애플리케이션 설정
app = FastAPI(
    title="LLM Automation Opportunity API",
    description="CSV 기반 부서별 LLM 사용 패턴 분석 및 AI 업무 자동화 추천 API",
    version="0.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_CSV_PATH = PROJECT_ROOT / "data-sample" / "sample_llm_logs.csv"

# 루트 API
@app.get("/")
def root():
    return {
        "service": "LLM Automation Opportunity API",
        "status": "running",
        "docs": "/docs",
    }


# 서비스 상태 확인 API
@app.get("/api/health")
def health_check():
    db = sql_status()
    return {
        "status": "ok",
        "db": db,
    }


# CSV 분석 API
@app.get("/api/analyze-sample")
def analyze_sample():
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}",
        )

    return analyze_csv_file(SAMPLE_CSV_PATH)


# CSV 업로드 API
@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """실행 흐름:
        1) upload_history INSERT (status=pending)
        2) tempfile 저장 → analyze_csv_file → 결과 산출
        3) 성공 시 upload_history UPDATE (status=completed + summary)
           실패 시 upload_history UPDATE (status=failed + error_message)
        4) 응답에 upload_id 포함 → FE 가 SCR-INPUT-004 화면에서 추적 가능
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")

    history_doc = history_svc.create_upload(
        filename=file.filename,
        uploaded_by="anonymous",
    )

    started = time.monotonic()
    try:
        history_svc.mark_processing(history_doc)

        content = await file.read()
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            result = analyze_csv_file(tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

        duration_ms = int((time.monotonic() - started) * 1000)
        summary = result.get("summary", {})
        total_rows = int(summary.get("total_logs", 0))

        history_svc.mark_completed(
            history_doc,
            summary=summary,
            total_rows=total_rows,
            valid_rows=total_rows,
            invalid_rows=0,
            duration_ms=duration_ms,
        )

        return {
            "upload_id": history_doc.upload_id,
            "status": history_doc.status,
            **result,
        }

    except HTTPException:
        history_svc.mark_failed(history_doc, error_message="HTTP 검증 실패")
        raise
    except Exception as exc:
        history_svc.mark_failed(history_doc, error_message=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"분석 처리 중 오류가 발생했습니다: {exc}",
        )


# 업로드 이력 목록 조회 API
@app.get("/api/uploads/history", response_model=UploadHistoryListResponse)
def list_upload_history(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
):
    """SCR-INPUT-004 — 데이터 입력 이력 목록 조회 (성공/실패/대기 포함).

    - 최신 업로드부터 정렬
    - limit/skip 페이징 (기본 50건)
    """
    docs = history_svc.list_uploads(limit=limit, skip=skip)
    total = history_svc.count_uploads()

    items = [
        UploadHistoryItem(
            upload_id=doc.upload_id,
            filename=doc.filename,
            uploaded_at=doc.uploaded_at,
            uploaded_by=doc.uploaded_by,
            status=str(doc.status),
            total_rows=doc.total_rows,
            valid_rows=doc.valid_rows,
            invalid_rows=doc.invalid_rows,
            duration_ms=doc.duration_ms,
            completed_at=doc.completed_at,
            error_message=doc.error_message,
            summary=doc.summary,
        )
        for doc in docs
    ]

    return UploadHistoryListResponse(items=items, total=total, limit=limit, skip=skip)


# 업로드 이력 상세 보기 API
@app.get("/api/uploads/{upload_id}", response_model=UploadHistoryDetailResponse)
def get_upload_history_detail(upload_id: str):
    """SCR-INPUT-004 — 단일 업로드 상태 변경 이력(status_history) 포함 상세."""
    doc = history_svc.get_upload(upload_id)
    if doc is None:
        raise HTTPException(
            status_code=404,
            detail=f"업로드 이력을 찾을 수 없습니다: {upload_id}",
        )

    return UploadHistoryDetailResponse(
        upload_id=doc.upload_id,
        filename=doc.filename,
        uploaded_at=doc.uploaded_at,
        uploaded_by=doc.uploaded_by,
        department_scope=doc.department_scope,
        total_rows=doc.total_rows,
        valid_rows=doc.valid_rows,
        invalid_rows=doc.invalid_rows,
        status=str(doc.status),
        status_history=doc.status_history,
        duration_ms=doc.duration_ms,
        completed_at=doc.completed_at,
        error_message=doc.error_message,
        summary=doc.summary,
        blob_path=doc.blob_path,
        blob_purged_at=doc.blob_purged_at,
    )


# Recommendations API
@app.get("/api/recommendations")
def get_recommendations():
    """전체 자동화 추천 카드 목록 조회."""
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}",
        )

    result = analyze_csv_file(SAMPLE_CSV_PATH)
    return {
        "count": len(result["recommendations"]),
        "recommendations": result["recommendations"],
    }

# 자동화 추천 카드 목록 조회 API
@app.get("/api/recommendations/{department}")
def get_recommendations_by_department(department: str):
    """특정 부서의 자동화 추천 카드 목록 조회."""
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}",
        )

    result = analyze_csv_file(SAMPLE_CSV_PATH)
    items = [
        item for item in result["recommendations"]
        if item["department"] == department
    ]

    return {
        "department": department,
        "count": len(items),
        "recommendations": items,
    }


# 자동화 추천 카드 상세 보기 API
@app.get("/api/recommendations/{department}/{task_label}")
def get_recommendation_detail(department: str, task_label: str):
    """SCR-RECO-002 추천 상세 보기 API."""
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}",
        )

    result = analyze_csv_file(SAMPLE_CSV_PATH)

    target = None
    for item in result["recommendations"]:
        if item["department"] == department and item["task_label"] == task_label:
            target = item
            break

    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"{department} - {task_label} 추천 정보를 찾을 수 없습니다.",
        )

    return build_recommendation_detail(target)


# Risk 기반 도입 판단 API
@app.get("/api/recommendations/{department}/{task_label}/decision")
def get_risk_based_decision(department: str, task_label: str):
    """SCR-RECO-004 Risk 기반 도입 판단 API."""
    detail = get_recommendation_detail(department, task_label)

    return {
        "department": detail["department"],
        "task_label": detail["task_label"],
        "service_name": detail["service_name"],
        "opportunity_score": detail["opportunity_score"],
        "risk_score": detail["risk_score"],
        "risk_level": detail["risk_level"],
        "decision": detail["decision"],
        "decision_level": detail["decision_level"],
        "decision_message": detail["decision_message"],
        "required_action": detail["required_action"],
    }
