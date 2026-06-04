# Azure SQL Database 스키마 (llmz-service)

> **최종 갱신**: 2026-06-03  
> **DB**: Azure SQL Database (`llmz-sql-team05` / DB `llmz`)  
> **ORM**: SQLAlchemy 2.x — `Base.metadata.create_all()` + `init_db()` 시 **선택적 ALTER** (`migrate_nvarchar`, `migrate_upload_history_file_hash`)

---

## 1. 개요

**4개 테이블**. 백엔드가 실제로 읽고 쓰는 스키마 기준 문서입니다.

```text
upload_history (1 CSV → N행 가능, created_at 월별 split)
    │
    ├── department_stats (N)   … upload_id × department
    ├── recommendations (N)    … upload_id × (department, task_label)
    └── prompt_logs (N)        … upload_id × log_id (마스킹 로그 전 행)
```

| 항목 | 내용 |
| --- | --- |
| 논리 FK | `department_stats` / `recommendations` / `prompt_logs`.`upload_id` → `upload_history.upload_id` |
| 물리 FK | 미선언 (앱 레벨 연결) |
| 원문 | `prompt_text` **DB·API 미저장** — `prompt_logs.masked_prompt` 만 |
| 월별 업로드 | 한 CSV에 여러 달 로그 → **`upload_id`·`department_scope=YYYY-MM` 별로 분리** persist |
| 대시보드·Risk·추천 집계 | `prompt_logs.created_at` 기간 필터 (**`uploaded_at` 아님**) |
| 이력·DateFilter(관리) | `upload_history.uploaded_at` = 파일을 올린 시각 |
| 중복 파일 | `file_content_sha256` — **completed** 동일 해시 재업로드 시 **409** (분석·INSERT 안 함) |

---

## 2. 테이블 상세

### 2.1 `upload_history`

SCR-INPUT-004 이력 API. **성공 시 CSV 1파일당 `log_months` 개수만큼 행**이 생길 수 있음(월별 `upload_id`).

| 컬럼 | SQL 타입 | NULL | 설명 |
| --- | --- | --- | --- |
| `upload_id` | `NVARCHAR(36)` PK | NO | 업로드 UUID (API `upload_id` / `upload_ids[]`) |
| `id` | `NVARCHAR(36)` | NO | 내부 문서 ID (별도 UUID) |
| `filename` | `NVARCHAR(512)` | NO | 원본 파일명 |
| `file_content_sha256` | `NVARCHAR(64)` | YES | 업로드 파일 전체 **SHA-256 hex** — 성공 업로드에 저장, 중복 검사용 |
| `uploaded_at` | `NVARCHAR(40)` | NO | ISO-8601 UTC (파일 업로드 시각) |
| `uploaded_by` | `NVARCHAR(128)` | NO | 기본 `anonymous` |
| `department_scope` | `NVARCHAR(64)` | NO | 성공·월별 split 시 **`YYYY-MM`** · 실패 등은 `ALL` |
| `total_rows` | `INT` | NO | 해당 scope 월 로그 행 수 |
| `valid_rows` | `INT` | NO | 유효 행 수 |
| `invalid_rows` | `INT` | NO | 검증 실패 행 수 |
| `validation_errors_json` | `NVARCHAR(MAX)` | YES | `[{row_index, errors[]}]` JSON |
| `blob_path` | `NVARCHAR(1024)` | YES | Blob 논리 경로 (첫 `upload_id`만, 선택) |
| `blob_purged_at` | `NVARCHAR(40)` | YES | Blob 삭제 시각 |
| `status` | `NVARCHAR(32)` | NO | `pending` / `processing` / `completed` / `failed` |
| `status_history_json` | `NVARCHAR(MAX)` | NO | 상태 변경 이력 JSON |
| `error_message` | `NVARCHAR(MAX)` | YES | 실패 메시지 |
| `summary_json` | `NVARCHAR(MAX)` | YES | 해당 월 `UploadSummary` JSON |
| `completed_at` | `NVARCHAR(40)` | YES | 완료/실패 시각 |
| `duration_ms` | `INT` | YES | 처리 소요(ms) |

**인덱스**

| 이름 | 컬럼 | 비고 |
| --- | --- | --- |
| `ix_upload_history_uploaded_at` | `uploaded_at` | |
| `ix_upload_history_file_sha256` | `file_content_sha256` | `WHERE file_content_sha256 IS NOT NULL` (기존 DB는 `init_db` 시 생성) |

**중복 파일 정책**

- `POST /api/upload` 시작 시: 동일 `file_content_sha256` + `status=completed` 존재 → **409** `이미 처리된 파일입니다.`
- `POST /api/admin/reset-upload-data?confirm=RESET` 후 동일 파일 재업로드 가능
- 배포 이전 `completed` 행은 해시 NULL → **최초 1회** 동일 파일 재적재 가능

**코드**

