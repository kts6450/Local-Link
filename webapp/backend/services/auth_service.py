"""회원가입·로그인·마스터 계정."""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime

from sqlalchemy import select

from db.database import SessionLocal
from db.models import UserRow
from services.auth_password import hash_password, verify_password
from services.auth_tokens import create_access_token

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VALID_SECTORS = frozenset(
    {"experience", "rural", "fishing", "craft", "leisure", "lodging"}
)


class AuthError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _master_credentials() -> tuple[str, str] | None:
    email = os.environ.get("LOCAL_LINK_MASTER_EMAIL", "").strip().lower()
    password = os.environ.get("LOCAL_LINK_MASTER_PASSWORD", "")
    if not email or not password:
        return None
    return email, password


def _user_to_token_payload(row: UserRow) -> dict:
    return {
        "sub": row.id,
        "email": row.email,
        "role": row.role,
        "display_name": row.display_name,
        "seller_sector": row.seller_sector,
        "seller_id": row.seller_id,
    }


def user_public(row: UserRow) -> dict:
    return {
        "id": row.id,
        "email": row.email,
        "role": row.role,
        "display_name": row.display_name,
        "seller_sector": row.seller_sector,
        "seller_id": row.seller_id,
    }


def register_user(
    *,
    email: str,
    password: str,
    role: str,
    display_name: str,
    seller_sector: str | None = None,
) -> dict:
    email = email.strip().lower()
    display_name = (display_name or "").strip()
    if not _EMAIL_RE.match(email):
        raise AuthError("올바른 이메일 주소를 입력해 주세요.")
    if len(password) < 8:
        raise AuthError("비밀번호는 8자 이상이어야 합니다.")
    if role not in ("consumer", "seller"):
        raise AuthError("역할은 구매자 또는 공급자만 선택할 수 있습니다.")
    if not display_name:
        raise AuthError("이름을 입력해 주세요.")

    sector: str | None = None
    seller_id: str | None = None
    uid = f"user-{uuid.uuid4().hex[:12]}"
    if role == "seller":
        sector = (seller_sector or "rural").strip()
        if sector not in _VALID_SECTORS:
            raise AuthError("공급자 업종을 선택해 주세요.")
        seller_id = uid

    with SessionLocal() as session:
        exists = session.scalar(select(UserRow.id).where(UserRow.email == email))
        if exists:
            raise AuthError("이미 가입된 이메일입니다.", status=409)

        row = UserRow(
            id=uid,
            email=email,
            password_hash=hash_password(password),
            role=role,
            display_name=display_name,
            seller_sector=sector,
            seller_id=seller_id,
            created_at=datetime.utcnow().isoformat(),
        )
        session.add(row)
        session.commit()
        session.refresh(row)

    token = create_access_token(_user_to_token_payload(row))
    return {"token": token, "user": user_public(row)}


def login_user(*, email: str, password: str) -> dict:
    email = email.strip().lower()
    if not email or not password:
        raise AuthError("이메일과 비밀번호를 입력해 주세요.")

    master = _master_credentials()
    if master and email == master[0] and password == master[1]:
        token = create_access_token(
            {
                "sub": "master",
                "email": email,
                "role": "master",
                "display_name": "운영자",
                "seller_sector": None,
                "seller_id": None,
            }
        )
        return {
            "token": token,
            "user": {
                "id": "master",
                "email": email,
                "role": "master",
                "display_name": "운영자",
                "seller_sector": None,
                "seller_id": None,
            },
        }

    with SessionLocal() as session:
        row = session.scalar(select(UserRow).where(UserRow.email == email))
        if not row or not verify_password(password, row.password_hash):
            raise AuthError("이메일 또는 비밀번호가 맞지 않습니다.", status=401)

    token = create_access_token(_user_to_token_payload(row))
    return {"token": token, "user": user_public(row)}


def update_user_profile(
    *,
    user_id: str,
    display_name: str | None = None,
    current_password: str | None = None,
    new_password: str | None = None,
) -> dict:
    """닉네임 변경 및/또는 비밀번호 변경. 변경 후 새 토큰과 유저 정보를 반환."""
    if not display_name and not new_password:
        raise AuthError("변경할 내용이 없습니다.")

    with SessionLocal() as session:
        row = session.scalar(select(UserRow).where(UserRow.id == user_id))
        if not row:
            raise AuthError("사용자를 찾을 수 없습니다.", status=404)

        # 비밀번호 변경
        if new_password:
            if not current_password or not verify_password(current_password, row.password_hash):
                raise AuthError("현재 비밀번호가 올바르지 않습니다.", status=401)
            row.password_hash = hash_password(new_password)

        # 닉네임 변경
        if display_name:
            row.display_name = display_name.strip()

        session.commit()
        session.refresh(row)

    token = create_access_token(_user_to_token_payload(row))
    return {"token": token, "user": user_public(row)}


def user_from_token_payload(payload: dict) -> dict:
    return {
        "id": payload.get("sub"),
        "email": payload.get("email"),
        "role": payload.get("role"),
        "display_name": payload.get("display_name"),
        "seller_sector": payload.get("seller_sector"),
        "seller_id": payload.get("seller_id"),
    }
