# llmz-service

부서별 LLM 사용 로그를 분석해 보안 위험과 AI 업무 자동화 기회를 함께 찾는 대시보드입니다.
프롬프트 원문을 장기 저장하지 않는다는 전제에서 민감정보를 마스킹하고, 업무 유형과 점수를 계산해 부서 단위 추천 카드로 제공합니다.

## 프로젝트 개요

- **목표**: 단순 사용량/비용 모니터링을 넘어, 어떤 부서의 어떤 업무를 AI 서비스로 전환할지 추천 (보안성을 매우 강조)
- **핵심 원칙**: 개인 감시가 아닌 부서 단위 업무 개선, 프롬프트 원문 미보관, 민감정보 마스킹 우선

## 주요 기능

- CSV 기반 LLM 사용 로그 업로드 및 샘플 로그 분석
- 이메일, 전화번호, 고객명, API Key, 기밀/재무/법무/HR 키워드 탐지 및 마스킹
- 업무 유형 분류 (본 프로젝트는 k = 6개, 아래 유형으로 진행)
  - 보고서 작성형
  - 코드 생성형
  - 고객 응대형
  - 문서 요약형
  - 데이터 분석형
  - 단순 검색/질문형
- 부서별 사용량, 비용, 위험도, 자동화 후보 집계
- Risk Score와 Opportunity Score 기반 자동화 추천
- 업로드 이력 조회 및 상태 추적

## 분석 흐름

```text
CSV 업로드
-> 스키마 검증
-> 프롬프트 민감정보 마스킹
-> 업무 유형 분류
-> Risk Score 계산
-> 부서별 집계
-> Opportunity Score 계산
-> 자동화 후보 추천
```

## 점수 기준

**Opportunity Score**

```text
사용 빈도 30% + 반복성 25% + 비용 영향 20% + 다수 사용자 여부 15% + ((남은 10% 어떻게 반영할건지?))
```

**Risk Score**

```text
개인정보 위험도 30% + 기밀정보 위험도 25% + 고객정보 위험도 20% + 재무/법무 민감도 15% + 원문 노출 가능성 10%
```

| Risk Score | 등급 | 의미 |
| --- | --- | --- |
| 0-30 | Low | 일반 업무 프롬프트 |
| 31-60 | Medium | 일부 민감정보 가능성 |
| 61-80 | High | 개인정보/기밀정보 포함 가능성 높음 |
| 81-100 | Critical | 원문 저장 금지, 관리자 검토 필요 |

## 기술 스택

- **Frontend**: React, TypeScript, Vite, Tailwind CSS
- **Backend**: FastAPI, Python, pandas
- **Storage**: Azure Cosmos DB (업로드 이력 저장, 미설정 시 분석 기능은 동작)
- **Sample Data**: `data-sample/sample_llm_logs.csv`

## 로컬 실행 방법

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API 문서는 다음 주소에서 확인합니다.

```text
http://127.0.0.1:8000/docs
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

프론트엔드는 기본적으로 `http://localhost:8000`의 백엔드 API를 호출합니다.

## 주요 API

| Method | Endpoint | 설명 |
| --- | --- | --- |
| `GET` | `/api/health` | 서비스 상태 확인 |
| `GET` | `/api/analyze-sample` | 샘플 CSV 분석 |

## 책임 있는 AI 원칙

- 프롬프트 원문은 장기 저장하지 않고 마스킹/분류 후 폐기합니다.
- 개인별 위험도, 비용, 프롬프트 순위는 제공하지 않습니다.
- 모든 분석은 부서 단위 통계와 추천 중심으로 제공합니다.
- Risk Score와 Opportunity Score를 분리해, 자동화 가치가 높아도 위험도가 높으면 보안 검토 대상으로 분류합니다.
- Embedding 등 원문 유추 가능성이 있는 파생 데이터는 민감 데이터로 취급하는 것을 원칙으로 합니다.

## 로드맵

- **P0**: CSV 업로드, 마스킹, 업무 유형 분류, Risk/Opportunity Score, 추천 카드
- **P1**: Embedding 기반 세부 업무 군집화, 반복 프롬프트/비용 트렌드, 추천 근거 설명 강화
- **P2**: Event Hub 기반 실시간 수집, Edge Masking Gateway, SSO/RBAC, Key Vault, 감사 로그
