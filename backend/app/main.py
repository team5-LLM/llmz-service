from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile

from app.schemas.log_schema import MaskingRuleCreate, MaskingRuleUpdate
from app.services.analysis_pipeline import analyze_csv_file
from app.services.csv_loader import inspect_csv
from app.services.recommender import build_recommendation_detail
from app.services.admin_rules import list_rules, create_rule, update_rule, delete_rule
from app.services.embedding_access import get_embedding_access_policy

app = FastAPI(
    title="LLMZ Target Feature API",
    description="요청된 ID 기능만 포함한 CSV 기반 LLM 사용 로그 분석 백엔드",
    version="1.0.0",
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


def _analyze_sample_or_404() -> dict:
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(status_code=404, detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}")

    inspection = inspect_csv(SAMPLE_CSV_PATH)
    if not inspection["valid"]:
        raise HTTPException(status_code=400, detail=inspection)

    return analyze_csv_file(SAMPLE_CSV_PATH)


@app.get("/")
def root():
    return {"service": "LLMZ Target Feature API", "status": "running", "docs": "/docs"}


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/analyze-sample")
def analyze_sample():
    """
    샘플 CSV 분석용 유지 API.
    """
    return _analyze_sample_or_404()


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    """
    SCR-INPUT-001 CSV 로그 업로드.
    CSV 파일을 업로드하면 유효성 검증 후 분석 결과를 반환합니다.
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")

    content = await file.read()

    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        inspection = inspect_csv(tmp_path)
        if not inspection["valid"]:
            return inspection

        return analyze_csv_file(tmp_path)
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass


@app.get("/api/recommendations")
def get_recommendations():
    """
    SCR-RECO-001 AI 자동화 후보 카드 리스트.
    """
    result = _analyze_sample_or_404()
    return {
        "count": len(result["recommendations"]),
        "recommendations": result["recommendations"],
    }


@app.get("/api/recommendations/{department}")
def get_recommendations_by_department(department: str):
    """
    부서별 추천 후보 리스트 조회.
    SCR-RECO-001을 부서 기준으로 필터링합니다.
    """
    result = _analyze_sample_or_404()
    items = [item for item in result["recommendations"] if item["department"] == department]
    return {"department": department, "count": len(items), "recommendations": items}


@app.get("/api/recommendations/{department}/{task_label}")
def get_recommendation_detail(department: str, task_label: str):
    """
    SCR-RECO-002 추천 상세 보기.
    """
    result = _analyze_sample_or_404()

    target = None
    for item in result["recommendations"]:
        if item["department"] == department and item["task_label"] == task_label:
            target = item
            break

    if target is None:
        raise HTTPException(status_code=404, detail=f"{department} - {task_label} 추천 정보를 찾을 수 없습니다.")

    return build_recommendation_detail(target)


@app.get("/api/recommendations/{department}/{task_label}/decision")
def get_risk_based_decision(department: str, task_label: str):
    """
    SCR-RECO-004 Risk 기반 도입 판단.
    """
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
