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

    # --- Boost Discord (per-user SOCKS5 proxy relay) ---
    # Public address of the 3proxy relay the desktop client connects to.
    PROXY_HOST: str = Field(default="194.87.200.215")
    PROXY_PORT: int = Field(default=1080)
    # Fernet key (44-char urlsafe-base64) used to encrypt proxy passwords at
    # rest. Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    PROXY_CREDENTIALS_ENCRYPTION_KEY: str = Field(default="change-me-generate-a-real-fernet-key")
    # Path to 3proxy's `users` auth file (format: `login:CL:password` per line).
    # Only used when the app server and the 3proxy relay run on the same host.
    PROXY_3PROXY_USERS_FILE: str = Field(default="/usr/local/etc/3proxy/conf/users")
    # Shell command run (via subprocess) after rewriting the users file so
    # 3proxy picks up the new credential list. Must be executable by the
    # app server's OS user (e.g. a scoped sudoers rule for this one command).
    PROXY_3PROXY_RELOAD_COMMAND: str = Field(default="systemctl reload 3proxy")
    # If false, credential provisioning still writes to the DB but skips
    # touching the 3proxy users file / reload — useful for local dev or a
    # deployment where the app server and relay are on different hosts.
    PROXY_SYNC_3PROXY_FILE: bool = Field(default=True)

    @property
    def cors_origins_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
