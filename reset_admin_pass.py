import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select
import os
from dotenv import load_dotenv
from app.database import Base, User
from passlib.context import CryptContext

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

async def reset_password():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        result = await session.execute(select(User).where(User.email == "admin@davinciai.eu"))
        user = result.scalars().first()
        
        if user:
            print(f"Found user: {user.email}")
            new_hash = pwd_context.hash("password123")
            user.password_hash = new_hash
            await session.commit()
            print("Password updated to 'password123'")
        else:
            print("User admin@davinciai.eu not found")

if __name__ == "__main__":
    asyncio.run(reset_password())
