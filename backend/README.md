# LLMZ Backend - Target Feature Set

이미지에 있는 ID 기능만 구현한 백엔드 코드입니다.

## 구현된 기능

### P0
- FUNC-PROC-006: Risk Score 계산
- FUNC-PROC-007: Opportunity Score 계산
- FUNC-PROC-008: 자동화 후보 매칭
- FUNC-PROC-009: 원문 폐기 검증
- SCR-INPUT-001: CSV 로그 업로드
- SCR-RECO-001: AI 자동화 후보 카드 리스트
- SCR-RECO-002: 추천 상세 보기
- SCR-RECO-004: Risk 기반 도입 판단

### P1
- SCR-RECO-003: 추천 근거 설명(XAI)
- FUNC-PROC-011: Embedding 접근 통제
- SCR-ADMIN-001: 마스킹 규칙 관리

## 실행 방법

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

## 샘플 CSV 위치

샘플 분석 API를 사용하려면 아래 구조여야 합니다.

```text
project-root/
  data-sample/
    sample_llm_logs.csv
  backend/
    app/
      main.py
```
