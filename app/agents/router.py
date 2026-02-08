"""
Agents Router - Production Implementation
Full CRUD with real database stats.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case
import json
import uuid

from app.database import get_db, Agent, CallLog
from app.auth.dependencies import get_current_user, get_token_payload, TokenPayload
from app.database import User

router = APIRouter()


# ============= REQUEST/RESPONSE MODELS =============

class AgentDetailResponse(BaseModel):
    agent_id: str
    agent_name: str
    agent_description: Optional[str] = None
    cartesia_agent_id: Optional[str] = None
    language_primary: str
    language_secondary: Optional[str] = None
    websocket_url: Optional[str] = None
    location: Optional[str] = None
    created_at: Optional[datetime] = None
    is_active: bool
    configuration: dict

    avatar_url: Optional[str] = None
    voice_sample_url: Optional[str] = None
    phone_number: Optional[str] = None
    sip_uri: Optional[str] = None
    cost_per_minute: float = 0.15
    routing_tier: str = "standard"

    llm_config: Optional[dict] = None
    voice_config: Optional[dict] = None
    flow_config: Optional[dict] = None

    stats: Optional[dict] = {"total_calls": 0, "total_minutes": 0, "success_rate": 0.0}


class CreateAgentRequest(BaseModel):
    agent_name: str
    agent_description: Optional[str] = None
    location: Optional[str] = None
    language_primary: str = "en"
    language_secondary: Optional[str] = None
    websocket_url: Optional[str] = None
    phone_number: Optional[str] = None
    sip_uri: Optional[str] = None
    cost_per_minute: float = 0.15
    routing_tier: str = "standard"
    avatar_url: Optional[str] = None
    voice_sample_url: Optional[str] = None
    cartesia_agent_id: Optional[str] = None
    wallet_id: Optional[str] = None
    llm_config: Optional[dict] = None
    voice_config: Optional[dict] = None
    flow_config: Optional[dict] = None


class UpdateAgentRequest(BaseModel):
    agent_name: Optional[str] = None
    agent_description: Optional[str] = None
    location: Optional[str] = None
    language_primary: Optional[str] = None
    language_secondary: Optional[str] = None
    websocket_url: Optional[str] = None
    phone_number: Optional[str] = None
    sip_uri: Optional[str] = None
    cost_per_minute: Optional[float] = None
    routing_tier: Optional[str] = None
    avatar_url: Optional[str] = None
    voice_sample_url: Optional[str] = None
    cartesia_agent_id: Optional[str] = None
    wallet_id: Optional[str] = None
    is_active: Optional[bool] = None
    llm_config: Optional[dict] = None
    voice_config: Optional[dict] = None
    flow_config: Optional[dict] = None


# ============= HELPERS =============

def _parse_json(json_str: Optional[str]) -> dict:
    if not json_str:
        return {}
    try:
        return json.loads(json_str)
    except (json.JSONDecodeError, TypeError):
        return {}


async def _get_agent_stats(db: AsyncSession, agent_id: str) -> dict:
    stats_query = select(
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
    ).where(CallLog.agent_id == agent_id)

    result = await db.execute(stats_query)
    row = result.first()

    return {
        "total_calls": row.total_calls or 0,
        "total_minutes": round((row.total_seconds or 0) / 60, 1),
        "success_rate": round(float(row.success_rate or 0.0), 3),
    }


def _agent_to_response(agent: Agent, stats: dict) -> dict:
    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.agent_name,
        "agent_description": agent.agent_description,
        "cartesia_agent_id": agent.cartesia_agent_id,
        "language_primary": agent.language_primary,
        "language_secondary": agent.language_secondary,
        "websocket_url": agent.websocket_url,
        "location": agent.location,
        "configuration": _parse_json(agent.configuration),
        "is_active": agent.is_active,
        "created_at": agent.created_at,
        "avatar_url": agent.avatar_url,
        "voice_sample_url": agent.voice_sample_url,
        "phone_number": agent.phone_number,
        "sip_uri": agent.sip_uri,
        "cost_per_minute": agent.cost_per_minute or 0.15,
        "routing_tier": agent.routing_tier or "standard",
        "llm_config": _parse_json(agent.llm_config),
        "voice_config": _parse_json(agent.voice_config),
        "flow_config": _parse_json(agent.flow_config),
        "stats": stats,
    }


# ============= ROUTES =============

@router.get("/{agent_id}", response_model=AgentDetailResponse)
async def get_agent_details(
    agent_id: str,
    token: TokenPayload = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed information about a specific agent."""
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    # Tenant isolation
    if agent.tenant_id != token.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    stats = await _get_agent_stats(db, agent_id)
    return _agent_to_response(agent, stats)


@router.post("/", response_model=AgentDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(
    request: CreateAgentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new agent for the current tenant."""
    agent = Agent(
        agent_id=str(uuid.uuid4()),
        tenant_id=user.tenant_id,
        wallet_id=request.wallet_id,
        agent_name=request.agent_name,
        agent_description=request.agent_description,
        location=request.location,
        language_primary=request.language_primary,
        language_secondary=request.language_secondary,
        websocket_url=request.websocket_url,
        phone_number=request.phone_number,
        sip_uri=request.sip_uri,
        cost_per_minute=request.cost_per_minute,
        routing_tier=request.routing_tier,
        avatar_url=request.avatar_url,
        voice_sample_url=request.voice_sample_url,
        cartesia_agent_id=request.cartesia_agent_id,
        llm_config=json.dumps(request.llm_config) if request.llm_config else None,
        voice_config=json.dumps(request.voice_config) if request.voice_config else None,
        flow_config=json.dumps(request.flow_config) if request.flow_config else None,
        is_active=True,
    )
    db.add(agent)
    await db.flush()

    return _agent_to_response(agent, {"total_calls": 0, "total_minutes": 0, "success_rate": 0.0})


@router.put("/{agent_id}", response_model=AgentDetailResponse)
async def update_agent(
    agent_id: str,
    request: UpdateAgentRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing agent."""
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if agent.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in ("llm_config", "voice_config", "flow_config") and value is not None:
            setattr(agent, field, json.dumps(value))
        else:
            setattr(agent, field, value)

    await db.flush()

    stats = await _get_agent_stats(db, agent_id)
    return _agent_to_response(agent, stats)


@router.delete("/{agent_id}", status_code=status.HTTP_200_OK)
async def delete_agent(
    agent_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete an agent (sets is_active to False)."""
    result = await db.execute(select(Agent).where(Agent.agent_id == agent_id))
    agent = result.scalars().first()

    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

    if agent.tenant_id != user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    agent.is_active = False
    await db.flush()

    return {"status": "deleted", "agent_id": agent_id}
