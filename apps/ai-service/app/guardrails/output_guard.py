def validate_grounded_output(answer: str, *, has_context: bool) -> str:
    if has_context and not answer.strip():
        raise ValueError("Grounded answer cannot be empty")
    return answer.strip()
