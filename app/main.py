"""
DaVinci AI Backend - FastAPI Application
Multi-tenant voice agent monitoring platform
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
import sys
import time

# Configure loguru
logger.remove()
logger.add(
    sys.stdout,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
)

from app.config import settings

# Import routers
from app.auth.router import router as auth_router
from app.tenants.router import router as tenants_router
from app.agents.router import router as agents_router
from app.metrics.router import router as metrics_router
from app.wallet.router import router as wallet_router
from app.webhooks.cartesia import router as webhooks_router
from app.webhooks.session import router as session_webhook_router

# Include database setup
from app.database import Base, engine

# Create FastAPI app
app = FastAPI(
    title="DaVinci AI Backend",
    description="Multi-tenant voice agent monitoring and billing platform",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
)


# ============= LIFECYCLE =============

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")
    logger.info(f"Environment: {settings.ENVIRONMENT}")


# ============= MIDDLEWARE =============

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    expose_headers=["X-Request-ID"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = round((time.time() - start_time) * 1000, 2)

    if request.url.path not in ("/health", "/"):
        logger.info(
            f"{request.method} {request.url.path} -> {response.status_code} ({duration}ms)"
        )

    return response


# ============= EXCEPTION HANDLERS =============

@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={"detail": "Resource not found"},
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    logger.error(f"Internal error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ============= ROUTERS =============

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(tenants_router, prefix="/api/tenants", tags=["Tenants"])
app.include_router(agents_router, prefix="/api/agents", tags=["Agents"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(wallet_router, prefix="/api/wallet", tags=["Wallet & Billing"])
app.include_router(webhooks_router, prefix="/api/webhooks", tags=["Webhooks"])
app.include_router(session_webhook_router, prefix="/api/webhooks", tags=["Session Webhooks"])


# ============= HEALTH & ROOT =============

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "davinciai-backend",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }


@app.get("/")
async def root():
    return {
        "message": "DaVinci AI Backend API",
        "version": "1.0.0",
        "docs": "/api/docs" if settings.DEBUG else None,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
