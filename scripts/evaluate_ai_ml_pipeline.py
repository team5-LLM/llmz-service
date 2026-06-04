"""
evaluate_ai_ml_pipeline.py

5,000개 sample_llm_logs_5000.csv를 기준으로 AI/ML 파이프라인을 평가한다.

평가 항목:
1. CSV row 처리 성공 여부
2. PII/기밀정보 마스킹 결과
3. 민감정보 leak 여부
4. 업무 유형 분포
5. 부서별 업무 유형 분포
6. cluster profile 생성 여부
7. 추천 카드 생성 여부
8. 문제 샘플 CSV 저장

실행:
cd /Users/woo/Documents/GitHub/llmz-service
PYTHONPATH=.:backend python scripts/evaluate_ai_ml_pipeline.py
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

from ai_ml.privacy_pipeline import (
    process_prompt_privacy,
    generate_cluster_based_recommendations,
)


ROOT = Path("/Users/woo/Documents/GitHub/llmz-service")
CSV_PATH = ROOT / "data-sample" / "sample_llm_logs_5000.csv"
OUT_DIR = ROOT / "data-sample" / "ai_ml_eval"
OUT_DIR.mkdir(parents=True, exist_ok=True)


SENSITIVE_LEAK_PATTERNS = [
    "example.invalid",
    "API_KEY_SAMPLE_DO_NOT_USE",
    "010-0000-0000",
    "가상고객",
    "샘플고객",
    "테스트고객",
    "데모고객",
]


EXPECTED_MASK_HINTS = {
    "example.invalid": "EMAIL",
    "API_KEY_SAMPLE_DO_NOT_USE": "SAMPLE_API_KEY",
    "010-0000-0000": "PHONE",
    "가상고객": "CUSTOMER_INFO",
    "샘플고객": "CUSTOMER_INFO",
    "테스트고객": "CUSTOMER_INFO",
    "데모고객": "CUSTOMER_INFO",
    "계약서": "CONTRACT_INFO",
    "위약금": "CONTRACT_INFO",
    "해지 조건": "CONTRACT_INFO",
    "인사평가": "HR_SENSITIVE",
    "면접 피드백": "HR_SENSITIVE",
    "매출": "FINANCIAL_KEYWORD",
    "비용": "FINANCIAL_KEYWORD",
}


def simple_risk(types: list[str]) -> tuple[int, str]:
    high = {
        "RRN",
        "CARD",
        "OPENAI_API_KEY",
        "AWS_ACCESS_KEY",
        "SAMPLE_API_KEY",
        "BEARER_TOKEN",
        "JWT",
        "DB_CONNECTION_STRING",
        "PASSWORD_ASSIGNMENT",
    }

    medium = {
        "EMAIL",
        "PHONE",
        "CUSTOMER_INFO",
        "VENDOR_INFO",
        "CONTRACT_INFO",
        "HR_SENSITIVE",
        "INTERNAL_CONFIDENTIAL",
        "SOURCE_CODE",
    }

    if not types:
        return 10, "Low"

    score = 10

    for t in types:
        if t in high:
            score += 30
        elif t in medium:
            score += 18
        else:
            score += 10

    score = min(score, 100)

    if score <= 30:
        level = "Low"
    elif score <= 60:
        level = "Medium"
    elif score <= 80:
        level = "High"
    else:
        level = "Critical"

    return score, level


def has_expected_hint(prompt_text: str) -> list[str]:
    expected = []

    for needle, entity_type in EXPECTED_MASK_HINTS.items():
        if needle in prompt_text:
            expected.append(entity_type)

    return sorted(set(expected))


def detect_leaks(masked_text: str | None) -> list[str]:
    if not masked_text:
        return []

    return [pattern for pattern in SENSITIVE_LEAK_PATTERNS if pattern in masked_text]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8-sig")
        return

    fieldnames = list(rows[0].keys())

    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    processed_rows: list[dict] = []
    rejected_rows: list[dict] = []
    leak_rows: list[dict] = []
    missed_expected_rows: list[dict] = []
    all_rows = []

    with CSV_PATH.open("r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)

        for row in reader:
            all_rows.append(row)

            result = process_prompt_privacy(
                prompt_text=row["prompt_text"],
                log_id=str(row["log_id"]),
            )

            expected_types = has_expected_hint(row["prompt_text"])
            detected_types = result.detected_sensitive_types

            leaks = detect_leaks(result.masked_text)

            missing_expected = [
                entity_type
                for entity_type in expected_types
                if entity_type not in detected_types
            ]

            if result.unmasked_rejected:
                rejected_rows.append(
                    {
                        "log_id": row["log_id"],
                        "department": row["department"],
                        "prompt_text": row["prompt_text"],
                        "detected_sensitive_types": "|".join(detected_types),
                        "reject_reason": result.reject_reason,
                    }
                )
                continue

            if leaks:
                leak_rows.append(
                    {
                        "log_id": row["log_id"],
                        "department": row["department"],
                        "prompt_text": row["prompt_text"],
                        "masked_text": result.masked_text,
                        "leaks": "|".join(leaks),
                        "detected_sensitive_types": "|".join(detected_types),
                    }
                )

            if missing_expected:
                missed_expected_rows.append(
                    {
                        "log_id": row["log_id"],
                        "department": row["department"],
                        "prompt_text": row["prompt_text"],
                        "masked_text": result.masked_text,
                        "expected_types": "|".join(expected_types),
                        "detected_sensitive_types": "|".join(detected_types),
                        "missing_expected": "|".join(missing_expected),
                    }
                )

            risk_score, risk_level = simple_risk(detected_types)

            processed_rows.append(
                {
                    "log_id": str(row["log_id"]),
                    "department": row["department"],
                    "user_hash": row["user_hash"],
                    "masked_text": result.masked_text,
                    "category": result.category,
                    "category_confidence": result.category_confidence,
                    "category_method": result.category_method,
                    "detected_sensitive_types": detected_types,
                    "masking_status": result.masking_status,
                    "original_disposed": result.original_disposed,
                    "cost": float(row["cost"]),
                    "total_tokens": int(row["total_tokens"]),
                    "created_at": row["created_at"],
                    "risk_score": risk_score,
                    "risk_level": risk_level,
                }
            )

    category_counter = Counter(r["category"] for r in processed_rows)
    masking_counter = Counter(r["masking_status"] for r in processed_rows)
    dept_counter = Counter(r["department"] for r in processed_rows)
    sensitive_type_counter = Counter()

    for r in processed_rows:
        sensitive_type_counter.update(r["detected_sensitive_types"])

    dept_category = defaultdict(Counter)
    for r in processed_rows:
        dept_category[r["department"]][r["category"]] += 1

    print("=" * 80)
    print("AI/ML PIPELINE EVALUATION")
    print("=" * 80)
    print("csv rows:", len(all_rows))
    print("processed:", len(processed_rows))
    print("rejected:", len(rejected_rows))
    print("leak rows:", len(leak_rows))
    print("missed expected rows:", len(missed_expected_rows))
    print("category:", category_counter)
    print("masking_status:", masking_counter)
    print("departments:", dept_counter)
    print("sensitive types:", sensitive_type_counter)

    print("\nDepartment x Category")
    for dept, counter in dept_category.items():
        print(dept, dict(counter))

    write_csv(OUT_DIR / "leak_rows.csv", leak_rows)
    write_csv(OUT_DIR / "missed_expected_rows.csv", missed_expected_rows)
    write_csv(OUT_DIR / "rejected_rows.csv", rejected_rows)

    category_rows = [
        {"category": k, "count": v}
        for k, v in category_counter.most_common()
    ]
    write_csv(OUT_DIR / "category_distribution.csv", category_rows)

    masking_rows = [
        {"masking_status": k, "count": v}
        for k, v in masking_counter.most_common()
    ]
    write_csv(OUT_DIR / "masking_distribution.csv", masking_rows)

    sensitive_rows = [
        {"sensitive_type": k, "count": v}
        for k, v in sensitive_type_counter.most_common()
    ]
    write_csv(OUT_DIR / "sensitive_type_distribution.csv", sensitive_rows)

    # Clustering + recommendation
    rec = generate_cluster_based_recommendations(
        processed_rows=processed_rows,
        group_by_department=True,
        max_clusters_per_group=8,
        max_cards=5,
    )

    clustered_rows = rec["clustered_rows"]
    cluster_profiles = rec["cluster_profiles"]
    recommendation_cards = rec["recommendation_cards"]

    print("\nClustering")
    print("clustered_rows:", len(clustered_rows))
    print("cluster_profiles:", len(cluster_profiles))
    print("recommendation_cards:", len(recommendation_cards))

    if recommendation_cards:
        print("first_card:", json.dumps(recommendation_cards[0], ensure_ascii=False, indent=2))

    # 저장
    write_csv(
        OUT_DIR / "cluster_profiles.csv",
        [
            {
                **p,
                "representative_masked_prompts": " || ".join(p.get("representative_masked_prompts", [])),
            }
            for p in cluster_profiles
        ],
    )

    write_csv(
        OUT_DIR / "recommendation_cards.csv",
        [
            {
                **card,
                "expected_effect": " || ".join(card.get("expected_effect", [])),
                "security_guardrails": " || ".join(card.get("security_guardrails", [])),
            }
            for card in recommendation_cards
        ],
    )

    # cluster별 대표 샘플 저장
    sample_rows = []
    by_cluster = defaultdict(list)
    for r in clustered_rows:
        by_cluster[r.get("sub_cluster_id")].append(r)

    for cluster_id, rows in by_cluster.items():
        for r in rows[:5]:
            sample_rows.append(
                {
                    "sub_cluster_id": cluster_id,
                    "department": r.get("department"),
                    "category": r.get("category"),
                    "masked_text": r.get("masked_text"),
                    "risk_score": r.get("risk_score"),
                    "risk_level": r.get("risk_level"),
                }
            )

    write_csv(OUT_DIR / "cluster_sample_rows.csv", sample_rows)

    print("\nSaved reports:")
    for p in sorted(OUT_DIR.glob("*.csv")):
        print("-", p)


if __name__ == "__main__":
    main()