import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from app.database import Base, User, Tenant, Agent
from passlib.context import CryptContext

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def create_test_data():
    engine = create_async_engine(DATABASE_URL)
    
    # Drop all tables to ensure clean schema (development only)
    async with engine.begin() as conn:
        print("Dropping existing tables...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Creating tables...")
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # 1. Ensure Tenant exists
        tenant_id = "065531ed-ac98-47d5-aed3-1e292c70bd6b"
        result = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
        tenant = result.scalars().first()
        
        if not tenant:
            tenant = Tenant(
                tenant_id=tenant_id,
                organization_name="Davinci AI Demo",
                subdomain="davinci-demo",
                plan_tier="enterprise"
            )
            session.add(tenant)
            print(f"Created Tenant: {tenant.organization_name}")
        
        # 2. Ensure User exists
        result = await session.execute(select(User).where(User.email == "admin@davinciai.eu"))
        user = result.scalars().first()
        
        if not user:
            user = User(
                user_id=str(uuid.uuid4()),
                tenant_id=tenant_id,
                email="admin@davinciai.eu",
                password_hash=pwd_context.hash("password123"),
                full_name="Admin User",
                role="admin"
            )
            session.add(user)
            print(f"Created User: {user.email}")
        else:
            user.password_hash = pwd_context.hash("password123")
            print(f"Updated User: {user.email} password")

        # 3. Create Test Agent
        agent_id = "agent-demo-001"
        result = await session.execute(select(Agent).where(Agent.agent_id == agent_id))
        agent = result.scalars().first()
        
        if not agent:
            agent = Agent(
                agent_id=agent_id,
                tenant_id=tenant_id,
                agent_name="TARA",
                agent_description="Enterprise-grade voice agent for Davinci AI",
                cartesia_agent_id="cartesia-demo-v1",
                language_primary="English",
                language_secondary="Telugu",
                websocket_url="wss://demo.davinciai.eu:8443/ws",
                location="Hyderabad, India",
                configuration='{"voice": "sonic-3", "model": "gpt-4o"}',
                is_active=True,
                created_at=datetime.utcnow() - timedelta(days=5) # 5 days uptime
            )
            session.add(agent)
            print(f"Created Agent: {agent.agent_name}")
        else:
            # Update existing agent with new fields
            agent.language_primary = "English"
            agent.language_secondary = "Telugu"
            agent.websocket_url = "wss://demo.davinciai.eu:8445/client"
            agent.created_at = datetime.utcnow() - timedelta(days=5) # Ensure uptime is reflected
            agent.location = "Hyderabad, India" # Ensure location is updated
            print(f"Updated Agent: {agent.agent_name} with new fields")

        await session.commit()
        print("Test data population complete.")

if __name__ == "__main__":
    asyncio.run(create_test_data())
