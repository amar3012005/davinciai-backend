
import asyncio
import json
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import engine
from app.database.models import Tenant, Agent, Wallet, CallLog, User, LoginMode
from sqlalchemy.future import select

async def seed_agent():
    async with AsyncSession(engine) as session:
        # 1. Target Data from Logs
        tenant_id = "5fc3fa72-d15d-48dc-812c-5c845b5172eb"
        agent_id = "davinci-demo-agent-001"
        agent_name = "demo"
        
        print(f"Checking for tenant: {tenant_id}")
        
        # 2. Ensure Tenant exists
        result = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
        tenant = result.scalars().first()
        if not tenant:
            tenant = Tenant(
                tenant_id=tenant_id,
                organization_name="Enterprise Demo Org",
                subdomain="enterprise-demo",
                plan_tier="enterprise",
                is_active=True
            )
            session.add(tenant)
            print(f"Created Tenant: {tenant_id}")
        else:
            print(f"Tenant already exists: {tenant_id}")

        # 3. Ensure Wallet exists for this tenant
        result = await session.execute(select(Wallet).where(Wallet.tenant_id == tenant_id))
        wallet = result.scalars().first()
        if not wallet:
            wallet = Wallet(
                wallet_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                balance=1000.00,
                currency="EUR",
                is_auto_recharge_enabled=True,
                auto_recharge_amount=200.00
            )
            session.add(wallet)
            await session.flush()
            print(f"Created Wallet: {wallet.wallet_id}")
        else:
            print(f"Wallet already exists: {wallet.wallet_id}")

        # 4. Ensure Agent exists
        result = await session.execute(select(Agent).where(Agent.agent_id == agent_id))
        agent = result.scalars().first()
        
        agent_data = {
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "wallet_id": wallet.wallet_id,
            "agent_name": agent_name,
            "agent_description": "Advanced Enterprise Voice Agent - Demo Mode",
            "avatar_url": "https://api.dicebear.com/7.x/bottts/svg?seed=demo-agent",
            "voice_sample_url": "https://storage.googleapis.com/davinci-samples/demo-voice.mp3",
            "location": "Frankfurt, DE (EU-West)",
            "websocket_url": "wss://api.enterprise.davinciai.eu:8450/ws/v1/demo",
            "phone_number": "+49-123-456789",
            "language_primary": "English",
            "language_secondary": "German",
            "llm_config": json.dumps({
                "model": "gpt-4o",
                "temperature": 0.5,
                "system_prompt": "You are a professional enterprise assistant named Demo Agent."
            }),
            "voice_config": json.dumps({
                "provider": "cartesia",
                "voice_id": "sonic-3-en",
                "speed": "normal"
            }),
            "flow_config": json.dumps({
                "first_sentence": "Welcome to Davinci Enterprise. How can I help you today?",
                "timeout_ms": 10000
            }),
            "cost_per_minute": 0.25,
            "routing_tier": "dedicated",
            "is_active": True,
            "created_at": datetime.now(timezone.utc)
        }

        if not agent:
            agent = Agent(**agent_data)
            session.add(agent)
            print(f"Created Agent: {agent_name} ({agent_id})")
        else:
            for key, value in agent_data.items():
                setattr(agent, key, value)
            print(f"Updated Agent: {agent_name} ({agent_id})")

        await session.commit()
        print("\n" + "="*50)
        print("SEEDING COMPLETE")
        print("="*50)
        print(f"AGENT_ID: {agent_id}")
        print(f"AGENT_NAME: {agent_name}")
        print(f"TENANT_ID: {tenant_id}")
        print("="*50)

if __name__ == "__main__":
    asyncio.run(seed_agent())
