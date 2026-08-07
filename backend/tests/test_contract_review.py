from app.services.contract_review import (
    detect_contract_type,
    review_contract,
    split_contract_clauses,
)


SOFTWARE_CONTRACT = """
HỢP ĐỒNG PHÁT TRIỂN PHẦN MỀM
Bên A: Công ty Khách hàng ABC
Bên B: Công ty Phần mềm XYZ
Ngày bắt đầu: 01/09/2026
Ngày kết thúc: 01/03/2027

Điều 1. Phạm vi công việc
Bên B phát triển một hệ thống.

Điều 2. Thanh toán
Bên A thanh toán 30% khi ký, 40% khi hoàn thành milestone và 30% sau nghiệm thu trong 15 ngày.

Điều 3. Quyền sở hữu trí tuệ
Bên A sở hữu toàn bộ mã nguồn ngay từ ngày bắt đầu dự án.

Điều 4. Chấm dứt
Bên A có quyền đơn phương chấm dứt bất kỳ lúc nào mà không cần bồi thường.

Điều 5. Thời hạn thanh toán khác
Hóa đơn được thanh toán trong 30 ngày.

Điều 6. Bảo mật
Các Bên bảo mật thông tin trong 3 năm.
"""


def test_detects_software_contract_and_splits_numbered_clauses():
    detection = detect_contract_type(SOFTWARE_CONTRACT)
    clauses = split_contract_clauses(SOFTWARE_CONTRACT)

    assert detection["contract_type"] == "SOFTWARE_DEVELOPMENT_CONTRACT"
    assert detection["confidence"] >= 0.55
    assert len(clauses) >= 6
    assert any(clause["number"] == "3" for clause in clauses)


def test_review_extracts_metadata_checklist_and_conflicts():
    result = review_contract(SOFTWARE_CONTRACT, "software.txt", "PARTY_B")

    assert result["review_version"] == "2.0"
    assert result["metadata"]["party_a"] == "Công ty Khách hàng ABC"
    assert result["metadata"]["party_b"] == "Công ty Phần mềm XYZ"
    assert result["metadata"]["start_date"] == "01/09/2026"
    assert result["internal_conflicts_count"] >= 1
    assert result["missing_clauses_count"] >= 1
    assert {item["status"] for item in result["checklist"]} == {"PRESENT", "MISSING"}


def test_unilateral_termination_is_perspective_aware():
    party_a = review_contract(SOFTWARE_CONTRACT, "software.txt", "PARTY_A")
    party_b = review_contract(SOFTWARE_CONTRACT, "software.txt", "PARTY_B")

    finding_a = next(
        item for item in party_a["findings"]
        if item["category"] == "TERMINATION" and item["finding_type"] == "COMMERCIAL_RISK"
    )
    finding_b = next(
        item for item in party_b["findings"]
        if item["category"] == "TERMINATION" and item["finding_type"] == "COMMERCIAL_RISK"
    )
    assert finding_a["severity"] == "LOW"
    assert finding_b["severity"] == "HIGH"


def test_high_finding_sets_high_floor_without_false_critical_label():
    result = review_contract(
        "HỢP ĐỒNG DỊCH VỤ\nĐiều 1. Trách nhiệm\nNhà cung cấp chịu unlimited liability.",
        "service.txt",
        "NEUTRAL",
    )

    assert result["risk_score"] >= 70
    assert result["risk_level"] == "HIGH"
    assert result["requires_legal_approval"] is True


def test_review_endpoint_requires_and_uses_represented_party(client, employee_token_headers):
    missing_party = client.post(
        "/api/v1/legal/review-document",
        files={"file": ("contract.txt", SOFTWARE_CONTRACT.encode(), "text/plain")},
        headers=employee_token_headers,
    )
    assert missing_party.status_code == 422

    response = client.post(
        "/api/v1/legal/review-document",
        files={"file": ("contract.txt", SOFTWARE_CONTRACT.encode(), "text/plain")},
        data={"represented_party": "PARTY_B"},
        headers=employee_token_headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["represented_party"] == "PARTY_B"
    assert payload["contract_type"] == "SOFTWARE_DEVELOPMENT_CONTRACT"
    assert payload["approval_created"] is True
    assert payload["findings"][0]["issue"]
    assert payload["findings"][0]["reason"]
    assert payload["findings"][0]["suggested_revision"]


def test_missing_party_names_use_company_customer_defaults():
    result = review_contract(
        "HỢP ĐỒNG DỊCH VỤ\nĐiều 1. Phạm vi\nCung cấp dịch vụ vận hành hệ thống.",
        "unnamed.txt",
        "PARTY_A",
    )
    metadata = result["metadata"]

    assert metadata["party_a"] == "Công ty"
    assert metadata["party_b"] == "Khách hàng"
    assert metadata["party_a_role"] == "COMPANY"
    assert metadata["party_b_role"] == "CUSTOMER"
    assert metadata["party_mapping_source"] == "SYSTEM_DEFAULT"
    assert metadata["party_a_source"] == "SYSTEM_DEFAULT"
    assert metadata["party_b_source"] == "SYSTEM_DEFAULT"


def test_document_party_role_conflict_is_reported():
    result = review_contract(SOFTWARE_CONTRACT, "software.txt", "PARTY_A")

    assert result["metadata"]["party_mapping_warnings"]
    assert any(
        item["category"] == "PARTY_ROLES" for item in result["findings"]
    )


def test_customer_ip_ownership_has_opposite_impact_for_company_and_customer():
    contract = """
HỢP ĐỒNG PHÁT TRIỂN PHẦN MỀM
Bên A: NovaSoft
Bên B: Khách hàng ABC
Điều 1. Sở hữu trí tuệ
Bên B sở hữu toàn bộ mã nguồn ngay từ ngày bắt đầu dự án.
"""
    company = review_contract(contract, "ip.txt", "PARTY_A")
    customer = review_contract(contract, "ip.txt", "PARTY_B")
    company_finding = next(
        item for item in company["findings"]
        if item["category"] == "INTELLECTUAL_PROPERTY"
        and item["finding_type"] == "COMMERCIAL_RISK"
    )
    customer_finding = next(
        item for item in customer["findings"]
        if item["category"] == "INTELLECTUAL_PROPERTY"
        and item["finding_type"] == "COMMERCIAL_RISK"
    )

    assert (company_finding["severity"], company_finding["impact"]) == (
        "HIGH",
        "ADVERSE",
    )
    assert (customer_finding["severity"], customer_finding["impact"]) == (
        "LOW",
        "BENEFICIAL",
    )
