# 장희진 — Backend 투두

> **기준 문서**: `docs/API명세서.md` (체크리스트 BE 담당 **희진** 12개), [`docs/페이지별-API-정리.md`](./페이지별-API-정리.md) (FE 화면별·함께 갱신), 기능명세서 P0/P1  
> **책임 영역**: 데이터 입력·저장·이력·대시보드·위험 **조회 API** + Azure SQL/Blob  
> **협업**: `POST /api/upload` 만 유진님(`analyze_csv_file()`)과 공동

---

## P0 — 데모 / BE API 구현 (먼저)

### 0. 사전 준비

- [x] 로컬 `.env`에 Azure SQL 연결 (`AZURE_SQL_CONNECTION_STRING` 등) — 이력·대시보드가 빈 배열로 나오지 않게
- [ ] 유진님과 `analyze_csv_file()` **결과 JSON 스키마** 확정 — 아래 「협업」 참고
- [x] (선택) `docs/db_schema.md` 초안 — `upload_history`, `prompt_logs`, `department_stats`, `recommendations` 테이블·인덱스·보관 정책

### 1. Azure SQL 영속화 (대시보드·추천 연동의 전제)

- [x] (전환) 기존 Cosmos 연동(`cosmos.py`, `upload_history_service`) → Azure SQL + SQLAlchemy
- [x] `config.py` — DB 연결 문자열 env 추가
- [x] `db/sql.py` (또는 `session.py`) — SQLAlchemy 엔진·세션 헬퍼
- [x] `persistence_service.py` (신규) — `persist_analysis_result(upload_id, result)`
  - [x] `department_stats[]` → 테이블 N행 INSERT
  - [x] `recommendations[]` → 테이블 N행 INSERT
  - [x] `prompt_logs` → 전체 행 bulk insert (masked_logs)
- [x] `POST /api/upload` 성공 시 `persist_analysis_result()` 호출 (유진 `analyze_csv_file()` **이후**)

### 2. SCR-INPUT-001 — CSV 업로드 (본인 파트)

- [x] Azure Blob 임시 업로드 (`uploads/{upload_id}/...`)
- [x] `upload_history.blob_path`, `blob_purged_at` 기록
- [x] 분석 완료 후 Blob 삭제(또는 TTL) + 폐기 시각 저장
- [x] (공동) 유진 검증 실패 시 `attach_validation_errors()` 연동 확인

### 3. SCR-INPUT-004 — 데이터 입력 이력 (보완)

- [x] `GET /api/uploads/history/summary` — `by_status` 카운트
- [x] `GET /api/uploads/history` — §0.5 + `filename_q`, `status`, `uploaded_by` 필터
- [x] 공통 기간 파싱 유틸 (`month` → `from_date`/`to_date`, §0.5 규칙) — `app/utils/date_range.py`

### 4. SCR-DASH-001 — 부서별 LLM 사용 현황 (BE API)

> **FE 참고** (응답 스키마 맞출 때만): `Dashboard.tsx` · `DepartmentDetail.tsx`, 타입 `frontend/src/api/types.ts`  
> **BE P0**: §3.2 + §3.3 (메인 + 부서 상세) · §4.2 추천은 유진 · **FE 연결 목록 → 아래 「후순위 — FE API 연결」**

#### 4-A. P0 — 메인 대시보드 + 부서 상세 (`Dashboard.tsx` · `DepartmentDetail.tsx`) ✅

- [x] `dashboard_service.py` (신규)
  - [x] `resolve_upload_ids(date_range)` — 기간 내 completed `upload_id`, 없으면 **최신 1건** (FE query `upload_id` 없음)
  - [x] `department_stats` SQL 조회 + `task_distribution.ratio` **0~100 → 0~1** 변환 (API명세 §3.0)
- [x] `schemas/dashboard.py` (또는 기존 `Summary`/`DepartmentStat` 재사용)
- [x] `GET /api/dashboard/summary` (§3.2)
  - [x] query: **`month=YYYY-MM`** (DateFilter) + §0.5
  - [x] response: `{ period, summary }` — `total_logs` / `total_tokens` / `total_cost` (KPI 3카드)
- [x] `GET /api/dashboard/departments` (§3.3)
  - [x] response: `{ period, department_stats[] }` — 메인 3차트 + **부서 상세** (`dept`로 1행 pick, KPI·`WorkTypeChart`·`DepartmentDropdown`)
  - [ ] (P1) query `sort` — FE 미사용
- [x] SQL 미연결·upload 없음 → summary 0 / `department_stats: []`
- [x] 스모크 테스트 — `backend/tests/test_dashboard.py` (merge·ratio·API 200/400/422)

#### 4-B. P1 — 부서 상세 확장 (현재 FE 미구현)

- [x] `GET /api/dashboard/departments/{department}` (§3.4) — `granularity`, `task_sort`
  - [x] `trend[]` ← `prompt_logs` 시계열 · `tasks_by_priority[]` ← `recommendations` 정렬
  - [ ] FE에 추이 차트·우선순위 테이블 추가 시 연동 (BE ✅ · `tests/test_dashboard.py`)

