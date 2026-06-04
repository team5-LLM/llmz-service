from __future__ import annotations

import re
from collections import Counter

from .pii_schema import CategoryResult


TASK_CATEGORIES = [
    "REPORT_WRITING",
    "CODE_GENERATION",
    "CUSTOMER_SUPPORT",
    "DOCUMENT_SUMMARY",
    "DATA_ANALYSIS",
    "SEARCH_QA",
]


# 점수 기반 rule.
# 너무 일반적인 "정리해줘", "작성해줘"는 특정 category keyword로 넣지 않는 것이 중요함.
WEIGHTED_RULES: dict[str, list[tuple[str, float]]] = {
    "CODE_GENERATION": [
        ("코드", 3.0),
        ("API", 2.5),
        ("FastAPI", 3.0),
        ("React", 3.0),
        ("Django", 3.0),
        ("SQLAlchemy", 3.0),
        ("Python", 3.0),
        ("버그", 2.5),
        ("에러", 2.5),
        ("단위 테스트", 3.0),
        ("구현", 2.5),
        ("파싱", 2.0),
        ("모듈", 1.5),
        ("[SOURCE_CODE]", 3.0),
        ("[SOURCE_CODE_SECRET]", 3.5),
    ],
    "CUSTOMER_SUPPORT": [
        ("고객 문의", 3.0),
        ("고객의", 2.0),
        ("상담사", 3.0),
        ("FAQ", 3.0),
        ("환불", 2.5),
        ("배송", 2.5),
        ("결제 오류", 3.0),
        ("불만 고객", 3.0),
        ("후속 안내", 3.0),
        ("공감형 안내", 3.0),
        ("정중한 답변", 2.5),
        ("답변을 작성", 2.5),
        ("메일을 작성", 2.0),
        ("[CUSTOMER_INFO]", 3.0),
    ],
    "DOCUMENT_SUMMARY": [
        ("긴 문서", 3.0),
        ("첨부 문서", 3.0),
        ("문서의 주요", 2.5),
        ("회의록", 3.0),
        ("계약서", 3.0),
        ("주요 쟁점", 3.0),
        ("후속 조치", 2.5),
        ("위험 조항", 3.0),
        ("확인 필요 항목", 3.0),
        ("3문단 요약", 3.0),
        ("요약해줘", 2.0),
        ("추려줘", 2.5),
        ("[CONTRACT_INFO]", 2.5),
        ("[LEGAL_REVIEW]", 2.5),
        ("[INTERNAL_MEETING]", 2.5),
    ],
    "DATA_ANALYSIS": [
        ("데이터", 2.5),
        ("지표", 2.5),
        ("분석", 2.5),
        ("이상치", 3.0),
        ("반복 패턴", 3.0),
        ("전환율", 3.0),
        ("클릭률", 3.0),
        ("도달률", 3.0),
        ("매출", 2.5),
        ("비용", 2.5),
        ("핵심 인사이트", 3.0),
        ("증가/감소 원인", 3.0),
        ("개선 액션", 3.0),
        ("예상 리스크", 2.5),
        ("성과 데이터", 2.5),
        ("[FINANCIAL_INFO]", 2.5),
        ("[MONEY_AMOUNT]", 2.0),
    ],
    "REPORT_WRITING": [
        ("보고서", 3.0),
        ("보고용", 3.0),
        ("경영진", 2.5),
        ("팀장", 2.5),
        ("임원", 2.5),
        ("1페이지", 2.5),
        ("성과를", 2.0),
        ("진행 상황", 2.5),
        ("초안", 2.5),
        ("공유할", 2.0),
        ("결과 보고서", 3.0),
        ("월간 업무 보고서", 3.0),
    ],
    "SEARCH_QA": [
        ("용어", 3.0),
        ("의미와 예시", 3.0),
        ("의미", 2.0),
        ("예시", 2.0),
        ("차이", 3.0),
        ("비교", 3.0),
        ("주의할 점", 3.0),
        ("설명해줘", 2.5),
        ("알려줘", 2.5),
        ("아이디어를 10개", 2.5),
        ("비전공자", 2.5),
    ],
}


# 동점일 때 업무성이 더 강한 유형을 우선.
# SEARCH_QA는 제일 마지막으로 둔다.
TIE_BREAK_PRIORITY = [
    "CODE_GENERATION",
    "CUSTOMER_SUPPORT",
    "DOCUMENT_SUMMARY",
    "REPORT_WRITING",
    "DATA_ANALYSIS",
    "SEARCH_QA",
]


