from datetime import date

from app.services.agents.agent_executor import (
    _extract_leave_slots,
    _parse_leave_date,
)


def test_parse_leave_date_defaults_missing_year_to_current_year():
    current_year = date.today().year

    assert _parse_leave_date("7/8") == date(current_year, 8, 7)
    assert _parse_leave_date("07-08") == date(current_year, 8, 7)


def test_extract_leave_slots_accepts_date_range_without_year():
    current_year = date.today().year

    slots = _extract_leave_slots(
        "ngày bắt đầu 7/8 kết thúc 9/8 lý do là về quê"
    )

    assert slots == {
        "start_date": date(current_year, 8, 7).isoformat(),
        "end_date": date(current_year, 8, 9).isoformat(),
        "reason": "về quê",
    }


def test_parse_leave_date_keeps_explicit_year_and_rejects_invalid_dates():
    assert _parse_leave_date("7/8/2030") == date(2030, 8, 7)
    assert _parse_leave_date("2030-08-07") == date(2030, 8, 7)
    assert _parse_leave_date("31/2") is None
