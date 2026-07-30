"""Enterprise Knowledge Base with document ACL, collections and file ingestion."""

import csv
import io
import ipaddress
import socket
import zipfile
from html.parser import HTMLParser
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import AnyHttpUrl, BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.models.models import DocumentChunk, User
from app.services.rag_service import hybrid_search_documents, ingest_document
from app.services.notification_service import create_notification

router = APIRouter(prefix="/documents", tags=["Knowledge Documents"])
KB_MANAGERS = {"Owner", "Admin", "CEO", "Manager"}
VALID_DEPARTMENTS = {"BOARD", "HR", "LEGAL", "IT", "FINANCE", "SALES", "ALL"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


def _notify_indexed(db: Session, user: User, document_name: str, chunks: int) -> None:
    create_notification(
        db,
        user=user,
        event_type="DOCUMENT_READY",
        title="Tài liệu đã xử lý xong",
        message=f"{document_name}: {chunks} chunks đã được lập chỉ mục.",
        severity="SUCCESS",
        entity_type="DOCUMENT",
        entity_id=document_name,
    )
    db.commit()


class RAGSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20)
    collections: Optional[list[str]] = None


class DocumentChunkResponse(BaseModel):
    id: str
    document_name: str
    section_title: str
    content: str
    score: float
    citation_tag: str


class DocumentUpdateRequest(BaseModel):
    document_name: Optional[str] = Field(None, min_length=1, max_length=255)
    collection_name: Optional[str] = Field(None, min_length=1, max_length=100)
    department_access: Optional[str] = None


class WebsiteImportRequest(BaseModel):
    url: AnyHttpUrl
    document_name: Optional[str] = Field(None, min_length=1, max_length=255)
    collection_name: str = Field(default="Website Imports", min_length=1, max_length=100)
    department_access: str = "ALL"


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._ignored_depth += 1
        elif tag in {"p", "div", "section", "article", "h1", "h2", "h3", "li", "br"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(part for part in self.parts if part.strip())


def _validate_management(current_user: User, department_access: str) -> str:
    if current_user.role not in KB_MANAGERS:
        raise HTTPException(status_code=403, detail="Insufficient permission to manage knowledge")
    department = department_access.upper()
    if department not in VALID_DEPARTMENTS:
        raise HTTPException(status_code=422, detail="Unsupported department_access")
    if current_user.role == "Manager" and department not in {
        current_user.department, "ALL"
    }:
        raise HTTPException(status_code=403, detail="Manager cannot publish to another department")
    return department


def _visible_chunks_query(db: Session, current_user: User):
    query = db.query(DocumentChunk).filter(
        DocumentChunk.tenant_id == current_user.tenant_id
    )
    if current_user.role in {"Owner", "Admin", "CEO"}:
        return query
    return query.filter(
        DocumentChunk.department_access.in_(("ALL", current_user.department))
    )


def _extract_docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            xml = archive.read("word/document.xml")
        root = ElementTree.fromstring(xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paragraphs = [
            "".join(node.text or "" for node in paragraph.iter(f"{namespace}t"))
            for paragraph in root.iter(f"{namespace}p")
        ]
        return "\n".join(text for text in paragraphs if text.strip())
    except (KeyError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
        raise HTTPException(status_code=422, detail="Invalid DOCX file") from exc


def _extract_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="PDF parser is not installed") from exc
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid or encrypted PDF file") from exc


def _extract_file_text(filename: str, data: bytes) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in {"txt", "md"}:
        return data.decode("utf-8-sig")
    if extension == "csv":
        decoded = data.decode("utf-8-sig")
        rows = csv.reader(io.StringIO(decoded))
        return "\n".join(" | ".join(cell.strip() for cell in row) for row in rows)
    if extension == "docx":
        return _extract_docx(data)
    if extension == "pdf":
        return _extract_pdf(data)
    raise HTTPException(
        status_code=415,
        detail="Supported file types: PDF, DOCX, TXT, MD and CSV",
    )


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=422, detail="Only public HTTP(S) URLs are allowed")
    try:
        addresses = {
            item[4][0]
            for item in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
            )
        }
    except socket.gaierror as exc:
        raise HTTPException(status_code=422, detail="Website hostname cannot be resolved") from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise HTTPException(status_code=422, detail="Private or reserved network URLs are blocked")


