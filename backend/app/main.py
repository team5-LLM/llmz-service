import logging
import time
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.db.blob import delete_blob, is_storage_configured, storage_status, upload_csv_bytes
from app.db.sql import init_db, is_sql_configured, sql_status
from app.models.upload_history import ValidationErrorItem
from app.services import upload_history_service as history_svc
from app.services.analysis_pipeline import analyze_csv_file
from app.services.csv_loader import CsvValidationError
from app.services.persistence_service import persist_analysis_result
from app.services.recommender import build_recommendation_detail
from app.schemas.dashboard import (
    DashboardDepartmentsResponse,
    DashboardDepartmentDetailResponse,
    DashboardPeriod,
    DashboardSummaryResponse,
)
from app.schemas.upload_history import (
    UploadHistoryDetailResponse,
    UploadHistoryItem,
    UploadHistoryListResponse,
    UploadHistorySummaryByStatus,
    UploadHistorySummaryResponse,
)
from app.schemas.repeat_pattern import (
    DashboardRepeatPatternsResponse,
    DepartmentRepeatPatternsResponse,
    DepartmentRepeatStat,
    RepeatPatternItem,
)
from app.services import dashboard_service as dashboard_svc
from app.services import repeat_pattern_service as repeat_svc
from app.utils.date_range import InvalidDateRangeError, resolve_date_range

from app.schemas.log_schema import MaskingRuleCreate, MaskingRuleUpdate
from app.services.admin_rules import list_rules, create_rule, update_rule, delete_rule
from app.services.embedding_access import get_embedding_access_policy

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


app = FastAPI(
    title="LLM Automation Opportunity API",
    description="CSV 기반 부서별 LLM 사용 패턴 분석 및 AI 업무 자동화 추천 API",
    version="0.5.0",
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

# SCR-INPUT-004 — 허용 status 값 (§7.1)
VALID_UPLOAD_STATUSES = frozenset({"pending", "processing", "completed", "failed"})


# §0.5 기간 파라미터 → DateRange (400/422 변환)
def _resolve_history_date_range(
    from_date: Optional[str],
    to_date: Optional[str],
    month: Optional[str],
):
    try:
        return resolve_date_range(from_date=from_date, to_date=to_date, month=month)
    except InvalidDateRangeError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# query param → UploadHistoryFilters 조립
def _build_history_filters(
    *,
    filename_q: Optional[str],
    status: Optional[str],
    uploaded_by: Optional[str],
    from_date: Optional[str],
    to_date: Optional[str],
    month: Optional[str],
) -> history_svc.UploadHistoryFilters:
    if status is not None and status not in VALID_UPLOAD_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                "status는 pending, processing, completed, failed 중 하나여야 합니다."
            ),
        )

    date_range = _resolve_history_date_range(from_date, to_date, month)
    return history_svc.UploadHistoryFilters(
        filename_q=filename_q,
        status=status,
        uploaded_by=uploaded_by,
        date_range=date_range,
    )

# SCR-RECO-001 샘플 CSV 기반 조회 API에서 반복되는 파일 확인/분석 로직
def _analyze_sample_or_404() -> dict:
    """
    샘플 CSV 기반 조회 API에서 반복되는 파일 확인/분석 로직.
    """
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}",
        )

    return analyze_csv_file(SAMPLE_CSV_PATH)

# SCR-ROOT-001 루트 엔드포인트 조회 API
@app.get("/")
def root():
    return {
        "service": "LLM Automation Opportunity API",
        "status": "running",
        "docs": "/docs",
    }


# SCR-ROOT-002 상태 확인 API
@app.get("/api/health")
def health_check():
    db = sql_status()
    storage = storage_status()
    return {
        "status": "ok",
        "db": db,
        "storage": storage,
    }


# SCR-RECO-001 샘플 CSV 기반 조회 API
@app.get("/api/analyze-sample")
def analyze_sample():
    return _analyze_sample_or_404()


# SCR-DASH-001 메인 대시보드 KPI API
@app.get("/api/dashboard/summary", response_model=DashboardSummaryResponse)
def get_dashboard_summary(
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
):
    """SCR-DASH-001 — 메인 대시보드 KPI (§3.2)."""
    date_range = _resolve_history_date_range(from_date, to_date, month)
    summary = dashboard_svc.get_dashboard_summary(date_range)
    return DashboardSummaryResponse(
        period=DashboardPeriod(
            from_date=date_range.from_date,
            to_date=date_range.to_date,
        ),
        summary=summary,
    )


