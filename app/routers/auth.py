#!/usr/bin/env python3
"""Authentication routes.

Endpoints to start and complete Google OAuth sign-in. These handlers use
Authlib and rely on session middleware to persist OAuth `state` between the
authorize request and the callback.
"""
import uuid

import jwt
from faker import Faker
from sqlmodel import select
from starlette.requests import Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException
from authlib.integrations.starlette_client import OAuth

from app.models import User, Wallet
from app.database import get_session
from app.core import get_settings

auth = APIRouter(prefix="/auth", tags=["auth"])
fake = Faker()
settings = get_settings()

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={
        "scope": "openid email profile",
        # "redirect_uri": settings.GOOGLE_REDIRECT_URI,
    },
)


@auth.get(
    "/google",
    summary="Start Google sign-in",
    description=(
        "Begin the OAuth2 flow by redirecting the user to Google's consent "
        "page. The OAuth state is saved in the session so the callback can "
        "validate it."
    ),
)
async def google(request: Request):
    """
    Build redirect URI dynamically from the incoming request so the state cookie is set for the same host/port that initiated the flow.
    This prevents CSRF mismatching_state when the configured static redirect URI doesn't match the actual request host/port.
    """
    redirect_uri = request.url_for("google_callback")

    redirect_uri = str(redirect_uri)

    return await oauth.google.authorize_redirect(  # type: ignore
        request, redirect_uri=redirect_uri
    )


@auth.get(
    "/google/callback",
    summary="Google OAuth2 callback",
    description=(
        "Callback endpoint for Google's OAuth2 flow. Validates the state, "
        "exchanges the authorization code for tokens, and returns an "
        "application JWT. Requires SessionMiddleware to be configured."
    ),
)
async def google_callback(
    request: Request, session: AsyncSession = Depends(get_session)
):
    try:
        token = await oauth.google.authorize_access_token(request)  # type:ignore

    except Exception as e:
        raise HTTPException(status_code=400, detail="Google OAuth failed")

    user_info = token.get("userinfo")
    if not user_info:
        raise HTTPException(status_code=400, detail="Failed to retrieve user info")

    email = user_info["email"]
    name = user_info.get("name", "Unknown")

    query = await session.execute(select(User).where(User.email == email))
    existing_user = query.scalars().first()

    if existing_user:
        user = existing_user
    else:
        user = User(email=email, name=name)
        session.add(user)
        await session.commit()
        await session.refresh(user)

        wallet = Wallet(user_id=user.id, balance=0, wallet_number=str(uuid.uuid4())[:6])  # type: ignore
        session.add(wallet)
        await session.commit()
        await session.refresh(wallet)

    token = jwt.encode(
        payload=user.model_dump(),
        key=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )

    return JSONResponse({"access_token": token, "token_type": "bearer"})
