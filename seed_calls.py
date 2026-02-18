
import asyncio
import uuid
import random
import os
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.future import select
from dotenv import load_dotenv

# Import models
from app.database import Base, CallLog, Agent

from app.config import settings

# Ensure async driver is used
DATABASE_URL = settings.DATABASE_URL
if "postgresql://" in DATABASE_URL and "+asyncpg" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

async def seed_calls():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the main demo agent
        result = await session.execute(select(Agent).limit(1))
        agent = result.scalars().first()
        
        if not agent:
            print("No agent found! Run seed_agent.py first.")
            return

        print(f"Seeding calls for agent: {agent.agent_name} ({agent.agent_id})")
        
        statuses = ["completed", "completed", "completed", "failed", "interrupted"]
        priorities = ["NORMAL", "NORMAL", "HIGH", "URGENT", "LOW"]
        
        new_calls = []
        
        # Generate 50 diverse calls
        for i in range(50):
            days_ago = random.randint(0, 10)
            seconds_ago = random.randint(0, 86000)
            
            # Use UTC explicit
            start_time = datetime.now(timezone.utc) - timedelta(days=days_ago, seconds=seconds_ago)
            duration = random.randint(30, 900)
            end_time = start_time + timedelta(seconds=duration)
            
            sentiment = random.random()
            if random.random() > 0.3:
                sentiment = 0.6 + (random.random() * 0.4)
            else:
                sentiment = random.random() * 0.6
                
            status = random.choice(statuses)
            is_churn = sentiment < 0.3 and random.random() > 0.7
            is_hot = sentiment > 0.8 and random.random() > 0.7
            
            call = CallLog(
                id=str(uuid.uuid4()),
                agent_id=agent.agent_id,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=duration,
                status=status,
                caller_id=f"+{random.randint(1000000000, 9999999999)}",
                ttft_ms=random.randint(200, 1500),
                sentiment_score=sentiment,
                avg_sentiment=sentiment,
                agent_iq=0.8 + (random.random() * 0.2),
                frustration_velocity="STABLE" if sentiment > 0.5 else "RISING",
                correction_count=random.randint(0, 5),
                is_churn_risk=is_churn,
                is_hot_lead=is_hot,
                priority_level=random.choice(priorities),
                cost_euros=round((duration / 60) * float(agent.cost_per_minute), 2)
            )
            new_calls.append(call)
            
        session.add_all(new_calls)
        await session.commit()
        print(f"Successfully seeded {len(new_calls)} diverse calls.")

if __name__ == "__main__":
    asyncio.run(seed_calls())
