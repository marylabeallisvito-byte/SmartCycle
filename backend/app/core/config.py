"""
SmartCycle — Centralized Configuration
Loads from environment variables with sensible defaults.
Uses pydantic-settings when available, otherwise plain os.getenv.
"""

import os
from pathlib import Path


# ═══════════════════════════════════════════════════════════════
# .env loader — loads backend/.env into os.environ
# ═══════════════════════════════════════════════════════════════

def _load_dotenv() -> None:
    """Load .env file from backend/ or project root."""
    current = Path(__file__).resolve().parent.parent.parent  # backend/
    for candidate in [current / ".env", current.parent / ".env"]:
        if candidate.is_file():
            with open(candidate, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, _, value = line.partition("=")
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            return


_load_dotenv()


# ═══════════════════════════════════════════════════════════════
# Settings class — works with or without pydantic-settings
# ═══════════════════════════════════════════════════════════════

class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.APP_NAME: str = os.getenv("APP_NAME", "SmartCycle")
        self.APP_VERSION: str = os.getenv("APP_VERSION", "0.3.0")
        self.ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
        self.LOG_LEVEL: str = os.getenv("LOG_LEVEL", "DEBUG")

        # CORS
        self.CORS_ORIGINS: list = ["http://localhost:3000"]

        # Database
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://smartcycle:smartcycle@localhost:5432/smartcycle",
        )

        # ChromaDB
        self.CHROMA_HOST: str = os.getenv("CHROMA_HOST", "localhost")
        self.CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8001"))

        # Redis
        self.REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        # LLM
        self.LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
        self.LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
        self.LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
        self.LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
        self.LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2048"))
        self.LLM_TIMEOUT: float = float(os.getenv("LLM_TIMEOUT", "45.0"))
        self.EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "BAAI/bge-large-zh-v1.5")

        # Auth
        self.JWT_SECRET: str = os.getenv("JWT_SECRET", "change-me-in-production-use-a-long-random-string")
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_EXPIRE_MINUTES: int = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

        # Demo User
        self.DEMO_USERNAME: str = os.getenv("DEMO_USERNAME", "admin")
        self.DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "smartcycle2024")


settings = Settings()
