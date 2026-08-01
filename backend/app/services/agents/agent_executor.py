"""
Unified Agent Execution Engine for AI Workforce.
Processes incoming chat messages for HR, Knowledge, Legal, IT, Finance, Sales, and CEO agents.
These deterministic tool flows emit audit logs but do not claim provider token usage.
"""

import logging
import re
import unicodedata
from datetime import date
from typing import Dict, Any, List
from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.models.models import (
    AIAgent,
    AgentWorkflow,
    ChatConversation,
    ChatMessage,
    User,
    WorkflowApproval,
)
from app.services.audit_events import add_audit_event
from app.services.hr_service import (
    can_manage_hr,
    can_approve_hr_request,
    create_onboarding_case,
    hr_scope_label,
    query_leave_balance,
    request_leave,
    scoped_employee_query,
)
from app.services.hr_employee_tools import (
    get_employee_sections,
    list_contract_status_summaries,
    query_company_users_sql,
)
from app.services.rag_service import hybrid_search_documents
from app.services.legal_service import audit_contract_text
from app.services.it_service import handle_it_request
from app.services.finance_service import audit_invoice_and_reconcile
from app.services.sales_service import handle_sales_request
from app.services.ceo_service import generate_and_execute_ceo_dag
from app.services.audit_service import log_audit_action

logger = logging.getLogger(__name__)

HR_CORE_TOOLS = {
    "hybrid_rag_search",
    "get_employee_basic_profile",
    "get_employee_private_profile",
    "get_employee_contract_summary",
    "get_employee_compensation_summary",
    "get_employee_leave_summary",
    "get_employee_full_profile",
    "query_company_users_sql",
    "query_leave_balance",
    "request_leave",
    "create_onboarding_workflow",
    "get_contract_expiry",
    "list_pending_hr_approvals",
    "create_hr_task",
    "send_hr_notification",
}


def _repair_hr_agent_capabilities(agent: AIAgent) -> None:
    """Upgrade legacy HR configuration once; later Admin/Owner choices remain authoritative."""
    if agent.role_code != "HR":
        return
    version = agent.configuration_version or 1
    denied = set(agent.disallowed_actions or [])
    tools = set(agent.tools_access or [])
    allowed = set(agent.allowed_actions or [])
    if version < 2:
        required = HR_CORE_TOOLS - denied
        tools |= required
        allowed |= required
    if version < 3:
        profile_tools = {
            "get_employee_basic_profile",
            "get_employee_private_profile",
            "get_employee_contract_summary",
            "get_employee_compensation_summary",
            "get_employee_leave_summary",
            "get_employee_full_profile",
        }
        legacy_enabled = "get_employee_profile" in tools and "get_employee_profile" not in denied
        legacy_denied = "get_employee_profile" in denied
        tools.discard("get_employee_profile")
        allowed.discard("get_employee_profile")
        denied.discard("get_employee_profile")
        if legacy_enabled:
            tools |= profile_tools
            allowed |= profile_tools
        elif legacy_denied:
            denied |= profile_tools
    if version < 4:
        if "get_employee_basic_profile" in tools and "get_employee_basic_profile" not in denied:
            tools.add("query_company_users_sql")
            allowed.add("query_company_users_sql")
        else:
            denied.add("query_company_users_sql")
        agent.configuration_version = 4
    agent.tools_access = sorted(tools)
    agent.allowed_actions = sorted(allowed)
    agent.disallowed_actions = sorted(denied)


def _require_tool(agent: AIAgent, tool_name: str) -> None:
    _repair_hr_agent_capabilities(agent)
    tools = set(agent.tools_access or [])
    allowed = set(agent.allowed_actions or [])
    denied = set(agent.disallowed_actions or [])
    if tool_name in denied:
        raise HTTPException(
            status_code=403,
            detail=f"AI Employee is explicitly forbidden from action '{tool_name}'",
        )
    if tool_name not in tools or (allowed and tool_name not in allowed):
        raise HTTPException(
            status_code=403,
            detail=f"AI Employee is not allowed to use tool '{tool_name}'",
        )


def _employee_profile_payload(
    db: Session,
    actor: User,
    employee: User,
    *,
    requested_sections: list[str],
    purpose: str,
    tool_name: str,
) -> dict[str, Any]:
    access = get_employee_sections(
        db,
        actor=actor,
        employee_id=employee.id,
        requested_sections=requested_sections,
        purpose=purpose,
        tool_name=tool_name,
    )
    basic = access["data"].get("basic", {})
    return {
        "type": "EMPLOYEE_PROFILE",
        "employee": basic,
        "leave_balance": access["data"].get("leave"),
        "private": access["data"].get("private"),
        "contracts": access["data"].get("contract"),
        "compensation": access["data"].get("compensation"),
        "access": {
            "request_id": access["request_id"],
            "purpose": access["purpose"],
            "scope": access["scope"],
            "allowed_sections": access["allowed_sections"],
            "denied_sections": access["denied_sections"],
            "masked_fields": access["masked_fields"],
        },
    }


def _sql_directory_item(employee: dict[str, Any], *, scope: str) -> dict[str, Any]:
    return {
        "type": "EMPLOYEE_PROFILE",
        "employee": employee,
        "leave_balance": None,
        "access": {
            "scope": scope,
            "purpose": "DIRECTORY_LOOKUP",
            "allowed_sections": ["BASIC"],
        },
    }


