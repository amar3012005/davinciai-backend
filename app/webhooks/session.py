"""
Session Webhook - Production Implementation
Ingests Enhanced Session Reports from DaVinci/Cartesia voice agents.
"""

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import IntegrityError
from loguru import logger

from app.database import get_db, Agent, CallLog, Wallet, Transaction
from rules import BILLING_RULES

router = APIRouter()


class SessionReportPayload(BaseModel):
    session_id: str
    user_id: Optional[str] = "anonymous"
    agent_name: Optional[str] = None
    agent_id: Optional[str] = None
    tenant_id: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    duration_seconds: float = 0.0
    total_turns: int = 0
    avg_ttft_ms: float = 0.0
    avg_ttfc_ms: float = 0.0
    status: str = "completed"
    caller_id: Optional[str] = None
    analysis: Optional[dict] = None


@router.post("/session")
async def ingest_session_report(
    payload: SessionReportPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Ingest session reports from DaVinci/Cartesia voice agents.
    Maps the session to the correct agent and tenant, records the call log,
    and deducts from the tenant wallet.

    Idempotent: duplicate session_id returns 200 with status "duplicate".
    """
    # Pre-check for duplicate session_id
    existing = await db.execute(
        select(CallLog).where(CallLog.id == payload.session_id)
    )
    if existing.scalars().first():
        logger.info(f"Session {payload.session_id}: already ingested, skipping")
        return {"status": "duplicate", "session_id": payload.session_id}

    # Detailed logging of incoming payload
    logger.info(f"Incoming session report for {payload.session_id}")
    logger.debug(f"Payload: {payload.model_dump_json()}")

    # 1. Resolve agent & Extract JWT context if present
    user_id = payload.user_id
    jwt_claims = {}
    
    # Check if user_id is a JWT (contains at least one dot and is relatively long)
    if user_id and "." in user_id and len(user_id) > 50:
        try:
            import json
            import base64
            # Decode JWT payload (middle part)
            parts = user_id.split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                # Pad if necessary
                payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                decoded = base64.b64decode(payload_b64).decode("utf-8")
                jwt_claims = json.loads(decoded)
                
                # Extract real sub (user_id) and tenant_id
                real_user_id = jwt_claims.get("sub")
                real_tenant_id = jwt_claims.get("tenant_id")
                
                if real_user_id:
                    logger.info(f"Decoded user_id from JWT: {real_user_id}")
                    user_id = real_user_id
                if real_tenant_id:
                    logger.info(f"Decoded tenant_id from JWT: {real_tenant_id}")
                    # Prioritize tenant_id from JWT if payload doesn't have it
                    if not payload.tenant_id:
                        payload.tenant_id = real_tenant_id
        except Exception as e:
            logger.warning(f"Failed to decode JWT user_id: {e}")

    agent = None

    if payload.agent_id:
        result = await db.execute(
            select(Agent).where(Agent.agent_id == payload.agent_id)
        )
        agent = result.scalars().first()

    if not agent and payload.agent_name:
        # If tenant_id is known, filter agent by name AND tenant
        if payload.tenant_id:
            result = await db.execute(
                select(Agent).where(
                    and_(
                        Agent.agent_name == payload.agent_name,
                        Agent.tenant_id == payload.tenant_id
                    )
                )
            )
            agent = result.scalars().first()
        
        # Fallback to name only if still not found
        if not agent:
            result = await db.execute(
                select(Agent).where(Agent.agent_name == payload.agent_name)
            )
            agent = result.scalars().first()

    if not agent:
        if payload.tenant_id:
            result = await db.execute(
                select(Agent).where(Agent.tenant_id == payload.tenant_id).limit(1)
            )
            agent = result.scalars().first()

    if not agent:
        logger.warning(f"Session {payload.session_id}: could not resolve agent (agent_id={payload.agent_id}, agent_name={payload.agent_name}, tenant_id={payload.tenant_id})")
        raise HTTPException(status_code=404, detail=f"Agent not found for session {payload.session_id}")

    logger.info(f"Resolved agent: {agent.agent_name} (ID: {agent.agent_id}) for tenant: {agent.tenant_id}")

    # 2. Calculate cost
    duration_secs = int(payload.duration_seconds)
    cost = Decimal(str(BILLING_RULES.calculate_call_cost(duration_secs)))

    # 3. Extract analysis/signals
    sentiment_score = None
    frustration_velocity = None
    agent_iq = None
    avg_sentiment = None
    correction_count = 0
    is_churn_risk = False
    is_hot_lead = False
    priority_level = "NORMAL"

    if payload.analysis and isinstance(payload.analysis, dict):
        logger.info(f"Processing analysis report: {list(payload.analysis.keys())}")
        
        # Extract Metrics
        metrics_payload = payload.analysis.get("metrics", {})
        if isinstance(metrics_payload, dict):
            frustration_velocity = metrics_payload.get("frustration_velocity")
            agent_iq = metrics_payload.get("agent_iq")
            avg_sentiment = metrics_payload.get("avg_sentiment")
            correction_count = metrics_payload.get("correction_count", 0)

        # Extract Business Signals
        business_signals = payload.analysis.get("business_signals", {})
        if isinstance(business_signals, dict):
            sentiment_score = business_signals.get("sentiment_score")
            is_churn_risk = business_signals.get("is_churn_risk", False)
            is_hot_lead = business_signals.get("is_hot_lead", False)
            priority_level = business_signals.get("priority_level", "NORMAL")
            
            logger.info(f"Extracted signals: sentiment={sentiment_score}, churn={is_churn_risk}, lead={is_hot_lead}")

    # 4. Parse timestamps
    start_time = None
    end_time = None
    try:
        if payload.start_time:
            start_time = datetime.fromisoformat(str(payload.start_time).replace('Z', '+00:00'))
        if payload.end_time:
            end_time = datetime.fromisoformat(str(payload.end_time).replace('Z', '+00:00'))
    except (ValueError, TypeError) as e:
        logger.warning(f"Timestamp parsing error: {e}. Falling back to now.")
        start_time = datetime.utcnow()

    if not start_time:
        start_time = datetime.utcnow()

    # 5. Create call log
    call_log = CallLog(
        id=payload.session_id,
        agent_id=agent.agent_id,
        start_time=start_time,
        end_time=end_time,
        duration_seconds=duration_secs,
        status=payload.status,
        caller_id=payload.caller_id or user_id,
        ttft_ms=int(payload.avg_ttft_ms) if payload.avg_ttft_ms else None,
        ttfc_ms=int(payload.avg_ttfc_ms) if payload.avg_ttfc_ms else None,
        sentiment_score=sentiment_score,
        frustration_velocity=frustration_velocity,
        agent_iq=agent_iq,
        avg_sentiment=avg_sentiment,
        correction_count=correction_count,
        is_churn_risk=is_churn_risk,
        is_hot_lead=is_hot_lead,
        priority_level=priority_level,
        cost_euros=cost,
    )
    db.add(call_log)

    # 6. Deduct from wallet
    if agent.wallet_id:
        wallet_result = await db.execute(
            select(Wallet).where(Wallet.wallet_id == agent.wallet_id)
        )
        wallet = wallet_result.scalars().first()

        if wallet:
            cost_decimal = Decimal(str(cost))
            wallet.balance = (Decimal(str(wallet.balance or 0))) - cost_decimal

            txn = Transaction(
                wallet_id=wallet.wallet_id,
                tenant_id=agent.tenant_id,
                type="deduction",
                amount_euros=-cost_decimal,
                description=f"Call {payload.session_id[:12]}... ({duration_secs}s)",
                reference_id=payload.session_id,
            )
            db.add(txn)

            logger.info(
                f"Session {payload.session_id}: deducted \u20ac{cost:.2f} from wallet {wallet.wallet_id} "
                f"(new balance: \u20ac{wallet.balance:.2f})"
            )

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning(f"Session {payload.session_id}: IntegrityError (likely duplicate), skipping")
        return {"status": "duplicate", "session_id": payload.session_id}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error persisting session {payload.session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error persisting session report")

    logger.info(
        f"Session ingested: {payload.session_id} | agent={agent.agent_name} | "
        f"duration={duration_secs}s | cost=\u20ac{cost} | status={payload.status}"
    )

    return {
        "status": "ingested",
        "session_id": payload.session_id,
        "agent_id": agent.agent_id,
        "cost_euros": float(cost),
    }
