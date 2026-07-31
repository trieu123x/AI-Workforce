def validate_input(text: str, *, max_characters: int = 50000) -> str:
    normalized = text.strip()
    if not normalized:
        raise ValueError("Input cannot be empty")
    if len(normalized) > max_characters:
        raise ValueError("Input exceeds the configured limit")
    return normalized
