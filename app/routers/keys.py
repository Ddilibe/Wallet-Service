#!/usr/bin/env python3
"""API key management routes.

Endpoints to create and rollover API keys. These endpoints require an
authenticated principal and enforce per-user limits and permissions.
"""
import json
import secrets
from datetime import datetime, timezone

from sqlmodel import select
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException

from app.models import User, APIKey
from app.database import get_session
from app.schemas import CreateKeyReq, RolloverReq
from app.deps import get_principal, hash_api_key, parse_expiry

keys = APIRouter(prefix="/keys", tags=["keys"])


@keys.post(
    "/create",
    summary="Create API key",
    description=(
        "Create a new API key for the authenticated user. A user may have up "
        "to 5 active API keys. Returns a plaintext API key (fingerprint + "
        "secret) and expiration information."
    ),
)
async def create_key(
    req: CreateKeyReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Create a new API key for the requesting user.

    Args:
        req: payload containing key name, permissions, and expiry.
        principal: resolved principal from API key or user auth.
        session: database session.

    Returns:
        JSON object with `api_key` (fingerprint.secret) and `expires_at`.

    Raises:
        HTTPException(401) if principal is not a user.
        HTTPException(400) if the user already has 5 active keys.
    """
    print(principal["user"])
    if principal["type"] != "user":
        raise HTTPException(
            status_code=401, detail="Unauthorized\nOnly users may create API keys"
        )
    user = principal["user"]

    now_utc = datetime.now(timezone.utc)
    user_id = user.id

    active_keys_statement = select(APIKey).where(
        APIKey.user_id == user_id,
        APIKey.revoked == False,
        APIKey.expires_at > now_utc,
    )

    active = await session.execute(active_keys_statement)
    active = active.scalars().all()

    if len(active) >= 5:
        raise HTTPException(status_code=400, detail="Max 5 active API keys allowed")

    raw = "sk_" + secrets.token_urlsafe(32)
    fingerprint = secrets.token_hex(8)

    ak = APIKey(
        user_id=user.id,
        fingerprint=fingerprint,
        name=req.name,
        permissions=json.dumps(req.permissions),
        key_hash=hash_api_key(raw),
        expires_at=parse_expiry(req.expiry),
    )

    session.add(ak)
    await session.commit()
    await session.refresh(ak)

    return {"api_key": f"{fingerprint}.{raw}", "expires_at": ak.expires_at.isoformat()}


@keys.post(
    "/rollover",
    summary="Rollover an API key",
    description=(
        "Replace an existing API key's secret with a new one (rotate the "
        "key). Requires the caller to own the key. Returns the new key "
        "plaintext secret."
    ),
)
async def rollover(
    req: RolloverReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Rotate an existing API key's secret.

    Args:
        req: contains the id of the API key to rollover and desired expiry.
        principal: caller principal (must be the owning user).
        session: database session.

    Returns:
        JSON object with new `api_key` and `expires_at`.

    Raises:
        HTTPException(401) if caller is not a user.
        HTTPException(404) if key not found or not owned by caller.
    """
    if principal["type"] != "user":
        raise HTTPException(
            status_code=401, detail="Unauthorized\nOnly users may rollover API keys"
        )

    ak = await session.get(APIKey, req.expired_key_id)
    now_utc = datetime.now(timezone.utc)
    print(ak)

    if not ak or ak.user_id != principal["user"].id or ak.revoked:
        raise HTTPException(status_code=404, detail="API key not found")

    aware_expires_at = ak.expires_at.replace(tzinfo=timezone.utc)
    if aware_expires_at < now_utc:
        raise HTTPException(status_code=400, detail="API key has expired")

    raw = "sk_" + secrets.token_urlsafe(32)
    fingerprint = secrets.token_hex(8)

    ak.key_hash = hash_api_key(raw)
    ak.fingerprint = fingerprint

    session.add(ak)
    await session.commit()
    await session.refresh(ak)

    return {"api_key": f"{fingerprint}.{raw}", "expires_at": parse_expiry(req.expiry)}
