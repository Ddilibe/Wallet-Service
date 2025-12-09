#!/usr/bin/env python3
from typing import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import create_db_and_tables
from app.routers import auth, keys, wallet


app = FastAPI(title="Wallet Service")


app.include_router(auth.auth)
app.include_router(keys.keys)
app.include_router(wallet.wallet)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    create_db_and_tables()
    yield
