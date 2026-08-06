import io

from app.services.legal_document_generator import generate_legal_document
from app.services.legal_service import (
    audit_contract_text,
    check_software_licenses,
    compare_contract_texts,
    detect_sensitive_data,
)


def test_contract_audit_scores_material_and_missing_clauses():
    result = audit_contract_text(
        "Customer owns all intellectual property. Supplier accepts unlimited liability. "
        "Payment is due within 90 days after invoice.",
        "msa.txt",
    )
    assert result["risk_level"] == "HIGH"
    assert result["risk_score"] >= 70
    assert {item["category"] for item in result["risks"]} >= {
        "INTELLECTUAL_PROPERTY",
        "LIABILITY",
        "TERMINATION",
    }
    assert all(item["evidence"] for item in result["risks"])


def test_privacy_checker_does_not_return_detected_values():
    source = "email,phone,cccd\ncustomer@example.com,0901234567,012345678901"
    result = detect_sensitive_data(source, ["email", "phone", "cccd"])
    assert result["requires_legal_approval"] is True
    assert {item["type"] for item in result["findings"]} >= {"EMAIL", "PHONE", "CCCD"}
    assert "customer@example.com" not in str(result)


def test_contract_comparison_reports_modified_terms():
    result = compare_contract_texts(
        "Clause 5 - Payment: 30 days\nClause 6 - Notice: 30 days",
        "Clause 5 - Payment: 90 days\nClause 6 - Notice: 30 days",
    )
    assert result["total_changes"] == 1
    assert result["changes"][0]["type"] == "MODIFIED"


def test_license_checker_flags_agpl_dependency():
    result = check_software_licenses(
        "requirements.txt", "fastapi==0.111\nultralytics==8.3"
    )
    assert result["risk_level"] == "HIGH"
    assert result["commercial_use_requires_review"] is True


def test_document_generator_outputs_valid_docx_archive():
    content, filename, media_type = generate_legal_document(
        "INTERNSHIP_CONTRACT",
        "docx",
        {"company": "NovaSoft", "person": "Student A", "allowance": "5,000,000 VND"},
    )
    assert filename.endswith(".docx")
    assert "officedocument" in media_type
    assert io.BytesIO(content).read(2) == b"PK"
