# sample_llm_logs.csv

이 파일은 프로젝트 데모를 위해 생성한 합성 데이터입니다.

- 실제 개인정보, 실제 기업 로그, 실제 API Key, 실제 고객정보는 포함되어 있지 않습니다.
- 민감정보처럼 보이는 값은 마스킹 기능 테스트를 위한 가짜 샘플입니다.
- `example.invalid`, `010-0000-0000`, `가상고객A`, `API_KEY_SAMPLE_DO_NOT_USE_0000` 등은 모두 데모용 합성 문자열입니다.
- `cost`는 실제 Azure/OpenAI 과금표가 아니라 프로젝트 테스트용 가상 비용입니다.
- 분석 결과 컬럼인 `masked_prompt`, `task_label`, `risk_score`, `opportunity_score` 등은 CSV에 미리 넣지 않았습니다. 서비스가 분석 후 생성해야 하는 값입니다.

## 컬럼

- log_id
- department
- user_hash
- prompt_text
- model
- input_tokens
- output_tokens
- total_tokens
- cost
- created_at
