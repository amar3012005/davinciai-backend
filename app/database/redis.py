from redis.asyncio import Redis, from_url
from app.config import settings
from loguru import logger

# Singleton instance
_redis_instance = None

async def get_redis() -> Redis:
    """Get or create the global Redis pool"""
    global _redis_instance
    if _redis_instance is None:
        logger.info(f"Connecting to Redis at {settings.REDIS_URL}")
        _redis_instance = from_url(
            settings.REDIS_URL, 
            encoding="utf-8", 
            decode_responses=True
        )
    return _redis_instance

async def close_redis():
    """Close the global Redis pool"""
    global _redis_instance
    if _redis_instance:
        await _redis_instance.close()
        _redis_instance = None
