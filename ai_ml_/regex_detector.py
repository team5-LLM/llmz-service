"""
[3.1 / FUNC-PROC-001]
regex_detector.py

기능:
- PII/기밀정보 1차 탐지
- 정규식 기반으로 이메일, 전화번호, 주민번호 패턴, 카드번호, 사업자번호,
  API Key, Token, DB connection string, 고객정보, 거래처정보,
  계약/재무/인사/내부기밀/소스코드 키워드 탐지
- 각 정규식 패턴에는 정책 기반 confidence를 부여
- 반환값은 Span(type, start, end, text, confidence, source='regex')

시스템 흐름:
CSV row의 prompt_text
→ detect_regex(prompt_text)
→ span_utils.merge_overlapping_spans()
→ masking.mask_text()

관련 기능명세서:
- 3.1 / FUNC-PROC-001: PII/기밀정보 탐지

Azure 리소스:
- 기본 동작에는 Azure 리소스 불필요
- LLM 기반 2차 탐지는 llm_detector.py에서 optional 수행
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
    'EMAIL': (
        r'(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}(?![A-Za-z0-9._%+\-])',
        0.98,
    ),
    'PHONE': (
        r'(?<![0-9])01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?![0-9])',
        0.97,
    ),
    'RRN': (
        r'(?<![0-9])\d{6}[-\s]?[1-4]\d{6}(?![0-9])',
        0.98,
    ),
    'CARD': (
        r'(?<![0-9])(?:\d{4}[-\s]?){3}\d{4}(?![0-9])',
        0.94,
    ),
    'BUSINESS_REG_NO': (
        r'(?<![0-9])\d{3}[-\s]?\d{2}[-\s]?\d{5}(?![0-9])',
        0.90,
    ),

    'OPENAI_API_KEY': (
        r'(?<![A-Za-z0-9_\-])sk-[A-Za-z0-9_\-]{20,}(?![A-Za-z0-9_\-])',
        0.99,
    ),
    'AWS_ACCESS_KEY': (
        r'(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])',
        0.99,
    ),
    'SAMPLE_API_KEY': (
        r'(?<![A-Za-z0-9_])API_KEY_SAMPLE_DO_NOT_USE_[A-Za-z0-9_]*(?![A-Za-z0-9_])',
        0.99,
    ),
    'BEARER_TOKEN': (
        r'(?<![A-Za-z0-9_])Bearer\s+[A-Za-z0-9._\-]{20,}(?![A-Za-z0-9._\-])',
        0.96,
    ),
    'JWT': (
        r'(?<![A-Za-z0-9_\-])eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+(?![A-Za-z0-9_\-])',
        0.96,
    ),
    'DB_CONNECTION_STRING': (
        r'(?<![A-Za-z0-9])(?:postgresql|postgres|mysql|mongodb|redis|mssql|sqlserver)://[^\s]+',
        0.96,
    ),
    'PASSWORD_ASSIGNMENT': (
        r'(?i)\b(password|passwd|pwd|secret|token)\s*[:=]\s*[\'\"]?[^\'\"\s,;]{6,}',
        0.90,
    ),

    'CUSTOMER_INFO': (
        r'(?:가상고객|샘플고객|테스트고객|데모고객)[A-Z0-9]*',
        0.90,
    ),
    'VENDOR_INFO': (
        r'(?:거래처|협력사|공급업체|파트너사)\s?[A-Z0-9]*',
        0.86,
    ),

    'MONEY_AMOUNT': (
        r'(?<![0-9])\d{1,3}(?:,\d{3})*원|(?<![0-9])\d+원|(?<![0-9])\d+(?:\.\d+)?억',
        0.88,
    ),
    'FINANCIAL_KEYWORD': (
        r'(매출|비용|영업이익|순이익|원가|정산|급여|예산|견적|마진|손익)',
        0.84,
    ),
    'CONTRACT_INFO': (
        r'(계약서|NDA|비밀유지|위약금|해지 조건|계약 조건|계약 조항|법무 검토|소송 가능성|약관)',
        0.88,
    ),
    'INTERNAL_MEETING': (
        r'(내부회의록|내부 회의록|회의록|임원 보고|경영진 보고|비공개 회의)',
        0.84,
    ),
    'INTERNAL_CONFIDENTIAL': (
        r'(기밀|대외비|비공개|내부 프로젝트|사업 전략|서비스 로드맵|경쟁사 분석)',
        0.86,
    ),
    'HR_SENSITIVE': (
        r'(인사평가|면접 피드백|평가 문구|채용 평가|징계|연봉|급여|지원자 수|입사 초기 이탈률)',
        0.88,
    ),
    'SOURCE_CODE': (
        r'(def\s+\w+\(|class\s+\w+\(|import\s+\w+|SELECT\s+.+\s+FROM|CREATE\s+TABLE|console\.log|function\s+\w+\()',
        0.86,
    ),
}

def detect_regex(text: str) -> list[Span]:
    if not text:
        return []
    spans: list[Span] = []
    for entity_type, (pattern, confidence) in PATTERNS.items():
        for m in re.finditer(pattern, text, flags=re.IGNORECASE):
            spans.append(Span(entity_type, m.start(), m.end(), m.group(), confidence, 'regex'))
    return spans
