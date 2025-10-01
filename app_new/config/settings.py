from __future__ import annotations
import os
from typing import Dict, Any, Optional


class Settings:
    """Lightweight settings wrapper that reads from environment variables.

    This keeps a stable shape for the rest of the codebase without
    introducing a runtime dependency on pydantic/pydantic-settings for tests.
    """

    def __init__(self) -> None:
        self.ENV: str = os.getenv('FLASK_ENV', 'development')
        self.DEBUG: bool = os.getenv('FLASK_DEBUG', '1').lower() in ('1', 'true', 'yes')
        self.DATABASE_URL: Optional[str] = os.getenv('DATABASE_URL')
        self.SECRET_KEY: Optional[str] = os.getenv('SECRET_KEY')

    @staticmethod
    def from_env() -> 'Settings':
        return Settings()

    def as_dict(self) -> Dict[str, Any]:
        return {
            'ENV': self.ENV,
            'DEBUG': self.DEBUG,
            'DATABASE_URL': self.DATABASE_URL,
            'SECRET_KEY': self.SECRET_KEY,
        }


# Convenience singleton
settings = Settings()
