from pathlib import Path
import math
from typing import Any
import numpy as np
import pandas as pd

from ai_ml.privacy_pipeline import (
    process_prompt_privacy,
    generate_cluster_based_recommendations,
)
from ai_ml.automation_matcher import match_automation_candidate_llm

from app.services.csv_loader import load_and_validate_csv
from app.services.scoring import (
    calculate_risk_score,
    risk_level,
    normalize,
    calculate_opportunity_score,
    adoption_decision,
)
from app.services.recommender import build_reason

def build_summary_from_dataframe(
    adf: pd.DataFrame,
    cluster_profiles: list[dict] | None = None,
    cluster_recommendations: list[dict] | None = None,
) -> dict:
    """
    dashboard_service.py 호환용 summary 생성 함수.

    adf: analyze_csv_file()에서 생성한 analyzed DataFrame
    cluster_profiles: AI/ML sub-clustering profile 목록
    cluster_recommendations: AI/ML cluster 기반 추천 카드 목록
    """
    if adf is None or len(adf) == 0:
        return {
            "total_logs": 0,
            "departments": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "avg_risk_score": 0.0,
            "masked_logs": 0,
            "no_sensitive_logs": 0,
            "rejected_logs": 0,
            "cluster_count": 0,
            "recommendation_count": 0,
        }

    summary = {
        "total_logs": int(len(adf)),
        "departments": int(adf["department"].nunique())
        if "department" in adf.columns else 0,
        "total_tokens": int(adf["total_tokens"].sum())
        if "total_tokens" in adf.columns else 0,
        "total_cost": round(float(adf["cost"].sum()), 2)
        if "cost" in adf.columns else 0.0,
        "avg_risk_score": round(float(adf["risk_score"].mean()), 2)
        if "risk_score" in adf.columns and len(adf) > 0 else 0.0,
        "masked_logs": int((adf["masking_status"] == "MASKED").sum())
        if "masking_status" in adf.columns else 0,
        "no_sensitive_logs": int((adf["masking_status"] == "NO_SENSITIVE_FOUND").sum())
        if "masking_status" in adf.columns else 0,
        "rejected_logs": int(adf["unmasked_rejected"].sum())
        if "unmasked_rejected" in adf.columns else 0,
        "cluster_count": int(len(cluster_profiles or [])),
        "recommendation_count": int(len(cluster_recommendations or [])),
    }

    return summary

