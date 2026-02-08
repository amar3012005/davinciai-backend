"""
Tenants Router - Production Implementation
Tenant info and agent listing with real stats from database.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case

from app.database import get_db, Tenant, Agent, CallLog
from app.auth.dependencies import get_token_payload, TokenPayload

router = APIRouter()


# ============= RESPONSE MODELS =============

class TenantResponse(BaseModel):
    tenant_id: str
    organization_name: str
    subdomain: str
    plan_tier: str
    is_active: bool
    created_at: str

class AgentListResponse(BaseModel):
    agent_id: str
    agent_name: str
    agent_description: Optional[str] = None
    language_primary: str
    language_secondary: Optional[str] = None
    websocket_url: Optional[str] = None
    is_active: bool
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    cost_per_minute: float = 0.15
    routing_tier: str = "standard"
    stats: Optional[dict] = {"total_calls": 0, "total_minutes": 0, "success_rate": 0.0}


# ============= ROUTES =============

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get tenant information."""
    if token.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    tenant = result.scalars().first()

    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    return {
        "tenant_id": tenant.tenant_id,
        "organization_name": tenant.organization_name,
        "subdomain": tenant.subdomain,
        "plan_tier": tenant.plan_tier,
        "is_active": tenant.is_active,
        "created_at": tenant.created_at.isoformat(),
    }


@router.get("/{tenant_id}/agents", response_model=List[AgentListResponse])
async def list_tenant_agents(
    tenant_id: str,
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """List all agents for a tenant with real stats."""
    if token.tenant_id != tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Verify tenant exists
    tenant_result = await db.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    if not tenant_result.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    # Get agents
    result = await db.execute(select(Agent).where(Agent.tenant_id == tenant_id))
    agents = result.scalars().all()

    # Batch-fetch stats for all agents
    agent_ids = [a.agent_id for a in agents]

    stats_map = {}
    if agent_ids:
        stats_query = (
            select(
                CallLog.agent_id,
                func.count(CallLog.id).label("total_calls"),
                func.coalesce(func.sum(CallLog.duration_seconds), 0).label("total_seconds"),
                func.coalesce(
                    func.avg(
                        case(
                            (CallLog.status == "completed", 1.0),
                            else_=0.0,
                        )
                    ),
                    0.0,
                ).label("success_rate"),
            )
            .where(CallLog.agent_id.in_(agent_ids))
            .group_by(CallLog.agent_id)
        )
        stats_result = await db.execute(stats_query)
        for row in stats_result.all():
            stats_map[row.agent_id] = {
                "total_calls": row.total_calls or 0,
                "total_minutes": round((row.total_seconds or 0) / 60, 1),
                "success_rate": round(float(row.success_rate or 0.0), 3),
            }

    return [
        AgentListResponse(
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            agent_description=agent.agent_description,
            language_primary=agent.language_primary,
            language_secondary=agent.language_secondary,
            websocket_url=agent.websocket_url,
            is_active=agent.is_active,
            location=agent.location,
            avatar_url=agent.avatar_url,
            cost_per_minute=agent.cost_per_minute or 0.15,
            routing_tier=agent.routing_tier or "standard",
            stats=stats_map.get(agent.agent_id, {"total_calls": 0, "total_minutes": 0, "success_rate": 0.0}),
        )
        for agent in agents
    ]
