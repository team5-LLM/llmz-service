from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import tempfile

from app.services.analysis_pipeline import analyze_csv_file

app = FastAPI(
    title="LLM Automation Opportunity API",
    description="CSV 기반 부서별 LLM 사용 패턴 분석 및 AI 업무 자동화 추천 API",
    version="0.1.0",
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
    return {"service": "LLM Automation Opportunity API", "status": "running", "docs": "/docs"}

@app.get("/api/health")
def health_check():
    return {"status": "ok"}

@app.get("/api/analyze-sample")
def analyze_sample():
    if not SAMPLE_CSV_PATH.exists():
        raise HTTPException(status_code=404, detail=f"샘플 CSV를 찾을 수 없습니다: {SAMPLE_CSV_PATH}")
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
