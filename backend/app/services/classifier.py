TASK_LABELS = [
    "보고서 작성형",
    "코드 생성형",
    "고객 응대형",
    "문서 요약형",
    "데이터 분석형",
    "단순 검색/질문형",
    "기타",
]

KEYWORDS = {
    "코드 생성형": ["python", "코드", "함수", "api", "에러", "error", "fastapi", "react", "sqlalchemy", "테스트 코드", "모듈", "파싱", "구현"],
    "고객 응대형": ["고객", "문의", "답변", "faq", "배송", "환불", "결제", "불만", "상담", "안내 메일", "후속 안내"],
    "문서 요약형": ["요약", "핵심", "회의록", "조항", "문서", "계약서", "쟁점", "후속 조치", "bullet"],
    "데이터 분석형": ["데이터", "분석", "지표", "kpi", "매출", "비용", "통계", "그래프", "전환율", "클릭률", "증가", "감소", "이상치"],
    "보고서 작성형": ["보고서", "성과", "주간", "월간", "경영진", "팀장", "보고용", "초안", "주요 성과", "다음 계획"],
    "단순 검색/질문형": ["개념", "차이", "설명", "체크리스트", "주의할 점", "의미", "예시", "비교"],
}

def classify_task(prompt: str) -> str:
    text = (prompt or "").lower()
    scores = {}
    for label, keywords in KEYWORDS.items():
        scores[label] = sum(1 for keyword in keywords if keyword.lower() in text)

    best_label = max(scores, key=scores.get)
    if scores[best_label] == 0:
        return "기타"
    return best_label
