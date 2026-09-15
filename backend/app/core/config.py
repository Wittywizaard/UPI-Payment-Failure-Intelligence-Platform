from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration, loaded from environment variables (see .env.example).
    No secrets are hardcoded; everything here has a safe local-dev default only
    where that default carries no real risk (e.g. CORS origin, algorithm name).
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "local"
    DATABASE_URL: str = "postgresql+psycopg2://upi_fip:upi_fip@localhost:5432/upi_fip"

    JWT_SECRET: str = "dev-only-secret-override-in-env"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_MINUTES: int = 480

    CORS_ORIGINS: str = "http://localhost:3000"

    ANTHROPIC_API_KEY: str = ""
    AI_MODEL: str = "claude-sonnet-4-6"
    AI_RATE_LIMIT_PER_MINUTE: int = 10

    SYNTHETIC_SEED: int = 42
    SYNTHETIC_TRANSACTION_COUNT: int = 750_000

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
