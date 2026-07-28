"""User authentication — simple token-based auth."""

import hashlib
import hmac
import os
import secrets
import time

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.config import settings
from app.service import tracker

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)

USERS_FILE = os.path.join(settings.data_dir, "users.json")
TOKEN_VALIDITY = 86400 * 30  # 30 days


class LoginRequest(BaseModel):
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


def _load_users() -> dict:
    """Load users from JSON file. Returns {username: {hash, salt}}."""
    if os.path.isfile(USERS_FILE):
        try:
            import json
            with open(USERS_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_users(users: dict):
    import json
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """Hash a password with scrypt. Returns (hash_hex, salt_hex)."""
    if salt is None:
        salt = secrets.token_hex(16)
    key = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32
    )
    return key.hex(), salt


def _verify_password(password: str, stored_hash: str, salt: str) -> bool:
    """Verify a password against stored hash."""
    key = hashlib.scrypt(
        password.encode(), salt=salt.encode(), n=16384, r=8, p=1, dklen=32
    )
    return hmac.compare_digest(key.hex(), stored_hash)


def _generate_token() -> str:
    """Generate a random auth token."""
    return secrets.token_urlsafe(48)


def _init_admin():
    """Ensure admin user exists on startup."""
    users = _load_users()
    if "admin" not in users:
        pwh, salt = _hash_password("admin")
        users["admin"] = {
            "hash": pwh,
            "salt": salt,
            "tokens": {},
            "created_at": time.time(),
        }
        _save_users(users)


def _validate_token(token: str) -> bool:
    """Check if a token is valid and not expired."""
    users = _load_users()
    for uname, udata in users.items():
        if token in udata.get("tokens", {}):
            expires = udata["tokens"][token]
            if expires > time.time():
                return True
            # Remove expired token
            del udata["tokens"][token]
            _save_users(users)
    return False


@router.post("/login")
async def login(req: LoginRequest):
    users = _load_users()
    admin = users.get("admin")
    if not admin:
        raise HTTPException(401, "No user configured")

    if not _verify_password(req.password, admin["hash"], admin["salt"]):
        raise HTTPException(401, "密码错误")

    token = _generate_token()
    admin["tokens"][token] = time.time() + TOKEN_VALIDITY
    _save_users(users)
    return {"token": token, "expires": TOKEN_VALIDITY}


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        return {"status": "ok"}
    users = _load_users()
    for uname, udata in users.items():
        if credentials.credentials in udata.get("tokens", {}):
            del udata["tokens"][credentials.credentials]
            _save_users(users)
            break
    return {"status": "ok"}


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest,
                          credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or not _validate_token(credentials.credentials):
        raise HTTPException(401, "未登录")

    users = _load_users()
    admin = users.get("admin")
    if not admin:
        raise HTTPException(401, "No user")

    if not _verify_password(req.old_password, admin["hash"], admin["salt"]):
        raise HTTPException(400, "原密码错误")

    pwh, salt = _hash_password(req.new_password)
    admin["hash"] = pwh
    admin["salt"] = salt
    admin["tokens"] = {}  # Invalidate all existing tokens
    _save_users(users)
    return {"status": "ok", "message": "密码已修改，请重新登录"}


@router.get("/check")
async def check_auth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials or not _validate_token(credentials.credentials):
        raise HTTPException(401, "未登录")
    return {"status": "ok", "user": "admin"}


def require_auth(credentials: HTTPAuthorizationCredentials | None = Depends(security)):
    """Dependency for protecting routes."""
    if credentials is None or not _validate_token(credentials.credentials):
        raise HTTPException(status_code=401, detail="请先登录")
    return credentials.credentials


# Initialize admin on import
_init_admin()