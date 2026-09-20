"""Environment-driven settings.

Every value has a default so the suite runs with no .env file at all.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    base_url: str = os.getenv("BASE_URL", "https://practicesoftwaretesting.com")
    api_base_url: str = os.getenv(
        "API_BASE_URL", "https://api.practicesoftwaretesting.com"
    )
    headless: bool = _flag("HEADLESS", True)
    slow_mo: int = int(os.getenv("SLOW_MO", "0"))
    mock_contact_api: bool = _flag("MOCK_CONTACT_API", True)

    @property
    def default_timeout(self) -> int:
        """Milliseconds. The demo backend is shared and occasionally slow."""
        return 15_000


settings = Settings()
