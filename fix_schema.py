import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Try to find a working database URL
# The running app works, so the env var MUST be set there. 
# But we are in a separate shell. 
# We'll try common defaults for this system.
POSSIBLE_URLS = [
    os.getenv("DATABASE_URL"),
    "postgresql+asyncpg://amar@localhost:5432/davinciai",
    "postgresql+asyncpg://postgres@localhost:5432/davinciai",
    "postgresql+asyncpg://davinciai:password@localhost:5432/davinciai"
]

async def migrate():
    print("Starting schema migration...")
    
    success = False
    
    for db_url in POSSIBLE_URLS:
        if not db_url:
            continue
            
        print(f"Trying connection to: {db_url}")
        try:
            engine = create_async_engine(db_url)
            async with engine.begin() as conn:
                # Add columns
                statements = [
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS frustration_velocity VARCHAR",
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS agent_iq FLOAT",
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS avg_sentiment FLOAT",
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS correction_count INTEGER DEFAULT 0",
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS is_churn_risk BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS is_hot_lead BOOLEAN DEFAULT FALSE",
                    "ALTER TABLE call_logs ADD COLUMN IF NOT EXISTS priority_level VARCHAR DEFAULT 'NORMAL'",
                ]
                
                for stmt in statements:
                    await conn.execute(text(stmt))
                    print(f"  Executed: {stmt}")
                    
            print("Migration successful!")
            success = True
            break
            
        except Exception as e:
            print(f"  Connection failed or error: {e}")
            
    if not success:
        print("\nCould not automatically connect to the database.")
        print("Please run this script with your DATABASE_URL environment variable set.")
        print("Example: DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/dbname python3 fix_schema.py")

if __name__ == "__main__":
    asyncio.run(migrate())
