from __future__ import annotations

from uuid import uuid4

# SCR-ADMIN-001 마스킹 규칙 관리
# MVP/P1 단계에서는 인메모리 저장소를 사용합니다.
# 서버 재시작 시 추가/수정/삭제된 규칙은 초기화됩니다.
MASKING_RULES: list[dict] = [
    {
        "rule_id": "rule-email",
        "rule_type": "regex",
        "pattern": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}",
        "replacement": "[EMAIL]",
        "category": "pii",
        "enabled": True,
    },
    {
        "rule_id": "rule-phone",
        "rule_type": "regex",
        "pattern": r"01[016789]-\\d{3,4}-\\d{4}|010-0000-0000",
        "replacement": "[PHONE]",
        "category": "pii",
        "enabled": True,
    },
    {
        "rule_id": "rule-secret",
        "rule_type": "regex",
        "pattern": r"(sk-[A-Za-z0-9_-]{8,}|API_KEY_[A-Z0-9_]+|fake-secret-token-[A-Za-z0-9_-]+|AZURE_OPENAI_KEY_SAMPLE)",
        "replacement": "[SECRET]",
        "category": "secret",
        "enabled": True,
    },
]


def list_rules() -> list[dict]:
    return MASKING_RULES


def create_rule(rule: dict) -> dict:
    item = {"rule_id": str(uuid4()), **rule}
    MASKING_RULES.append(item)
    return item


def update_rule(rule_id: str, payload: dict) -> dict | None:
    for item in MASKING_RULES:
        if item["rule_id"] == rule_id:
            for key, value in payload.items():
                if value is not None:
                    item[key] = value
            return item
    return None


def delete_rule(rule_id: str) -> bool:
    for idx, item in enumerate(MASKING_RULES):
        if item["rule_id"] == rule_id:
            MASKING_RULES.pop(idx)
            return True
    return False
