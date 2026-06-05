"""
분석 결과 Azure SQL 영속화

persist_analysis_result(upload_id, result):
  - department_stats[] → department_stats 테이블
  - recommendations[] → recommendations 테이블
  - masked_logs[]     → prompt_logs 테이블 (전체 행, API 응답에는 sample 20건만)
"""

from __future__ import annotations

import json
import logging

from sqlalchemy.exc import SQLAlchemyError

from app.db.sql import safe_session
from app.models.analysis_result_tables import (
    ClusterRecommendationRow,
    DepartmentStatRow,
    PromptLogRow,
    RecommendationRow,
)

logger = logging.getLogger(__name__)


def _dump_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def persist_analysis_result(upload_id: str, result: dict) -> bool:
    """analyze_csv_file() 결과를 Azure SQL에 저장. SQL 미설정 시 False."""
    session = safe_session()
    if session is None:
        logger.warning(
            "SQL 미설정 — persist_analysis_result skip (upload_id=%s)", upload_id
        )
        return False

    try:
        session.query(PromptLogRow).filter(PromptLogRow.upload_id == upload_id).delete()
        session.query(RecommendationRow).filter(
            RecommendationRow.upload_id == upload_id
        ).delete()
        session.query(DepartmentStatRow).filter(
            DepartmentStatRow.upload_id == upload_id
        ).delete()
        session.query(ClusterRecommendationRow).filter(
            ClusterRecommendationRow.upload_id == upload_id
        ).delete()

        for stat in result.get("department_stats", []):
            session.add(
                DepartmentStatRow(
                    upload_id=upload_id,
                    department=stat["department"],
                    total_requests=int(stat["total_requests"]),
                    total_tokens=int(stat["total_tokens"]),
                    total_cost=float(stat["total_cost"]),
                    user_count=int(stat["user_count"]),
                    avg_risk_score=float(stat["avg_risk_score"]),
                    risk_level=str(stat["risk_level"]),
                    high_critical_ratio=float(stat["high_critical_ratio"]),
                    task_distribution_json=_dump_json(stat.get("task_distribution", [])),
                )
            )

        for card in result.get("cluster_recommendations", []):
            expected_effect = card.get("expected_effect", [])
            guardrails = card.get("security_guardrails", [])
            session.add(
                ClusterRecommendationRow(
                    upload_id=upload_id,
                    department=str(card["department"]),
                    sub_cluster_id=str(card["sub_cluster_id"]),
                    recommendation_title=str(card.get("recommendation_title", "")),
                    automation_candidate_type=str(card.get("automation_candidate_type", "")),
                    macro_category=str(card.get("macro_category", "")),
                    opportunity_score=int(card.get("opportunity_score", 0) or 0),
                    risk_score=float(card.get("risk_score", 0) or 0),
                    decision=str(card.get("decision", "")),
                    summary=str(card.get("summary", "")),
                    expected_effect_json=_dump_json(expected_effect),
                    security_guardrails_json=_dump_json(guardrails),
                    implementation_difficulty=str(card.get("implementation_difficulty", "Medium")),
                    priority_reason=str(card.get("priority_reason", "")),
                    source_cluster_label=str(card.get("source_cluster_label", "")),
                    method=str(card.get("method", "rule")),
                )
            )

        for rec in result.get("recommendations", []):
            session.add(
                RecommendationRow(
                    upload_id=upload_id,
                    department=rec["department"],
                    task_label=rec["task_label"],
                    service_name=rec["service_name"],
                    expected_effect=rec["expected_effect"],
                    difficulty=rec["difficulty"],
                    required_resources_json=_dump_json(rec.get("required_resources", [])),
                    opportunity_score=int(rec["opportunity_score"]),
                    risk_score=float(rec["risk_score"]),
                    risk_level=str(rec["risk_level"]),
                    decision=rec["decision"],
                    decision_level=rec["decision_level"],
                    decision_message=rec["decision_message"],
                    required_action=rec["required_action"],
                    reason_json=_dump_json(rec.get("reason", [])),
                )
            )

        for log in result.get("masked_logs", []):
            session.add(
                PromptLogRow(
                    upload_id=upload_id,
                    log_id=int(log["log_id"]),
                    department=str(log["department"]),
                    user_hash=str(log["user_hash"]),
                    model=str(log["model"]),
                    input_tokens=float(log["input_tokens"]),
                    output_tokens=float(log["output_tokens"]),
                    total_tokens=float(log["total_tokens"]),
                    cost=float(log["cost"]),
                    created_at=str(log["created_at"]),
                    masked_prompt=str(log["masked_prompt"]),
                    task_label=str(log["task_label"]),
                    risk_score=int(log["risk_score"]),
                    risk_level=str(log["risk_level"]),
                    original_prompt_stored=bool(log.get("original_prompt_stored", False)),
                    original_discard_verified=bool(
                        log.get("original_discard_verified", True)
                    ),
                    discard_verification_message=log.get("discard_verification_message"),
                    pii_detected=bool(log.get("pii_detected", False)),
                    customer_detected=bool(log.get("customer_detected", False)),
                    confidential_detected=bool(log.get("confidential_detected", False)),
                    financial_detected=bool(log.get("financial_detected", False)),
                    legal_detected=bool(log.get("legal_detected", False)),
                    secret_detected=bool(log.get("secret_detected", False)),
                    hr_detected=bool(log.get("hr_detected", False)),
                    exposure_detected=bool(log.get("exposure_detected", False)),
                )
            )

        session.commit()
        logger.info(
            "persist_analysis_result 완료 (upload_id=%s, stats=%s, cluster_recs=%s, recs=%s, logs=%s)",
            upload_id,
            len(result.get("department_stats", [])),
            len(result.get("cluster_recommendations", [])),
            len(result.get("recommendations", [])),
            len(result.get("masked_logs", [])),
        )
        return True
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("persist_analysis_result 실패 (upload_id=%s): %s", upload_id, exc)
        return False
    finally:
        session.close()