def _contains(text: str, keyword: str) -> bool:
    return re.search(re.escape(keyword), text, flags=re.IGNORECASE) is not None


def _score_text(text: str) -> Counter:
    scores: Counter = Counter()

    for category, rules in WEIGHTED_RULES.items():
        for keyword, weight in rules:
            if _contains(text, keyword):
                scores[category] += weight

    return scores


def _apply_strong_pattern_overrides(text: str, scores: Counter) -> str | None:
    """
    특정 표현은 다른 keyword와 섞여도 category가 명확하므로 우선 적용.
    """

    # 코드/개발은 가장 명확함
    if any(
        _contains(text, kw)
        for kw in [
            "코드",
            "FastAPI",
            "React",
            "Django",
            "SQLAlchemy",
            "Python",
            "단위 테스트",
            "구현하는 예시",
            "버그",
            "에러",
        ]
    ):
        return "CODE_GENERATION"

    # 고객 응대
    if any(
        _contains(text, kw)
        for kw in [
            "고객 문의",
            "상담사",
            "FAQ 답변",
            "불만 고객",
            "후속 안내",
            "공감형 안내",
            "정중한 답변",
            "결제 오류 문의",
            "[CUSTOMER_INFO]",
        ]
    ):
        return "CUSTOMER_SUPPORT"

    # 문서 요약
    if any(
        _contains(text, kw)
        for kw in [
            "긴 문서",
            "첨부 문서",
            "회의록",
            "주요 쟁점",
            "후속 조치",
            "위험 조항",
            "확인 필요 항목",
            "3문단 요약",
            "추려줘",
        ]
    ):
        return "DOCUMENT_SUMMARY"

    # 보고서 작성
    if any(
        _contains(text, kw)
        for kw in [
            "보고서",
            "보고용",
            "경영진",
            "팀장",
            "임원",
            "1페이지",
            "진행 상황",
            "보고서 초안",
            "결과 보고서",
        ]
    ):
        return "REPORT_WRITING"

    # 데이터 분석
    if any(
        _contains(text, kw)
        for kw in [
            "데이터",
            "지표",
            "이상치",
            "반복 패턴",
            "전환율",
            "클릭률",
            "도달률",
            "매출",
            "비용",
            "핵심 인사이트",
            "증가/감소 원인",
            "개선 액션",
            "예상 리스크",
        ]
    ):
        return "DATA_ANALYSIS"

    # 검색/질문
    if any(
        _contains(text, kw)
        for kw in [
            "용어",
            "의미와 예시",
            "차이",
            "비교",
            "주의할 점",
            "설명해줘",
            "알려줘",
            "아이디어를 10개",
        ]
    ):
        return "SEARCH_QA"

    return None


def _best_category(scores: Counter) -> tuple[str, float]:
    if not scores:
        return "SEARCH_QA", 0.50

    max_score = max(scores.values())

    if max_score <= 0:
        return "SEARCH_QA", 0.50

    candidates = {
        category
        for category, score in scores.items()
        if score == max_score
    }

    for category in TIE_BREAK_PRIORITY:
        if category in candidates:
            return category, float(max_score)

    return "SEARCH_QA", float(max_score)


def _confidence(best_score: float, scores: Counter) -> float:
    if best_score <= 0:
        return 0.50

    sorted_scores = sorted(scores.values(), reverse=True)
    second_score = sorted_scores[1] if len(sorted_scores) > 1 else 0.0

    margin = best_score - second_score

    # base + evidence + margin
    conf = 0.55 + min(best_score, 6.0) * 0.05 + min(max(margin, 0.0), 4.0) * 0.03
    return round(min(conf, 0.95), 4)


def classify_task(masked_text: str) -> CategoryResult:
    """
    masked_text를 6개 상위 업무 유형으로 분류.
    Azure/embedding에 의존하지 않는 deterministic rule classifier.
    """

    text = str(masked_text or "").strip()

    if not text:
        return CategoryResult(
            category="SEARCH_QA",
            confidence=0.30,
            method="empty_fallback",
        )

    scores = _score_text(text)

    override = _apply_strong_pattern_overrides(text, scores)

    if override is not None:
        best = override
        best_score = float(scores.get(best, 1.0))
    else:
        best, best_score = _best_category(scores)

    return CategoryResult(
        category=best,
        confidence=_confidence(best_score, scores),
        method="rule_keyword_v2",
    )