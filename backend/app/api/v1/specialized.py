"""
API Endpoints for Legal, IT, Finance, and Sales domain operations.
"""

from typing import Dict, Any, Optional, List
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.models import User
from app.services.legal_service import audit_contract_text
from app.services.it_service import handle_it_request
from app.services.finance_service import audit_invoice_and_reconcile
from app.services.sales_service import handle_sales_request

router = APIRouter(tags=["Specialized Domain APIs"])


class ContractAuditRequest(BaseModel):
    document_name: str = "Contract.pdf"
    contract_text: str


class CreateJiraTicketRequest(BaseModel):
    summary: str
    description: Optional[str] = None
    priority: str = "MEDIUM"


class AuditInvoiceRequest(BaseModel):
    invoice_text: str


class SalesQuotationRequest(BaseModel):
    customer_name: str = "Khách Hàng Doanh Nghiệp"
    item_query: str


# --- LEGAL ---
@router.post("/api/v1/legal/audit-contract", summary="Audit contract text for high-risk clauses")
def audit_contract_endpoint(
    req: ContractAuditRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return audit_contract_text(req.contract_text, req.document_name)


@router.get("/api/v1/legal/download-redline/{file_id}", response_class=PlainTextResponse, summary="Download contract redline docx file")
def download_redline(file_id: str):
    return f"SIMULATED REDLINE DOCX FILE FOR {file_id}\nAll penalty clauses adjusted to 8% max limit per Law."


# --- IT ---
@router.post("/api/v1/it/tickets", summary="Create Jira ticket for technical issue")
def create_jira_ticket_endpoint(
    req: CreateJiraTicketRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return handle_it_request(db, current_user, f"{req.summary} - {req.description or ''}")


# --- FINANCE ---
@router.post("/api/v1/finance/audit-invoice", summary="Audit invoice text and reconcile PO")
def audit_invoice_endpoint(
    req: AuditInvoiceRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return audit_invoice_and_reconcile(req.invoice_text)


# --- SALES ---
@router.post("/api/v1/sales/quotation", summary="Generate sales quotation PDF payload")
def generate_quotation_endpoint(
    req: SalesQuotationRequest,
    current_user: User = Depends(get_current_active_user),
) -> Dict[str, Any]:
    return handle_sales_request(req.item_query, customer_name=req.customer_name)


@router.get("/api/v1/sales/download-quote/{file_id}", response_class=PlainTextResponse, summary="Download sales PDF quotation file")
def download_quote(file_id: str):
    return f"SIMULATED PDF QUOTATION FILE FOR {file_id}\nOfficial AI Workforce Quotation Document."
