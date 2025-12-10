#!/usr/bin/env python3
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


@keys.post("/create")
async def create_key(
    req: CreateKeyReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    print(principal["user"])
    if principal["type"] != "user":
        raise HTTPException(
            status_code=401, detail="Unauthorized\nOnly users may create API keys"
        )
    user = principal["user"][0]

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


@keys.post("/rollover")
async def rollover(
    req: RolloverReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    if principal["type"] != "user":
        raise HTTPException(
            status_code=401, detail="Unauthorized\nOnly users may rollover API keys"
        )

    ak = await session.get(APIKey, req.expired_key_id)
    now_utc = datetime.now(timezone.utc)
    print(ak)

    if not ak or ak.user_id != principal["user"][0].id or ak.revoked:
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
