"""
Cartesia Webhooks - Production Implementation
Handles incoming webhooks from Cartesia platform with DB integration.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from decimal import Decimal
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError

from app.database import get_db, Agent, CallLog, Wallet, Transaction
from rules import BILLING_RULES

router = APIRouter()


class WebhookResponse(BaseModel):
    status: str
    message: str


@router.post("/cartesia/{agent_id}", response_model=WebhookResponse)
async def handle_cartesia_webhook(
    agent_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Handle Cartesia webhook events with full database integration.
    Logs calls, calculates costs, and deducts from wallet.
    """
    try:
        data = await request.json()
        event_type = data.get("type")

        logger.info(f"Webhook received: {event_type} for agent {agent_id}")

        # Verify agent exists
        result = await db.execute(
            select(Agent).where(Agent.agent_id == agent_id)
        )
        agent = result.scalars().first()

        if not agent:
            logger.warning(f"Webhook for unknown agent: {agent_id}")
            raise HTTPException(status_code=404, detail="Agent not found")

        if event_type == "call_started":
            request_id = data.get("request_id")
            logger.info(f"Call started: {request_id} for agent {agent.agent_name}")

        elif event_type == "call_completed":
            request_id = data.get("request_id", "")
            body = data.get("body", [])

            duration_seconds = 0
            if body and isinstance(body, list) and len(body) > 0:
                start_ts = body[0].get("start_timestamp", 0)
                end_ts = body[-1].get("end_timestamp", 0)
                duration_seconds = max(0, int(end_ts - start_ts))

            cost = Decimal(str(BILLING_RULES.calculate_call_cost(duration_seconds)))

            # Create call log
            call_log = CallLog(
                id=request_id or None,
                agent_id=agent.agent_id,
                duration_seconds=duration_seconds,
                status="completed",
                cost_euros=cost,
            )
            db.add(call_log)

            # Flush to catch duplicate PK
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                return WebhookResponse(status="duplicate", message="Call already recorded")

            # Deduct from wallet
            if agent.wallet_id:
                wallet_result = await db.execute(
                    select(Wallet).where(Wallet.wallet_id == agent.wallet_id)
                )
                wallet = wallet_result.scalars().first()

                if wallet:
                    wallet.balance = Decimal(str(wallet.balance or 0)) - cost

                    txn = Transaction(
                        wallet_id=wallet.wallet_id,
                        tenant_id=agent.tenant_id,
                        type="deduction",
                        amount_euros=-cost,
                        description=f"Cartesia call {request_id[:12] if request_id else 'unknown'}... ({duration_seconds}s)",
                        reference_id=request_id,
                    )
                    db.add(txn)

            await db.flush()

            logger.info(
                f"Call completed: {request_id} | "
                f"Duration: {duration_seconds}s | Cost: \u20ac{cost:.2f}"
            )

        elif event_type == "call_failed":
            request_id = data.get("request_id", "")
            logger.warning(f"Call failed: {request_id}")

            call_log = CallLog(
                id=request_id or None,
                agent_id=agent.agent_id,
                duration_seconds=0,
                status="failed",
                cost_euros=0.0,
            )
            db.add(call_log)
            await db.flush()

        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return WebhookResponse(status="duplicate", message="Call already recorded")
        except Exception as e:
            await db.rollback()
            logger.error(f"Error persisting Cartesia webhook: {e}")
            raise HTTPException(status_code=500, detail="Internal server error")

        return WebhookResponse(
            status="success",
            message=f"Webhook {event_type} processed",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
