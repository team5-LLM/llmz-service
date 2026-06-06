"""
[DEPRECATED — 런타임 미사용]

AI/ML 연동(e75d870~) 이후 `ai_ml.privacy_pipeline.process_prompt_privacy`로 대체됨.
Risk 플래그 호환은 `app.utils.sensitive_flags` 어댑터가 담당.
삭제 전 admin_rules API·문서 참조 여부 확인 필요.
"""

import re
from dataclasses import dataclass, asdict

from app.services.admin_rules import list_rules


@dataclass
class MaskingResult:
    masked_prompt: str
    pii_detected: bool = False
    customer_detected: bool = False
    confidential_detected: bool = False
    financial_detected: bool = False
    legal_detected: bool = False
    secret_detected: bool = False
    hr_detected: bool = False
    exposure_detected: bool = False

    def to_dict(self):
        return asdict(self)


CUSTOMER_RE = re.compile(r"(가상고객[A-Z가-힣]?|샘플고객[A-Z가-힣]?|테스트고객[A-Z가-힣]?|데모고객[A-Z가-힣]?)")

CONFIDENTIAL_KEYWORDS = ["계약서", "위약금", "해지 조건", "NDA", "기밀", "내부회의록", "계약 조건", "비공개", "내부자료"]
FINANCIAL_KEYWORDS = ["매출", "비용", "급여", "정산", "견적", "영업 실적", "계약 성공률", "손익", "예산", "가격 정책"]
LEGAL_KEYWORDS = ["소송", "법무", "법률", "검토 의견", "약관", "컴플라이언스", "분쟁"]
HR_KEYWORDS = ["인사평가", "면접 피드백", "채용", "지원자", "온보딩", "연봉", "퇴사"]


def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)


def apply_admin_masking_rules(text: str) -> tuple[str, dict[str, bool]]:
    """
    SCR-ADMIN-001 마스킹 규칙 관리와 연동되는 마스킹 처리.
    admin_rules.py의 인메모리 규칙을 읽어서 regex/keyword 치환을 수행합니다.
    """
    masked = text
    flags = {
        "pii_detected": False,
        "secret_detected": False,
    }

    for rule in list_rules():
        if not rule.get("enabled", True):
            continue

        rule_type = rule.get("rule_type")
        pattern = rule.get("pattern", "")
        replacement = rule.get("replacement", "[MASKED]")
        category = rule.get("category", "custom")

        if not pattern:
            continue

        before = masked

        if rule_type == "regex":
            masked = re.sub(pattern, replacement, masked, flags=re.IGNORECASE)
        elif rule_type == "keyword":
            masked = masked.replace(pattern, replacement)

        changed = before != masked

        if changed and category == "pii":
            flags["pii_detected"] = True
        if changed and category == "secret":
            flags["secret_detected"] = True

    return masked, flags


def mask_prompt(prompt_text: str) -> MaskingResult:
    """
    FUNC-PROC-009 원문 폐기 검증 전처리.
    명확한 민감값은 마스킹하고, 기업 기밀 키워드는 flag로 탐지합니다.
    """
    text = prompt_text or ""
    masked, admin_flags = apply_admin_masking_rules(text)

    customer_detected = False
    if CUSTOMER_RE.search(masked):
        customer_detected = True
        masked = CUSTOMER_RE.sub("[CUSTOMER]", masked)

    confidential_detected = contains_any(text, CONFIDENTIAL_KEYWORDS)
    financial_detected = contains_any(text, FINANCIAL_KEYWORDS)
    legal_detected = contains_any(text, LEGAL_KEYWORDS)
    hr_detected = contains_any(text, HR_KEYWORDS)

    pii_detected = admin_flags["pii_detected"]
    secret_detected = admin_flags["secret_detected"]

    exposure_detected = any([
        pii_detected,
        secret_detected,
        customer_detected,
        confidential_detected,
        financial_detected,
        legal_detected,
        hr_detected,
    ])

    return MaskingResult(
        masked_prompt=masked,
        pii_detected=pii_detected,
        customer_detected=customer_detected,
        confidential_detected=confidential_detected,
        financial_detected=financial_detected,
        legal_detected=legal_detected,
        secret_detected=secret_detected,
        hr_detected=hr_detected,
        exposure_detected=exposure_detected,
    )
