#!/usr/bin/env python3
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core import settings
from app.routers import auth, keys, wallet
from app.database import create_db_and_tables


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await create_db_and_tables()
    yield


app = FastAPI(title="Wallet Service", lifespan=lifespan)

app.include_router(auth.auth)
app.include_router(keys.keys)
app.include_router(wallet.wallet)

app.add_middleware(
    SessionMiddleware, secret_key=settings.MIDDLEWARE_SECRET_KEY, https_only=False
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
