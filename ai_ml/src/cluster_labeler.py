"""cluster profile 및 사람이 읽기 쉬운 cluster label 생성."""
from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from .common import azure_chat_client, bool_setting, chat_deployment


@dataclass(frozen=True)
class ClusterProfile:
    sub_cluster_id: str
    department: str
    macro_category: str
    cluster_label: str
    cluster_summary: str
    representative_masked_prompts: list[str]
    log_count: int
    user_count: int
    total_cost: float
    total_tokens: int
    avg_risk_score: float
    high_risk_ratio: float
    repeat_ratio: float
    label_method: str

    def to_dict(self) -> dict:
        return asdict(self)


def _get(row: dict, key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _macro_category(row: dict) -> str:
    return str(row.get("category") or row.get("task_label") or row.get("macro_category") or "SEARCH_QA")


def _risk_level(row: dict) -> str:
    return str(row.get("risk_level") or "Low")


def _cluster_key(row: dict) -> str | None:
    value = row.get("sub_cluster_id")
    return None if value is None else str(value)


def _choose_representatives(rows: list[dict], max_examples: int = 5) -> list[str]:
    unique: list[str] = []
    seen: set[str] = set()
    sorted_rows = sorted(
        rows,
        key=lambda r: (
            999999.0 if r.get("distance_to_centroid") is None else float(r.get("distance_to_centroid")),
            len(str(r.get("masked_text") or "")),
        ),
    )
    for row in sorted_rows:
        text = str(row.get("masked_text") or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique.append(text)
        if len(unique) >= max_examples:
            break
    return unique


def _fallback_label(macro_category: str, prompts: list[str]) -> tuple[str, str]:
    joined = " ".join(prompts)
    keyword_groups = [
        ("캠페인 성과 리포트", ["캠페인", "광고", "클릭률", "전환율", "SNS"]),
        ("고객 문의 자동 응대", ["고객", "문의", "배송", "환불", "결제", "후속 안내", "FAQ"]),
        ("계약/문서 요약", ["계약", "문서", "회의록", "요약", "주요 쟁점", "bullet"]),
        ("개발 코드 생성/오류 해결", ["코드", "FastAPI", "React", "Python", "API", "에러", "버그", "단위 테스트"]),
        ("매출/비용 데이터 분석", ["매출", "비용", "데이터", "지표", "이상치", "패턴", "인사이트"]),
        ("HR 문서/교육자료 생성", ["채용", "온보딩", "교육", "지원자", "인사평가", "면접"]),
        ("영업 제안/고객 미팅 지원", ["영업", "제안서", "리드", "고객 미팅", "계약 성공률"]),
        ("사내 지식검색/개념 설명", ["용어", "개념", "차이", "비교", "주의할 점", "설명"]),
    ]
    for label, keywords in keyword_groups:
        if any(re.search(re.escape(keyword), joined, flags=re.IGNORECASE) for keyword in keywords):
            return label, f"{label} 관련 반복 프롬프트가 묶인 클러스터입니다."

    macro_label = {
        "REPORT_WRITING": "보고서 작성 자동화",
        "CODE_GENERATION": "코드 생성 자동화",
        "CUSTOMER_SUPPORT": "고객 응대 자동화",
        "DOCUMENT_SUMMARY": "문서 요약 자동화",
        "DATA_ANALYSIS": "데이터 분석 자동화",
        "SEARCH_QA": "사내 지식검색 자동화",
    }.get(macro_category, "AI 업무 자동화")
    return macro_label, f"{macro_category} 유형의 유사 업무 요청이 묶인 클러스터입니다."


def _llm_label_cluster(
    department: str,
    macro_category: str,
    representative_prompts: list[str],
) -> tuple[str, str] | None:
    if not bool_setting("USE_LLM_CLUSTER_LABEL", default=False):
        return None

    client = azure_chat_client(required_flag="USE_LLM_CLUSTER_LABEL")
    deployment = chat_deployment("AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT", "AZURE_OPENAI_DEPLOYMENT")
    if client is None or not deployment:
        return None

    system = """
당신은 기업 LLM 사용 패턴 분석 서비스의 클러스터 라벨러입니다.
입력은 이미 마스킹된 프롬프트입니다. 원문 개인정보는 없습니다.
각 클러스터에 대해 사람이 이해하기 쉬운 업무명과 한 줄 설명을 생성하세요.
반드시 JSON object만 응답하세요.
형식: {"cluster_label":"배송 지연 문의 자동 응대","cluster_summary":"고객지원팀의 배송 지연, 결제 오류, 후속 안내 업무가 반복되는 클러스터입니다."}
"""
    payload = {
        "department": department,
        "macro_category": macro_category,
        "representative_masked_prompts": representative_prompts[:5],
    }

    try:
        response = client.chat.completions.create(
            model=deployment,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            response_format={"type": "json_object"},
            temperature=0,
            max_tokens=300,
        )
        data = json.loads(response.choices[0].message.content)
        label = str(data.get("cluster_label", "")).strip()
        summary = str(data.get("cluster_summary", "")).strip()
        if not label:
            return None
        return label, summary or f"{label} 관련 업무 클러스터입니다."
    except Exception:
        return None


def build_cluster_profiles(
    clustered_rows: list[dict],
    max_examples: int = 5,
    use_llm_label: bool = True,
) -> list[dict]:
    groups: dict[str, list[dict]] = {}
    for row in clustered_rows:
        cluster_id = _cluster_key(row)
        if cluster_id:
            groups.setdefault(cluster_id, []).append(row)

    profiles: list[ClusterProfile] = []
    for cluster_id, rows in groups.items():
        department = Counter(str(_get(row, "department", "UNKNOWN")) for row in rows).most_common(1)[0][0]
        macro_category = Counter(_macro_category(row) for row in rows).most_common(1)[0][0]
        representative_prompts = _choose_representatives(rows, max_examples=max_examples)

        llm_label = None
        if use_llm_label:
            llm_label = _llm_label_cluster(department, macro_category, representative_prompts)

        if llm_label:
            cluster_label, cluster_summary = llm_label
            label_method = "llm"
        else:
            cluster_label, cluster_summary = _fallback_label(macro_category, representative_prompts)
            label_method = "rule"

        users = {str(_get(row, "user_hash", "")) for row in rows if _get(row, "user_hash")}
        total_cost = sum(float(_get(row, "cost", 0.0) or 0.0) for row in rows)
        total_tokens = sum(int(_get(row, "total_tokens", 0) or 0) for row in rows)
        risk_scores = [float(_get(row, "risk_score", 0) or 0) for row in rows]
        avg_risk = sum(risk_scores) / len(risk_scores) if risk_scores else 0.0
        high_risk_count = sum(1 for row in rows if _risk_level(row) in {"High", "Critical"})
        high_risk_ratio = high_risk_count / len(rows) if rows else 0.0
        repeat_ratio = min(1.0, len(rows) / max(len(clustered_rows), 1) * 6)

        profiles.append(
            ClusterProfile(
                sub_cluster_id=cluster_id,
                department=department,
                macro_category=macro_category,
                cluster_label=cluster_label,
                cluster_summary=cluster_summary,
                representative_masked_prompts=representative_prompts,
                log_count=len(rows),
                user_count=len(users),
                total_cost=round(total_cost, 2),
                total_tokens=total_tokens,
                avg_risk_score=round(avg_risk, 2),
                high_risk_ratio=round(high_risk_ratio, 3),
                repeat_ratio=round(repeat_ratio, 3),
                label_method=label_method,
            )
        )

    profiles.sort(key=lambda p: (p.log_count, p.total_cost, p.user_count), reverse=True)
    return [profile.to_dict() for profile in profiles]
