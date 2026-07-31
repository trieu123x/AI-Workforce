from typing import Any

from pydantic import BaseModel, Field


class AgentState(BaseModel):
    thread_id: str
    initiator_role: str
    current_agent: str
    messages: list[dict[str, str]] = Field(default_factory=list)
    context: list[dict[str, Any]] = Field(default_factory=list)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    execution_trace: list[dict[str, Any]] = Field(default_factory=list)
    completed: bool = False
