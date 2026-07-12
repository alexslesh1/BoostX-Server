"""Application settings, loaded from environment variables (.env in local dev)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- App ---
    APP_NAME: str = "BoostX Server"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = Field(default="local")  # local | production
    DEBUG: bool = Field(default=True)

    # --- Database ---
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://boostx:boostx@localhost:5432/boostx"
    )

    # --- JWT ---
    JWT_SECRET_KEY: str = Field(default="change-me-in-production")
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    REFRESH_TOKEN_EXPIRE_DAYS_REMEMBER_ME: int = Field(default=30)

    # --- Verification codes ---
    VERIFICATION_CODE_EXPIRE_MINUTES: int = Field(default=10)

    # --- Email / SMTP ---
    EMAIL_BACKEND: str = Field(default="console")  # smtp | console
    SMTP_HOST: str = Field(default="localhost")
    SMTP_PORT: int = Field(default=587)
    SMTP_USER: str = Field(default="")
    SMTP_PASSWORD: str = Field(default="")
    SMTP_FROM_EMAIL: str = Field(default="no-reply@boostx.app")
    SMTP_USE_TLS: bool = Field(default=True)

    # --- CORS ---
    CORS_ORIGINS: str = Field(default="*")

    # --- Devices ---
    MAX_DEVICES_PER_USER: int = Field(default=5)  # 0 = unlimited

    # --- Rate limiting ---
    RATE_LIMIT_STORAGE_URI: str = Field(default="")  # empty = in-memory

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