def analyze_csv_file(csv_path: str | Path) -> dict:
    df = load_and_validate_csv(csv_path)

    analyzed_rows = []

    for index, row in df.iterrows():
        raw_prompt = row.get("prompt_text", "")

        if pd.isna(raw_prompt):
            prompt_text = ""
        else:
            prompt_text = str(raw_prompt).strip()

        if not prompt_text:
            continue

        log_id = str(row.get("log_id", index))

        # AI/ML row 단위 privacy pipeline 호출
        privacy_result = process_prompt_privacy(
            prompt_text=prompt_text,
            log_id=log_id,
        ).to_dict()

        # 기존 backend 필드명과 호환시키기
        masked_prompt = privacy_result.get("masked_text")
        task_label = privacy_result.get("category")

        # 기존 scoring 함수가 masking_dict를 받는 구조를 유지하기 위한 adapter
        masking_dict = {
            "masked_prompt": masked_prompt,
            "masked_text": masked_prompt,
            "detected_spans": privacy_result.get("detected_spans", []),
            "detected_sensitive_types": privacy_result.get("detected_sensitive_types", []),
            "masking_status": privacy_result.get("masking_status"),
            "masking_min_confidence": privacy_result.get("masking_min_confidence"),
            "original_disposed": privacy_result.get("original_disposed"),
            "disposal_verification": privacy_result.get("disposal_verification"),
            "unmasked_rejected": privacy_result.get("unmasked_rejected"),
            "reject_reason": privacy_result.get("reject_reason", ""),
        }

        risk_score_value = calculate_risk_score(masking_dict)

        analyzed_rows.append({
            "log_id": log_id,
            "department": row["department"],
            "user_hash": row["user_hash"],
            "model": row["model"],
            "input_tokens": float(row["input_tokens"]),
            "output_tokens": float(row["output_tokens"]),
            "total_tokens": float(row["total_tokens"]),
            "cost": float(row["cost"]),
            "created_at": str(row["created_at"]),

            # 원문 prompt_text 저장 금지
            # 기존 DB/persistence 호환을 위해 masked_prompt 이름 유지
            "masked_prompt": masked_prompt,

            # AI/ML 표준 필드도 함께 저장 가능하게 추가
            "masked_text": masked_prompt,
            "detected_spans": privacy_result.get("detected_spans", []),
            "detected_sensitive_types": privacy_result.get("detected_sensitive_types", []),
            "masking_status": privacy_result.get("masking_status"),
            "masking_min_confidence": privacy_result.get("masking_min_confidence"),

            # FUNC-PROC-009 원문 폐기 검증
            "original_prompt_stored": False,
            "original_discard_verified": privacy_result.get("original_disposed", True),
            "discard_verification_message": privacy_result.get(
                "disposal_verification",
                "PASSED_NO_RAW_PROMPT_FIELD_IN_PERSISTED_PAYLOAD",
            ),

            # AI/ML 업무 유형 분류 결과
            # 기존 backend 호환을 위해 task_label 이름 유지
            "task_label": task_label,
            "category": task_label,
            "category_confidence": privacy_result.get("category_confidence"),
            "category_method": privacy_result.get("category_method"),

            "risk_score": risk_score_value,
            "risk_level": risk_level(risk_score_value),

            "unmasked_rejected": privacy_result.get("unmasked_rejected", False),
            "reject_reason": privacy_result.get("reject_reason", ""),
        })

    adf = pd.DataFrame(analyzed_rows)

    if len(adf) == 0:
        return make_json_safe({
            "summary": build_summary_from_dataframe(adf),
            "department_stats": [],
            "recommendations": [],
            "cluster_profiles": [],
            "cluster_recommendations": [],
            "sample_masked_logs": [],
            "masked_logs": [],
        })

    # AI/ML batch clustering/recommendation
    processed_rows = adf.to_dict(orient="records")

    cluster_result = generate_cluster_based_recommendations(
        processed_rows=processed_rows,
        group_by_department=True,
    )

    clustered_rows = cluster_result.get("clustered_rows", [])
    cluster_profiles = cluster_result.get("cluster_profiles", [])
    cluster_recommendations = cluster_result.get("recommendation_cards", [])

    # clustered_rows 결과를 기존 analyzed row에 반영
    cluster_by_log_id = {
        str(row.get("log_id")): row
        for row in clustered_rows
        if row.get("log_id") is not None
    }

    for item in analyzed_rows:
        clustered = cluster_by_log_id.get(str(item.get("log_id")))
        if not clustered:
            continue

        item["sub_cluster_id"] = clustered.get("sub_cluster_id")
        item["local_cluster_id"] = clustered.get("local_cluster_id")
        item["cluster_method"] = clustered.get("cluster_method")
        item["distance_to_centroid"] = clustered.get("distance_to_centroid")

    adf = pd.DataFrame(analyzed_rows)

    result = {
        "summary": build_summary_from_dataframe(
            adf,
            cluster_profiles=cluster_profiles,
            cluster_recommendations=cluster_recommendations,
        ),
        "department_stats": build_department_stats(adf),
        "recommendations": build_recommendations(adf),
        "cluster_profiles": cluster_profiles,
        "cluster_recommendations": cluster_recommendations,
        "sample_masked_logs": adf.head(20).to_dict(orient="records"),
        "masked_logs": adf.to_dict(orient="records"),
    }

    return make_json_safe(result)


