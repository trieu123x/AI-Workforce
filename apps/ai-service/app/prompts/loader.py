from functools import lru_cache
from pathlib import Path


PROMPT_ROOT = Path(__file__).parent


@lru_cache(maxsize=128)
def load_prompt(key: str) -> str:
    path = (PROMPT_ROOT / f"{key}.txt").resolve()
    if PROMPT_ROOT.resolve() not in path.parents:
        raise ValueError("Invalid prompt key")
    return path.read_text(encoding="utf-8").strip()
