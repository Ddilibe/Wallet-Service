#!/usr/bin/env python3
import hmac
import hashlib
import secrets
from datetime import datetime, timezone

import requests
from sqlmodel import select, desc
from fastapi import APIRouter, Depends, Request, HTTPException

from app.core import get_settings
from app.database import get_session
from app.schemas import DepositReq, TransferReq
from app.models import Wallet, Transaction, TransactionStatus, TransactionType, User
from app.deps import get_principal, require_permission, get_settings, get_session

wallet = APIRouter(prefix="/wallet", tags=["wallet"])

settings = get_settings()


@wallet.post("/deposit")
def init_deposit(
    req: DepositReq, principal=Depends(get_principal), session=Depends(get_session)
):
    require_permission(principal, "deposit")

    if principal["type"] == "user":
        user = principal["user"]
    else:
        user = session.get(User, principal["api_key"].user_id)

    wallet = session.exec(select(Wallet).where(Wallet.user_id == user.id)).first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    ref = "ps_" + secrets.token_urlsafe(12)

    tx = Transaction(
        id=wallet.id,
        tx_type=TransactionType.deposit,
        amount=req.amount,
        status=TransactionStatus.pending,
        reference=ref,
        user_id=user.id,
    )
    session.add(tx)
    session.commit()
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
    return {"reference": ref, "authorization_url": data["data"]["authorization_url"]}


@wallet.post("/paystack/webhook")
async def paystack_webhook(request: Request, session=Depends(get_session)):

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

    tx = session.exec(select(Transaction).where(Transaction.reference == ref)).first()

    if not tx:
        return {"status": True}

    if tx.status == TransactionStatus.success:
        return {"status": True}

    if status == "success":

        with session.begin():
            w = session.exec(select(Wallet).where(Wallet.id == tx.wallet_id)).one()
            w.balance += tx.amount

        tx.status = TransactionStatus.success
        tx.updated_at = datetime.now(timezone.utc)

        session.add(w)
        session.add(tx)
        session.commit()

        return {"status": True}
    else:
        tx.status = TransactionStatus.failed

        session.add(tx)
        session.commit()

        return {"status": True}


@wallet.get("/deposit/{reference}/status")
def deposit_status(
    reference: str, principal=Depends(get_principal), session=Depends(get_session)
):
    require_permission(principal, "read")

    tx = session.exec(
        select(Transaction).where(Transaction.reference == reference)
    ).first()

    if not tx:
        raise HTTPException(404, "not found")

    return {"reference": reference, "status": tx.status.value, "amount": tx.amount}


@wallet.get("/balance")
def balance(principal=Depends(get_principal), session=Depends(get_session)):

    require_permission(principal, "read")

    if principal["type"] == "user":
        user = principal["user"]
    else:
        user = session.get(User, principal["api_key"].user_id)

    wallet = session.exec(select(Wallet).where(Wallet.user_id == user.id)).first()

    if not wallet:
        raise HTTPException(404, "Wallet not found")

    return {"balance": wallet.balance}


@wallet.post("/transfer")
def transfer(
    req: TransferReq, principal=Depends(get_principal), session=Depends(get_session)
):
    require_permission(principal, "transfer")

    if principal["type"] == "user":
        actor = principal["user"]
    else:
        actor = session.get(User, principal["api_key"].user_id)

    sender = session.exec(select(Wallet).where(Wallet.user_id == actor.id)).first()

    recipient = session.exec(
        select(Wallet).where(Wallet.wallet_number == req.wallet_number)
    ).first()

    if not recipient:
        raise HTTPException(404, "recipient not found")

    if sender.balance < req.amount:
        raise HTTPException(400, "insufficient balance")

    with session.begin():
        s = session.exec(select(Wallet).where(Wallet.id == sender.id)).one()
        r = session.exec(select(Wallet).where(Wallet.id == recipient.id)).one()

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
            user_id=actor.id,
        )

        tx2 = Transaction(
            id=r.id,
            tx_type=TransactionType.transfer,
            amount=req.amount,
            status=TransactionStatus.success,
            reference=ref,
            user_id=actor.id,
        )

        session.add(s)
        session.add(r)
        session.add(tx1)
        session.add(tx2)
        session.commit()
        session.refresh(tx1)
        session.refresh(tx2)

    return {"status": "success", "message": "Transfer completed"}


@wallet.get("/transactions")
def transactions(principal=Depends(get_principal), session=Depends(get_session)):
    require_permission(principal, "read")
    if principal["type"] == "user":
        user = principal["user"]
    else:
        user = session.get(User, principal["api_key"].user_id)
    wallet = session.exec(select(Wallet).where(Wallet.user_id == user.id)).first()
    txs = session.exec(
        select(Transaction)
        .where(Transaction.id == wallet.id)
        .order_by(desc(Transaction.created_at))
    ).all()
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