- ORM: `backend/app/models/upload_history_table.py`
- Pydantic: `backend/app/models/upload_history.py`
- CRUD·중복 조회: `backend/app/services/upload_history_service.py`
- 마이그레이션: `backend/app/db/migrate_upload_history_file_hash.py` (`init_db` 자동 호출)

---

### 2.2 `department_stats`

업로드 1건(`upload_id`) × 부서 1개 = 1행. 대시보드 API는 기간 내 **`prompt_logs` 재집계**도 사용.

| 컬럼 | SQL 타입 | NULL | 설명 |
| --- | --- | --- | --- |
| `id` | `INT` PK (IDENTITY) | NO | 자동 증가 |
| `upload_id` | `NVARCHAR(36)` | NO | 업로드 FK (논리) |
| `department` | `NVARCHAR(128)` | NO | 부서명 (Unicode/NVARCHAR) |
| `total_requests` | `INT` | NO | 요청 건수 |
| `total_tokens` | `INT` | NO | 토큰 합 |
| `total_cost` | `FLOAT` | NO | 비용 합 |
| `user_count` | `INT` | NO | 고유 `user_hash` 수 |
| `avg_risk_score` | `FLOAT` | NO | 평균 Risk Score |
| `risk_level` | `NVARCHAR(16)` | NO | `Low` / `Medium` / `High` / `Critical` |
| `high_critical_ratio` | `FLOAT` | NO | High+Critical 비율(%) |
| `task_distribution_json` | `NVARCHAR(MAX)` | NO | `[{label, count, ratio}]` JSON (`ratio` 0~1) |

**제약·인덱스**

| 이름 | 종류 | 컬럼 |
| --- | --- | --- |
| `uq_department_stats_upload_dept` | UNIQUE | `upload_id`, `department` |
| `ix_department_stats_upload_id` | INDEX | `upload_id` |

**데이터 출처**: `analyze_csv_file()` → 월별 split → `persist_analysis_result()`

---

### 2.3 `recommendations`

업로드 1건 × (부서, 업무유형) 1행. **`기타` 제외**.

| 컬럼 | SQL 타입 | NULL | 설명 |
| --- | --- | --- | --- |
| `id` | `INT` PK (IDENTITY) | NO | 자동 증가 |
| `upload_id` | `NVARCHAR(36)` | NO | 업로드 FK (논리) |
| `department` | `NVARCHAR(128)` | NO | 부서명 |
| `task_label` | `NVARCHAR(64)` | NO | 업무유형 |
| `service_name` | `NVARCHAR(256)` | NO | 자동화 서비스명 |
| `expected_effect` | `NVARCHAR(MAX)` | NO | 기대 효과 |
| `difficulty` | `NVARCHAR(16)` | NO | `하` / `중` / `중상` / `상` |
| `required_resources_json` | `NVARCHAR(MAX)` | NO | Azure 리소스 목록 JSON |
| `opportunity_score` | `INT` | NO | 0~100 |
| `risk_score` | `FLOAT` | NO | 0~100 |
| `risk_level` | `NVARCHAR(16)` | NO | Risk 등급 |
| `decision` | `NVARCHAR(64)` | NO | 도입 판단 문구 |
| `decision_level` | `NVARCHAR(32)` | NO | `proceed` / `review` / `low_priority` |
| `decision_message` | `NVARCHAR(MAX)` | NO | 판단 설명 |
| `required_action` | `NVARCHAR(MAX)` | NO | 필요 조치 |
| `reason_json` | `NVARCHAR(MAX)` | NO | 추천 근거 JSON 배열 |

**제약·인덱스**

| 이름 | 종류 | 컬럼 |
| --- | --- | --- |
| `uq_recommendations_upload_dept_task` | UNIQUE | `upload_id`, `department`, `task_label` |
| `ix_recommendations_upload_id` | INDEX | `upload_id` |

**조회**: `recommendation_service` — `prompt_logs.created_at` 필터 + 재집계 병행

---

### 2.4 `prompt_logs`

업로드 1건 × CSV `log_id` 1행. **마스킹 프롬프트만** 저장.

