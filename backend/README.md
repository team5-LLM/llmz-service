# LLM Automation Opportunity — Backend

부서별 LLM 사용 로그(CSV)를 분석해 **대시보드·위험도·자동화 추천** API를 제공하는 FastAPI 서비스입니다.

- **스택:** Python 3.11+, FastAPI, pandas, SQLAlchemy, pyodbc, Azure SQL, Azure Blob(선택)
- **운영 API 문서:** [Swagger](https://llmz-team05.azurewebsites.net/docs) · [헬스 체크](https://llmz-team05.azurewebsites.net/api/health)

## 빠른 시작

**백엔드는 이미 Azure에 배포되어 있습니다.** BE 코드를 수정하지 않는다면 Python·venv·`uvicorn` 설치 없이 아래만 하면 됩니다.

1. 프론트: `cd frontend` → `npm install` → `npm run dev`
2. `frontend/.env.development`가 운영 API를 가리키는지 확인 (기본값 그대로면 OK)

   ```env
   VITE_API_BASE_URL=https://llmz-team05.azurewebsites.net
   ```

3. 브라우저에서 대시보드 동작 확인. API만 직접 보려면 [Swagger](https://llmz-team05.azurewebsites.net/docs) 사용.

로컬에서 FastAPI를 띄우거나 BE 코드를 고칠 때만 → [로컬 실행 (선택)](#로컬-실행-선택) · [사전 설치](#사전-설치-로컬--be-개발용).

---

## 운영 배포 (완료)

팀 공용 백엔드는 **Azure App Service**에 배포되어 있습니다.

| 항목 | 값 |
| --- | --- |
| **서비스 URL** | https://llmz-team05.azurewebsites.net |
| **Swagger** | https://llmz-team05.azurewebsites.net/docs |
| **헬스 체크** | https://llmz-team05.azurewebsites.net/api/health |
| **Azure 리소스** | Web App `llmz-team05` (Production 슬롯) |
| **연동 DB / Blob** | `llmz-sql-team05` · `llmzteam05blob` (App Service 환경 변수로 연결) |

### 팀원 안내

| 상황 | 할 일 |
| --- | --- |
| 프론트만 개발 | `npm run dev` — 배포된 API 자동 사용 (`.env.development`) |
| API·업로드만 확인 | Swagger 또는 `GET /api/health` |
| 로컬 BE 디버깅 | `frontend/.env.local`에 `VITE_API_BASE_URL=http://127.0.0.1:8000` + [로컬 실행](#로컬-실행-선택) |

**배포 후 동작 확인**

1. `GET /api/health` → `status: ok`, `db`·`storage` 확인  
2. Swagger에서 예: `GET /api/dashboard/summary?month=2026-05`  
3. 대시보드에 데이터가 없으면 `POST /api/upload`로 CSV 업로드(또는 팀이 올려 둔 DB 데이터 사용)

**비밀값:** 운영 서버에는 `backend/.env`를 올리지 않습니다. Azure Portal → App Service `llmz-team05` → **구성 → 애플리케이션 설정**에 연결 문자열이 등록되어 있습니다. **로컬 개발만** `backend/.env`를 사용합니다.

### 자동 배포 (CI/CD)

`main` 브랜치에 **`backend/`** 또는 워크플로 파일이 push되면 GitHub Actions가 빌드·배포합니다.

- 워크플로: [`.github/workflows/main_llmz-team05.yml`](../.github/workflows/main_llmz-team05.yml)
- Python 3.11 · `pip install -r requirements.txt` 검증 후 `backend/`를 Web App에 배포
- 수동 실행: GitHub **Actions** → **Build and deploy Python app to Azure Web App - llmz-team05** → **Run workflow**

배포 후 1~2분 뒤 `/api/health`를 다시 확인하세요. 실패 시 Actions 로그·App Service **배포 센터**를 확인합니다.

### App Service 설정 참고

- **시작 명령:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **ODBC:** 이미지에 Driver 17/18 포함된 경우가 많음. SQL 연결 오류 시 연결 문자열·방화벽(IP) 확인
- **환경 변수 변경 후** App Service **다시 시작**이 필요할 수 있음

---

## 로컬 실행 (선택)

BE 수정·오프라인 분석·DB 연결 테스트가 필요할 때만 진행합니다. 프론트만 할 때는 [빠른 시작](#빠른-시작-대부분의-팀원)만 보면 됩니다.

`python -m venv`는 PowerShell뿐 아니라 Python이 PATH에 있는 **어떤 터미널**에서도 동일합니다. **활성화**만 쉘마다 다릅니다.

```bash
cd backend

python -m venv .venv   # 최초 1회

# 활성화 (하나만)
# PowerShell:  .\.venv\Scripts\Activate.ps1
# cmd:         .\.venv\Scripts\activate.bat
# Git Bash:    source .venv/Scripts/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| URL | 설명 |
| --- | --- |
| http://127.0.0.1:8000/docs | Swagger |
| http://127.0.0.1:8000/api/health | DB·Blob 설정 상태 |

로컬 BE를 쓸 때는 `frontend/.env.local`에 `VITE_API_BASE_URL=http://127.0.0.1:8000`을 설정합니다.

```bash
# DB 연결·테이블 초기화 테스트
python -m scripts.test_sql_connection

# 샘플 CSV 오프라인 분석 (DB 없이) → analysis_result.json
python run_analysis.py
```

API 샘플 엔드포인트(`GET /api/analyze-sample`)는 `data-sample/sample_llm_logs.csv`를 사용합니다 (`sample_llm_logs_5000.csv`와 별도).

## 사전 설치 (로컬 / BE 개발용)

운영 API만 쓸 때는 **Python·ODBC 설치 불필요**합니다.

| 순서 | 항목 | 설명 |
| --- | --- | --- |
| 1 | **Python 3.11+** | PATH 포함 설치 |
| 2 | **ODBC Driver 18 for SQL Server** | [다운로드](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server) — 로컬에서 Azure SQL 접속 시 |
| 3 | 가상환경 + `requirements.txt` | [로컬 실행](#로컬-실행-선택) |
| 4 | **`backend/.env`** | `.env.example` 복사 (**Git 커밋 금지**) |

### ODBC 드라이버 확인 (Windows)

```powershell
cd backend
.\.venv\Scripts\python.exe -c "import pyodbc; print(pyodbc.drivers())"
```

출력에 **`ODBC Driver 18 for SQL Server`**(또는 17)가 있으면 OK.

## 환경 변수 (로컬)

`.env.example` → `backend/.env`

| 변수 | 용도 |
| --- | --- |
| `AZURE_SQL_CONNECTION_STRING` | `mssql+pyodbc://...` (`!` → `%21`) |
| `AZURE_STORAGE_CONNECTION_STRING` | CSV Blob 임시 저장(선택) |
| `AZURE_STORAGE_CONTAINER` | 기본 `uploads` |
| `AZURE_OPENAI_*` | (예약) |

SQL·Blob 없이도 `/api/analyze-sample` 등은 동작합니다. **업로드 이력·대시보드**는 DB의 `completed` `prompt_logs`가 필요합니다.

## CSV 업로드 흐름 (`POST /api/upload`)

1. 파일 전체 **SHA-256** — 동일 내용으로 `completed` 이력이 있으면 **409** (`이미 처리된 파일입니다.`)
2. CSV 스키마 검증 (`log_schema.REQUIRED_COLUMNS`)
3. 마스킹 → 업무유형 분류 → Risk Score → 부서별 집계 → 추천 생성
4. `created_at` 기준 **월(YYYY-MM)별** 분할 후 `upload_history` + SQL persist (`file_content_sha256` 저장)
5. Blob 설정 시 CSV 임시 업로드 후 분석 완료 시 삭제

같은 파일을 다시 넣으려면 `POST /api/admin/reset-upload-data?confirm=RESET` 후 재업로드.

대시보드·Risk·추천은 **`prompt_logs.created_at`이 요청 기간에 포함된 `completed` 업로드**만 집계합니다.

**필수 컬럼:** `log_id`, `department`, `user_hash`, `prompt_text`, `model`, `input_tokens`, `output_tokens`, `total_tokens`, `cost`, `created_at`  
합성 데이터: [`../data-sample/README_sample_data.md`](../data-sample/README_sample_data.md)

## 분석 파이프라인

```text
CSV 읽기 → 스키마 검증 → 프롬프트 마스킹 → 업무유형 분류
  → Risk Score → 부서별 집계(user_count = 부서별 user_hash 고유 수)
  → Opportunity Score → 자동화 후보 추천 → (선택) Azure SQL / Blob
```

핵심: `app/services/analysis_pipeline.py`, `masking.py`, `scoring.py`, `recommender.py`

**XAI(추천 근거):** `recommender.enrich_recommendation_xai()` — `ai_ml/xai_explainer.py`는 미연동(deprecated).

## API 개요

기간: `?month=YYYY-MM` 또는 `?from_date=...&to_date=...`  
운영 Base URL: `https://llmz-team05.azurewebsites.net`

| 구분 | 메서드 | 경로 |
| --- | --- | --- |
| 공통 | GET | `/`, `/api/health`, `/api/users/me` |
| 샘플 | GET | `/api/analyze-sample` |
| 대시보드 | GET | `/api/dashboard/summary`, `/api/dashboard/departments`, `/api/dashboard/departments/{department}` |
| 반복 패턴 | GET | `/api/dashboard/repeat-patterns`, `.../departments/{department}/repeat-patterns` |
| 위험도 | GET | `/api/risk/overview`, `/api/risk/levels`, `/api/risk/departments/{department}` |
| 업로드 | POST | `/api/upload` |
| 이력 | GET | `/api/uploads/history`, `/api/uploads/history/summary`, `/api/uploads/{upload_id}` |
| 추천 | GET | `/api/recommendations`, `/api/recommendations/{department}`, `.../{task_label}`, `.../decision` |
| 정책 | GET | `/api/embedding/access-policy` |
| 관리 | GET/POST/PATCH/DELETE | `/api/admin/masking-rules`, `.../{rule_id}` |
| 관리 | POST | `/api/admin/reset-upload-data?confirm=RESET` |

## 디렉터리 구조

```text
backend/
├── app/
│   ├── main.py
│   ├── core/config.py
│   ├── db/
│   ├── models/
│   ├── schemas/
│   └── services/
├── scripts/
├── tests/
├── requirements.txt
├── run_analysis.py
└── .env.example
```

## 테스트

```bash
cd backend
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
