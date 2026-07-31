from app.agents.base.agent import BaseAgent

agent = BaseAgent(
    role="HR",
    name="Human Resources AI",
    description="Answer governed HR questions and prepare HR workflows.",
    capabilities=("search_hr_policy", "prepare_leave_request", "query_leave_balance"),
    system_prompt_key="system/human_resources",
)
