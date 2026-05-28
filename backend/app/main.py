from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile

from app.services.analysis_pipeline import analyze_csv_file
from app.services.recommender import build_recommendation_detail

app = FastAPI(
    title="LLM Automation Opportunity API",
    description="CSV 기반 부서별 LLM 사용 패턴 분석 및 AI 업무 자동화 추천 API",
    version="0.2.0",
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


@app.get("/")
def root():
    return {
        "service": "LLM Automation Opportunity API",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/api/health")
def health_check():
    return {"status": "ok"}


@app.get("/api/analyze-sample")
def analyze_sample():
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}",
        )

    return analyze_csv_file(SAMPLE_CSV_PATH)


@app.post("/api/upload")
async def upload_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="CSV 파일만 업로드할 수 있습니다.")

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

    return result


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