def _employee_profile_reply(payload: dict[str, Any]) -> str:
    employee = payload["employee"]
    balance = payload.get("leave_balance")
    reply = (
        f"Hồ sơ nhân sự của **{employee['name']}**:\n"
        f"- Email: **{employee['email']}**\n"
        f"- Vai trò: **{employee['role']}**\n"
        f"- Phòng ban: **{employee['department']}**\n"
        f"- Chức danh: **{employee['job_title'] or 'Chưa cập nhật'}**\n"
        f"- Trạng thái: **{employee['employment_status']}**\n"
        f"- Quản lý trực tiếp: **{employee['manager_name'] or 'Chưa thiết lập'}**"
    )
    if balance:
        reply += f"\n- Phép còn lại: **{balance['remaining_days']} ngày**"
    private = payload.get("private") or {}
    if private:
        reply += (
            f"\n- Điện thoại: **{private.get('phone') or 'Chưa cập nhật'}**"
            f"\n- Khu vực: **{private.get('city') or 'Chưa cập nhật'}"
            f"{', ' + private['country'] if private.get('country') else ''}**"
        )
    compensation = payload.get("compensation") or {}
    if compensation:
        salary = compensation.get("monthly_salary")
        salary_text = f"{salary:,.0f}" if isinstance(salary, (int, float)) else "Chưa cập nhật"
        reply += (
            f"\n- Lương tháng: **{salary_text} {compensation.get('salary_currency') or 'VND'}**"
        )
    contracts = payload.get("contracts")
    if contracts is not None:
        reply += f"\n- Hợp đồng được phép xem: **{len(contracts)}**"
    access = payload.get("access") or {}
    if access:
        reply += (
            f"\n\nPhạm vi dữ liệu: **{', '.join(access.get('allowed_sections') or [])}** · "
            f"Mục đích: **{access.get('purpose')}**."
        )
    return reply


def _normalize_intent_text(message: str) -> str:
    normalized = unicodedata.normalize("NFD", message.lower().replace("đ", "d"))
    return " ".join(
        "".join(char for char in normalized if unicodedata.category(char) != "Mn").split()
    )


def _classify_hr_intent(message: str) -> str:
    """Separate read-only HR questions from state-changing HR actions."""
    normalized = _normalize_intent_text(message)
    if any(term in normalized for term in (
        "con bao nhieu ngay phep",
        "so ngay phep",
        "phep con lai",
        "quy phep",
    )):
        return "QUERY_LEAVE_BALANCE"
    if any(term in normalized for term in (
        "xuat file",
        "export file",
        "tai file",
        "xuat bao cao",
    )):
        return "ACTION_EXPORT"

    leave_context = "nghi" in normalized and "phep" in normalized
    informational_markers = (
        "chinh sach",
        "quy dinh",
        "thu tuc",
        "quy trinh",
        "dieu kien",
        "cach ",
        "lam sao",
        "la gi",
        "nhu the nao",
        "co duoc",
        "co can",
        "bao nhieu",
        "can gi",
        "can nhung",
        "yeu cau gi",
        "huong dan",
    )
    if leave_context and any(marker in normalized for marker in informational_markers):
        return "INFORMATION"

    leave_action_markers = (
        "toi muon xin nghi",
        "toi muon nghi phep",
        "toi xin nghi",
        "cho toi xin nghi",
        "xin nghi phep",
        "xin phep nghi",
        "tao don nghi",
        "gui don nghi",
        "nop don nghi",
        "dang ky nghi",
        "cho toi nghi",
    )
    if any(marker in normalized for marker in leave_action_markers):
        return "ACTION_LEAVE_REQUEST"
    return "INFORMATION"


_LEAVE_DATE_PATTERN = re.compile(
    r"\b(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}[/-]\d{1,2}[/-]\d{4})\b"
)


def _parse_leave_date(value: str) -> date | None:
    cleaned = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", cleaned):
            year, month, day = (int(part) for part in cleaned.split("-"))
        else:
            day, month, year = (int(part) for part in re.split(r"[/-]", cleaned))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _load_leave_draft(
    db: Session,
    user: User,
    thread_id: str | None,
) -> dict[str, Any] | None:
    if not thread_id:
        return None
    conversation = db.query(ChatConversation).filter(
        ChatConversation.tenant_id == user.tenant_id,
        ChatConversation.user_id == user.id,
        ChatConversation.thread_id == thread_id,
    ).first()
    if not conversation:
        return None
    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id,
        ChatMessage.sender == "ASSISTANT",
    ).order_by(ChatMessage.created_at.desc()).limit(20).all()
    for chat_message in messages:
        for attachment in chat_message.attachments or []:
            attachment_type = str(attachment.get("type", ""))
            payload = attachment.get("payload") or {}
            if (
                attachment_type == "APPROVAL_CARD"
                and payload.get("action_type") in {"XIN NGHỈ PHÉP", "LEAVE_REQUEST"}
            ):
                return None
            if (
                attachment_type == "HR_CARD"
                and payload.get("type") == "LEAVE_REQUEST_DRAFT"
            ):
                return payload if payload.get("status") == "COLLECTING" else None
    return None


