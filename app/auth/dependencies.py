"""
JWT Authentication Dependencies
Provides get_current_user and get_current_tenant for route protection.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.config import settings
from app.database import get_db, User, Tenant

security = HTTPBearer()


class TokenPayload:
    """Parsed JWT token payload."""
    def __init__(self, user_id: str, tenant_id: str, role: str):
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.role = role


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        user_id = payload.get("sub")
        tenant_id = payload.get("tenant_id")
        role = payload.get("role")

        if not user_id or not tenant_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        return TokenPayload(user_id=user_id, tenant_id=tenant_id, role=role)

    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate the current user from the JWT token."""
    token_data = decode_token(credentials.credentials)

    result = await db.execute(
        select(User).where(User.user_id == token_data.user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Extract and validate the current tenant from the JWT token."""
    token_data = decode_token(credentials.credentials)

    result = await db.execute(
        select(Tenant).where(Tenant.tenant_id == token_data.tenant_id)
    )
    tenant = result.scalars().first()

    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not found or inactive",
        )

    return tenant


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> TokenPayload:
    """Lightweight token validation without DB lookup."""
    return decode_token(credentials.credentials)


async def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """Require the current user to have admin role."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
