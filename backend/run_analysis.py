from pathlib import Path
import json
from app.services.analysis_pipeline import analyze_csv_file

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "data-sample" / "sample_llm_logs.csv"

if not CSV_PATH.exists():
    raise FileNotFoundError(f"샘플 CSV를 찾을 수 없습니다: {CSV_PATH}")

result = analyze_csv_file(CSV_PATH)

out_path = Path(__file__).resolve().parent / "analysis_result.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(f"분석 완료: {out_path}")
print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
