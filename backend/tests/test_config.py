import pytest
from pydantic import ValidationError

from app.config import Settings

BASE = dict(
    database_url="postgresql+asyncpg://u:p@h/db",
    turnstile_site_key="site",
    turnstile_secret="secret",
    mail_reply_to="orgas@example.org",
    contact_email="contact@example.org",
    admin_emails="admin@example.org",
    admin_secret="s",
)

BASE_WITHOUT_ADMIN = {k: v for k, v in BASE.items() if k not in ("admin_emails", "admin_secret")}


def test_reads_comma_separated_emails_from_env(monkeypatch):
    for key, value in BASE.items():
        monkeypatch.setenv(key.upper(), value)
    monkeypatch.setenv("ORGANIZER_EMAILS", " a@example.org, b@example.org ,")
    settings = Settings()
    assert settings.organizer_emails == ["a@example.org", "b@example.org"]
    assert settings.mail_from == "crf@fsspnantes.fr"
    assert settings.mail_backend == "console"


def test_rejects_empty_recipients():
    with pytest.raises(ValidationError):
        Settings(**BASE, organizer_emails="")


@pytest.mark.parametrize("value", ["9:30", "24:00", "21h30"])
def test_rejects_bad_apero_time(value):
    with pytest.raises(ValidationError):
        Settings(**BASE, organizer_emails="a@example.org", apero_start_time=value)


def test_rejects_unknown_timezone():
    with pytest.raises(ValidationError):
        Settings(**BASE, organizer_emails="a@example.org", timezone="Mars/Olympus")


def test_admin_settings_defaults():
    settings = Settings(
        **BASE_WITHOUT_ADMIN,
        organizer_emails="a@example.org",
        admin_emails=" admin@example.org , ",
        admin_secret="s",
    )
    assert settings.admin_emails == ["admin@example.org"]
    assert settings.admin_session_days == 30
    assert settings.admin_code_ttl_minutes == 10
    assert settings.admin_code_max_attempts == 5
    assert settings.admin_codes_per_hour == 3
    assert settings.admin_cookie_secure is True


def test_rejects_empty_admin_emails():
    with pytest.raises(ValidationError):
        Settings(
            **BASE_WITHOUT_ADMIN,
            organizer_emails="a@example.org",
            admin_emails="",
            admin_secret="s",
        )


def test_admin_secret_is_required():
    with pytest.raises(ValidationError):
        Settings(
            **BASE_WITHOUT_ADMIN,
            organizer_emails="a@example.org",
            admin_emails="admin@example.org",
        )
