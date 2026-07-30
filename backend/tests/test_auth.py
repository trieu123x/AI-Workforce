"""
Tests for Authentication & User endpoints (JWT login, current user profile).
"""

def test_login_success(client):
    """Test login with valid user credentials."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@company.com", "password": "Password123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@company.com"
    assert data["user"]["role"] == "CEO"


def test_login_invalid_password(client):
    """Test login with incorrect password."""
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@company.com", "password": "WrongPassword!"},
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_get_current_user_profile(client, ceo_token_headers):
    """Test fetching current authenticated user profile."""
    response = client.get("/api/v1/users/me", headers=ceo_token_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@company.com"
    assert data["role"] == "CEO"
    assert data["department"] == "BOARD"


def test_refresh_token_via_cookie(client):
    """Test refreshing access token using HttpOnly refresh_token cookie."""
    # 1. Login to set refresh_token cookie
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@company.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    assert "refresh_token" in login_resp.cookies

    # 2. Call /auth/refresh with the cookie
    refresh_resp = client.post("/api/v1/auth/refresh", cookies=login_resp.cookies)
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    assert "access_token" in refresh_data
    assert refresh_data["user"]["email"] == "admin@company.com"


def test_refresh_token_via_json_payload(client):
    """Test refreshing access token using JSON payload fallback."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@company.com", "password": "Password123!"},
    )
    assert login_resp.status_code == 200
    refresh_token = login_resp.json()["refresh_token"]

    # Call /auth/refresh with JSON payload
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_resp.status_code == 200
    refresh_data = refresh_resp.json()
    assert "access_token" in refresh_data


def test_refresh_token_invalid(client):
    """Test refreshing access token with an invalid refresh token."""
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        cookies={"refresh_token": "invalid_fake_token_string"},
    )
    assert refresh_resp.status_code == 401

