from app.llm.base import LLMProvider, LLMResult


def generate_with_fallback(
    providers: list[LLMProvider],
    messages: list[dict[str, str]],
    *,
    model: str | None = None,
) -> LLMResult:
    failures: list[str] = []
    for provider in providers:
        try:
            return provider.generate(messages, model=model)
        except Exception as exc:
            failures.append(f"{provider.name}: {exc.__class__.__name__}")
    raise RuntimeError(f"All LLM providers failed: {', '.join(failures)}")
