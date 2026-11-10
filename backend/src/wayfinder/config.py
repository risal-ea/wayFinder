"""Application settings, read from environment variables or `.env`."""

from functools import lru_cache

import httpx
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wayfinder import __version__


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Wikimedia requires a way to contact the operator in the User-Agent.
    wikivoyage_contact: str
    app_url: str = "https://github.com/risal-ea/wayFinder"
    wikivoyage_lang: str = "en"
    wikivoyage_min_interval: float = 0.2
    http_timeout: float = 30.0

    # Later phases.
    redis_url: str = "redis://localhost:6379/0"

    @field_validator("wikivoyage_contact")
    @classmethod
    def _contact_is_reachable(cls, value: str) -> str:
        value = value.strip()
        if "@" not in value and not value.startswith(("http://", "https://")):
            raise ValueError(
                "WIKIVOYAGE_CONTACT must be an email address or URL "
                "(Wikimedia requires contact info in the User-Agent)"
            )
        return value

    @property
    def user_agent(self) -> str:
        return build_user_agent(self.app_url, self.wikivoyage_contact)


def build_user_agent(app_url: str, contact: str) -> str:
    """Wikimedia format: `<client>/<version> (<contact>) <library>/<version>`."""
    contact_part = app_url if contact == app_url else f"{app_url}; {contact}"
    return f"WayFinder/{__version__} ({contact_part}) httpx/{httpx.__version__}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