# SCR-DASH-001 부서별 분포 차트 API
@app.get("/api/dashboard/departments", response_model=DashboardDepartmentsResponse)
def get_dashboard_departments(
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
):
    """SCR-DASH-001 — 부서별 분포 차트 (§3.3)."""
    date_range = _resolve_history_date_range(from_date, to_date, month)
    department_stats = dashboard_svc.get_dashboard_departments(date_range)
    return DashboardDepartmentsResponse(
        period=DashboardPeriod(
            from_date=date_range.from_date,
            to_date=date_range.to_date,
        ),
        department_stats=department_stats,
    )


# SCR-DASH-001 부서 상세 확장 — 시계열·우선순위 (§3.4)
@app.get(
    "/api/dashboard/departments/{department}",
    response_model=DashboardDepartmentDetailResponse,
)
def get_dashboard_department_detail(
    department: str,
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    granularity: str = Query(default="daily", description="daily | weekly | monthly"),
    task_sort: str = Query(default="priority", description="priority | count | ratio"),
):
    """SCR-DASH-001 P1 — 단일 부서 상세·시계열 (§3.4)."""
    if granularity not in dashboard_svc._VALID_GRANULARITIES:
        raise HTTPException(
            status_code=422,
            detail="granularity는 daily, weekly, monthly 중 하나여야 합니다.",
        )
    if task_sort not in dashboard_svc._VALID_TASK_SORTS:
        raise HTTPException(
            status_code=422,
            detail="task_sort는 priority, count, ratio 중 하나여야 합니다.",
        )

    date_range = _resolve_history_date_range(from_date, to_date, month)
    detail = dashboard_svc.get_dashboard_department_detail(
        department,
        date_range,
        granularity=granularity,  # type: ignore[arg-type]
        task_sort=task_sort,  # type: ignore[arg-type]
    )
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail=f"부서를 찾을 수 없습니다: {department}",
        )
    return DashboardDepartmentDetailResponse(
        department=detail["department"],
        period=DashboardPeriod(**detail["period"]),
        overview=detail["overview"],
        trend=detail["trend"],
        tasks_by_priority=detail["tasks_by_priority"],
    )


def _parse_repeat_pattern_params(
    method: str,
    min_pattern_count: int,
) -> tuple[str, int]:
    if method not in repeat_svc._VALID_METHODS:
        raise HTTPException(
            status_code=422,
            detail="method는 auto, heuristic, cluster 중 하나여야 합니다.",
        )
    if min_pattern_count < 2:
        raise HTTPException(
            status_code=422,
            detail="min_pattern_count는 2 이상이어야 합니다.",
        )
    return method, min_pattern_count


def _to_department_repeat_stat(data: dict) -> DepartmentRepeatStat:
    return DepartmentRepeatStat(
        department=data["department"],
        total_requests=data["total_requests"],
        repeat_requests=data["repeat_requests"],
        repeat_ratio=data["repeat_ratio"],
        unique_patterns=data["unique_patterns"],
        patterns=[RepeatPatternItem(**item) for item in data["patterns"]],
    )


# SCR-DASH-003 — 부서별 반복 프롬프트 비율 (§3.5)
@app.get(
    "/api/dashboard/repeat-patterns",
    response_model=DashboardRepeatPatternsResponse,
)
def get_dashboard_repeat_patterns(
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    method: str = Query(
        default="auto",
        description="auto | heuristic | cluster (FUNC-PROC-005 cluster_id 연동)",
    ),
    min_pattern_count: int = Query(
        default=repeat_svc.DEFAULT_MIN_PATTERN_COUNT,
        ge=2,
        description="반복 패턴 최소 발생 횟수",
    ),
):
    """SCR-DASH-003 — 전체 부서 반복 프롬프트 비율."""
    method, min_pattern_count = _parse_repeat_pattern_params(method, min_pattern_count)
    date_range = _resolve_history_date_range(from_date, to_date, month)
    result = repeat_svc.get_repeat_patterns(
        date_range,
        method=method,  # type: ignore[arg-type]
        min_pattern_count=min_pattern_count,
    )
    return DashboardRepeatPatternsResponse(
        period=DashboardPeriod(**result["period"]),
        analysis_method=result["analysis_method"],
        min_pattern_count=result["min_pattern_count"],
        departments=[_to_department_repeat_stat(item) for item in result["departments"]],
    )


