"""Configuration management using Pydantic BaseSettings"""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Database
    database_url: str = "sqlite:///./chats.db"

    # JWT
    secret_key: str = "your-super-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_hours: int = 24
    refresh_token_expire_days: int = 7

    # API Keys
    groq_api_key: str = ""
    sentry_dsn: str = ""

    # CORS
    frontend_url: str = "http://localhost:3000"

    # Environment
    environment: str = "development"  # development, staging, production
    debug: bool = False

    # File Upload
    max_file_size_mb: int = 10  # 10MB limit

    # Logging
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == "production"

    def validate_secrets(self) -> None:
        """Validate that required secrets are set"""
        if self.is_production:
            if not self.secret_key or self.secret_key == "your-super-secret-key-change-in-production":
                raise ValueError("SECRET_KEY must be set in production")
            if not self.groq_api_key:
                raise ValueError("GROQ_API_KEY must be set in production")
            if not self.sentry_dsn:
                raise ValueError("SENTRY_DSN should be set in production")


# Load settings from environment
settings = Settings()

# Validate on startup if production
if settings.is_production:
    settings.validate_secrets()
