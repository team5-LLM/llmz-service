"""
[3.5 / FUNC-PROC-005]
[5.3 / SCR-RECO-003]

cluster_labeler.py

기능:
- sub_cluster_id별로 clustered_rows를 그룹화
- 각 cluster의 대표 masked prompt 추출
- cluster_label, cluster_summary 생성
- cluster별 log_count, user_count, total_cost, total_tokens,
  avg_risk_score, high_risk_ratio, repeat_ratio 계산
- Azure OpenAI 사용 가능 시 LLM 기반 cluster label 생성
- Azure 미사용 시 rule fallback label 생성

시스템 흐름:
clustered_rows
→ build_cluster_profiles()
→ sub_cluster_id별 그룹화
→ representative_masked_prompts 추출
→ cluster_label / cluster_summary 생성
→ cluster_profiles 반환

관련 기능명세서:
- 3.5 / FUNC-PROC-005: 카테고리 내부 Sub-Clustering 결과 해석
- 5.3 / SCR-RECO-003: 추천 근거 설명(XAI)

Azure 리소스 optional:
- Azure OpenAI gpt-4o-mini deployment

필요 환경변수 optional:
- USE_AZURE_OPENAI
- USE_LLM_CLUSTER_LABEL
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_KEY
- AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT
- AZURE_OPENAI_API_VERSION

설치 패키지:
- openai (optional)
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any


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


def _setting(name: str, default: Any = None) -> Any:
    try:
        from app.core.config import settings

        value = getattr(settings, name, None)
        if value not in (None, ""):
            return value
    except Exception:
        pass

    return os.getenv(name, default)


def _bool_setting(name: str, default: bool = False) -> bool:
    value = _setting(name, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _chat_client():
    if not _bool_setting("USE_AZURE_OPENAI", default=False):
        return None

    endpoint = _setting("AZURE_OPENAI_ENDPOINT")
    key = _setting("AZURE_OPENAI_KEY")

    if not endpoint or not key:
        return None

    from openai import AzureOpenAI

    return AzureOpenAI(
        api_key=key,
        api_version=str(_setting("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")),
        azure_endpoint=endpoint,
    )


def _chat_deployment() -> str | None:
    return (
        _setting("AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT")
        or _setting("AZURE_OPENAI_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_RECOMMENDATION_DEPLOYMENT")
        or os.getenv("AZURE_OPENAI_DEPLOYMENT")
    )


def _get(row: dict, key: str, default: Any = None) -> Any:
    return row.get(key, default)


def _macro_category(row: dict) -> str:
    return str(
        row.get("category")
        or row.get("task_label")
        or row.get("macro_category")
        or "SEARCH_QA"
    )


def _risk_level(row: dict) -> str:
    return str(row.get("risk_level") or "Low")


def _cluster_key(row: dict) -> str | None:
    value = row.get("sub_cluster_id")
    return None if value is None else str(value)


def _choose_representatives(rows: list[dict], max_examples: int = 5) -> list[str]:
    """
    centroid 거리 정보가 있으면 가까운 순서로 대표 프롬프트를 고릅니다.
    없으면 짧고 중복 적은 순서로 고릅니다.
    """
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
    if not _bool_setting("USE_LLM_CLUSTER_LABEL", default=False):
        return None

    client = _chat_client()
    deployment = _chat_deployment()

    system = """
당신은 기업 LLM 사용 패턴 분석 서비스의 클러스터 라벨러입니다.
입력은 이미 마스킹된 프롬프트입니다. 원문 개인정보는 없습니다.

각 클러스터에 대해 사람이 이해하기 쉬운 업무명과 한 줄 설명을 생성하세요.

반드시 JSON object만 응답하세요.
형식:
{
  "cluster_label": "배송 지연 문의 자동 응대",
  "cluster_summary": "고객지원팀의 배송 지연, 결제 오류, 후속 안내 업무가 반복되는 클러스터입니다."
}
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
    """
    embedding_clusterer.cluster_processed_logs() 결과를 받아
    cluster profile 목록을 생성합니다.
    """

    groups: dict[str, list[dict]] = {}

    for row in clustered_rows:
        cluster_id = _cluster_key(row)
        if not cluster_id:
            continue
        groups.setdefault(cluster_id, []).append(row)

    profiles: list[ClusterProfile] = []

    for cluster_id, rows in groups.items():
        department_counter = Counter(str(_get(row, "department", "UNKNOWN")) for row in rows)
        macro_counter = Counter(_macro_category(row) for row in rows)

        department = department_counter.most_common(1)[0][0]
        macro_category = macro_counter.most_common(1)[0][0]

        representative_prompts = _choose_representatives(rows, max_examples=max_examples)

        llm_label = None
        if use_llm_label:
            llm_label = _llm_label_cluster(
                department=department,
                macro_category=macro_category,
                representative_prompts=representative_prompts,
            )

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

        # 같은 cluster에 묶인 비율 자체를 반복성 proxy로 사용
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

    profiles.sort(
        key=lambda p: (
            p.log_count,
            p.total_cost,
            p.user_count,
        ),
        reverse=True,
    )

    return [profile.to_dict() for profile in profiles]