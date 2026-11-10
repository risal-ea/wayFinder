import pytest
from pydantic import ValidationError

from wayfinder.config import Settings


def test_contact_is_required(monkeypatch):
    monkeypatch.delenv("WIKIVOYAGE_CONTACT", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_contact_must_be_email_or_url():
    with pytest.raises(ValidationError, match="email address or URL"):
        Settings(_env_file=None, wikivoyage_contact="risal")


def test_user_agent_follows_wikimedia_format():
    settings = Settings(_env_file=None, wikivoyage_contact="dev@example.com", app_url="https://example.com/wf")
    assert settings.user_agent.startswith("WayFinder/0.1.0 (https://example.com/wf; dev@example.com) httpx/")
