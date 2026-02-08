"""
Wallet Router - Production Implementation
Real database queries for wallet balance, transactions, and top-ups.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import and_
from loguru import logger

from app.database import get_db, Wallet, Transaction
from app.auth.dependencies import get_token_payload, TokenPayload
from rules import BILLING_RULES, get_pricing_display

router = APIRouter()


# ============= RESPONSE MODELS =============

class WalletResponse(BaseModel):
    wallet_id: str
    balance_euros: float
    currency: str
    estimated_calls_remaining: int
    balance_status: str
    is_auto_recharge_enabled: bool
    auto_recharge_amount: float
    low_balance_threshold: float

class TransactionResponse(BaseModel):
    transaction_id: str
    type: str
    amount_euros: float
    description: Optional[str] = None
    reference_id: Optional[str] = None
    created_at: str

class TopUpRequest(BaseModel):
    amount_euros: float


# ============= ROUTES =============

@router.get("/{tenant_id}", response_model=WalletResponse)
async def get_wallet_balance(
    tenant_id: str,
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get wallet balance for a tenant."""
    # Enforce tenant isolation
    if token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    result = await db.execute(
        select(Wallet).where(Wallet.tenant_id == tenant_id)
    )
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )

    balance = wallet.balance or 0.0

    return WalletResponse(
        wallet_id=wallet.wallet_id,
        balance_euros=round(balance, 2),
        currency=wallet.currency or "EUR",
        estimated_calls_remaining=BILLING_RULES.get_estimated_calls_remaining(balance),
        balance_status=BILLING_RULES.get_balance_status(balance),
        is_auto_recharge_enabled=wallet.is_auto_recharge_enabled,
        auto_recharge_amount=wallet.auto_recharge_amount or 0.0,
        low_balance_threshold=wallet.low_balance_threshold or 10.0,
    )


@router.get("/{tenant_id}/transactions", response_model=List[TransactionResponse])
async def get_transaction_history(
    tenant_id: str,
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    type_filter: Optional[str] = Query(None, alias="type"),
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get transaction history for a tenant from the database."""
    if token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    query = select(Transaction).where(Transaction.tenant_id == tenant_id)

    if type_filter:
        query = query.where(Transaction.type == type_filter)

    query = query.order_by(Transaction.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return [
        TransactionResponse(
            transaction_id=t.transaction_id,
            type=t.type,
            amount_euros=t.amount_euros,
            description=t.description,
            reference_id=t.reference_id,
            created_at=t.created_at.isoformat() if t.created_at else "",
        )
        for t in transactions
    ]


@router.post("/{tenant_id}/topup")
async def initiate_topup(
    tenant_id: str,
    request: TopUpRequest,
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Initiate a wallet top-up."""
    if token.tenant_id != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    if request.amount_euros < BILLING_RULES.min_topup_amount_euros:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Minimum top-up is \u20ac{BILLING_RULES.min_topup_amount_euros}",
        )

    if request.amount_euros > BILLING_RULES.max_topup_amount_euros:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum top-up is \u20ac{BILLING_RULES.max_topup_amount_euros}",
        )

    # Get wallet
    result = await db.execute(
        select(Wallet).where(Wallet.tenant_id == tenant_id)
    )
    wallet = result.scalars().first()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found",
        )

    # Credit wallet
    topup_amount = Decimal(str(request.amount_euros))
    wallet.balance = Decimal(str(wallet.balance or 0)) + topup_amount

    # Record transaction
    txn = Transaction(
        wallet_id=wallet.wallet_id,
        tenant_id=tenant_id,
        type="topup",
        amount_euros=topup_amount,
        description=f"Top-up of \u20ac{topup_amount:.2f}",
    )
    db.add(txn)
    await db.flush()

    logger.info(f"Wallet {wallet.wallet_id} topped up by \u20ac{request.amount_euros:.2f}")

    return {
        "status": "completed",
        "amount_euros": request.amount_euros,
        "new_balance": round(wallet.balance, 2),
        "transaction_id": txn.transaction_id,
    }


@router.get("/pricing/display")
async def get_pricing_tiers():
    """Get pricing tiers for display on frontend."""
    return {
        "tiers": get_pricing_display(),
        "topup_presets": BILLING_RULES.topup_presets_euros,
    }
