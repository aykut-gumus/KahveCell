from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    jwt_secret_key: str = Field(min_length=32)
    bootstrap_admin_phone: str | None = None
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    otp_expiration_minutes: int = 5

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