def _extract_leave_slots(
    message: str,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    slots = {
        "start_date": (existing or {}).get("start_date"),
        "end_date": (existing or {}).get("end_date"),
        "reason": (existing or {}).get("reason"),
    }
    normalized = _normalize_intent_text(message)
    parsed_dates = [
        parsed
        for raw in _LEAVE_DATE_PATTERN.findall(message)
        if (parsed := _parse_leave_date(raw)) is not None
    ]
    if len(parsed_dates) >= 2:
        slots["start_date"] = parsed_dates[0].isoformat()
        slots["end_date"] = parsed_dates[1].isoformat()
    elif len(parsed_dates) == 1:
        parsed_value = parsed_dates[0].isoformat()
        if any(marker in normalized for marker in ("ket thuc", "den ngay", "toi ngay")):
            slots["end_date"] = parsed_value
        elif any(marker in normalized for marker in ("bat dau", "tu ngay")):
            slots["start_date"] = parsed_value
        elif not slots["start_date"]:
            slots["start_date"] = parsed_value
        elif not slots["end_date"]:
            slots["end_date"] = parsed_value

    reason_match = re.search(
        r"(?:vì|lý\s*do(?:\s+là)?|ly\s*do(?:\s+la)?)\s*[:\-]?\s*(.+)$",
        message,
        re.IGNORECASE,
    )
    if reason_match:
        reason = reason_match.group(1).strip(" .")
        if reason:
            slots["reason"] = reason
    elif existing and not slots["reason"] and not parsed_dates:
        # In an active slot-filling turn, a short plain answer can be the reason
        # even when the user chooses to provide that field before the dates.
        previous_missing = existing.get("missing_fields") or []
        informational_answer = "?" in message or any(marker in normalized for marker in (
            "chinh sach",
            "quy dinh",
            "thu tuc",
            "quy trinh",
            "bao nhieu",
            "la gi",
            "nhu the nao",
        ))
        if "reason" in previous_missing and not informational_answer:
            reason = message.strip(" .")
            if reason:
                slots["reason"] = reason
    return slots


def _leave_missing_fields(slots: dict[str, Any]) -> list[str]:
    return [
        field
        for field in ("start_date", "end_date", "reason")
        if not slots.get(field)
    ]


def _is_leave_draft_continuation(message: str, draft: dict[str, Any]) -> bool:
    normalized = _normalize_intent_text(message)
    if _LEAVE_DATE_PATTERN.search(message):
        return True
    if re.search(r"(?:vì|lý\s*do|ly\s*do)\s*[:\-]?", message, re.IGNORECASE):
        return True
    if "reason" in (draft.get("missing_fields") or []):
        return "?" not in message and not any(marker in normalized for marker in (
            "chinh sach",
            "quy dinh",
            "thu tuc",
            "quy trinh",
            "bao nhieu",
            "la gi",
            "nhu the nao",
        ))
    return False


def _leave_draft_card(
    slots: dict[str, Any],
    missing_fields: list[str],
    *,
    validation_error: str | None = None,
    status: str = "COLLECTING",
) -> dict[str, Any]:
    return {
        "type": "LEAVE_REQUEST_DRAFT",
        "status": status,
        "start_date": slots.get("start_date"),
        "end_date": slots.get("end_date"),
        "reason": slots.get("reason"),
        "missing_fields": missing_fields,
        "validation_error": validation_error,
    }


def _leave_follow_up_reply(slots: dict[str, Any], missing_fields: list[str]) -> str:
    labels = {
        "start_date": "ngày bắt đầu nghỉ (YYYY-MM-DD hoặc DD/MM/YYYY)",
        "end_date": "ngày kết thúc nghỉ (YYYY-MM-DD hoặc DD/MM/YYYY)",
        "reason": "lý do nghỉ",
    }
    missing_text = ", ".join(f"**{labels[field]}**" for field in missing_fields)
    known = []
    if slots.get("start_date"):
        known.append(f"Bắt đầu: **{slots['start_date']}**")
    if slots.get("end_date"):
        known.append(f"Kết thúc: **{slots['end_date']}**")
    if slots.get("reason"):
        known.append(f"Lý do: **{slots['reason']}**")
    known_text = "\n".join(f"- {item}" for item in known)
    prefix = f"Tôi đã ghi nhận:\n{known_text}\n\n" if known else ""
    return (
        f"{prefix}Để tạo đơn nghỉ phép, bạn vui lòng bổ sung {missing_text}. "
        "Tôi chỉ gửi đơn cho cấp trên sau khi đủ cả 3 thông tin."
    )


def execute_agent_chat(
    db: Session,
    user: User,
    role_code: str,
    message: str,
    thread_id: str | None = None,
) -> Dict[str, Any]:
    """
    Main dispatch entry point for processing agent queries.
    Returns structured response containing answer text, citations, tool calls, and specialized card payloads.
    """
    role_code_upper = role_code.upper()
    agent = db.query(AIAgent).filter(
        AIAgent.tenant_id == user.tenant_id,
        AIAgent.role_code == role_code_upper
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{role_code_upper}' not found")
    if not agent.is_active:
        raise HTTPException(status_code=409, detail=f"Agent '{role_code_upper}' is inactive")

    agent_name = agent.name if agent else f"{role_code_upper} Agent"
    agent_emoji = agent.avatar_emoji if agent else "🤖"

    response_data: Dict[str, Any] = {
        "agent_name": agent_name,
        "agent_role": role_code_upper,
        "avatar_emoji": agent_emoji,
        "reply": "",
        "citations": [],
        "tools_executed": [],
        "approval_card": None,
        "hr_card": None,
        "jira_card": None,
        "legal_risk_card": None,
        "invoice_card": None,
        "quote_card": None,
        "dag_plan_card": None,
    }

    # -----------------------------------------------------------------------
    # 1. HR Agent Processing
    # -----------------------------------------------------------------------
    if role_code_upper == "HR":
        msg_lower = message.lower()
        hr_intent = _classify_hr_intent(message)
        leave_draft = _load_leave_draft(db, user, thread_id)
        normalized_message = _normalize_intent_text(message)

        if leave_draft and any(marker in normalized_message for marker in (
            "huy don",
            "huy yeu cau",
            "khong xin nua",
            "khong nghi nua",
        )):
            cancelled_slots = _extract_leave_slots("", leave_draft)
            response_data["reply"] = (
                "Tôi đã hủy bản nháp xin nghỉ. Chưa có đơn nào được tạo hoặc gửi cho cấp trên."
            )
            response_data["hr_card"] = _leave_draft_card(
                cancelled_slots,
                _leave_missing_fields(cancelled_slots),
                status="CANCELLED",
            )
            return response_data

        if leave_draft and _is_leave_draft_continuation(message, leave_draft):
            hr_intent = "ACTION_LEAVE_REQUEST"

        if any(keyword in msg_lower for keyword in ["tạo onboarding", "khởi tạo onboarding", "onboard "]):
            _require_tool(agent, "create_onboarding_workflow")
            if not can_manage_hr(user):
                raise HTTPException(status_code=403, detail="Only HR can create onboarding workflows")
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", message)
            if not email_match:
                response_data["reply"] = (
                    "Để tạo onboarding an toàn, vui lòng cung cấp email nhân viên, "
                    "ví dụ: **Tạo onboarding cho new.hire@company.com**."
                )
                return response_data
            employee = db.query(User).filter(
                User.tenant_id == user.tenant_id,
                User.email == email_match.group(0).lower(),
            ).first()
            if not employee:
                response_data["reply"] = "Không tìm thấy nhân viên có email này trong workspace."
                return response_data
            case = create_onboarding_case(
                db,
                employee=employee,
                creator=user,
                start_date=date.today(),
                probation_end_date=None,
                mentor_id=None,
            )
            response_data["tools_executed"].append({
                "tool_name": "create_onboarding_workflow",
                "input": {"employee_id": str(employee.id)},
                "result": {"onboarding_id": str(case.id), "tasks": len(case.steps)},
            })
            response_data["reply"] = (
                f"Đã tạo workflow onboarding cho **{employee.full_name}** với "
                f"**{len(case.steps)} nhiệm vụ** cho HR, IT, quản lý, Finance và nhân viên."
            )
            response_data["hr_card"] = {
                "type": "ONBOARDING",
                "id": str(case.id),
                "employee_name": employee.full_name,
                "status": case.status,
                "start_date": case.start_date.isoformat(),
                "task_count": len(case.steps),
            }
            return response_data

        full_profile_markers = ["hồ sơ đầy đủ", "toàn bộ hồ sơ", "full profile"]
        if any(marker in msg_lower for marker in full_profile_markers):
            _require_tool(agent, "get_employee_full_profile")
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", message)
            if not email_match:
                response_data["reply"] = (
                    "Để kiểm soát đúng người và tránh lộ dữ liệu nhạy cảm, vui lòng cung cấp "
                    "**email công ty** của nhân viên và **mục đích nghiệp vụ**."
                )
                return response_data
            purpose_sections: tuple[str, list[str]] | None = None
            if any(marker in normalized_message for marker in ("gia han hop dong", "contract renewal")):
                purpose_sections = "CONTRACT_RENEWAL", ["BASIC", "CONTRACT"]
            elif any(marker in normalized_message for marker in ("danh gia cuoi nam", "danh gia hieu suat")):
                purpose_sections = "PERFORMANCE_REVIEW", ["BASIC", "PERFORMANCE"]
            elif "onboarding" in normalized_message:
                purpose_sections = "ONBOARDING", ["BASIC", "PRIVATE", "CONTRACT", "DOCUMENTS"]
            elif any(marker in normalized_message for marker in ("xu ly bang luong", "payroll")):
                purpose_sections = "PAYROLL_PROCESSING", ["BASIC", "COMPENSATION"]
            if not purpose_sections:
                response_data["reply"] = (
                    "Yêu cầu hồ sơ sâu bắt buộc có mục đích hợp lệ, ví dụ: "
                    "**gia hạn hợp đồng**, **đánh giá hiệu suất**, **onboarding** hoặc "
                    "**xử lý bảng lương**. Tôi chưa truy cập dữ liệu khi chưa có mục đích."
                )
                return response_data
            employee = db.query(User).filter(
                User.tenant_id == user.tenant_id,
                User.email == email_match.group(0).lower(),
            ).first()
            if not employee:
                response_data["reply"] = "Không tìm thấy nhân viên trong workspace hiện tại."
                return response_data
            purpose, requested_sections = purpose_sections
            profile_payload = _employee_profile_payload(
                db,
                user,
                employee,
                requested_sections=requested_sections,
                purpose=purpose,
                tool_name="get_employee_full_profile",
            )
            response_data["tools_executed"].append({
                "tool_name": "get_employee_full_profile",
                "input": {
                    "employee_id": str(employee.id),
                    "requested_sections": requested_sections,
                    "purpose": purpose,
                },
                "result": {
                    "allowed_sections": profile_payload["access"]["allowed_sections"],
                    "denied_sections": profile_payload["access"]["denied_sections"],
                    "masked_fields": profile_payload["access"]["masked_fields"],
                },
            })
            response_data["reply"] = _employee_profile_reply(profile_payload)
            response_data["hr_card"] = profile_payload
            return response_data

        if any(marker in msg_lower for marker in ["lương của tôi", "mức lương của tôi", "thu nhập của tôi"]):
            _require_tool(agent, "get_employee_compensation_summary")
            profile_payload = _employee_profile_payload(
                db,
                user,
                user,
                requested_sections=["BASIC", "COMPENSATION"],
                purpose="SELF_SERVICE",
                tool_name="get_employee_compensation_summary",
            )
            response_data["tools_executed"].append({
                "tool_name": "get_employee_compensation_summary",
                "input": {
                    "employee_id": str(user.id),
                    "requested_sections": ["BASIC", "COMPENSATION"],
                    "purpose": "SELF_SERVICE",
                },
                "result": "authorized_self_compensation",
            })
            response_data["reply"] = _employee_profile_reply(profile_payload)
            response_data["hr_card"] = profile_payload
            return response_data

        if any(marker in msg_lower for marker in ["thông tin cá nhân của tôi", "hồ sơ riêng tư của tôi"]):
            _require_tool(agent, "get_employee_private_profile")
            profile_payload = _employee_profile_payload(
                db,
                user,
                user,
                requested_sections=["BASIC", "PRIVATE"],
                purpose="SELF_SERVICE",
                tool_name="get_employee_private_profile",
            )
            response_data["tools_executed"].append({
                "tool_name": "get_employee_private_profile",
                "input": {
                    "employee_id": str(user.id),
                    "requested_sections": ["BASIC", "PRIVATE"],
                    "purpose": "SELF_SERVICE",
                },
                "result": "authorized_self_private_profile",
            })
            response_data["reply"] = _employee_profile_reply(profile_payload)
            response_data["hr_card"] = profile_payload
            return response_data

        if any(keyword in msg_lower for keyword in ["hồ sơ của tôi", "thông tin nhân sự của tôi"]):
            _require_tool(agent, "get_employee_full_profile")
            profile_payload = _employee_profile_payload(
                db,
                user,
                user,
                requested_sections=["BASIC", "LEAVE"],
                purpose="SELF_SERVICE",
                tool_name="get_employee_full_profile",
            )
            response_data["tools_executed"].append({
                "tool_name": "get_employee_full_profile",
                "input": {
                    "employee_id": str(user.id),
                    "requested_sections": ["BASIC", "LEAVE"],
                    "purpose": "SELF_SERVICE",
                },
                "result": "authorized_self_profile",
            })
            response_data["reply"] = _employee_profile_reply(profile_payload)
            response_data["hr_card"] = profile_payload
            return response_data

        manager_directory_keywords = [
            "danh sách quản lý",
            "danh sách quản lí",
            "liệt kê quản lý",
            "liệt kê quản lí",
            "các quản lý",
            "các quản lí",
            "danh sach quan ly",
        ]
        if any(keyword in msg_lower for keyword in manager_directory_keywords):
            _require_tool(agent, "query_company_users_sql")
            directory = query_company_users_sql(
                db,
                actor=user,
                roles=["Admin", "Manager"],
                active_only=True,
                limit=100,
            )
            items = [
                _sql_directory_item(employee, scope=directory["scope"])
                for employee in directory["items"]
            ]
            scope = directory["scope"]
            response_data["tools_executed"].append({
                "tool_name": "query_company_users_sql",
                "input": {
                    "directory": "managers",
                    "scope": scope,
                    "requested_sections": ["BASIC"],
                    "purpose": "DIRECTORY_LOOKUP",
                },
                "result_count": len(items),
            })
            response_data["reply"] = (
                f"Tôi tìm thấy **{len(items)} quản lý** trong phạm vi **{scope}** "
                "bạn được phép xem."
            )
            response_data["hr_card"] = {
                "type": "EMPLOYEE_SEARCH",
                "directory_type": "MANAGERS",
                "scope": scope,
                "items": items,
            }
            return response_data

        if any(keyword in msg_lower for keyword in ["danh sách nhân viên", "liệt kê nhân viên", "tất cả nhân viên"]):
            _require_tool(agent, "query_company_users_sql")
            directory = query_company_users_sql(
                db,
                actor=user,
                active_only=True,
                limit=100,
            )
            items = [
                _sql_directory_item(employee, scope=directory["scope"])
                for employee in directory["items"]
            ]
            scope = directory["scope"]
            response_data["tools_executed"].append({
                "tool_name": "query_company_users_sql",
                "input": {
                    "query": "*",
                    "scope": scope,
                    "requested_sections": ["BASIC"],
                    "purpose": "DIRECTORY_LOOKUP",
                },
                "result_count": len(items),
            })
            response_data["reply"] = (
                f"Tôi tìm thấy **{len(items)} nhân viên** trong phạm vi **{scope}** bạn được phép xem."
            )
            response_data["hr_card"] = {
                "type": "EMPLOYEE_SEARCH",
                "scope": scope,
                "items": items,
            }
            return response_data

        employee_search_keywords = [
            "tìm nhân viên",
            "tìm hồ sơ",
            "tra cứu nhân viên",
            "xem hồ sơ của",
            "hồ sơ nhân viên",
            "hồ sơ của ",
        ]
        if any(keyword in msg_lower for keyword in employee_search_keywords):
            _require_tool(agent, "query_company_users_sql")
            email_match = re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", message)
            search_term = email_match.group(0) if email_match else ""
            if not search_term:
                for pattern in [
                    r"(?:tìm nhân viên|tìm hồ sơ|tra cứu nhân viên|xem hồ sơ của|hồ sơ nhân viên|hồ sơ của)\s+(.+)",
                ]:
                    match = re.search(pattern, message, re.IGNORECASE)
                    if match:
                        search_term = match.group(1).strip(" .?!")
                        break
            if not search_term:
                response_data["reply"] = "Vui lòng cung cấp tên hoặc email nhân viên cần tra cứu."
                return response_data

            directory = query_company_users_sql(
                db,
                actor=user,
                search=search_term,
                active_only=False,
                limit=10,
            )
            matches = directory["items"]
            scope = directory["scope"]
            response_data["tools_executed"].append({
                "tool_name": "query_company_users_sql",
                "input": {
                    "query": search_term,
                    "scope": scope,
                    "requested_sections": ["BASIC"],
                    "purpose": "DIRECTORY_LOOKUP",
                },
                "result_count": len(matches),
            })
            if not matches:
                response_data["reply"] = (
                    "Không tìm thấy nhân viên phù hợp trong phạm vi bạn được phép xem."
                )
                return response_data
            if len(matches) == 1:
                profile_payload = _sql_directory_item(matches[0], scope=scope)
                response_data["reply"] = _employee_profile_reply(profile_payload)
                response_data["hr_card"] = profile_payload
                return response_data
            response_data["reply"] = (
                f"Tìm thấy **{len(matches)} hồ sơ** trong phạm vi **{scope}**. "
                "Bạn có thể tìm lại bằng email để chọn chính xác một người."
            )
            response_data["hr_card"] = {
                "type": "EMPLOYEE_SEARCH",
                "scope": scope,
                "items": [
                    _sql_directory_item(employee, scope=scope)
                    for employee in matches
                ],
            }
            return response_data

        if any(keyword in msg_lower for keyword in ["hợp đồng của tôi", "thử việc của tôi"]):
            _require_tool(agent, "get_employee_contract_summary")
            profile_payload = _employee_profile_payload(
                db,
                user,
                user,
                requested_sections=["BASIC", "CONTRACT"],
                purpose="SELF_SERVICE",
                tool_name="get_employee_contract_summary",
            )
            response_data["tools_executed"].append({
                "tool_name": "get_employee_contract_summary",
                "input": {"employee_id": str(user.id), "purpose": "SELF_SERVICE"},
                "result_count": len(profile_payload.get("contracts") or []),
            })
            response_data["reply"] = _employee_profile_reply(profile_payload)
            response_data["hr_card"] = profile_payload
            return response_data

        if "hợp đồng sắp hết hạn" in msg_lower:
            _require_tool(agent, "get_contract_expiry")
            contract_result = list_contract_status_summaries(
                db,
                actor=user,
                purpose="CONTRACT_STATUS_MONITORING",
                limit=10,
                tool_name="get_contract_expiry",
            )
            contracts = contract_result["items"]
            response_data["tools_executed"].append({
                "tool_name": "get_contract_expiry",
                "input": {
                    "scope": contract_result["scope"],
                    "purpose": contract_result["purpose"],
                },
                "result_count": len(contracts),
            })
            if not contracts:
                response_data["reply"] = "Không tìm thấy hợp đồng đang hiệu lực trong phạm vi bạn được phép xem."
            else:
                lines = [
                    f"- **{item['employee_name']}** · {item['contract_type']} · "
                    f"hết hạn {item['end_date'] or 'không thời hạn'}"
                    for item in contracts
                ]
                response_data["reply"] = "Các hợp đồng đang hiệu lực:\n" + "\n".join(lines)
            response_data["hr_card"] = {
                "type": "CONTRACTS",
                "scope": contract_result["scope"],
                "purpose": contract_result["purpose"],
                "items": contracts,
            }
            return response_data

        if any(keyword in msg_lower for keyword in ["đơn chờ duyệt", "yêu cầu chờ duyệt", "phê duyệt đang chờ"]):
            _require_tool(agent, "list_pending_hr_approvals")
            approvals = db.query(WorkflowApproval).join(AgentWorkflow).filter(
                AgentWorkflow.tenant_id == user.tenant_id,
                WorkflowApproval.status == "WAITING",
            ).order_by(WorkflowApproval.updated_at.desc()).all()
            visible = [item for item in approvals if can_approve_hr_request(db, user, item)]
            response_data["reply"] = (
                f"Bạn có **{len(visible)} yêu cầu** đang chờ xử lý."
                if visible else "Hiện không có yêu cầu nào đang chờ bạn phê duyệt."
            )
            response_data["hr_card"] = {
                "type": "PENDING_APPROVALS",
                "items": [
                    {
                        "id": str(item.id),
                        "workflow_title": item.workflow.title,
                        "action_type": item.action_type,
                        "risk_level": item.risk_level,
                        "payload": item.payload or {},
                        "status": item.status,
                        "expires_at": item.expires_at.isoformat() if item.expires_at else None,
                    }
                    for item in visible[:20]
                ],
            }
            return response_data

        if hr_intent == "ACTION_LEAVE_REQUEST":
            _require_tool(agent, "request_leave")
            slots = _extract_leave_slots(message, leave_draft)
            missing_fields = _leave_missing_fields(slots)
            if missing_fields:
                response_data["reply"] = _leave_follow_up_reply(slots, missing_fields)
                response_data["hr_card"] = _leave_draft_card(slots, missing_fields)
                return response_data

            parsed_start = date.fromisoformat(str(slots["start_date"]))
            parsed_end = date.fromisoformat(str(slots["end_date"]))
            if parsed_end < parsed_start:
                validation_error = "Ngày kết thúc phải bằng hoặc sau ngày bắt đầu."
                response_data["reply"] = (
                    f"{validation_error} Vui lòng cung cấp lại ngày kết thúc nghỉ."
                )
                response_data["hr_card"] = _leave_draft_card(
                    slots,
                    [],
                    validation_error=validation_error,
                )
                return response_data

            req_result = request_leave(
                db,
                user,
                days=None,
                reason=str(slots["reason"]),
                start_date=str(slots["start_date"]),
                end_date=str(slots["end_date"]),
            )

            response_data["tools_executed"].append({
                "tool_name": "request_leave",
                "input": {
                    "start_date": slots["start_date"],
                    "end_date": slots["end_date"],
                    "reason": slots["reason"],
                },
                "result": "Success" if req_result["success"] else "Failed",
            })

            log_audit_action(
                db,
                user.tenant_id,
                "HR",
                "request_leave",
                {
                    "start_date": slots["start_date"],
                    "end_date": slots["end_date"],
                },
                {"success": req_result["success"]},
            )

            if req_result["success"]:
                response_data["reply"] = (
                    f"Tôi đã tổng hợp và gửi đơn nghỉ phép của **{user.full_name}** tới cấp trên:\n"
                    f"- Ngày bắt đầu: **{slots['start_date']}**\n"
                    f"- Ngày kết thúc: **{slots['end_date']}**\n"
                    f"- Lý do: **{slots['reason']}**\n\n"
                    "Sau khi được phê duyệt, hệ thống sẽ cập nhật quỹ phép và đồng bộ lịch."
                )
                response_data["approval_card"] = req_result["approval_card"]
            else:
                response_data["reply"] = req_result["message"]
                response_data["hr_card"] = _leave_draft_card(
                    slots,
                    [],
                    validation_error=req_result["message"],
                )

            return response_data

        if hr_intent == "QUERY_LEAVE_BALANCE":
            _require_tool(agent, "query_leave_balance")
            bal = query_leave_balance(db, user)
            response_data["tools_executed"].append({
                "tool_name": "query_leave_balance",
                "input": {"user_id": str(user.id)},
                "result": bal,
            })
            log_audit_action(db, user.tenant_id, "HR", "query_leave_balance", {"user_id": str(user.id)}, bal)

            response_data["reply"] = (
                f"Thông tin số ngày phép của **{user.full_name}**:\n"
                f"- **Tổng số ngày phép năm**: {bal['total_days']} ngày\n"
                f"- **Đã sử dụng**: {bal['used_days']} ngày\n"
                f"- **Còn lại**: **{bal['remaining_days']} ngày** hưởng nguyên lương."
            )
            response_data["hr_card"] = {"type": "LEAVE_BALANCE", "balance": bal}
            return response_data

        if hr_intent == "ACTION_EXPORT":
            response_data["reply"] = (
                "Đây là một yêu cầu hành động xuất file. Bạn vui lòng cho biết muốn xuất "
                "**lịch sử hội thoại**, **danh sách nhân sự** hay **báo cáo HR**, và định dạng "
                "mong muốn (**PDF**, **Excel** hoặc **JSON**). Tôi chưa thực hiện xuất file "
                "khi chưa đủ phạm vi và định dạng."
            )
            return response_data

        else:
            _require_tool(agent, "hybrid_rag_search")
            search_results = hybrid_search_documents(
                db,
                user.tenant_id,
                message,
                department="HR",
                collections=None,
                agent_access=agent.knowledge_access if agent.knowledge_access else None,
                user_role=user.role,
                user_department=user.department,
            )
            response_data["tools_executed"].append({
                "tool_name": "hybrid_rag_search",
                "input": {"query": message},
                "result_count": len(search_results),
            })
            log_audit_action(
                db,
                user.tenant_id,
                "HR",
                "hybrid_rag_search",
                {"query": message},
                {
                    "count": len(search_results),
                    "chunks": [
                        {
                            "chunk_id": item["id"],
                            "document_id": item["document_id"],
                            "version": item["version"],
                            "page": item["page"],
                        }
                        for item in search_results
                    ],
                },
            )

            if search_results:
                top_result = search_results[0]
                response_data["citations"] = search_results
                policy_dates = []
                if top_result.get("effective_date"):
                    policy_dates.append(f"Hiệu lực từ {top_result['effective_date']}")
                if top_result.get("expiration_date"):
                    policy_dates.append(f"hết hiệu lực {top_result['expiration_date']}")
                policy_date_line = (
                    f"\n\n**Thông tin hiệu lực:** {' · '.join(policy_dates)}"
                    if policy_dates else ""
                )
                response_data["reply"] = (
                    f"Dựa trên quy định HR của công ty:\n\n"
                    f"{top_result['content']}\n\n"
                    f"{top_result['citation_tag']}"
                    f"{policy_date_line}"
                )
            else:
                response_data["reply"] = (
                    "Tôi chưa tìm thấy chính sách còn hiệu lực và phù hợp trong kho tài liệu HR. "
                    "Tôi sẽ không tự suy diễn quy định; vui lòng liên hệ HR để được xác nhận."
                )
            return response_data

    # -----------------------------------------------------------------------
    # 2. KNOWLEDGE Agent Processing (Hybrid RAG)
    # -----------------------------------------------------------------------
    elif role_code_upper == "KNOWLEDGE":
        _require_tool(agent, "hybrid_search_documents")
        search_results = hybrid_search_documents(
            db,
            user.tenant_id,
            message,
            department="*" if user.role in {"Owner", "Admin", "CEO"} else user.department,
            collections=None,
            agent_access=agent.knowledge_access if agent.knowledge_access else None,
            user_role=user.role,
            user_department=user.department,
        )

        # Out-of-domain query check: ensure at least some word overlap with knowledge base
        msg_words = set(re.findall(r'\w+', message.lower()))
        filtered_results = []
        for c in search_results:
            c_words = set(re.findall(r'\w+', c["content"].lower()))
            if len(msg_words.intersection(c_words)) > 0:
                filtered_results.append(c)

        search_results = filtered_results

        response_data["tools_executed"].append({
            "tool_name": "hybrid_search_documents",
            "input": {"query": message, "department": user.department},
            "result_count": len(search_results),
        })
        log_audit_action(
            db,
            user.tenant_id,
            "KNOWLEDGE",
            "hybrid_search_documents",
            {"query": message},
            {
                "count": len(search_results),
                "chunks": [
                    {
                        "chunk_id": item["id"],
                        "document_id": item["document_id"],
                        "version": item["version"],
                        "page": item["page"],
                    }
                    for item in search_results
                ],
            },
        )

        if search_results:
            response_data["citations"] = search_results
            best_chunk = search_results[0]
            citations_str = " ".join([c["citation_tag"] for c in search_results[:2]])

            response_data["reply"] = (
                f"Theo tài liệu tri thức doanh nghiệp:\n\n"
                f"{best_chunk['content']}\n\n"
                f"**Nguồn trích dẫn:** {citations_str}"
            )
        else:
            response_data["reply"] = (
                f"Hiện chưa tìm thấy tài liệu phù hợp trong Kho tri thức cho câu hỏi: *'{message}'*.\n"
                f"Bạn có thể tải thêm tài liệu quy định/SOP vào trang **Knowledge Base** để tôi truy xuất!"
            )
        return response_data

    # -----------------------------------------------------------------------
    # 3. LEGAL Agent Processing (Contract Risk Audit & Redline)
    # -----------------------------------------------------------------------
    elif role_code_upper == "LEGAL":
        _require_tool(agent, "audit_contract_risk")
        audit_res = audit_contract_text(message)
        response_data["tools_executed"].append({
            "tool_name": "audit_contract_risk",
            "input": {"text_length": len(message)},
            "risks_found": audit_res["total_risks_found"],
        })
        log_audit_action(db, user.tenant_id, "LEGAL", "audit_contract_risk", {"text_length": len(message)}, {"risks": audit_res["total_risks_found"]})

        response_data["reply"] = (
            f"Tôi là Legal Counsel AI Agent. Tôi đã rà soát nội dung hợp đồng và phát hiện **{audit_res['total_risks_found']} điều khoản có rủi ro cao**.\n\n"
            f"Thẻ Phân Tích Rủi Ro & Đề Xuất Sửa Đổi (.docx redline) đã được khởi tạo bên dưới."
        )
        response_data["legal_risk_card"] = audit_res
        return response_data

    # -----------------------------------------------------------------------
    # 4. IT Agent Processing (Technical Help & Jira Tickets)
    # -----------------------------------------------------------------------
    elif role_code_upper == "IT":
        it_res = handle_it_request(db, user, message)
        _require_tool(
            agent,
            "create_jira_ticket" if it_res.get("ticket_created") else "search_it_kb",
        )
        response_data["tools_executed"].append({
            "tool_name": "create_jira_ticket" if it_res.get("ticket_created") else "search_it_kb",
            "input": {"message": message},
            "result": "Jira Ticket Created" if it_res.get("ticket_created") else "KB Resolved",
        })
        log_audit_action(db, user.tenant_id, "IT", "create_jira_ticket" if it_res.get("ticket_created") else "search_it_kb", {"msg": message}, {"ticket": it_res.get("ticket_created")})

        response_data["reply"] = it_res["reply"]
        if it_res.get("jira_card"):
            response_data["jira_card"] = it_res["jira_card"]
        return response_data

    # -----------------------------------------------------------------------
    # 5. FINANCE Agent Processing (Invoice OCR & PO Reconciliation)
    # -----------------------------------------------------------------------
    elif role_code_upper == "FINANCE":
        _require_tool(agent, "reconcile_po_db")
        fin_res = audit_invoice_and_reconcile(message)
        response_data["tools_executed"].append({
            "tool_name": "reconcile_po_db",
            "input": {"text_length": len(message)},
            "status": fin_res["invoice_card"]["status"],
        })
        log_audit_action(db, user.tenant_id, "FINANCE", "reconcile_po_db", {"msg": message[:30]}, {"status": fin_res["invoice_card"]["status"]})

        response_data["reply"] = fin_res["reply"]
        response_data["invoice_card"] = fin_res["invoice_card"]
        return response_data

    # -----------------------------------------------------------------------
    # 6. SALES Agent Processing (Catalog Lookup & Quotation PDF)
    # -----------------------------------------------------------------------
    elif role_code_upper == "SALES":
        _require_tool(agent, "generate_quotation_pdf")
        sales_res = handle_sales_request(message, customer_name=user.full_name)
        response_data["tools_executed"].append({
            "tool_name": "generate_quotation_pdf",
            "input": {"message": message},
            "total_amount": sales_res["quote_card"]["total_amount"],
        })
        log_audit_action(db, user.tenant_id, "SALES", "generate_quotation_pdf", {"msg": message}, {"total": sales_res["quote_card"]["total_amount"]})

        response_data["reply"] = sales_res["reply"]
        response_data["quote_card"] = sales_res["quote_card"]
        return response_data

    # -----------------------------------------------------------------------
    # 7. CEO Agent (Master Orchestrator DAG)
    # -----------------------------------------------------------------------
    elif role_code_upper == "CEO":
        _require_tool(agent, "generate_and_execute_ceo_dag")
        ceo_res = generate_and_execute_ceo_dag(db, user, message)
        response_data["tools_executed"].append({
            "tool_name": "generate_and_execute_ceo_dag",
            "input": {"prompt": message},
            "subtasks_count": 4,
        })
        log_audit_action(db, user.tenant_id, "CEO", "generate_and_execute_ceo_dag", {"prompt": message}, {"nodes": 4})

        response_data["reply"] = ceo_res["reply"]
        response_data["dag_plan_card"] = ceo_res["dag_plan_card"]
        return response_data

    else:
        response_data["reply"] = f"Agent {role_code_upper} đã tiếp nhận chỉ thị: {message}"
        return response_data
