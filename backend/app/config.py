import re
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from app.sessions import DEFAULT_SESSIONS_FILE


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    database_url: str
    turnstile_site_key: str
    turnstile_secret: str
    organizer_emails: Annotated[list[str], NoDecode]
    mail_from: str = "crf@fsspnantes.fr"
    mail_reply_to: str
    contact_email: str
    event_info: str = ""
    event_address: str = ""
    event_map_url: str = ""
    apero_start_time: str = "21:30"
    aws_region: str = "eu-west-3"
    mail_backend: Literal["ses", "console"] = "console"
    timezone: str = "Europe/Paris"
    sessions_file: Path = DEFAULT_SESSIONS_FILE
    static_dir: Path | None = None
    rate_limit_per_hour: int = 5
    admin_emails: Annotated[list[str], NoDecode]
    admin_secret: str
    admin_session_days: int = 30
    admin_code_ttl_minutes: int = 10
    admin_code_max_attempts: int = 5
    admin_codes_per_hour: int = 3
    admin_cookie_secure: bool = True

    @field_validator("organizer_emails", "admin_emails", mode="before")
    @classmethod
    def _split_emails(cls, value: object) -> list[str]:
        items = value.split(",") if isinstance(value, str) else list(value)  # type: ignore[arg-type]
        emails = [item.strip() for item in items if item.strip()]
        if not emails:
            raise ValueError("au moins un destinataire est requis")
        return emails

    @field_validator("apero_start_time")
    @classmethod
    def _check_time(cls, value: str) -> str:
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", value):
            raise ValueError("format HH:MM attendu")
        return value

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"fuseau inconnu : {value}") from exc
        return value
