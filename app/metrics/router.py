"""
Metrics Router - Production Implementation
Real database queries for call metrics, analytics, and real-time data.
"""

from fastapi import APIRouter, Query, Depends, status
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
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
    
    # Advanced Metrics
    frustration_velocity: Optional[str] = None
    agent_iq: Optional[float] = None
    avg_sentiment: Optional[float] = None
    correction_count: int = 0
    
    # Business Signals
    is_churn_risk: bool = False
    is_hot_lead: bool = False
    priority_level: str = "NORMAL"

class AnalyticsResponse(BaseModel):
    total_calls_today: int
    total_minutes_today: int
    total_cost_today: float
    success_rate: float
    avg_call_duration: int
    active_calls: int
    call_volume_trend: List[Dict[str, Any]]
    cost_breakdown: Dict[str, Dict[str, Any]]
    
    # Intelligence Metrics
    leads_today: int = 0
    churn_risks_today: int = 0
    avg_agent_iq: float = 0.0

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
            frustration_velocity=log.frustration_velocity,
            agent_iq=log.agent_iq,
            avg_sentiment=log.avg_sentiment,
            correction_count=log.correction_count or 0,
            is_churn_risk=log.is_churn_risk or False,
            is_hot_lead=log.is_hot_lead or False,
            priority_level=log.priority_level or "NORMAL",
        )
        for log in logs
    ]


@router.get("/analytics", response_model=AnalyticsResponse)
async def get_analytics(
    agent_id: Optional[str] = Query(None),
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get aggregated analytics from real database data. Cached for 60s."""
    from app.database.redis import get_redis
    import json
    
    # Try Cache
    cache_key = f"metrics:{token.tenant_id}:analytics:{datetime.utcnow().date()}:{agent_id or 'all'}"
    redis = await get_redis()
    
    cached_data = await redis.get(cache_key)
    if cached_data:
        try:
            return json.loads(cached_data)
        except Exception:
            pass # Invalid cache, fall through to DB
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
            # New Intelligence Aggregations
            func.count(CallLog.id).filter(CallLog.is_hot_lead == True).label("leads_today"),
            func.count(CallLog.id).filter(CallLog.is_churn_risk == True).label("churn_risks_today"),
            func.coalesce(func.avg(CallLog.agent_iq), 0).label("avg_agent_iq"),
        )
        .join(Agent, CallLog.agent_id == Agent.agent_id)
        .where(base_filter)
    )

    result = await db.execute(agg_query)
    agg_res = result.first()

    total_calls = agg_res.total_calls if agg_res else 0
    total_seconds = int(agg_res.total_seconds) if agg_res else 0
    total_cost = float(agg_res.total_cost) if agg_res else 0.0
    success_rate = float(agg_res.success_rate) if agg_res else 0.0
    avg_duration = int(agg_res.avg_duration) if agg_res else 0

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

    response = AnalyticsResponse(
        total_calls_today=total_calls,
        total_minutes_today=total_seconds // 60,
        total_cost_today=round(total_cost, 2),
        success_rate=round(success_rate, 3),
        avg_call_duration=avg_duration,
        active_calls=active_calls,
        call_volume_trend=call_volume_trend,
        cost_breakdown=cost_breakdown,
        leads_today=agg_res.leads_today or 0,
        churn_risks_today=agg_res.churn_risks_today or 0,
        avg_agent_iq=float(agg_res.avg_agent_iq or 0),
    )
    
    # Cache result
    await redis.set(cache_key, response.model_dump_json(), ex=60)
    
    return response


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
