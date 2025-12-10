#!/usr/bin/env python3
from functools import lru_cache

from decouple import config
from pydantic import BaseModel


class Settings(BaseModel):
    # DATABASE_URL: str = "postgresql://user:password@host:port/database"
    DATABASE_URL: str = str(config("DATABASE_URL"))
    JWT_SECRET: str = str(config("JWT_SECRET"))
    JWT_ALGORITHM: str = str(config("JWT_ALGORITHM"))
    JWT_EXPIRATION: int = int(config("JWT_EXPIRATION"))
    PAYSTACK_SECRET_KEY: str = str(config("PAYSTACK_SECRET_KEY"))
    PAYSTACK_PUBLIC_KEY: str = str(config("PAYSTACK_PUBLIC_KEY"))
    MIDDLEWARE_SECRET_KEY: str = str(config("MIDDLEWARE_SECRET_KEY"))
    GOOGLE_CLIENT_ID: str = str(config("GOOGLE_CLIENT_ID"))
    GOOGLE_CLIENT_SECRET: str = str(config("GOOGLE_CLIENT_SECRET"))
    GOOGLE_REDIRECT_URI: str = str(config("GOOGLE_REDIRECT_URI"))

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()
