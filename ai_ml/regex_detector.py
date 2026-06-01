"""
[3.1 / FUNC-PROC-001]
regex_detector.py
- PII/기밀정보 탐지 1차 (정규식 기반 탐지)
- 이메일, 전화번호, API Key, 계약/재무/인사 키워드 등 정규식 탐지
- regex 탐지 결과는 confidence 0.84~0.99로 고정하여 반환 (실제 정밀도와 무관)
- 향후 모델 기반 탐지(@llm_detector.py)와 함께 통합되어 최종 PII 후보
"""

import re
from dataclasses import dataclass

@dataclass(frozen=True)
class Span:
    type: str
    start: int
    end: int
    text: str
    confidence: float
    source: str = 'regex'

PATTERNS: dict[str, tuple[str, float]] = {
    'EMAIL': (r'\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b', 0.98),
    'PHONE': (r'\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b', 0.97),
    'RRN': (r'\b\d{6}[-\s]?[1-4]\d{6}\b', 0.98),
    'CARD': (r'\b(?:\d{4}[-\s]?){3}\d{4}\b', 0.94),
    'BUSINESS_REG_NO': (r'\b\d{3}[-\s]?\d{2}[-\s]?\d{5}\b', 0.90),
    'OPENAI_API_KEY': (r'\bsk-[A-Za-z0-9_\-]{20,}\b', 0.99),
    'AWS_ACCESS_KEY': (r'\bAKIA[0-9A-Z]{16}\b', 0.99),
    'SAMPLE_API_KEY': (r'\bAPI_KEY_SAMPLE_DO_NOT_USE_[A-Za-z0-9_]*\b', 0.99),
    'BEARER_TOKEN': (r'\bBearer\s+[A-Za-z0-9._\-]{20,}\b', 0.96),
    'JWT': (r'\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b', 0.96),
    'DB_CONNECTION_STRING': (r'\b(?:postgresql|postgres|mysql|mongodb|redis|mssql|sqlserver)://[^\s]+', 0.96),
    'PASSWORD_ASSIGNMENT': (r'(?i)\b(password|passwd|pwd|secret|token)\s*[:=]\s*[\'\"]?[^\'\"\s,;]{6,}', 0.90),
    'CUSTOMER_INFO': (r'\b(?:가상고객|샘플고객|테스트고객|데모고객)[A-Z가-힣0-9]*\b', 0.90),
    'VENDOR_INFO': (r'\b(?:거래처|협력사|공급업체|파트너사)\s?[A-Z가-힣0-9]*\b', 0.86),
    'MONEY_AMOUNT': (r'\b\d{1,3}(?:,\d{3})*원\b|\b\d+원\b|\b\d+(?:\.\d+)?억\b', 0.88),
    'FINANCIAL_KEYWORD': (r'(매출|비용|영업이익|순이익|원가|정산|급여|예산|견적|마진|손익)', 0.84),
    'CONTRACT_INFO': (r'(계약서|NDA|비밀유지|위약금|해지 조건|계약 조건|계약 조항|법무 검토|소송 가능성|약관)', 0.88),
    'INTERNAL_MEETING': (r'(내부회의록|내부 회의록|회의록|임원 보고|경영진 보고|비공개 회의)', 0.84),
    'INTERNAL_CONFIDENTIAL': (r'(기밀|대외비|비공개|내부 프로젝트|사업 전략|서비스 로드맵|경쟁사 분석)', 0.86),
    'HR_SENSITIVE': (r'(인사평가|면접 피드백|평가 문구|채용 평가|징계|연봉|급여|지원자 수|입사 초기 이탈률)', 0.88),
    'SOURCE_CODE': (r'(def\s+\w+\(|class\s+\w+\(|import\s+\w+|SELECT\s+.+\s+FROM|CREATE\s+TABLE|console\.log|function\s+\w+\()', 0.86),
}

def detect_regex(text: str) -> list[Span]:
    if not text:
        return []
    spans: list[Span] = []
    for entity_type, (pattern, confidence) in PATTERNS.items():
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            spans.append(Span(entity_type, m.start(), m.end(), m.group(), confidence, 'regex'))
    return spans
