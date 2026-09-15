"""
Auth dependencies. get_current_user extracts and validates the bearer JWT
and loads the corresponding active user; require_role builds a dependency
that additionally checks the user's role against an allow-list.

Role permission matrix (see docs/decisions.md D24):
    admin    - all actions
    pm       - create/update incidents & interventions, create experiments
    ops      - create/update incidents & interventions
    engineer - update incidents (diagnosis notes); read everything
    support  - read-only
    viewer   - read-only
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db

bearer_scheme = HTTPBearer(auto_error=False)


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"error": {"code": "UNAUTHORIZED", "message": message}},
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    if credentials is None:
        raise _unauthorized("Missing bearer token")

    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise _unauthorized("Invalid or expired token")

    row = db.execute(
        text("SELECT user_id, email, display_name, role, is_active FROM users WHERE email = :email"),
        {"email": payload["sub"]},
    ).mappings().first()

    if row is None or not row["is_active"]:
        raise _unauthorized("User not found or inactive")

    return {
        "user_id": str(row["user_id"]),
        "email": row["email"],
        "display_name": row["display_name"],
        "role": row["role"],
    }


def require_role(*allowed_roles: str):
    def _dependency(current_user: dict = Depends(get_current_user)) -> dict:
        if current_user["role"] not in allowed_roles and current_user["role"] != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error": {"code": "FORBIDDEN",
                                  "message": f"Role '{current_user['role']}' cannot perform this action"}},
            )
        return current_user
    return _dependency
