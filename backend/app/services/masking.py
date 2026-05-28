import re
from dataclasses import dataclass, asdict

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

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"01[016789]-\d{3,4}-\d{4}|010-0000-0000")
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{8,}|API_KEY_[A-Z0-9_]+|fake-secret-token-[A-Za-z0-9_-]+|AZURE_OPENAI_KEY_SAMPLE)",
    re.IGNORECASE,
)
CUSTOMER_RE = re.compile(r"(가상고객[A-Z가-힣]?|샘플고객[A-Z가-힣]?|테스트고객[A-Z가-힣]?|데모고객[A-Z가-힣]?)")

CONFIDENTIAL_KEYWORDS = ["계약서", "위약금", "해지 조건", "NDA", "기밀", "내부회의록", "계약 조건"]
FINANCIAL_KEYWORDS = ["매출", "비용", "급여", "정산", "견적", "영업 실적", "계약 성공률"]
LEGAL_KEYWORDS = ["소송", "법무", "법률", "검토 의견", "약관", "컴플라이언스"]
HR_KEYWORDS = ["인사평가", "면접 피드백", "채용", "지원자", "온보딩"]

def contains_any(text: str, keywords: list[str]) -> bool:
    return any(keyword.lower() in text.lower() for keyword in keywords)

def mask_prompt(prompt_text: str) -> MaskingResult:
    text = prompt_text or ""
    masked = text
    pii_detected = False
    secret_detected = False
    customer_detected = False

    if EMAIL_RE.search(masked):
        pii_detected = True
        masked = EMAIL_RE.sub("[EMAIL]", masked)

    if PHONE_RE.search(masked):
        pii_detected = True
        masked = PHONE_RE.sub("[PHONE]", masked)

    if SECRET_RE.search(masked):
        secret_detected = True
        masked = SECRET_RE.sub("[SECRET]", masked)

    if CUSTOMER_RE.search(masked):
        customer_detected = True
        masked = CUSTOMER_RE.sub("[CUSTOMER]", masked)

    confidential_detected = contains_any(text, CONFIDENTIAL_KEYWORDS)
    financial_detected = contains_any(text, FINANCIAL_KEYWORDS)
    legal_detected = contains_any(text, LEGAL_KEYWORDS)
    hr_detected = contains_any(text, HR_KEYWORDS)

    exposure_detected = any([
        pii_detected, secret_detected, customer_detected, confidential_detected,
        financial_detected, legal_detected, hr_detected,
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
