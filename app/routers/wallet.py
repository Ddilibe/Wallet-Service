#!/usr/bin/env python3
"""Wallet-related endpoints.

Includes deposit initialization, Paystack webhook handling, balance and
transfer operations and transaction listing. Endpoints require appropriate
permissions which are enforced using dependency helpers.
"""
import hmac
import hashlib
import secrets
from datetime import datetime, timezone

import requests
from sqlmodel import select, desc
from fastapi import APIRouter, Depends, Request, HTTPException

from app.models import User
from app.core import get_settings
from app.database import get_session
from app.schemas import DepositReq, TransferReq
from sqlalchemy.ext.asyncio import AsyncSession
from app.deps import get_principal, require_permission, get_settings, get_session
from app.models import Wallet, Transaction, TransactionStatus, TransactionType, User

wallet = APIRouter(prefix="/wallet", tags=["wallet"])

settings = get_settings()


@wallet.post(
    "/deposit",
    summary="Initialize deposit",
    description=(
        "Create a pending deposit transaction and initialize a Paystack "
        "payment session. Returns a `reference` and `authorization_url` for "
        "the client to complete payment."
    ),
)
async def init_deposit(
    req: DepositReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Initialize a deposit via Paystack.

    Args:
        req: deposit amount and any client-provided data.
        principal: authenticated principal.
        session: DB session.

    Returns:
        JSON with `reference` and `authorization_url` for completing payment.

    Raises:
        HTTPException(401) if caller lacks permission.
        HTTPException(502) if Paystack initialization fails.
    """
    require_permission(principal, "deposit")
    try:
        if principal["type"] == "user":
            user: User = principal["user"][0]
        else:
            user = await session.get(User, principal["api_key"][0].user_id)  # type: ignore

        wallet = await session.execute(select(Wallet).where(Wallet.user_id == user.id))
        wallet = wallet.first()[0]  # type: ignore
        print(wallet)

        if not wallet:
            raise HTTPException(404, "Wallet not found")

        ref = "ps_" + secrets.token_urlsafe(12)

        tx = Transaction(
            id=wallet.id,
            tx_type=TransactionType.deposit,
            amount=req.amount,
            status=TransactionStatus.pending,
            reference=ref,
            user_id=user.id,  # type: ignore
        )
        session.add(tx)
        await session.commit()
        # call paystack
        resp = requests.post(
            "https://api.paystack.co/transaction/initialize",
            headers={
                "Authorization": f"Bearer {settings.PAYSTACK_PUBLIC_KEY}",
                "Content-Type": "application/json",
            },
            json={"amount": req.amount, "reference": ref, "email": user.email},
        )

        if not resp.ok:
            raise HTTPException(502, "Paystack initialize failed")

        data = resp.json()
        return {
            "reference": ref,
            "authorization_url": data["data"]["authorization_url"],
        }
    except Exception:
        raise HTTPException(status_code=502, detail="Paystack Initialization failed")


@wallet.post(
    "/paystack/webhook",
    summary="Paystack webhook",
    description=(
        "Endpoint for Paystack to POST transaction status updates. Validates "
        "the HMAC signature and updates the internal transaction and wallet "
        "records accordingly."
    ),
)
async def paystack_webhook(
    request: Request, session: AsyncSession = Depends(get_session)
):
    """Handle Paystack webhook callbacks.

    This endpoint validates the `x-paystack-signature` header and applies
    transaction updates atomically to the database.

    Raises:
        HTTPException(400) for missing or invalid signature.
    """

    body = await request.body()
    sig = request.headers.get("x-paystack-signature")

    if not sig:
        raise HTTPException(400, "Missing signature")

    computed = hmac.new(
        settings.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(computed, sig):
        raise HTTPException(400, "Invalid signature")

    payload = await request.json()
    data = payload.get("data", {})
    ref = data.get("reference")
    status = data.get("status")

    tx = await session.execute(select(Transaction).where(Transaction.reference == ref))
    tx = tx.first()[0]  # type: ignore

    if not tx:
        return {"status": True}

    if tx.status == TransactionStatus.success:
        return {"status": True}

    if status == "success":

        async with session.begin():
            w = await session.execute(select(Wallet).where(Wallet.id == tx.wallet_id))
            w = w.first()
            w.balance += tx.amount  # type: ignore

        tx.status = TransactionStatus.success
        tx.updated_at = datetime.now(timezone.utc)

        session.add(w)
        session.add(tx)
        await session.commit()

        return {"status": True}
    else:
        tx.status = TransactionStatus.failed

        session.add(tx)
        await session.commit()

        return {"status": True}


@wallet.get(
    "/deposit/{reference}/status",
    summary="Deposit status",
    description="Return the status and amount for a deposit identified by reference.",
)
async def deposit_status(
    reference: str, principal=Depends(get_principal), session=Depends(get_session)
):
    """Check deposit status by reference.

    Requires read permission. Returns reference, status, and amount.

    Raises:
        HTTPException(404) if transaction not found.
    """
    require_permission(principal, "read")

    tx = await session.execute(
        select(Transaction).where(Transaction.reference == reference)
    )
    tx = tx.first()[0]

    if not tx:
        raise HTTPException(404, "not found")
    print(tx)

    return {"reference": reference, "status": tx.status.value, "amount": tx.amount}


@wallet.get(
    "/balance",
    summary="Get wallet balance",
    description="Return the current balance for the caller's wallet.",
)
async def balance(
    principal=Depends(get_principal), session: AsyncSession = Depends(get_session)
):
    """Return the wallet balance for the authenticated principal.

    Requires read permission.
    """

    require_permission(principal, "read")

    if principal["type"] == "user":
        user = principal["user"][0]
    else:
        user = await session.get(User, principal["api_key"][0].user_id)

    wallet = await session.execute(select(Wallet).where(Wallet.user_id == user.id))  # type: ignore
    wallet = wallet.first()[0]  # type: ignore

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    return {"balance": wallet.balance}


@wallet.post(
    "/transfer",
    summary="Transfer funds",
    description=(
        "Transfer funds from the caller's wallet to another wallet by "
        "wallet number. Requires 'transfer' permission."
    ),
)
async def transfer(
    req: TransferReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
    """Transfer funds between wallets.

    Validates balances, deducts and credits wallets, and creates two
    transaction records representing the debit and credit.

    Raises:
        HTTPException(404) if recipient not found.
        HTTPException(400) for insufficient balance.
    """
    require_permission(principal, "transfer")

    if principal["type"] == "user":
        actor = principal["user"]
    else:
        actor = await session.get(User, principal["api_key"][0].user_id)

    sender = await session.execute(select(Wallet).where(Wallet.user_id == actor.id))  # type: ignore
    sender = sender.first()[0]  # type: ignore

    recipient = await session.execute(
        select(Wallet).where(Wallet.wallet_number == req.wallet_number)
    )
    recipient = recipient.first()[0]  # type: ignore

    if not recipient:
        raise HTTPException(404, "recipient not found")

    if sender.balance < req.amount:
        raise HTTPException(400, "insufficient balance")

    async with session.begin():
        s = await session.execute(select(Wallet).where(Wallet.id == sender.id))
        s = s.one()
        r = await session.execute(select(Wallet).where(Wallet.id == recipient.id))
        r = r.one()

        if s.balance < req.amount:
            raise HTTPException(400, "insufficient balance")

        s.balance -= req.amount
        r.balance += req.amount
        ref = "tr_" + secrets.token_urlsafe(10)

        tx1 = Transaction(
            id=s.id,
            tx_type=TransactionType.transfer,
            amount=-req.amount,
            status=TransactionStatus.success,
            reference=ref,
            user_id=actor.id,  # type: ignore
        )

        tx2 = Transaction(
            id=r.id,
            tx_type=TransactionType.transfer,
            amount=req.amount,
            status=TransactionStatus.success,
            reference=ref,
            user_id=actor.id,  # type: ignore
        )

        session.add(s)
        session.add(r)
        session.add(tx1)
        session.add(tx2)
        await session.commit()
        await session.refresh(tx1)
        await session.refresh(tx2)

    return {"status": "success", "message": "Transfer completed"}


@wallet.get(
    "/transactions",
    summary="List transactions",
    description="Return recent transactions for the authenticated principal.",
)
async def transactions(
    principal=Depends(get_principal), session: AsyncSession = Depends(get_session)
):
    """List transactions for the caller's wallet.

    Requires read permission. Returns an array of transactions (type, amount,
    status and reference).
    """
    require_permission(principal, "read")
    if principal["type"] == "user":
        user = principal["user"][0]
    else:
        user = await session.get(User, principal["api_key"].user_id)
    print(user)
    wallet = await session.execute(select(Wallet).where(Wallet.user_id == user.id))  # type: ignore
    wallet = wallet.first()
    txs = await session.execute(
        select(Transaction)
        .where(Transaction.id == user.id)  # type: ignore
        .order_by(desc(Transaction.created_at))
    )
    txs = txs.all()
    out = [
        {
            "type": t.tx_type.value,
            "amount": t.amount,
            "status": t.status.value,
            "reference": t.reference,
        }
        for t in txs
    ]
    return out
