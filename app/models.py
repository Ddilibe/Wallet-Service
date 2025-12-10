#!/usr/bin/env python3
import enum
from typing import Optional, List
from datetime import datetime, timezone

from pydantic import field_serializer
from sqlmodel import SQLModel, JSON, Field, Relationship


class Permission(str, enum.Enum):
    deposit = "deposit"
    transfer = "transfer"
    read = "read"


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, nullable=False)
    name: Optional[str]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    wallet: Optional["Wallet"] = Relationship(
        back_populates="user", sa_relationship_kwargs={"uselist": False}
    )
    # permissions: List[Permission] = Field

    @field_serializer("created_at")
    def serialize_created_At(self, dt: datetime) -> str:
        """Converts the datetime object to a specific ISO-8601 string format."""
        return dt.isoformat(timespec="seconds") + "Z"

    @field_serializer("wallet", check_fields=False)
    def serialize_wallet(self, wallet: "Wallet") -> dict[str, str]:
        return wallet.model_dump()


class Wallet(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)
    balance: float = Field(default=0.0)
    wallet_number: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user: Optional[User] = Relationship(back_populates="wallet")


class TransactionType(str, enum.Enum):
    deposit = "deposit"
    transfer = "transfer"
    withdrawal = "withdrawal"


class TransactionStatus(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class Transaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    tx_type: TransactionType
    amount: float
    status: TransactionStatus = Field(default=TransactionStatus.pending)
    reference: Optional[str] = Field(index=True, unique=True)
    meta: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=dict(onupdate=lambda: datetime.now(timezone.utc)),
    )


class APIKey(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    key_hash: str = Field(index=True, unique=True)
    name: str
    permissions: str = Field(sa_column=JSON)
    fingerprint: str
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
