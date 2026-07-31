"""
Unified Agent Execution Engine for AI Workforce.
Processes incoming chat messages for HR, Knowledge, Legal, IT, Finance, Sales, and CEO agents.
These deterministic tool flows emit audit logs but do not claim provider token usage.
"""

import logging
import re
from typing import Dict, Any, List
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models import User, AIAgent
from app.services.hr_service import query_leave_balance, request_leave
from app.services.rag_service import hybrid_search_documents
from app.services.legal_service import audit_contract_text
from app.services.it_service import handle_it_request
from app.services.finance_service import audit_invoice_and_reconcile
from app.services.sales_service import handle_sales_request
from app.services.ceo_service import generate_and_execute_ceo_dag
from app.services.audit_service import log_audit_action

logger = logging.getLogger(__name__)


def _require_tool(agent: AIAgent, tool_name: str) -> None:
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

        if any(keyword in msg_lower for keyword in ["xin nghỉ", "xin nghỉ phép", "nghỉ phép", "nghỉ 1 ngày", "nghỉ 2 ngày", "nghỉ 3 ngày"]):
            _require_tool(agent, "request_leave")
            days_match = re.search(r'(\d+)\s*ngày', msg_lower)
            days = int(days_match.group(1)) if days_match else 1

            reason_match = re.search(r'vì\s+(.+)', message, re.IGNORECASE) or re.search(r'lý do\s+(.+)', message, re.IGNORECASE)
            reason = reason_match.group(1).strip() if reason_match else "Việc cá nhân"

            req_result = request_leave(db, user, days=days, reason=reason)

            response_data["tools_executed"].append({
                "tool_name": "request_leave",
                "input": {"days": days, "reason": reason},
                "result": "Success" if req_result["success"] else "Failed",
            })

            log_audit_action(db, user.tenant_id, "HR", "request_leave", {"days": days}, {"success": req_result["success"]})

            if req_result["success"]:
                response_data["reply"] = (
                    f"Chào **{user.full_name}**, tôi đã ghi nhận yêu cầu nghỉ phép **{days} ngày** (Lý do: {reason}).\n\n"
                    f"Thẻ Phê Duyệt (Approval Card) đã được gửi tới Quản lý của bạn. Sau khi Quản lý phê duyệt, hệ thống sẽ tự động cập nhật số ngày phép của bạn."
                )
                response_data["approval_card"] = req_result["approval_card"]
            else:
                response_data["reply"] = req_result["message"]

            return response_data

        elif any(keyword in msg_lower for keyword in ["còn bao nhiêu ngày phép", "số ngày phép", "phép còn lại", "ngày phép", "quỹ phép"]):
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
            return response_data

        else:
            _require_tool(agent, "hybrid_rag_search")
            search_results = hybrid_search_documents(
                db,
                user.tenant_id,
                message,
                department="HR",
                collections=agent.knowledge_access or None,
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
                response_data["reply"] = (
                    f"Dựa trên quy định HR của công ty:\n\n"
                    f"{top_result['content']}\n\n"
                    f"{top_result['citation_tag']}"
                )
            else:
                response_data["reply"] = (
                    f"Tôi là HR AI Employee. Bạn có thể hỏi tôi về quy định nghỉ phép, "
                    f"tra cứu số ngày phép còn lại hoặc gửi đơn xin nghỉ phép."
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
            collections=agent.knowledge_access or None,
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
