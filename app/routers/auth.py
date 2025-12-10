#!/usr/bin/env python3
import jwt
from faker import Faker
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi.responses import JSONResponse
from fastapi import APIRouter, Depends, HTTPException

from app.models import User
from app.core import get_settings
from app.database import get_session

auth = APIRouter(prefix="/auth", tags=["auth"])
fake = Faker()
settings = get_settings()


@auth.get("/google")
async def google():
    return JSONResponse({})


@auth.get("/google/callback")
async def google_callback(session: AsyncSession = Depends(get_session)):
    new_user = User(email=fake.email(), name=fake.name())
    session.add(new_user)
    await session.commit()

    query = await session.execute(select(User).where(User.id == new_user.id))

    payload = query.first()
    if not payload:
        raise HTTPException(
            status_code=404, detail="Invalid call on google callback function"
        )
    token = jwt.encode(
        payload=new_user.model_dump(),
        key=settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )
    return JSONResponse({"access_token": str(token), "token_type": "bearer"})
