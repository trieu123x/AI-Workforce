from app.agents.base.agent import BaseAgent


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.role.upper()] = agent

    def get(self, role: str) -> BaseAgent:
        normalized = role.upper()
        if normalized not in self._agents:
            raise KeyError(f"Unknown agent role: {role}")
        return self._agents[normalized]

    def resolve(self, requested_role: str | None, message: str) -> BaseAgent:
        if requested_role and requested_role.upper() in self._agents:
            return self.get(requested_role)
        lowered = message.lower()
        intent_map = (
            ("FINANCE", ("hóa đơn", "chi phí", "ngân sách", "invoice")),
            ("HR", ("nghỉ phép", "nhân sự", "tuyển dụng", "lương")),
            ("SOFTWARE_ENGINEER", ("code", "bug", "api", "database", "deploy")),
            ("PROJECT_MANAGER", ("task", "deadline", "dự án", "tiến độ")),
            ("CUSTOMER_SUPPORT", ("khách hàng", "ticket", "khiếu nại", "hỗ trợ")),
        )
        for role, keywords in intent_map:
            if any(keyword in lowered for keyword in keywords):
                return self.get(role)
        return self.get("CUSTOMER_SUPPORT")

    def all(self) -> list[BaseAgent]:
        return list(self._agents.values())


agent_registry = AgentRegistry()


def _register_defaults() -> None:
    from app.agents.customer_support.agent import agent as customer_support
    from app.agents.finance.agent import agent as finance
    from app.agents.human_resources.agent import agent as human_resources
    from app.agents.project_manager.agent import agent as project_manager
    from app.agents.software_engineer.agent import agent as software_engineer

    for item in (customer_support, human_resources, finance, project_manager, software_engineer):
        agent_registry.register(item)


_register_defaults()
