# LLM Automation Opportunity Backend Starter

CSV 업로드 기반 P0 분석 파이프라인용 FastAPI 백엔드 예시입니다.

## 팀 공통 사전 설치 (필수)

로컬에서 Azure SQL에 붙으려면 **팀원 PC마다** 아래를 설치합니다.

| 순서 | 항목 | 설명 |
| --- | --- | --- |
| 1 | **Python 3.11+** | PATH 포함 설치 |
| 2 | **ODBC Driver 18 for SQL Server** | Microsoft 공식 DB 드라이버 (아래 링크) |
| 3 | `pip install -r requirements.txt` | Python 패키지 (pyodbc 포함) |
| 4 | `backend/.env` | Azure SQL 연결 문자열 (Git 커밋 X) |

### ODBC Driver 18 설치

- 다운로드: [Microsoft ODBC Driver 18 for SQL Server](https://learn.microsoft.com/sql/connect/odbc/download-odbc-driver-for-sql-server)
- Windows: **x64** `msodbcsql.msi` 실행 → 설치 완료 후 **터미널 재시작**
- 설치 확인:

```powershell
python -c "import pyodbc; print(pyodbc.drivers())"
```

출력에 **`ODBC Driver 18 for SQL Server`** 가 보이면 OK.

> Driver 17도 동작합니다. **구형 `SQL Server` 드라이버만 있으면 Azure SQL 연결이 안 됩니다.**

## 실행 방법

```bash
cd backend
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### Azure SQL 연결 (backend/.env)

`.env.example` 을 복사해 `.env` 를 만들고, 비밀번호만 팀 Azure SQL admin 값으로 채웁니다.

```env
AZURE_SQL_CONNECTION_STRING=mssql+pyodbc://llmzadmin:<비밀번호>@llmz-sql-team05.database.windows.net:1433/llmz?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes&TrustServerCertificate=no
```

- 비밀번호 특수문자는 URL 인코딩 (`!` → `%21`, `@` → `%40`)
- **Azure Portal → SQL Server → Networking** 에서 본인 IP 허용 필요 (IP 바뀔 때마다 재추가)

### DB 연결 테스트

```bash
python -m scripts.test_sql_connection
```

### 서버 실행

```bash
uvicorn app.main:app --reload
```

브라우저에서 확인:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/api/health
```

`/api/health` 예시 (정상):

```json
{
  "status": "ok",
  "db": {
    "configured": true,
    "odbc_driver": "ODBC Driver 18 for SQL Server",
    "ready": true,
    "message": "connected"
  }
}
```

드라이버 미설치 시 `odbc_driver: null`, `message`에 설치 안내가 표시됩니다.

## API

- `GET /api/analyze-sample`: `data-sample/sample_llm_logs.csv` 분석
- `POST /api/upload`: CSV 업로드 후 즉시 분석 (+ upload_history SQL 저장)
- `GET /api/uploads/history`: 업로드 이력 목록
- `GET /api/uploads/{upload_id}`: 업로드 이력 상세

## 분석 흐름

CSV 읽기 → 스키마 검증 → 프롬프트 마스킹 → 업무유형 분류 → Risk Score 계산 → 부서별 집계 → Opportunity Score 계산 → 자동화 후보 추천
