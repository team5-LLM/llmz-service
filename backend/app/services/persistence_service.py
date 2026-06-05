"""
분석 결과 Azure SQL 영속화

persist_analysis_result(upload_id, result):
  - department_stats[]         → department_stats 테이블
  - cluster_recommendations[]  → cluster_recommendations 테이블
  - masked_logs[]              → prompt_logs 테이블 (전체 행, API sample 20건만)

recommendations 테이블(task 스냅샷)은 API read 경로가 없어 INSERT 하지 않는다.
재업로드 시 해당 upload_id 레거시 행만 DELETE (reset 호환).
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


def _build_cluster_label_lookup(result: dict) -> dict[tuple[str, str], str]:
    """(department, sub_cluster_id) → 표시용 pattern_label (cluster_profiles 우선)."""
    lookup: dict[tuple[str, str], str] = {}

    for profile in result.get("cluster_profiles", []):
        sub_cluster_id = profile.get("sub_cluster_id")
        if not sub_cluster_id:
            continue
        label = profile.get("cluster_label") or profile.get("source_cluster_label")
        if label:
            lookup[(str(profile.get("department", "")), str(sub_cluster_id))] = str(label)

    for card in result.get("cluster_recommendations", []):
        sub_cluster_id = card.get("sub_cluster_id")
        if not sub_cluster_id:
            continue
        key = (str(card.get("department", "")), str(sub_cluster_id))
        if key not in lookup:
            source = card.get("source_cluster_label")
            if source:
                lookup[key] = str(source)

    return lookup


def _cluster_fields_for_log(
    log: dict,
    *,
    label_lookup: dict[tuple[str, str], str],
) -> tuple[str | None, str | None]:
    """masked_log → (cluster_id, pattern_label). cluster_id는 AI/ML sub_cluster_id."""
    raw_cluster_id = log.get("sub_cluster_id") or log.get("cluster_id")
    if not raw_cluster_id:
        return None, None

    cluster_id = str(raw_cluster_id)
    dept = str(log.get("department", ""))
    pattern_label = label_lookup.get((dept, cluster_id))
    if not pattern_label:
        inline = log.get("pattern_label") or log.get("cluster_label")
        pattern_label = str(inline) if inline else None
    return cluster_id, pattern_label


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

        # result["recommendations"] — analyze 파이프라인 산출물이나 DB 미영속(deprecated snapshot).
        # SCR-RECO API는 cluster_recommendations 또는 prompt_logs 재집계만 사용.

        cluster_label_lookup = _build_cluster_label_lookup(result)

        for log in result.get("masked_logs", []):
            cluster_id, pattern_label = _cluster_fields_for_log(
                log,
                label_lookup=cluster_label_lookup,
            )
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
                    cluster_id=cluster_id,
                    pattern_label=pattern_label,
                )
            )

        session.commit()
        logger.info(
            "persist_analysis_result 완료 (upload_id=%s, stats=%s, cluster_recs=%s, logs=%s)",
            upload_id,
            len(result.get("department_stats", [])),
            len(result.get("cluster_recommendations", [])),
            len(result.get("masked_logs", [])),
        )
        return True
    except SQLAlchemyError as exc:
        session.rollback()
        logger.error("persist_analysis_result 실패 (upload_id=%s): %s", upload_id, exc)
        return False
    finally:
        session.close()
