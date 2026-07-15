from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "dev-insecure-change-me-please-set-a-real-32B+-secret"


class Settings(BaseSettings):
    """Application settings. Override via PAPER_* env vars or a .env file.

    Defaults to SQLite for local dev; set PAPER_DATABASE_URL to a Postgres
    DSN in staging/prod (see HLD §5).
    """

    model_config = SettingsConfigDict(env_prefix="PAPER_", env_file=".env", extra="ignore")

    app_name: str = "Paper API"
    environment: str = "dev"  # dev | test | staging | prod
    database_url: str = "sqlite:///./paper_dev.db"
    # Dev convenience: create tables at startup. Prod sets this false and runs
    # `alembic upgrade head` instead (NFR-12).
    auto_create_tables: bool = True
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    # Users allowed to verify marketplace providers (their own registrations
    # are auto-verified). Set PAPER_PLATFORM_ADMIN_EMAILS='["ops@paper.in"]'.
    platform_admin_emails: list[str] = []


settings = Settings()