@app.get(
    "/api/dashboard/departments/{department}/repeat-patterns",
    response_model=DepartmentRepeatPatternsResponse,
)
def get_department_repeat_patterns(
    department: str,
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
    method: str = Query(default="auto", description="auto | heuristic | cluster"),
    min_pattern_count: int = Query(
        default=repeat_svc.DEFAULT_MIN_PATTERN_COUNT,
        ge=2,
    ),
):
    """SCR-DASH-003 — 단일 부서 반복 패턴 상세."""
    method, min_pattern_count = _parse_repeat_pattern_params(method, min_pattern_count)
    date_range = _resolve_history_date_range(from_date, to_date, month)
    result = repeat_svc.get_repeat_patterns(
        date_range,
        department=department,
        method=method,  # type: ignore[arg-type]
        min_pattern_count=min_pattern_count,
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"부서를 찾을 수 없습니다: {department}",
        )
    dept = result["departments"][0]
    return DepartmentRepeatPatternsResponse(
        period=DashboardPeriod(**result["period"]),
        analysis_method=result["analysis_method"],
        min_pattern_count=result["min_pattern_count"],
        department=dept["department"],
        total_requests=dept["total_requests"],
        repeat_requests=dept["repeat_requests"],
        repeat_ratio=dept["repeat_ratio"],
        unique_patterns=dept["unique_patterns"],
        patterns=[RepeatPatternItem(**item) for item in dept["patterns"]],
    )


