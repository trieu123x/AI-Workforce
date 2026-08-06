"""Generate simple, editable first-draft legal documents as DOCX or PDF."""

from __future__ import annotations

import io
import zipfile
from html import escape
from typing import Any


SUPPORTED_TEMPLATES = {
    "NDA": "Non-Disclosure Agreement",
    "EMPLOYMENT_CONTRACT": "Employment Contract",
    "FREELANCER_CONTRACT": "Freelancer Contract",
    "INTERNSHIP_CONTRACT": "Internship Agreement",
    "SERVICE_AGREEMENT": "Service Agreement",
    "SOFTWARE_DEVELOPMENT_CONTRACT": "Software Development Agreement",
    "MAINTENANCE_CONTRACT": "Software Maintenance Agreement",
}


def render_contract_text(document_type: str, fields: dict[str, Any]) -> str:
    title = SUPPORTED_TEMPLATES[document_type]
    party_a = str(fields.get("party_a") or fields.get("company") or "[COMPANY]")
    party_b = str(fields.get("party_b") or fields.get("person") or "[COUNTERPARTY]")
    effective_date = str(fields.get("effective_date") or "[EFFECTIVE DATE]")
    duration = str(fields.get("duration") or "[DURATION]")
    fee = str(fields.get("fee") or fields.get("allowance") or "[FEE / ALLOWANCE]")
    scope = str(fields.get("scope") or "[SCOPE OF WORK]")
    return f"""{title}

This {title} is made effective on {effective_date} between {party_a} (Party A) and {party_b} (Party B).

1. PURPOSE AND SCOPE
{scope}

2. TERM
This Agreement remains effective for {duration}, unless terminated earlier under Clause 8.

3. FEES AND PAYMENT
The agreed fee or allowance is {fee}. Payment is due within 30 days after receipt of a valid invoice, where applicable.

4. CONFIDENTIALITY
Each party must protect confidential information, use it only for this Agreement, and disclose it only to authorized persons. These duties survive for three years after termination.

5. DATA PROTECTION
Personal data must be processed only for the stated purpose, with appropriate security and in accordance with applicable law and company policy.

6. INTELLECTUAL PROPERTY
Pre-existing intellectual property remains with its owner. Ownership and permitted use of deliverables must be confirmed in the applicable statement of work.

7. LIABILITY
Except for fraud, wilful misconduct and obligations that cannot legally be limited, aggregate liability is capped at the fees paid under this Agreement in the preceding 12 months.

8. TERMINATION
Either party may terminate for material breach not cured within 15 days after written notice. Either party may terminate for convenience with 30 days' written notice.

9. GOVERNING LAW AND DISPUTES
This Agreement is governed by the laws of Vietnam. The parties will first attempt good-faith negotiation before commencing formal proceedings.

10. SIGNATURES

For {party_a}: ____________________    Date: __________

For {party_b}: ____________________    Date: __________

LEGAL REVIEW NOTICE
This is an AI-generated first draft. It must be reviewed and approved by authorized Legal personnel before signature.
"""


def _docx_bytes(text: str) -> bytes:
    paragraphs = "".join(
        f'<w:p><w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r></w:p>'
        for line in text.splitlines()
    )
    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{paragraphs}<w:sectPr/></w:body></w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'''
    relationships = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'''
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", relationships)
        archive.writestr("word/document.xml", document_xml)
    return output.getvalue()


def _pdf_bytes(text: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    output = io.BytesIO()
    pdf = canvas.Canvas(output, pagesize=A4)
    width, height = A4
    cursor_y = height - 54
    for raw_line in text.splitlines():
        words = raw_line.encode("latin-1", "replace").decode("latin-1").split()
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if pdf.stringWidth(candidate, "Helvetica", 10) > width - 108:
                lines.append(current)
                current = word
            else:
                current = candidate
        lines.append(current)
        for line in lines or [""]:
            if cursor_y < 54:
                pdf.showPage()
                cursor_y = height - 54
            pdf.setFont("Helvetica-Bold" if raw_line and raw_line[0].isdigit() else "Helvetica", 10)
            pdf.drawString(54, cursor_y, line)
            cursor_y -= 14
        cursor_y -= 4
    pdf.save()
    return output.getvalue()


def generate_legal_document(
    document_type: str,
    output_format: str,
    fields: dict[str, Any],
) -> tuple[bytes, str, str]:
    normalized_type = document_type.upper()
    normalized_format = output_format.lower()
    if normalized_type not in SUPPORTED_TEMPLATES:
        raise ValueError("Unsupported legal document template")
    text = render_contract_text(normalized_type, fields)
    safe_name = normalized_type.lower()
    if normalized_format == "docx":
        return _docx_bytes(text), f"{safe_name}.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if normalized_format == "pdf":
        return _pdf_bytes(text), f"{safe_name}.pdf", "application/pdf"
    raise ValueError("output_format must be docx or pdf")
