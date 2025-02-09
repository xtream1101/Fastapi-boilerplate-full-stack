from typing import List, Literal, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application Settings
    VERSION: str = "0.1.0"
    ENV: Literal["dev", "staging", "prod"] = "dev"
    HOST: str = "http://localhost:8000"
    CORS_ORIGINS: List[str] = [
        "http://localhost:8000",
        "http://localhost:8080",
    ]

    # Database Settings
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: str = "postgres"
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_NAME: str = "postgres"

    # Authentication Settings
    SECRET_KEY: str = "SECRET"  # Should be overridden in production
    VALIDATION_LINK_EXPIRATION: int = 60 * 60  # (sec) 1 hour
    PASSWORD_RESET_LINK_EXPIRATION: int = 60 * 60  # (sec) 1 hour

    # Cookie Settings
    COOKIE_NAME: str = "fastapi-boilerplate"
    COOKIE_MAX_AGE: int = 60 * 60 * 24 * 30  # (sec) 30 days

    # Email Settings
    SMTP_HOST: Optional[str] = "example.com"
    SMTP_PORT: Optional[int] = 587
    SMTP_USER: Optional[str] = "foobar@example.com"
    SMTP_PASSWORD: Optional[str] = "password"
    SMTP_STARTTLS: bool = False
    SMTP_SSL: bool = False
    SMTP_FROM: Optional[str] = "foobar@example.com"
    SMTP_FROM_NAME: Optional[str] = "Example"
    # Enables debug output for email
    SMTP_DEBUG: bool = False
    # Disables sending of emails and prints locally in terminal for local dev
    SMTP_LOCAL_DEV: bool = False

    # Supported SSO Services
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None
    GITHUB_AUTO_VERIFY_EMAIL: bool = True

    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_AUTO_VERIFY_EMAIL: bool = True

    # Callback for custom provider will be /auth/{GENERIC_OIDC_NAME}/callback
    GENERIC_OIDC_DISCOVERY_URL: Optional[str] = None
    GENERIC_OIDC_NAME: Optional[str] = None
    GENERIC_OIDC_CLIENT_ID: Optional[str] = None
    GENERIC_OIDC_CLIENT_SECRET: Optional[str] = None
    GENERIC_OIDC_ALLOW_INSECURE_HTTP: bool = False
    GENERIC_OIDC_AUTO_VERIFY_EMAIL: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

    @property
    def is_prod(self) -> bool:
        return self.ENV == "prod"

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"


# Create settings instance
settings = Settings()
