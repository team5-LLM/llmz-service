# LLM Automation Opportunity Backend Starter

CSV 업로드 기반 P0 분석 파이프라인용 FastAPI 백엔드 예시입니다.

## 실행 방법

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
uvicorn app.main:app --reload
```

브라우저에서 확인:

```text
http://127.0.0.1:8000/docs
```

## API

- `GET /api/analyze-sample`: `data-sample/sample_llm_logs.csv` 분석
- `POST /api/upload`: CSV 업로드 후 즉시 분석

## 분석 흐름

CSV 읽기 → 스키마 검증 → 프롬프트 마스킹 → 업무유형 분류 → Risk Score 계산 → 부서별 집계 → Opportunity Score 계산 → 자동화 후보 추천
