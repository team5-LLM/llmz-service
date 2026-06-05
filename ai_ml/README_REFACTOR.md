# AI/ML Privacy Pipeline Refactor

## 목적

AI/ML 설정 로딩, Azure OpenAI client 생성, schema 정의, embedding 호출 로직을 정리했습니다.

## 구조

```text
ai_ml/
  common.py                  # 공통 설정/환경변수/Azure client/embedding helper
  pii_schema.py              # 공통 dataclass schema
  regex_detector.py          # 정규식 기반 PII/기밀정보 탐지
  llm_detector.py            # Azure OpenAI 기반 optional 2차 탐지
  span_utils.py              # span 정규화/병합/confidence 처리
  masking.py                 # span 기반 마스킹
  task_classifier.py         # 6개 상위 업무 유형 분류
  embedding_clusterer.py     # masked_text embedding + KMeans sub-clustering
  cluster_labeler.py         # cluster profile 및 label 생성
  recommendation_generator.py# 자동화 추천 카드 생성
  automation_matcher.py      # 부서/업무유형 기반 자동화 후보 매칭
  xai_explainer.py           # (DEPRECATED) LLM 설명 — BE 미연동, recommender.enrich_recommendation_xai 사용
  privacy_pipeline.py        # main orchestration
```

## 핵심 공개 함수

```python
from ai_ml.privacy_pipeline import (
    process_prompt_privacy,
    generate_cluster_based_recommendations,
)
```

## 주요사항

1. `_setting`, `_bool_setting`, `_chat_client`, `_chat_deployment` 중복 제거.
   - `common.py`의 `get_setting`, `bool_setting`, `azure_chat_client`, `chat_deployment`로 통합.

2. `AZURE_OPENAI_KEY` / `AZURE_OPENAI_API_KEY` 혼용 방어
   - 둘 중 하나만 있어도 동작하도록 alias 처리를 넣었습니다.

3. schema 중복 정리
   - `SensitiveSpan`, `CategoryResult`, `PrivacyProcessResult`는 `pii_schema.py`에서만 정의합니다.
   - `regex_detector.py`의 기존 `Span` import 호환성을 위해 `Span = SensitiveSpan` alias를 유지했습니다.

4. Azure embedding 중복 정리
   - `common.py`의 `embed_texts_azure()`를 공통으로 사용합니다.
   - `embedding_clusterer.py`는 Azure 실패 시 TF-IDF fallback을 사용합니다.
   - `task_classifier.py`는 Azure 실패 시 rule/anchor fallback을 사용합니다.

5. 보안 처리 유지
   - `PrivacyProcessResult`에는 원문 `prompt_text`를 넣지 않습니다.
   - `detected_spans.text`도 외부 반환 시 `[TYPE]` 형태로 치환합니다.
   - DB 저장 payload에 `prompt_text`, `raw_prompt`, `original_prompt`, `unmasked_prompt`가 없는지 검증합니다.

## 적용 방법

기존 프로젝트의 `ai_ml/` 폴더를 백업한 뒤, 이 폴더의 파일을 교체하거나 비교 병합하세요.

권장 순서:

1. 기존 `ai_ml/` 백업
2. `common.py` 추가
3. schema import가 `ai_ml.pii_schema` 기준인지 확인
4. Azure 환경변수 이름 정리
5. `process_prompt_privacy()` smoke test
6. `/api/upload` 통합 테스트

## 환경변수

필수는 아니며, 없으면 fallback으로 동작합니다.

```env
USE_AZURE_OPENAI=false
USE_LLM_PII_DETECTION=false
USE_LLM_TASK_CLASSIFICATION=false
USE_AZURE_EMBEDDING=false
USE_LLM_CLUSTER_LABEL=false
USE_LLM_RECOMMENDATION=false

AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_KEY=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=2024-08-01-preview

MASKING_CONFIDENCE_THRESHOLD=0.80
REJECT_ON_LOW_CONFIDENCE=true
STORE_MASKED_TEXT=true
MAX_LLM_RECOMMENDATION_CARDS=5
```
