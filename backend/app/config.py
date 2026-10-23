from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./school_demo.db"
    DATABASE_SSL_REQUIRED: bool = False
    DATABASE_SSL_CA: str | None = None
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    BOOTSTRAP_ADMIN_EMAIL: str | None = None
    BOOTSTRAP_ADMIN_PASSWORD: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "store@example.test"
    SMTP_USE_TLS: bool = True
    ADMIN_NOTIFICATION_EMAIL: str | None = None

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, value: str) -> str:
        if len(value) < 32 or value.lower().startswith(
            ("replace-", "generate-", "change-me", "school-demo")
        ):
            raise ValueError("SECRET_KEY must be a unique secret of at least 32 characters.")
        return value

    @model_validator(mode="after")
    def validate_admin_bootstrap(self):
        if bool(self.BOOTSTRAP_ADMIN_EMAIL) != bool(self.BOOTSTRAP_ADMIN_PASSWORD):
            raise ValueError("Set both BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD.")
        if self.BOOTSTRAP_ADMIN_PASSWORD and len(self.BOOTSTRAP_ADMIN_PASSWORD) < 16:
            raise ValueError("BOOTSTRAP_ADMIN_PASSWORD must be at least 16 characters.")
        if self.BOOTSTRAP_ADMIN_PASSWORD and self.BOOTSTRAP_ADMIN_PASSWORD.lower().startswith(
            ("replace-", "generate-", "change-me", "admin123")
        ):
            raise ValueError("Replace the bootstrap admin password placeholder before startup.")
        return self

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        extra="ignore",
        validate_default=True,
    )


settings = Settings()
