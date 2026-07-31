"""Personal profile, protected employment data and avatar regression tests."""

from app.api.v1 import users as users_api
from app.models.models import User


def test_self_profile_and_protected_employment_fields(
    client,
    employee_token_headers,
    ceo_token_headers,
    transactional_db_session,
):
    employee = transactional_db_session.query(User).filter(
        User.email == "employee@company.com"
    ).one()

    initial = client.get("/api/v1/users/me/profile", headers=employee_token_headers)
    assert initial.status_code == 200
    assert "employment" in initial.json()
    assert "leave" in initial.json()["employment"]

    updated = client.patch(
        "/api/v1/users/me/profile",
        headers=employee_token_headers,
        json={
            "full_name": "Employee Profile Test",
            "phone": "0901234567",
            "address": "123 Nguyen Hue",
            "city": "Ho Chi Minh City",
            "country": "Vietnam",
            "gender": "prefer_not_to_say",
            "bio": "Knowledge worker",
            "preferences": {
                "hobbies": ["reading", "running"],
                "preferred_language": "vi",
                "timezone": "Asia/Ho_Chi_Minh",
                "work_style": "deep_focus",
                "theme": "system",
                "communication_channels": ["IN_APP", "EMAIL"],
            },
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["full_name"] == "Employee Profile Test"
    assert updated.json()["preferences"]["hobbies"] == ["reading", "running"]

    forbidden = client.patch(
        f"/api/v1/users/{employee.id}/employment",
        headers=employee_token_headers,
        json={"monthly_salary": 75000000, "leave_total_days": 20},
    )
    assert forbidden.status_code == 403

    employment = client.patch(
        f"/api/v1/users/{employee.id}/employment",
        headers=ceo_token_headers,
        json={
            "job_title": "Senior Engineer",
            "employee_code": "EMP-001",
            "monthly_salary": 75000000,
            "salary_currency": "VND",
            "leave_total_days": 20,
            "leave_used_days": 3,
        },
    )
    assert employment.status_code == 200, employment.text
    assert employment.json()["employment"]["monthly_salary"] == 75000000.0
    assert employment.json()["employment"]["leave"] == {
        "total_days": 20.0,
        "used_days": 3.0,
        "remaining_days": 17.0,
    }


def test_avatar_upload_updates_current_user(
    client, employee_token_headers, monkeypatch
):
    expected_url = "https://res.cloudinary.com/demo/image/upload/avatar.webp"
    monkeypatch.setattr(
        users_api,
        "upload_avatar",
        lambda content, **kwargs: expected_url,
    )
    response = client.post(
        "/api/v1/users/me/avatar",
        headers=employee_token_headers,
        files={"file": ("avatar.webp", b"fake-webp-image", "image/webp")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["avatar_url"] == expected_url
    me = client.get("/api/v1/users/me", headers=employee_token_headers)
    assert me.json()["avatar_url"] == expected_url
