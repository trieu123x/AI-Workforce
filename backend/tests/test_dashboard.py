"""
Unit tests for Dashboard & Analytics API endpoints (/api/v1/dashboard).
"""

import pytest


def test_get_dashboard_stats(client, ceo_token_headers):
    """Test fetching real dashboard stats with authentic DB counts."""
    res = client.get("/api/v1/dashboard/stats?period=week", headers=ceo_token_headers)
    assert res.status_code == 200, f"Dashboard stats failed: {res.text}"
    data = res.json()
    
    assert "kpi" in data
    assert "monthly_summary" in data
    assert "chatbots" in data
    assert "top_employees" in data
    assert "usage_trend" in data
    assert "monthly_data" in data

    assert data["kpi"]["total_agents"] >= 1
    assert data["kpi"]["total_employees"] >= 1
    assert isinstance(data["chatbots"], list)
    assert len(data["usage_trend"]) == 7
    assert len(data["monthly_data"]) == 12


def test_export_report_excel(client, ceo_token_headers):
    """Test Excel (.xlsx) report generation endpoint."""
    res = client.get("/api/v1/dashboard/reports/export/excel?period=week", headers=ceo_token_headers)
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers["content-type"] or "csv" in res.headers["content-type"]
    assert len(res.content) > 0


def test_export_report_pdf(client, ceo_token_headers):
    """Test PDF report export endpoint."""
    res = client.get("/api/v1/dashboard/reports/export/pdf?period=week", headers=ceo_token_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF") or len(res.content) > 0

