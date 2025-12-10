#!/usr/bin/env python3
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


@wallet.post("/deposit")
async def init_deposit(
    req: DepositReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
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


@wallet.post("/paystack/webhook")
async def paystack_webhook(
    request: Request, session: AsyncSession = Depends(get_session)
):

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


@wallet.get("/deposit/{reference}/status")
async def deposit_status(
    reference: str, principal=Depends(get_principal), session=Depends(get_session)
):
    require_permission(principal, "read")

    tx = await session.execute(
        select(Transaction).where(Transaction.reference == reference)
    )
    tx = tx.first()[0]

    if not tx:
        raise HTTPException(404, "not found")
    print(tx)

    return {"reference": reference, "status": tx.status.value, "amount": tx.amount}


@wallet.get("/balance")
async def balance(
    principal=Depends(get_principal), session: AsyncSession = Depends(get_session)
):

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


@wallet.post("/transfer")
async def transfer(
    req: TransferReq,
    principal=Depends(get_principal),
    session: AsyncSession = Depends(get_session),
):
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


@wallet.get("/transactions")
async def transactions(
    principal=Depends(get_principal), session: AsyncSession = Depends(get_session)
):
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