def _download_public_html(initial_url: str) -> tuple[str, str]:
    current_url = initial_url
    with httpx.Client(timeout=15.0, follow_redirects=False) as client:
        for _ in range(4):
            _validate_public_url(current_url)
            with client.stream("GET", current_url, headers={"User-Agent": "AI-Workforce-KB/1.0"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise HTTPException(status_code=422, detail="Website redirect is missing Location")
                    current_url = urljoin(current_url, location)
                    continue
                if response.status_code >= 400:
                    raise HTTPException(status_code=422, detail=f"Website returned HTTP {response.status_code}")
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    raise HTTPException(status_code=415, detail="Website did not return HTML content")
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > 5 * 1024 * 1024:
                        raise HTTPException(status_code=413, detail="Website exceeds the 5 MB import limit")
                    chunks.append(chunk)
                return current_url, b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
    raise HTTPException(status_code=422, detail="Website has too many redirects")


@router.get("/", summary="List visible knowledge documents")
def list_documents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[dict[str, Any]]:
    chunks = _visible_chunks_query(db, current_user).order_by(
        DocumentChunk.created_at.desc()
    ).all()
    docs: dict[str, dict[str, Any]] = {}
    for chunk in chunks:
        key = chunk.document_id or chunk.document_name
        item = docs.setdefault(key, {
            "document_id": key,
            "document_name": chunk.document_name,
            "collection_name": chunk.collection_name,
            "department_access": chunk.department_access,
            "chunk_count": 0,
            "status": "INDEXED",
            "created_at": chunk.created_at.isoformat() if chunk.created_at else None,
        })
        item["chunk_count"] += 1
    return list(docs.values())


@router.post("/search", response_model=list[DocumentChunkResponse], summary="Search knowledge")
def search_rag(
    req: RAGSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> list[DocumentChunkResponse]:
    results = hybrid_search_documents(
        db=db,
        tenant_id=current_user.tenant_id,
        query_text=req.query,
        department=(
            "*" if current_user.role in {"Owner", "Admin", "CEO"}
            else current_user.department
        ),
        top_k=req.top_k,
        collections=req.collections,
    )
    return [DocumentChunkResponse(**result) for result in results]


@router.post("/ingest-text", summary="Ingest text into a collection")
def ingest_text_document(
    document_name: str = Form(...),
    content: str = Form(...),
    department_access: str = Form("ALL"),
    collection_name: str = Form("General Knowledge"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    department = _validate_management(current_user, department_access)
    if not document_name.strip() or not content.strip():
        raise HTTPException(status_code=400, detail="Document name and content are required")
    chunks = ingest_document(
        db=db,
        tenant_id=current_user.tenant_id,
        document_name=document_name.strip(),
        content=content,
        department_access=department,
        collection_name=collection_name.strip() or "General Knowledge",
    )
    _notify_indexed(db, current_user, document_name.strip(), len(chunks))
    return {
        "success": True,
        "document_id": document_name.strip(),
        "document_name": document_name.strip(),
        "status": "INDEXED",
        "chunks_created": len(chunks),
    }


@router.post("/upload", status_code=201, summary="Upload PDF, DOCX, TXT or CSV")
async def upload_document(
    file: UploadFile = File(...),
    department_access: str = Form("ALL"),
    collection_name: str = Form("General Knowledge"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    department = _validate_management(current_user, department_access)
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit")
    filename = (file.filename or "document").strip()
    content = _extract_file_text(filename, data).strip()
    if not content:
        raise HTTPException(status_code=422, detail="No readable text found in the file")
    chunks = ingest_document(
        db=db,
        tenant_id=current_user.tenant_id,
        document_name=filename,
        content=content,
        department_access=department,
        collection_name=collection_name.strip() or "General Knowledge",
    )
    _notify_indexed(db, current_user, filename, len(chunks))
    return {
        "success": True,
        "document_id": filename,
        "document_name": filename,
        "status": "INDEXED",
        "chunks_created": len(chunks),
    }


@router.post("/import-website", status_code=201, summary="Import a public website")
def import_website(
    req: WebsiteImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    department = _validate_management(current_user, req.department_access)
    final_url, html = _download_public_html(str(req.url))
    parser = _HTMLTextExtractor()
    parser.feed(html)
    content = parser.text().strip()
    if not content:
        raise HTTPException(status_code=422, detail="No readable text found on website")
    name = req.document_name or urlparse(final_url).hostname or "website"
    chunks = ingest_document(
        db=db,
        tenant_id=current_user.tenant_id,
        document_name=name,
        content=content,
        department_access=department,
        collection_name=req.collection_name,
        source_metadata={"source_type": "WEBSITE", "source_url": final_url},
    )
    _notify_indexed(db, current_user, name, len(chunks))
    return {
        "success": True,
        "document_id": name,
        "document_name": name,
        "source_url": final_url,
        "status": "INDEXED",
        "chunks_created": len(chunks),
    }


@router.patch("/{document_id}", summary="Update document metadata")
def update_document(
    document_id: str,
    req: DocumentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    if current_user.role not in KB_MANAGERS:
        raise HTTPException(status_code=403, detail="Insufficient permission to manage knowledge")
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.tenant_id == current_user.tenant_id,
        or_(
            DocumentChunk.document_id == document_id,
            DocumentChunk.document_name == document_id,
        ),
    ).all()
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role == "Manager" and any(
        chunk.department_access not in {"ALL", current_user.department} for chunk in chunks
    ):
        raise HTTPException(status_code=403, detail="Manager cannot edit this document")
    data = req.model_dump(exclude_unset=True)
    if "department_access" in data:
        data["department_access"] = _validate_management(
            current_user, data["department_access"]
        )
    for chunk in chunks:
        for field_name, value in data.items():
            setattr(chunk, field_name, value)
    db.commit()
    return {"message": "Document updated successfully", "chunks_updated": len(chunks)}


@router.delete("/{document_id}", summary="Delete a document and all of its chunks")
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    if current_user.role not in KB_MANAGERS:
        raise HTTPException(status_code=403, detail="Insufficient permission to manage knowledge")
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.tenant_id == current_user.tenant_id,
        or_(
            DocumentChunk.document_id == document_id,
            DocumentChunk.document_name == document_id,
        ),
    ).all()
    if not chunks:
        raise HTTPException(status_code=404, detail="Document not found")
    if current_user.role == "Manager" and any(
        chunk.department_access not in {"ALL", current_user.department} for chunk in chunks
    ):
        raise HTTPException(status_code=403, detail="Manager cannot delete this document")
    for chunk in chunks:
        db.delete(chunk)
    db.commit()
    return {"message": "Document deleted successfully", "chunks_deleted": len(chunks)}
