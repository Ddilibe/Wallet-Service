#!/usr/bin/env python3
from functools import lru_cache
from pydantic import BaseModel


class Settings(BaseModel):
    # DATABASE_URL: str = "postgresql://user:password@host:port/database"
    DATABASE_URL: str = "sqlite+aiosqlite:///walletservice.db"
    JWT_SECRET: str = "secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION: int = 3600
    PAYSTACK_SECRET_KEY: str = "sk_test_secret_key"
    PAYSTACK_PUBLIC_KEY: str = "pk_test_public_key"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
