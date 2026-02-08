from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime, timedelta
from jose import jwt
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from passlib.context import CryptContext

from app.config import settings
from app.database import get_db, User, Tenant
from app.auth.dependencies import get_current_user as get_current_user_dep

router = APIRouter()

# Password hashing setup
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ============= REQUEST/RESPONSE MODELS =============

class RegisterRequest(BaseModel):
    organization_name: str
    email: EmailStr
    password: str
    full_name: str
    phone_number: Optional[str] = None
    address: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict
    tenant: dict

# ============= HELPER FUNCTIONS =============

def create_access_token(user_id: str, tenant_id: str, role: str) -> str:
    """Create JWT access token"""
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# ============= ROUTES =============

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(request: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new tenant and admin user with PostgreSQL integration
    """
    
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == request.email))
    if result.scalars().first():
        throw_msg = "Email already registered"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=throw_msg
        )
    
    # Create tenant
    tenant_id = str(uuid.uuid4())
    subdomain = request.organization_name.lower().replace(" ", "-")[:20]
    
    new_tenant = Tenant(
        tenant_id=tenant_id,
        organization_name=request.organization_name,
        subdomain=subdomain,
        address=request.address,
        plan_tier="enterprise",
        is_active=True
    )
    db.add(new_tenant)
    
    # Create user
    user_id = str(uuid.uuid4())
    new_user = User(
        user_id=user_id,
        tenant_id=tenant_id,
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.full_name,
        phone_number=request.phone_number,
        role="admin"
    )
    db.add(new_user)
    
    # Flush to get objects in session (ID is already set manually)
    await db.flush()
    
    # Create access token
    access_token = create_access_token(user_id, tenant_id, "admin")
    
    return AuthResponse(
        access_token=access_token,
        user={
            "user_id": user_id,
            "email": request.email,
            "full_name": request.full_name,
            "role": "admin",
            "login_mode": "enterprise"  # New registrations default to enterprise
        },
        tenant={
            "tenant_id": tenant_id,
            "organization_name": request.organization_name,
            "subdomain": subdomain
        }
    )

@router.post("/login", response_model=AuthResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login existing user with PostgreSQL integration
    """
    
    # Find user
    result = await db.execute(select(User).where(User.email == request.email))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Verify password
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    # Get tenant
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == user.tenant_id))
    tenant = result.scalars().first()
    
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant account is inactive"
        )
    
    # Create access token
    access_token = create_access_token(
        user.user_id,
        user.tenant_id,
        user.role
    )
    
    return AuthResponse(
        access_token=access_token,
        user={
            "user_id": user.user_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "login_mode": user.login_mode.value  # Include login_mode from database
        },
        tenant={
            "tenant_id": tenant.tenant_id,
            "organization_name": tenant.organization_name,
            "subdomain": tenant.subdomain
        }
    )

@router.get("/me")
async def get_me(
    user: User = Depends(get_current_user_dep),
    db: AsyncSession = Depends(get_db),
):
    """Get current authenticated user info."""
    result = await db.execute(select(Tenant).where(Tenant.tenant_id == user.tenant_id))
    tenant = result.scalars().first()

    return {
        "user": {
            "user_id": user.user_id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "login_mode": user.login_mode.value,
        },
        "tenant": {
            "tenant_id": tenant.tenant_id,
            "organization_name": tenant.organization_name,
            "subdomain": tenant.subdomain,
        } if tenant else None,
    }