### 5. 공통·보조 API (FE 와이어프레임)

- [ ] `GET /api/users/me` (§1.3, 단일 관리자 고정값)
- [ ] (P1) `GET /api/departments` (§4.5) — FE `DepartmentDropdown`은 §3.3으로 대체 중

### 6. SCR-RISK-001 — 부서별 Risk Overview (BE, P0)

- [ ] `GET /api/risk/overview` (§5.1, Critical/High 부서 요약)
- [ ] `GET /api/risk/levels` (§5.3, 정적 등급 정의 — 툴팁용)

### 7. 마무리

- [ ] `GET /api/risk/guidelines` (§5.4, `level` / `department` query)
- [x] `docs/API명세서.md` 상단 체크리스트 — §3.2·§3.3·§3.4 ✅ 갱신
- [ ] 업로드 → 이력 → 대시보드 → risk 스모크 테스트 (Swagger/Postman) — **dashboard API 단위 테스트 ✅** (`tests/test_dashboard.py` · §3.4 포함)

---

## P1 — 데모 강화 (P0 이후)

### 8. SCR-DASH-003 — 부서별 반복 프롬프트 비율

- [x] 부서별 반복률 집계 — `repeat_pattern_service.py` (heuristic · `cluster_id` 연동 준비)
- [x] BE API — `GET /api/dashboard/repeat-patterns` · `GET /api/dashboard/departments/{department}/repeat-patterns` (§3.5)
- [ ] FE 반복률 차트 연동 (BE ✅ · `tests/test_repeat_pattern.py`)

### 9. SCR-RISK-002 — 민감정보 유형별 통계

- [ ] `GET /api/risk/departments/{department}` (§5.2, `sensitive_breakdown[]`)
- [ ] `prompt_logs` 마스킹 플래그 기반 집계

### 10. 백엔드 Azure 배포 (팀 공용 API URL)

> **기능명세서 기준**: App Service **P0**, GitHub Actions 자동 배포 **P1**, Container Apps **P2**(App Service 대체).  
> **팀 판단**: 기능명세서상 Container Apps는 P2이나, 로컬 백엔드 공유·환경 세팅 부담이 커서 **배포 작업 자체는 P1로 앞당겨 진행**.  
> 1차는 **App Service + GitHub Actions** (기획서 P0/P1 경로). Container Apps는 여유 있을 때 검토.

- [ ] **배포 대상·방식 합의** — App Service(Linux) 우선 / Container Apps는 P2 백로그
- [ ] `Dockerfile` (선택) — Container Apps 또는 App Service 컨테이너 배포 대비
- [ ] **GitHub Actions** — `main` push 시 `backend/` → App Service 자동 배포 워크플로
- [ ] **App Service** 리소스 생성·설정
  - [ ] Python 3.x / FastAPI startup (`uvicorn app.main:app`)
  - [ ] App Service **환경변수**: `AZURE_SQL_CONNECTION_STRING`, Blob 연결, `WEBSITES_PORT` 등
  - [ ] `/api/health` 헬스 프로브 연동
- [ ] **Azure SQL 방화벽** — App Service 아웃바운드 IP 허용 (또는 VNet 통합)
- [ ] **Blob Storage** — 배포 환경에서 업로드 경로 동작 확인
- [ ] **CORS** — Static Web Apps(FE) origin 허용 (또는 API Gateway/Front Door 경로)
- [ ] **배포 URL 팀 공유** — Swagger `/docs` 등
- [ ] 배포 환경 **스모크 테스트** — upload → history → (dashboard) end-to-end

---

## 후순위 — FE ↔ BE API 연결 (BE 구현·스모크 후, 팀 협의)

> **지금 착수 X** — dashboard/risk BE API 완료 후 FE 담당과 일정 맞춰 진행. 연결할 항목만 미리 적어 둠.  
> **FE 담당**: 예은(YEN) 등 · **본인 역할**: BE API 준비·CORS·배포 URL 공유 (아래 BE 협업 항목)

### A. Dashboard · 부서 상세 (`api/index.ts` · 예은)

- [ ] `getDashboardSummary(month)` → `GET /api/dashboard/summary` (§3.2)
- [ ] `getDashboardDepartments(month)` → `GET /api/dashboard/departments` (§3.3)
- [ ] `Dashboard.tsx` — 더미 제거 · `DateFilter` `onChange` → query `month=YYYY-MM`
- [ ] `DepartmentDetail.tsx` — §3.3 `department_stats[]`에서 `dept` pick (KPI·`WorkTypeChart`·`DepartmentDropdown`)
- [ ] `getRecommendationsByDepartment(dept, month)` → `GET /api/recommendations/{department}` (§4.2 · `RecommendationList`)
- [ ] `required_resources`: BE `string[]` → FE 표시용 join (또는 `types.ts`를 `string[]`로 수정)

### B. 이력 · Risk · 기타 (해당 화면 FE 담당과 협의)

