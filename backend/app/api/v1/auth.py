"""
Auth API routes: Access Token in RAM/LocalStorage + Refresh Token in HttpOnly Cookie.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Response, Request, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    LoginResponse,
    TokenRefreshRequest,
)
from app.services.auth_service import login_user, refresh_tokens, register_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


from app.core.config import settings


def set_refresh_cookie(response: Response, refresh_token_str: str):
    """Store Refresh Token strictly in an HttpOnly cookie to prevent XSS theft."""
    max_age_seconds = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    response.set_cookie(
        key="refresh_token",
        value=refresh_token_str,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS production
        path="/",
        max_age=max_age_seconds,
    )


@router.post("/register", response_model=LoginResponse, status_code=201, summary="Register new user")
def register(
    data: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    res = register_user(db, data)
    set_refresh_cookie(response, res.refresh_token)
    return res


@router.post("/login", response_model=LoginResponse, summary="Login and receive JWT tokens")
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> LoginResponse:
    res = login_user(db, data)
    set_refresh_cookie(response, res.refresh_token)
    return res


@router.post("/refresh", response_model=LoginResponse, summary="Refresh JWT access token using HttpOnly Cookie")
def refresh(
    request: Request,
    response: Response,
    data: Optional[TokenRefreshRequest] = None,
    db: Session = Depends(get_db),
) -> LoginResponse:
    # 1. Extract refresh_token from HttpOnly cookie first
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token and data:
        refresh_token = data.refresh_token

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from cookie or request",
        )

    res = refresh_tokens(db, refresh_token)
    set_refresh_cookie(response, res.refresh_token)
    return res


@router.post("/logout", summary="Logout user and clear HttpOnly refresh cookie")
def logout(response: Response) -> dict:
    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully"}
