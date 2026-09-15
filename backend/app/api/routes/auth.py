from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.db.session import get_db

router = APIRouter(tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    display_name: str


@router.post("/auth/login", response_model=LoginResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    row = db.execute(
        text("SELECT email, password_hash, role, display_name, is_active FROM users WHERE email = :email"),
        {"email": payload.email},
    ).mappings().first()

    if row is None or not row["is_active"] or not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail={
            "error": {"code": "INVALID_CREDENTIALS", "message": "Incorrect email or password"}
        })

    token = create_access_token(subject=row["email"], role=row["role"])
    return LoginResponse(access_token=token, role=row["role"], display_name=row["display_name"])


@router.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
