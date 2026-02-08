
import asyncio
import uuid
import json
from datetime import datetime
from app.database import Base, engine, get_db, Tenant, User, Agent, Wallet, CallLog, LoginMode
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.router import pwd_context # Assuming pwd_context is available for hashing

async def seed_data():
    async with AsyncSession(engine) as session:
        # 1. Create Tenant
        tenant_id = "065531ed-ac98-47d5-aed3-1e292c70bd6b" # From the error log
        tenant = Tenant(
            tenant_id=tenant_id,
            organization_name="Davinci AI",
            subdomain="demo",
            plan_tier="enterprise"
        )
        session.add(tenant)
        
        # 2. Create Wallet
        wallet = Wallet(
            tenant_id=tenant_id,
            balance=500.0,
            currency="EUR",
            is_auto_recharge_enabled=True,
            auto_recharge_amount=100.0
        )
        session.add(wallet)
        await session.flush() # Get wallet_id
        
        # 3. Create User
        user = User(
            email="admin@davinciai.eu",
            full_name="Admin User",
            password_hash=pwd_context.hash("password123"),
            tenant_id=tenant_id,
            role="admin",
            login_mode=LoginMode.ENTERPRISE
        )
        session.add(user)
        
        # 4. Create Agent
        agent = Agent(
            agent_id="agent-demo-001",
            tenant_id=tenant_id,
            wallet_id=wallet.wallet_id,
            agent_name="TARA",
            agent_description="Enterprise-grade voice agent for Davinci AI",
            location="Hyderabad, India",
            avatar_url="https://api.dicebear.com/7.x/bottts/svg?seed=Tara",
            language_primary="de",
            language_secondary="en",
            websocket_url="wss://demo.davinciai.eu:8443/ws",
            cost_per_minute=0.15,
            routing_tier="premium",
            llm_config=json.dumps({"model": "gpt-4o", "temperature": 0.7}),
            voice_config=json.dumps({"voice_id": "sonic-3", "provider": "cartesia"}),
            flow_config=json.dumps({
                "intro_in_primary_lang": "Guten Tag! Ich bin Tara von Davinci AI. Wie kann ich Ihnen heute helfen?",
                "intro_in_secondary_lang": "Hello! I am Tara from Davinci AI. How can I assist you today?",
                "stt_mode": "audio",
                "tts_mode": "audio"
            }),
            is_active=True
        )
        session.add(agent)
        
        await session.commit()
        print("Data seeded successfully.")

if __name__ == "__main__":
    asyncio.run(seed_data())
