def get_embedding_access_policy() -> dict:
    """
    FUNC-PROC-011 Embedding 접근 통제.
    실제 RBAC/보관기간 인프라 연결 전, 접근 정책을 API로 반환합니다.
    """
    return {
        "status": "policy_defined",
        "embedding_storage": "not_persisted_in_p0_p1",
        "allowed_roles": ["admin", "ml_engineer"],
        "retention_days": 30,
        "restrictions": [
            "원문 prompt_text는 embedding 생성 대상에서 제외해야 합니다.",
            "마스킹된 masked_prompt만 embedding 생성에 사용할 수 있습니다.",
            "embedding vector는 운영 단계에서 RBAC가 적용된 저장소에만 보관합니다.",
            "현재 구현에서는 embedding 생성 및 저장을 수행하지 않습니다.",
        ],
        "future_extension": [
            "Azure SQL 또는 Vector DB 저장 시 role 기반 접근 제어 적용",
            "보관 기간 만료 시 embedding 삭제 작업 추가",
            "감사 로그 테이블과 연동하여 조회 이력 기록",
        ],
    }
