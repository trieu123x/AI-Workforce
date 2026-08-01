from app.agents.base.agent import BaseAgent

agent = BaseAgent(
    role="HR",
    name="Human Resources AI",
    description="Answer governed HR questions and prepare HR workflows.",
    capabilities=(
        "search_hr_policy",
        "get_employee_basic_profile",
        "get_employee_private_profile",
        "get_employee_contract_summary",
        "get_employee_compensation_summary",
        "get_employee_leave_summary",
        "get_employee_full_profile",
        "query_company_users_sql",
        "search_employee_profiles",
        "query_leave_balance",
        "create_leave_request",
        "create_onboarding_workflow",
        "get_contract_expiry",
        "list_pending_hr_approvals",
        "create_hr_task",
        "send_hr_notification",
    ),
    system_prompt_key="system/human_resources",
)