def build_department_stats(adf: pd.DataFrame) -> list[dict]:
    stats = []

    for dept, group in adf.groupby("department"):
        task_counts = group["task_label"].value_counts()
        total = len(group)

        task_distribution = [
            {
                "label": label,
                "count": int(count),
                "ratio": round(float(count / total * 100), 1),
            }
            for label, count in task_counts.items()
        ]

        high_critical_count = int(group[group["risk_score"] > 60].shape[0])
        avg_risk = round(float(group["risk_score"].mean()), 2)

        stats.append({
            "department": dept,
            "total_requests": int(total),
            "total_tokens": int(group["total_tokens"].sum()),
            "total_cost": round(float(group["cost"].sum()), 2),
            "user_count": int(group["user_hash"].nunique()),
            "avg_risk_score": avg_risk,
            "risk_level": risk_level(avg_risk),
            "high_critical_ratio": round(float(high_critical_count / total * 100), 1),
            "task_distribution": task_distribution,
        })

    return sorted(stats, key=lambda x: x["total_cost"], reverse=True)


def build_recommendations(adf: pd.DataFrame) -> list[dict]:
    recommendations = []

    max_cost = float(adf.groupby(["department", "task_label"])["cost"].sum().max())
    max_users = int(adf.groupby(["department", "task_label"])["user_hash"].nunique().max())
    max_count = int(adf.groupby(["department", "task_label"]).size().max())

    for (dept, task_label), group in adf.groupby(["department", "task_label"]):
        if task_label in {"기타", None, ""}:
            continue

        dept_total = len(adf[adf["department"] == dept])
        task_count = len(group)
        task_ratio = task_count / dept_total * 100
        total_cost = float(group["cost"].sum())
        unique_users = int(group["user_hash"].nunique())
        avg_risk = float(group["risk_score"].mean())

        # FUNC-PROC-008 자동화 후보 매칭
        auto_info = match_automation_candidate_llm(
            department=dept,
            task_label=task_label,
            task_ratio=task_ratio,
            user_count=unique_users,
            avg_risk=avg_risk,
        )

        # FUNC-PROC-007 Opportunity Score 계산
        opportunity = calculate_opportunity_score(
            frequency_ratio=task_ratio,
            repeat_score=normalize(task_count, max_count),
            cost_score=normalize(total_cost, max_cost),
            user_score=normalize(unique_users, max_users),
        )

        # SCR-RECO-004 Risk 기반 도입 판단
        decision_info = adoption_decision(opportunity, avg_risk)

        # SCR-RECO-003 추천 근거 설명
        reason = build_reason(
            department=dept,
            task_label=task_label,
            task_ratio=task_ratio,
            user_count=unique_users,
            avg_risk=avg_risk,
            total_cost=total_cost,
            opportunity_score=opportunity,
        )

        recommendations.append({
            "department": dept,
            "task_label": task_label,
            "service_name": auto_info["service_name"],
            "expected_effect": auto_info["expected_effect"],
            "difficulty": auto_info["difficulty"],
            "required_resources": auto_info["required_resources"],
            "opportunity_score": opportunity,
            "risk_score": round(avg_risk, 2),
            "risk_level": risk_level(avg_risk),
            "decision": decision_info["decision"],
            "decision_level": decision_info["decision_level"],
            "decision_message": decision_info["message"],
            "required_action": decision_info["required_action"],
            "reason": reason,
        })

    if not recommendations:
        return []

    result = []
    rdf = pd.DataFrame(recommendations)

    for _, group_items in rdf.groupby("department"):
        top_items = group_items.sort_values("opportunity_score", ascending=False).head(3)
        result.extend(top_items.to_dict(orient="records"))

    return sorted(result, key=lambda x: x["opportunity_score"], reverse=True)

def split_analysis_result_by_month(result: dict) -> dict:
    """
    현재는 월별 분할 없이 전체 분석 결과를 그대로 반환.
    추후 created_at 기준 월별 분할 저장이 필요하면 여기서 구현.
    """
    return result

def make_json_safe(value: Any) -> Any:
    """
    FastAPI JSON 응답에서 NaN / inf / numpy scalar 때문에 터지는 문제 방지.
    dict/list 내부까지 재귀적으로 변환합니다.
    """
    if value is None:
        return None

    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, np.floating):
        value = float(value)
        if math.isnan(value) or math.isinf(value):
            return None
        return value

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.ndarray):
        return [make_json_safe(v) for v in value.tolist()]

    if isinstance(value, dict):
        return {
            str(k): make_json_safe(v)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    return value