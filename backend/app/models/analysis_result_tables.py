"""분석 결과 영속화 테이블 — department_stats, recommendations, prompt_logs."""

from typing import Optional

from sqlalchemy import Float, Index, Integer, Unicode, UnicodeText, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.sql import Base


class DepartmentStatRow(Base):
    __tablename__ = "department_stats"
    __table_args__ = (
        Index("ix_department_stats_upload_id", "upload_id"),
        UniqueConstraint("upload_id", "department", name="uq_department_stats_upload_dept"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(Unicode(36), nullable=False)
    department: Mapped[str] = mapped_column(Unicode(128), nullable=False)

    total_requests: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    user_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(Unicode(16), nullable=False)
    high_critical_ratio: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    task_distribution_json: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="[]")


class RecommendationRow(Base):
    __tablename__ = "recommendations"
    __table_args__ = (
        Index("ix_recommendations_upload_id", "upload_id"),
        UniqueConstraint(
            "upload_id",
            "department",
            "task_label",
            name="uq_recommendations_upload_dept_task",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(Unicode(36), nullable=False)
    department: Mapped[str] = mapped_column(Unicode(128), nullable=False)
    task_label: Mapped[str] = mapped_column(Unicode(64), nullable=False)

    service_name: Mapped[str] = mapped_column(Unicode(256), nullable=False)
    expected_effect: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    difficulty: Mapped[str] = mapped_column(Unicode(16), nullable=False)
    required_resources_json: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="[]")

    opportunity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    risk_level: Mapped[str] = mapped_column(Unicode(16), nullable=False)

    decision: Mapped[str] = mapped_column(Unicode(64), nullable=False)
    decision_level: Mapped[str] = mapped_column(Unicode(32), nullable=False)
    decision_message: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    required_action: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    reason_json: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="[]")


class ClusterRecommendationRow(Base):
    """AI/ML cluster_recommendations 영속화."""

    __tablename__ = "cluster_recommendations"
    __table_args__ = (
        Index("ix_cluster_recommendations_upload_id", "upload_id"),
        UniqueConstraint(
            "upload_id",
            "department",
            "sub_cluster_id",
            name="uq_cluster_recommendations_upload_dept_cluster",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(Unicode(36), nullable=False)
    department: Mapped[str] = mapped_column(Unicode(128), nullable=False)
    sub_cluster_id: Mapped[str] = mapped_column(Unicode(128), nullable=False)

    recommendation_title: Mapped[str] = mapped_column(Unicode(256), nullable=False)
    automation_candidate_type: Mapped[str] = mapped_column(Unicode(64), nullable=False)
    macro_category: Mapped[str] = mapped_column(Unicode(64), nullable=False)
    opportunity_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    decision: Mapped[str] = mapped_column(Unicode(64), nullable=False)
    summary: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="")
    expected_effect_json: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="[]")
    security_guardrails_json: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="[]")
    implementation_difficulty: Mapped[str] = mapped_column(Unicode(16), nullable=False)
    priority_reason: Mapped[str] = mapped_column(UnicodeText, nullable=False, default="")
    source_cluster_label: Mapped[str] = mapped_column(Unicode(256), nullable=False, default="")
    method: Mapped[str] = mapped_column(Unicode(16), nullable=False, default="rule")


class PromptLogRow(Base):
    __tablename__ = "prompt_logs"
    __table_args__ = (
        Index("ix_prompt_logs_upload_id", "upload_id"),
        Index("ix_prompt_logs_upload_department", "upload_id", "department"),
        UniqueConstraint("upload_id", "log_id", name="uq_prompt_logs_upload_log"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_id: Mapped[str] = mapped_column(Unicode(36), nullable=False)
    log_id: Mapped[int] = mapped_column(Integer, nullable=False)

    department: Mapped[str] = mapped_column(Unicode(128), nullable=False)
    user_hash: Mapped[str] = mapped_column(Unicode(128), nullable=False)
    model: Mapped[str] = mapped_column(Unicode(64), nullable=False)

    input_tokens: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    output_tokens: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    total_tokens: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[str] = mapped_column(Unicode(40), nullable=False)

    masked_prompt: Mapped[str] = mapped_column(UnicodeText, nullable=False)
    task_label: Mapped[str] = mapped_column(Unicode(64), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    risk_level: Mapped[str] = mapped_column(Unicode(16), nullable=False)

    original_prompt_stored: Mapped[bool] = mapped_column(nullable=False, default=False)
    original_discard_verified: Mapped[bool] = mapped_column(nullable=False, default=True)
    discard_verification_message: Mapped[Optional[str]] = mapped_column(UnicodeText, nullable=True)

    pii_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    customer_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    confidential_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    financial_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    legal_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    secret_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    hr_detected: Mapped[bool] = mapped_column(nullable=False, default=False)
    exposure_detected: Mapped[bool] = mapped_column(nullable=False, default=False)

    # FUNC-PROC-005 Sub-Clustering 연동 예정 (nullable · 마이그레이션 후 persist)
    # cluster_id: Mapped[Optional[str]] = mapped_column(Unicode(64), nullable=True)
    # pattern_label: Mapped[Optional[str]] = mapped_column(Unicode(128), nullable=True)
