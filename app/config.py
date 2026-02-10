"""Configuration management for DaVinci AI Backend"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://davinciai_user:3012005%40Amarsai@kw8c88c8o0kcg8wg8kw8gwk4:5432/postgres"
    REDIS_URL: str = "redis://davinci_user:3012005%40Amarsai@rgw004os4ggwokkg88c4g04w:6379/0"
    
    # Cartesia
    CARTESIA_API_KEY: str = ""
    
    # Security
    JWT_SECRET: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Frontend
    FRONTEND_URL: str = "https://enterprise.davinciai.eu"
    ALLOWED_ORIGINS: str = "https://enterprise.davinciai.eu,https://demo.davinciai.eu,http://localhost:3000"
    
    @property
    def allowed_origins_list(self) -> list[str]:
        """Parse ALLOWED_ORIGINS string into a list"""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
