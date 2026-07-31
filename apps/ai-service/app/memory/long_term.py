from dataclasses import dataclass


@dataclass(frozen=True)
class LongTermMemoryRecord:
    tenant_id: str
    user_id: str
    key: str
    value: str
    sensitivity: str = "internal"
