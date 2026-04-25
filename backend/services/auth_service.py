"""JWT auth + bcrypt password hashing + role-based access control."""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

import bcrypt
import jwt
from fastapi import HTTPException, Request, status
from fastapi import Depends

JWT_ALG = "HS256"
ACCESS_TTL_MIN = 60 * 8  # 8h
REFRESH_TTL_DAYS = 7

ROLES = ["admin", "manager", "user", "viewer"]
ROLE_RANK = {"viewer": 0, "user": 1, "manager": 2, "admin": 3}


def _secret() -> str:
    return os.environ["JWT_SECRET"]


def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8"), hashed.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TTL_MIN),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALG)


def create_refresh_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TTL_DAYS),
    }
    return jwt.encode(payload, _secret(), algorithm=JWT_ALG)


def decode(token: str) -> dict:
    return jwt.decode(token, _secret(), algorithms=[JWT_ALG])


# ---------------------------------------------------------------------------
# FastAPI dependencies (attached in server.py via closures that pass `db`)
# ---------------------------------------------------------------------------

def make_auth_deps(db):
    async def get_current_user(request: Request) -> dict:
        token = request.cookies.get("access_token")
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        if not token:
            raise HTTPException(status_code=401, detail="Not authenticated")

        try:
            payload = decode(token)
            if payload.get("type") != "access":
                raise HTTPException(status_code=401, detail="Invalid token type")
            user = await db.users.find_one({"id": payload["sub"]}, {"_id": 0, "password_hash": 0})
            if not user:
                raise HTTPException(status_code=401, detail="User not found")
            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")

    def require_roles(*roles: str):
        allowed = set(roles)

        async def _inner(user: dict = Depends(get_current_user)) -> dict:
            if user.get("role") not in allowed:
                raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
            return user

        return _inner

    def require_min_role(min_role: str):
        threshold = ROLE_RANK[min_role]

        async def _inner(user: dict = Depends(get_current_user)) -> dict:
            if ROLE_RANK.get(user.get("role", "viewer"), -1) < threshold:
                raise HTTPException(status_code=403, detail="Forbidden: insufficient role")
            return user

        return _inner

    return {
        "get_current_user": get_current_user,
        "require_roles": require_roles,
        "require_min_role": require_min_role,
    }


def set_auth_cookies(response, access: str, refresh: str) -> None:
    response.set_cookie(
        "access_token", access, httponly=True, secure=True, samesite="none",
        max_age=ACCESS_TTL_MIN * 60, path="/",
    )
    response.set_cookie(
        "refresh_token", refresh, httponly=True, secure=True, samesite="none",
        max_age=REFRESH_TTL_DAYS * 86400, path="/",
    )


def clear_auth_cookies(response) -> None:
    response.delete_cookie("access_token", path="/", httponly=True, secure=True, samesite="none")
    response.delete_cookie("refresh_token", path="/", httponly=True, secure=True, samesite="none")


def new_user_doc(email: str, password: str, name: str, role: str) -> dict:
    assert role in ROLES
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": str(uuid.uuid4()),
        "email": email.lower().strip(),
        "password_hash": hash_password(password),
        "name": name,
        "role": role,
        "created_at": now,
        "updated_at": now,
    }


def public_user(u: dict) -> dict:
    return {k: v for k, v in u.items() if k not in ("password_hash", "_id")}
