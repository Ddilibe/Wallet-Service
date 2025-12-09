#!/usr/bin/env python3
from typing import List, Optional
from datetime import datetime, timezone

from pydantic import BaseModel

from app.models import Permission

class CreateKeyReq(BaseModel):
    name: str
    permissions: List[Permission]
    expiry: str

class RolloverReq(BaseModel):
    expired_key_id: int
    expiry: str

class DepositReq(BaseModel):
    amount: int

class TransferReq(BaseModel):
    amount: int
    wallet_number: str

class APIKeyOut(BaseModel):
    name: str
    permissions: List[Permission]
    expires_at: datetime
    revoked: bool
    created_at: datetime
    key: Optional[str] = None