- [ ] `DataManagement` / INPUT-004 — `GET /api/uploads/history`, `/history/summary` (지수 등)
- [ ] `Risk.tsx` — `GET /api/risk/overview`, `/risk/levels`, `/risk/guidelines` (§5)
- [ ] Layout 사용자명 — `GET /api/users/me` (§1.3)
- [ ] FE `.env` — `VITE_API_BASE_URL` (§10 배포 URL 확정 후)

### C. BE 쪽 (연결 착수 시 본인)

- [ ] CORS — Static Web Apps origin 허용 확인 (§10과 함께)
- [ ] 팀 공유 — Swagger `/docs`, base URL, API명세 변경점
- [ ] 연결 후 E2E — upload → history → dashboard → department → risk (FE + BE)

---

## P2 — 백로그 (여유 있을 때)

- [ ] **Azure Container Apps** — App Service 대체/확장 (기능명세서 P2)
- [ ] SCR-INPUT-002 — 실시간 Gateway 수집 (Infra 공동)
- [ ] SCR-ADMIN-002 — SQL 보관 기간·자동 삭제 스케줄
- [ ] SCR-ADMIN-004 — 부서/사용자 매핑 API
- [ ] SCR-AUDIT-002 — App Insights 연동
- [ ] SCR-AUDIT-003 — 완전 삭제 API

---

## 유진님과 맞출 것 (본인 구현 X)

| 시점 | 내용 |
| --- | --- |
| 업로드 연동 전 | **`analyze_csv_file()` 반환 dict 스키마 고정** — `summary` / `department_stats[]` / `recommendations[]` / `sample_masked_logs[]` 필드명·타입·중첩 구조. 희진 `persist_analysis_result()`·대시보드 조회가 이 키에 의존 |
| 업로드 연동 전 | **`masked_logs` 전체 행 SQL 저장 여부** — 현재는 `masked_logs` 전체 → `prompt_logs`, API 응답은 `sample_masked_logs` 20건만. 유진 파이프라인 변경 시 깨지지 않게 합의 |
| SQL 저장 후 | 추천 API → 최신 `upload_id` / Azure SQL 조회 (유진) |
| 검증 실패 시 | `validation_errors` 리스트 형식 합의 |

---

## 추천 진행 순서

```text
Azure SQL 연결 → persist_analysis_result → upload 보완(Blob+저장) ✅
  → history summary/필터 ✅
  → dashboard summary + departments (Dashboard + DepartmentDetail P0) ✅
  → users/me · risk overview/levels/guidelines ← 지금
  → App Service 배포 + GitHub Actions (P1)
  → dashboard/{department} trend (§3.4) ✅ — FE 추이 차트 연동은 후순위
  → (후순위) FE API 연결 — 팀 협의 후 「후순위 — FE API 연결」
```

### 지금 1순위 3개

1. **`dashboard_service.py` + `GET /api/dashboard/summary`** — §3.2 · `month` query · `{ period, summary }`
2. **`GET /api/dashboard/departments`** — §3.3 · `department_stats[]` · ratio 0~1
3. **`GET /api/risk/overview` + `GET /api/risk/levels`** — §5.1·§5.3 (dashboard 다음)

### P1 (대시보드·공통)

- ~~**`GET /api/dashboard/departments/{department}`**~~ ✅ — `trend[]`·`tasks_by_priority[]` (FE 추이 차트 연동 ⬜)
- **`GET /api/users/me` + `GET /api/departments`** — §5 공통 API

### P1 병행 추천 (API 어느 정도 붙은 뒤)

- **§10 App Service 배포** — dashboard/risk API 1~2개만 올라가도 팀 공용 URL 확보에 유리. SQL/Blob env·방화벽만 맞추면 upload·history는 이미 배포 가능

---

## API명세서 — 희진 담당 엔드포인트 (2026-06-01)

| 상태 | Method | Path | 비고 |
| --- | --- | --- | --- |
| ⬜ | GET | `/api/users/me` | |
| ✅ | GET | `/api/uploads/history` | §0.5 기간 + 필터 |
| ✅ | GET | `/api/uploads/{upload_id}` | |
| ✅ | GET | `/api/uploads/history/summary` | |
| ✅ | GET | `/api/dashboard/summary` | §3.2 · `month` |
| ✅ | GET | `/api/dashboard/departments` | §3.3 · `department_stats[]` |
| ✅ | GET | `/api/dashboard/departments/{department}` | §3.4 · trend·tasks_by_priority (FE 미연동) |
| ✅ | GET | `/api/dashboard/repeat-patterns` | §3.5 · SCR-DASH-003 |
| ✅ | GET | `/api/dashboard/departments/{department}/repeat-patterns` | §3.5 · SCR-DASH-003 |
| ⬜ | GET | `/api/departments` | P1 · Dropdown은 §3.3 사용 중 |
| ⬜ | GET | `/api/risk/overview` | |
| ⬜ | GET | `/api/risk/departments/{department}` | P1 |
| ⬜ | GET | `/api/risk/levels` | |
| ⬜ | GET | `/api/risk/guidelines` | |
| ✅ | POST | `/api/upload` | Blob·이력·SQL 저장 ✅ |

> 상세: `docs/API명세서.md` §API 구현 현황 체크리스트
