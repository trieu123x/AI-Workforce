"""
LangGraph Multi-Agent StateGraph Engine for AI Workforce.
Manages stateful multi-agent execution graphs, step-by-step node transitions, and fallback intent routing.
"""

import logging
import uuid
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentState(BaseModel):
    """LangGraph execution state schema."""
    thread_id: str
    initiator_role: str
    current_node: str
    messages: List[Dict[str, str]] = []
    task_dag: Optional[Dict[str, Any]] = None
    execution_trace: List[Dict[str, Any]] = []
    is_complete: bool = False


class LangGraphEngine:
    """StateGraph execution runner simulating LangGraph node transitions."""

    def __init__(self, thread_id: Optional[str] = None):
        self.thread_id = thread_id or f"th-{uuid.uuid4().hex[:8]}"

    def init_state(self, user_role: str, user_message: str) -> AgentState:
        return AgentState(
            thread_id=self.thread_id,
            initiator_role=user_role,
            current_node="Entrypoint",
            messages=[{"role": "user", "content": user_message}],
            execution_trace=[{"step": 0, "node": "Entrypoint", "status": "INIT"}],
        )

    def route_intent(self, state: AgentState, target_role: str) -> AgentState:
        """Transitions state from Entrypoint to target AI Employee node."""
        target_role_upper = target_role.upper()
        allowed_nodes = {"CEO", "HR", "LEGAL", "IT", "FINANCE", "SALES", "KNOWLEDGE"}
        
        if target_role_upper not in allowed_nodes:
            target_role_upper = "KNOWLEDGE"  # Safe fallback

        state.current_node = f"{target_role_upper}_Agent"
        state.execution_trace.append({
            "step": len(state.execution_trace),
            "node": state.current_node,
            "status": "EXECUTING",
        })
        return state

    def complete_state(self, state: AgentState, agent_reply: str) -> AgentState:
        state.messages.append({"role": "assistant", "content": agent_reply})
        state.is_complete = True
        state.execution_trace.append({
            "step": len(state.execution_trace),
            "node": state.current_node,
            "status": "COMPLETED",
        })
        return state
