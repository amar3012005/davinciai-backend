"""
Metrics Router - Production Implementation
Real database queries for call metrics, analytics, and real-time data.
"""

from fastapi import APIRouter, Query, Depends, status
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case, and_, extract
from loguru import logger

from app.database import get_db, Agent, CallLog
from app.auth.dependencies import get_token_payload, TokenPayload

router = APIRouter()


# ============= RESPONSE MODELS =============

class CallLogResponse(BaseModel):
    call_id: str
    agent_id: str
    duration_display: str
    duration_seconds: int
    cost_euros: float
    status: str
    start_time: str
    sentiment_score: Optional[float] = None
    ttft_ms: Optional[int] = None

class AnalyticsResponse(BaseModel):
    total_calls_today: int
    total_minutes_today: int
    total_cost_today: float
    success_rate: float
    avg_call_duration: int
    active_calls: int
    call_volume_trend: List[dict]
    cost_breakdown: dict

class LiveCallResponse(BaseModel):
    call_id: str
    agent_id: str
    duration_seconds: int
    estimated_cost: float
    status: str


# ============= ROUTES =============

@router.get("/calls", response_model=List[CallLogResponse])
async def get_call_logs(
    agent_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get call logs from the database, filtered by tenant."""
    query = select(CallLog).join(Agent, CallLog.agent_id == Agent.agent_id)

    # Tenant isolation
    query = query.where(Agent.tenant_id == token.tenant_id)

    if agent_id:
        query = query.where(CallLog.agent_id == agent_id)

    if status_filter:
        query = query.where(CallLog.status == status_filter)

    query = query.order_by(CallLog.start_time.desc()).offset(offset).limit(limit)

    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        CallLogResponse(
            call_id=log.id,
            agent_id=log.agent_id,
            duration_seconds=log.duration_seconds or 0,
            duration_display=f"{(log.duration_seconds or 0) // 60}:{(log.duration_seconds or 0) % 60:02d}",
            cost_euros=log.cost_euros or 0.0,
            status=log.status or "completed",
            start_time=log.start_time.isoformat() if log.start_time else "",
            sentiment_score=log.sentiment_score,
            ttft_ms=log.ttft_ms,
        )
        for log in logs
    ]


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    agent_id: Optional[str] = Query(None),
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated analytics from real database data."""
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    # Base filter: tenant isolation + today's data
    base_filter = and_(
        Agent.tenant_id == token.tenant_id,
        CallLog.start_time >= today_start,
    )
    if agent_id:
        base_filter = and_(base_filter, CallLog.agent_id == agent_id)

    # Aggregation query
    agg_query = (
        select(
            func.count(CallLog.id).label("total_calls"),
            func.coalesce(func.sum(CallLog.duration_seconds), 0).label("total_seconds"),
            func.coalesce(func.sum(CallLog.cost_euros), 0).label("total_cost"),
            func.coalesce(
                func.avg(
                    case(
                        (CallLog.status == "completed", 1.0),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("success_rate"),
            func.coalesce(func.avg(CallLog.duration_seconds), 0).label("avg_duration"),
        )
        .join(Agent, CallLog.agent_id == Agent.agent_id)
        .where(base_filter)
    )

    result = await db.execute(agg_query)
    row = result.first()

    total_calls = row.total_calls if row else 0
    total_seconds = int(row.total_seconds) if row else 0
    total_cost = float(row.total_cost) if row else 0.0
    success_rate = float(row.success_rate) if row else 0.0
    avg_duration = int(row.avg_duration) if row else 0

    # Hourly call volume trend
    hourly_query = (
        select(
            extract("hour", CallLog.start_time).label("hour"),
            func.count(CallLog.id).label("calls"),
        )
        .join(Agent, CallLog.agent_id == Agent.agent_id)
        .where(base_filter)
        .group_by(extract("hour", CallLog.start_time))
        .order_by(extract("hour", CallLog.start_time))
    )

    hourly_result = await db.execute(hourly_query)
    hourly_rows = hourly_result.all()

    # Build full 24h trend (fill missing hours with 0)
    hourly_map = {int(r.hour): r.calls for r in hourly_rows}
    call_volume_trend = [
        {"hour": f"{h:02d}:00", "calls": hourly_map.get(h, 0)}
        for h in range(0, 24, 2)
    ]

    # Cost breakdown by duration bucket
    cost_breakdown_query = (
        select(
            func.count(CallLog.id).label("calls"),
            func.coalesce(func.sum(CallLog.cost_euros), 0).label("cost"),
            case(
                (CallLog.duration_seconds <= 300, "0-5_min"),
                (CallLog.duration_seconds <= 600, "5-10_min"),
                (CallLog.duration_seconds <= 900, "10-15_min"),
                else_="15+_min",
            ).label("bucket"),
        )
        .join(Agent, CallLog.agent_id == Agent.agent_id)
        .where(base_filter)
        .group_by("bucket")
    )

    cost_result = await db.execute(cost_breakdown_query)
    cost_rows = cost_result.all()

    cost_breakdown = {
        "0-5_min": {"calls": 0, "cost": 0.0},
        "5-10_min": {"calls": 0, "cost": 0.0},
        "10-15_min": {"calls": 0, "cost": 0.0},
        "15+_min": {"calls": 0, "cost": 0.0},
    }
    for r in cost_rows:
        cost_breakdown[r.bucket] = {"calls": r.calls, "cost": round(float(r.cost), 2)}

    # Active calls (calls started in the last 30 minutes with no end_time)
    active_filter = and_(
        Agent.tenant_id == token.tenant_id,
        CallLog.start_time >= datetime.utcnow() - timedelta(minutes=30),
        CallLog.end_time.is_(None),
        CallLog.status == "in_progress",
    )
    if agent_id:
        active_filter = and_(active_filter, CallLog.agent_id == agent_id)

    active_query = (
        select(func.count(CallLog.id))
        .join(Agent, CallLog.agent_id == Agent.agent_id)
        .where(active_filter)
    )
    active_result = await db.execute(active_query)
    active_calls = active_result.scalar() or 0

    return AnalyticsResponse(
        total_calls_today=total_calls,
        total_minutes_today=total_seconds // 60,
        total_cost_today=round(total_cost, 2),
        success_rate=round(success_rate, 3),
        avg_call_duration=avg_duration,
        active_calls=active_calls,
        call_volume_trend=call_volume_trend,
        cost_breakdown=cost_breakdown,
    )


@router.get("/realtime", response_model=List[LiveCallResponse])
async def get_realtime_calls(
    agent_id: Optional[str] = Query(None),
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get currently active calls from the database."""
    active_filter = and_(
        Agent.tenant_id == token.tenant_id,
        CallLog.start_time >= datetime.utcnow() - timedelta(minutes=60),
        CallLog.end_time.is_(None),
        CallLog.status == "in_progress",
    )
    if agent_id:
        active_filter = and_(active_filter, CallLog.agent_id == agent_id)

    query = (
        select(CallLog)
        .join(Agent, CallLog.agent_id == Agent.agent_id)
        .where(active_filter)
        .order_by(CallLog.start_time.desc())
        .limit(20)
    )

    result = await db.execute(query)
    calls = result.scalars().all()

    now = datetime.utcnow()
    return [
        LiveCallResponse(
            call_id=call.id,
            agent_id=call.agent_id,
            duration_seconds=int((now - call.start_time).total_seconds()) if call.start_time else 0,
            estimated_cost=call.cost_euros or 0.0,
            status=call.status or "in_progress",
        )
        for call in calls
    ]