# SCR-INPUT-004 데이터 입력 이력 목록 조회 API
@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """실행 흐름:
        1) upload_history INSERT (status=pending)
        2) Blob 임시 업로드 (설정 시) → blob_path 기록
        3) tempfile 저장 → analyze_csv_file → 결과 산출
        4) 분석 후 Blob 삭제 → blob_purged_at 기록 (Lifecycle 7일은 백업)
        5) persist_analysis_result → Azure SQL (department_stats, recommendations, prompt_logs)
        6) 성공/실패 upload_history UPDATE
        7) 응답에 upload_id 포함 → FE 가 SCR-INPUT-004 화면에서 추적 가능
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")

    history_doc = history_svc.create_upload(
        filename=file.filename,
        uploaded_by="anonymous",
    )

    started = time.monotonic()
    blob_name: str | None = None
    try:
        history_svc.mark_processing(history_doc)

        content = await file.read()

        if is_storage_configured():
            try:
                blob_path, blob_name = upload_csv_bytes(
                    upload_id=history_doc.upload_id,
                    filename=file.filename,
                    data=content,
                )
                history_svc.record_blob_path(history_doc, blob_path)
            except Exception as exc:
                logger.warning(
                    "Blob 업로드 실패 — 로컬 tempfile 분석만 진행 (upload_id=%s): %s",
                    history_doc.upload_id,
                    exc,
                )
                blob_name = None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            result = analyze_csv_file(tmp_path)
        except CsvValidationError as exc:
            errors = [
                ValidationErrorItem(row_index=exc.row_index, errors=exc.errors)
            ]
            history_svc.mark_validation_failed(
                history_doc,
                errors=errors,
                error_message=str(exc),
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "message": str(exc),
                    "validation_errors": [
                        item.model_dump(mode="json") for item in errors
                    ],
                },
            )
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

        persist_analysis_result(history_doc.upload_id, result)

        response = {k: v for k, v in result.items() if k != "masked_logs"}
        return {
            "upload_id": history_doc.upload_id,
            "status": history_doc.status,
            **response,
        }

    except HTTPException:
        raise
    except Exception as exc:
        history_svc.mark_failed(history_doc, error_message=str(exc))
        raise HTTPException(
            status_code=500,
            detail=f"분석 처리 중 오류가 발생했습니다: {exc}",
        )
    finally:
        if blob_name and is_storage_configured():
            try:
                delete_blob(blob_name)
                history_svc.record_blob_purged(history_doc)
            except Exception as exc:
                logger.warning(
                    "Blob 삭제 실패 — Portal Lifecycle(7일)이 정리합니다 (upload_id=%s): %s",
                    history_doc.upload_id,
                    exc,
                )


@app.get("/api/uploads/history", response_model=UploadHistoryListResponse)
def list_upload_history(
    limit: int = Query(default=50, ge=1, le=200),
    skip: int = Query(default=0, ge=0),
    filename_q: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    uploaded_by: Optional[str] = Query(default=None),
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
):
    """SCR-INPUT-004 — 데이터 입력 이력 목록 조회."""
    filters = _build_history_filters(
        filename_q=filename_q,
        status=status,
        uploaded_by=uploaded_by,
        from_date=from_date,
        to_date=to_date,
        month=month,
    )
    docs = history_svc.list_uploads(limit=limit, skip=skip, filters=filters)
    total = history_svc.count_uploads(filters=filters)

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


@app.get("/api/uploads/history/summary", response_model=UploadHistorySummaryResponse)
def get_upload_history_summary(
    from_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    to_date: Optional[str] = Query(default=None, description="YYYY-MM-DD"),
    month: Optional[str] = Query(default=None, description="YYYY-MM"),
):
    """SCR-INPUT-004 — 데이터 입력 이력 요약 카운트."""
    date_range = _resolve_history_date_range(from_date, to_date, month)
    filters = history_svc.UploadHistoryFilters(date_range=date_range)
    by_status = history_svc.count_uploads_by_status(filters=filters)
    total = history_svc.count_uploads(filters=filters)

    return UploadHistorySummaryResponse(
        total=total,
        by_status=UploadHistorySummaryByStatus(**by_status),
        from_date=date_range.from_date,
        to_date=date_range.to_date,
    )


@app.get("/api/uploads/{upload_id}", response_model=UploadHistoryDetailResponse)
def get_upload_history_detail(upload_id: str):
    """SCR-INPUT-004 — 단일 업로드 상태 변경 이력 포함 상세."""
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
        validation_errors=doc.validation_errors,
    )


@app.get("/api/recommendations")
def get_recommendations():
    """전체 자동화 추천 카드 목록 조회."""
    result = _analyze_sample_or_404()
    return {
        "count": len(result["recommendations"]),
        "recommendations": result["recommendations"],
    }


@app.get("/api/recommendations/{department}")
def get_recommendations_by_department(department: str):
    """특정 부서의 자동화 추천 카드 목록 조회."""
    result = _analyze_sample_or_404()
    items = [
        item for item in result["recommendations"]
        if item["department"] == department
    ]

    return {
        "department": department,
        "count": len(items),
        "recommendations": items,
    }


@app.get("/api/recommendations/{department}/{task_label}")
def get_recommendation_detail(department: str, task_label: str):
    """SCR-RECO-002 추천 상세 보기 API."""
    result = _analyze_sample_or_404()

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


@app.get("/api/embedding/access-policy")
def embedding_access_policy():
    """
    FUNC-PROC-011 Embedding 접근 통제.
    원문 prompt_text를 embedding 대상으로 사용하지 않고,
    masked_prompt만 사용한다는 정책을 반환합니다.
    """
    return get_embedding_access_policy()


@app.get("/api/admin/masking-rules")
def admin_list_masking_rules():
    """
    SCR-ADMIN-001 마스킹 규칙 목록 조회.
    """
    return {"count": len(list_rules()), "items": list_rules()}


@app.post("/api/admin/masking-rules")
def admin_create_masking_rule(rule: MaskingRuleCreate):
    """
    SCR-ADMIN-001 마스킹 규칙 생성.
    """
    return create_rule(rule.model_dump())


@app.patch("/api/admin/masking-rules/{rule_id}")
def admin_update_masking_rule(rule_id: str, payload: MaskingRuleUpdate):
    """
    SCR-ADMIN-001 마스킹 규칙 수정.
    """
    updated = update_rule(rule_id, payload.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="마스킹 규칙을 찾을 수 없습니다.")
    return updated


@app.delete("/api/admin/masking-rules/{rule_id}")
def admin_delete_masking_rule(rule_id: str):
    """
    SCR-ADMIN-001 마스킹 규칙 삭제.
    """
    ok = delete_rule(rule_id)
    if not ok:
        raise HTTPException(status_code=404, detail="마스킹 규칙을 찾을 수 없습니다.")
    return {"deleted": True, "rule_id": rule_id}