| 컬럼 | SQL 타입 | NULL | 설명 |
| --- | --- | --- | --- |
| `id` | `INT` PK (IDENTITY) | NO | 자동 증가 |
| `upload_id` | `NVARCHAR(36)` | NO | 업로드 FK (논리) |
| `log_id` | `INT` | NO | CSV `log_id` |
| `department` | `NVARCHAR(128)` | NO | 부서명 |
| `user_hash` | `NVARCHAR(128)` | NO | 익명 사용자 해시 |
| `model` | `NVARCHAR(64)` | NO | LLM 모델명 |
| `input_tokens` | `FLOAT` | NO | 입력 토큰 |
| `output_tokens` | `FLOAT` | NO | 출력 토큰 |
| `total_tokens` | `FLOAT` | NO | 합계 토큰 |
| `cost` | `FLOAT` | NO | 가상 비용 |
| `created_at` | `NVARCHAR(40)` | NO | LLM 사용 시각 — **대시보드 `month=` 집계 기준** |
| `masked_prompt` | `NVARCHAR(MAX)` | NO | 마스킹된 프롬프트 |
| `task_label` | `NVARCHAR(64)` | NO | 업무유형 |
| `risk_score` | `INT` | NO | 0~100 |
| `risk_level` | `NVARCHAR(16)` | NO | Risk 등급 |
| `original_prompt_stored` | `BIT` | NO | 기본 `false` |
| `original_discard_verified` | `BIT` | NO | 기본 `true` |
| `discard_verification_message` | `NVARCHAR(MAX)` | YES | 폐기 검증 메시지 |
| `pii_detected` ~ `exposure_detected` | `BIT` | NO | 마스킹·Risk 플래그 (8종) |

**제약·인덱스**

| 이름 | 종류 | 컬럼 |
| --- | --- | --- |
| `uq_prompt_logs_upload_log` | UNIQUE | `upload_id`, `log_id` |
| `ix_prompt_logs_upload_id` | INDEX | `upload_id` |
| `ix_prompt_logs_upload_department` | INDEX | `upload_id`, `department` |

**P1 예정 (ORM 주석만)**: `cluster_id`, `pattern_label`

---

## 3. 데이터 흐름

### 3.1 `POST /api/upload` (성공 경로)

```text
multipart CSV 수신
  │
  ├─ file_content_sha256 계산
  ├─ completed 이력에 동일 해시? → 409 (분석·DB INSERT 없음)
  │
  ├─ tempfile → analyze_csv_file()
  ├─ split_analysis_result_by_month()  (masked_logs.created_at 기준)
  │
  ├─ (선택) 첫 upload_id만 Blob 임시 업로드 → blob_path → 분석 후 삭제
  │
  └─ 월마다:
        upload_history INSERT (department_scope=YYYY-MM, file_content_sha256 동일)
        → processing → completed
        → persist_analysis_result(upload_id, 월별 result)
              ├─ department_stats
              ├─ recommendations
              └─ prompt_logs
```

### 3.2 조회·집계

```text
Dashboard / Risk / repeat-patterns / recommendations(재집계)
  → completed upload_id 목록
  → prompt_logs WHERE created_at ∈ [period]
  → build_* 재집계 (upload_id 스냅샷 fallback 없음)

GET /api/uploads/history
  → upload_history WHERE uploaded_at ∈ [period]  (업로드일 기준)
```

### 3.3 `POST /api/admin/reset-upload-data?confirm=RESET`

```text
DELETE prompt_logs, recommendations, department_stats, upload_history (전체)
(선택) Blob uploads 컨테이너 purge — Storage 설정 시
```

**동일 `upload_id` 재 persist**: `persist_analysis_result` 가 해당 id의 3테이블 DELETE 후 INSERT (멱등).

---

## 4. 보관·보안 정책 (현재 코드)

| 항목 | 정책 |
| --- | --- |
| 원문 `prompt_text` | DB·API **미저장** |
| CSV 원본 | 메모리·tempfile 분석 |
| 마스킹 텍스트 | `prompt_logs.masked_prompt` |
| 개인 식별 | `user_hash` 만 |
| 중복 CSV | `file_content_sha256` + completed 이력 → 409 |
| 행 단위 중복 | **미구현** (P2·실시간 수집 시 검토) |

---

## 5. 스키마 변경·마이그레이션

| 방식 | 용도 |
| --- | --- |
| `create_all()` | 신규 테이블 생성 |
| `migrate_varchar_to_nvarchar()` | 한글 부서명 VARCHAR → NVARCHAR (분석 3테이블 재생성) |
| `migrate_upload_history_file_hash()` | `file_content_sha256` 컬럼·인덱스 ADD |

둘 다 **`init_db()`** (앱 `lifespan` 시작 시) 에서 자동 실행.

| 변경 종류 | 수정 포인트 |
| --- | --- |
| nullable 컬럼 | ORM + `upload_history_service._apply_doc_to_row` (+ migrate 모듈) |
| NOT NULL 컬럼 | 위 + backfill |
| JSON 내부 | 파이프라인 + persist |
| 테이블 추가 | ORM + `init_db` import + service + API |

---

## 6. 관련 파일 맵

```
backend/app/db/sql.py
backend/app/db/migrate_nvarchar.py
backend/app/db/migrate_upload_history_file_hash.py
backend/app/utils/file_hash.py
backend/app/models/upload_history_table.py
backend/app/models/upload_history.py
backend/app/models/analysis_result_tables.py
backend/app/services/upload_history_service.py
backend/app/services/persistence_service.py
backend/app/services/dashboard_service.py
backend/app/services/reset_service.py
backend/app/main.py
```

