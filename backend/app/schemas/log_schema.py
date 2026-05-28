REQUIRED_COLUMNS = [
    "log_id",
    "department",
    "user_hash",
    "prompt_text",
    "model",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cost",
    "created_at",
]

def validate_columns(columns: list[str]) -> tuple[bool, list[str]]:
    missing = [col for col in REQUIRED_COLUMNS if col not in columns]
    return len(missing) == 0, missing
