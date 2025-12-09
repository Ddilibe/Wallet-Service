#!/usr/bin/env python3
import os
import hashlib
from typing import Optional
from datetime import datetime, timezone, timedelta

import jwt
from sqlmodel import select
from fastapi import Header, HTTPException, Depends

from app.core import get_settings
from app.models import APIKey, User
from app.database import get_session

settings = get_settings()


def hash_api_key(key: str) -> str:
    return hashlib.sha256((key + settings.JWT_SECRET).encode()).hexdigest()


async def get_principal(
    authorization: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    session=Depends(get_session),
):
    if authorization:
        parts = authorization.split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid authorization header")

        token = parts[1]

        try:

            payload = jwt.decode(
                token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
            )
            user_id = payload.get("user_id")

            if not user_id:
                raise HTTPException(status_code=401, detail="Invalid token")

            user = session.exec(select(User).where(User.id == user_id)).first()

            if not user:
                raise HTTPException(status_code=401, detail="User not found")

            return user
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")

    if x_api_key:
        try:
            key = session.exec(
                select(APIKey).where(APIKey.key_hash == hash_api_key(x_api_key))
            ).first()

            if not key or key.revoked or key.expires_at > datetime.now(timezone.utc):
                raise HTTPException(status_code=401, detail="Invalid API key")

            user = session.exec(select(User).where(User.id == key.user_id)).first()

            return user

        except Exception:
            raise Exception("Invalid API key")

    raise HTTPException(
        status_code=401, detail="Missing authorization header or API key"
    )


def require_permission(principal, permission):
    from .models import Permission as perm

    if principal["type"] == "user":
        return
    ak = principal["api_key"]
    if permission not in ak.permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return ak


def parse_expiry(exp: str) -> datetime:
    now = datetime.now(timezone.utc)
    units = dict(
        H1=timedelta(hours=1),
        D1=timedelta(days=1),
        M1=timedelta(days=30),
        Y1=timedelta(days=365),
    )
    val = sorted(exp.upper(), reverse=True)
    if val not in units:
        raise ValueError("Invalid expiry format")
    return now + units[val]
