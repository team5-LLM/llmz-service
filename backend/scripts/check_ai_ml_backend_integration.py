from __future__ import annotations

import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from ai_ml.privacy_pipeline import process_prompt_privacy
from app.services.analysis_pipeline import analyze_csv_file

# 샘플데이터 경로명에 맞추어 변경 필요 !!
SAMPLE_PATH = Path(
    "/Users/woo/Documents/GitHub/llmz-service/data-sample/sample_llm_logs_5000_v08.csv"
)


def assert_no_bad_float(value: Any, path: str = "root") -> None:
    if isinstance(value, float):
        assert not math.isnan(value), f"NaN found at {path}"
        assert not math.isinf(value), f"Inf found at {path}"
    elif isinstance(value, dict):
        for k, v in value.items():
            assert_no_bad_float(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            assert_no_bad_float(v, f"{path}[{i}]")


def count_possible_leaks(rows: list[dict]) -> dict:
    """
    masked_prompt / masked_text 안에 실제 원문성 민감정보가 남았는지 간단 점검.
    토큰 [EMAIL], [PHONE], [API_KEY]는 정상으로 봄.
    """
    patterns = {
        "email": re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}"),
        "phone": re.compile(r"(?<!\d)01[016789][-\s]?\d{3,4}[-\s]?\d{4}(?!\d)"),
        "rrn": re.compile(r"(?<!\d)\d{6}[-\s]?[1-4]\d{6}(?!\d)"),
        "openai_key": re.compile(r"(?<![A-Za-z0-9_\-])sk-[A-Za-z0-9_\-]{20,}"),
        "aws_key": re.compile(r"(?<![A-Z0-9])AKIA[0-9A-Z]{16}(?![A-Z0-9])"),
    }

    leak_counts = {k: 0 for k in patterns}

    for row in rows:
        text = str(row.get("masked_prompt") or row.get("masked_text") or "")
        for name, pattern in patterns.items():
            if pattern.search(text):
                leak_counts[name] += 1

    return leak_counts


def main() -> None:
    print("=" * 80)
    print("1) 파일 존재 확인")
    print("=" * 80)

    print("sample:", SAMPLE_PATH)
    assert SAMPLE_PATH.exists(), f"샘플 CSV가 없습니다: {SAMPLE_PATH}"
    print("OK: sample file exists")

    print("\n" + "=" * 80)
    print("2) AI/ML row pipeline 단독 테스트")
    print("=" * 80)

    row_result = process_prompt_privacy(
        "홍길동 고객 전화번호는 010-1234-5678이고 이메일은 test@example.com 입니다.",
        log_id="integration_test_001",
    ).to_dict()

    print(row_result)

    assert row_result["masked_text"] is not None
    assert "010-1234-5678" not in row_result["masked_text"]
    assert "test@example.com" not in row_result["masked_text"]
    assert row_result["original_disposed"] is True
    print("OK: process_prompt_privacy")

    print("\n" + "=" * 80)
    print("3) Backend analyze_csv_file() 5000개 샘플 분석")
    print("=" * 80)

    result = analyze_csv_file(SAMPLE_PATH)

    assert isinstance(result, dict)
    assert "summary" in result
    assert "masked_logs" in result
    assert "department_stats" in result
    assert "recommendations" in result
    assert "cluster_profiles" in result
    assert "cluster_recommendations" in result

    summary = result["summary"]
    rows = result["masked_logs"]

    print("summary:", json.dumps(summary, ensure_ascii=False, indent=2))
    print("result keys:", list(result.keys()))

    assert summary["total_logs"] == 5000, f"total_logs expected 5000, got {summary['total_logs']}"
    assert len(rows) == 5000, f"masked_logs expected 5000, got {len(rows)}"

    print("OK: analyze_csv_file returned expected structure")

    print("\n" + "=" * 80)
    print("4) 마스킹/민감정보 분포 확인")
    print("=" * 80)

    masking_counter = Counter(row.get("masking_status") for row in rows)
    sensitive_counter = Counter()

    for row in rows:
        for t in row.get("detected_sensitive_types") or []:
            sensitive_counter[t] += 1

    print("masking:", masking_counter)
    print("sensitive types:", sensitive_counter)

    masked_logs = int(summary.get("masked_logs", 0))
    no_sensitive_logs = int(summary.get("no_sensitive_logs", 0))
    rejected_logs = int(summary.get("rejected_logs", 0))

    assert masked_logs + no_sensitive_logs + rejected_logs == 5000, (
        "masked + no_sensitive + rejected 합이 total_logs와 맞지 않습니다."
    )

    leak_counts = count_possible_leaks(rows)
    print("possible leaks:", leak_counts)

    assert sum(leak_counts.values()) == 0, f"마스킹 후 원문성 민감정보 leak 의심: {leak_counts}"
    print("OK: masking / leak check")

    print("\n" + "=" * 80)
    print("5) 업무 유형 분류 확인")
    print("=" * 80)

    category_counter = Counter(
        row.get("category") or row.get("task_label")
        for row in rows
    )

    print("category:", category_counter)

    expected_categories = {
        "REPORT_WRITING",
        "CODE_GENERATION",
        "CUSTOMER_SUPPORT",
        "DOCUMENT_SUMMARY",
        "DATA_ANALYSIS",
        "SEARCH_QA",
    }

    missing = expected_categories - set(category_counter.keys())
    assert not missing, f"누락된 category가 있습니다: {missing}"

    max_ratio = max(category_counter.values()) / 5000
    assert max_ratio < 0.80, f"특정 category가 과도하게 몰림: {category_counter}"

    print("OK: task classification distribution")

    print("\n" + "=" * 80)
    print("6) Risk Score 확인")
    print("=" * 80)

    risk_counter = Counter(row.get("risk_level") for row in rows)
    risk_scores = [float(row.get("risk_score", 0) or 0) for row in rows]

    print("risk:", risk_counter)
    print("avg risk:", sum(risk_scores) / len(risk_scores))

    assert summary["avg_risk_score"] > 0, "avg_risk_score가 0입니다. risk score 연결이 안 된 상태일 수 있습니다."
    assert any(score > 0 for score in risk_scores), "모든 risk_score가 0입니다."

    print("OK: risk scoring")

    print("\n" + "=" * 80)
    print("7) Clustering / Recommendation 확인")
    print("=" * 80)

    cluster_profiles = result.get("cluster_profiles", [])
    cluster_recommendations = result.get("cluster_recommendations", [])
    recommendations = result.get("recommendations", [])

    print("cluster_profiles:", len(cluster_profiles))
    print("cluster_recommendations:", len(cluster_recommendations))
    print("recommendations:", len(recommendations))

    assert len(cluster_profiles) > 0, "cluster_profiles가 비었습니다."
    assert len(cluster_recommendations) > 0, "cluster_recommendations가 비었습니다."
    assert len(recommendations) > 0, "기존 recommendations가 비었습니다."

    print("OK: clustering / recommendations")

    print("\n" + "=" * 80)
    print("8) JSON-safe 확인")
    print("=" * 80)

    assert_no_bad_float(result)
    json.dumps(result, ensure_ascii=False, allow_nan=False)

    print("OK: JSON-safe response")

    print("\n" + "=" * 80)
    print("최종 결과")
    print("=" * 80)
    print("PASS: AI/ML 전체 기능이 Backend analyze_csv_file()과 연결되어 정상 동작합니다.")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as exc:
        print("\nFAIL:", exc)
        sys.exit(1)
    except Exception as exc:
        print("\nERROR:", type(exc).__name__, exc)
        raise
