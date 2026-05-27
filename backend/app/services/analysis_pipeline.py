from pathlib import Path
import pandas as pd

from app.services.csv_loader import load_and_validate_csv
from app.services.masking import mask_prompt
from app.services.classifier import classify_task
from app.services.scoring import (
    calculate_risk_score,
    risk_level,
    normalize,
    calculate_opportunity_score,
    adoption_decision,
)
from app.services.recommender import (
    match_automation_candidate,
    build_reason,
)


def analyze_csv_file(csv_path: str | Path) -> dict:
    df = load_and_validate_csv(csv_path)

    analyzed_rows = []
    for _, row in df.iterrows():
        masking_result = mask_prompt(row["prompt_text"])
        masking_dict = masking_result.to_dict()

        task_label = classify_task(masking_result.masked_prompt)
        risk_score_value = calculate_risk_score(masking_dict)

        analyzed_rows.append({
            "log_id": int(row["log_id"]),
            "department": row["department"],
            "user_hash": row["user_hash"],
            "model": row["model"],
            "input_tokens": float(row["input_tokens"]),
            "output_tokens": float(row["output_tokens"]),
            "total_tokens": float(row["total_tokens"]),
            "cost": float(row["cost"]),
            "created_at": str(row["created_at"]),

            # 원문은 저장하지 않고 마스킹 결과만 저장합니다.
            "masked_prompt": masking_result.masked_prompt,

            # FUNC-PROC-009 원문 폐기 검증
            "original_prompt_stored": False,
            "original_discard_verified": True,
            "discard_verification_message": "원문 prompt_text는 결과 JSON/DB 저장 대상에서 제외되고 masked_prompt만 저장됩니다.",

            "task_label": task_label,
            "risk_score": risk_score_value,
            "risk_level": risk_level(risk_score_value),
            **{k: v for k, v in masking_dict.items() if k != "masked_prompt"},
        })

    adf = pd.DataFrame(analyzed_rows)

    return {
        "summary": {
            "total_logs": int(len(adf)),
            "departments": int(adf["department"].nunique()),
            "total_tokens": int(adf["total_tokens"].sum()),
            "total_cost": round(float(adf["cost"].sum()), 2),
            "avg_risk_score": round(float(adf["risk_score"].mean()), 2),
        },
        "department_stats": build_department_stats(adf),
        "recommendations": build_recommendations(adf),
        "sample_masked_logs": adf.head(20).to_dict(orient="records"),
    }


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
        if task_label == "기타":
            continue

        dept_total = len(adf[adf["department"] == dept])
        task_count = len(group)
        task_ratio = task_count / dept_total * 100

        total_cost = float(group["cost"].sum())
        unique_users = int(group["user_hash"].nunique())
        avg_risk = float(group["risk_score"].mean())

        # FUNC-PROC-008 자동화 후보 매칭
        auto_info = match_automation_candidate(task_label)

        opportunity = calculate_opportunity_score(
            frequency_ratio=task_ratio,
            repeat_score=normalize(task_count, max_count),
            cost_score=normalize(total_cost, max_cost),
            user_score=normalize(unique_users, max_users),
            difficulty=auto_info["difficulty"],
        )

        # SCR-RECO-004 Risk 기반 도입 판단
        decision_info = adoption_decision(opportunity, avg_risk)

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
            "reason": build_reason(
                department=dept,
                task_label=task_label,
                task_ratio=task_ratio,
                user_count=unique_users,
                avg_risk=avg_risk,
                total_cost=total_cost,
            ),
        })

    if not recommendations:
        return []

    result = []
    rdf = pd.DataFrame(recommendations)

    for _, group_items in rdf.groupby("department"):
        top_items = group_items.sort_values("opportunity_score", ascending=False).head(3)
        result.extend(top_items.to_dict(orient="records"))

    return sorted(result, key=lambda x: x["opportunity_score"], reverse=True)
