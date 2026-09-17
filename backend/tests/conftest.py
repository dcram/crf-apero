import datetime as dt
import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.config import Settings
from app.db import make_engine, make_sessionmaker
from app.main import create_app

BACKEND_DIR = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://crf:crf@localhost:5433/crf_test"
)
TODAY = dt.date(2026, 9, 13)
CLIENT_IP = "203.0.113.7"


def make_settings(**overrides) -> Settings:
    values = dict(
        database_url=TEST_DATABASE_URL,
        turnstile_site_key="1x00000000000000000000AA",
        turnstile_secret="test-secret",
        organizer_emails="orga1@example.org,orga2@example.org",
        mail_reply_to="orgas@example.org",
        contact_email="contact@example.org",
        event_info="Mardi 20h30 – Sainte-Élisabeth",
        apero_start_time="21:30",
        mail_backend="console",
        sessions_file=FIXTURES / "sessions.yaml",
    )
    values.update(overrides)
    return Settings(**values)


class FakeVerifier:
    def __init__(self) -> None:
        self.result = True
        self.error: Exception | None = None
        self.calls: list[tuple[str, str | None]] = []

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        self.calls.append((token, remote_ip))
        if self.error:
            raise self.error
        return self.result


class FakeMailer:
    def __init__(self) -> None:
        self.sent = []
        self.error: Exception | None = None

    def send(self, email) -> None:
        if self.error:
            raise self.error
        self.sent.append(email)


@asynccontextmanager
async def open_client(app):
    transport = httpx.ASGITransport(app=app, client=(CLIENT_IP, 50000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(scope="session")
def migrated_db() -> str:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["database_url"] = TEST_DATABASE_URL
    cfg.attributes["configure_logger"] = False
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    return TEST_DATABASE_URL


@pytest.fixture
async def engine(migrated_db):
    eng = make_engine(migrated_db)
    async with eng.begin() as conn:
        await conn.execute(text("TRUNCATE bookings RESTART IDENTITY"))
    yield eng
    await eng.dispose()


@pytest.fixture
def sessionmaker(engine):
    return make_sessionmaker(engine)


@pytest.fixture
def fake_verifier() -> FakeVerifier:
    return FakeVerifier()


@pytest.fixture
def fake_mailer() -> FakeMailer:
    return FakeMailer()


@pytest.fixture
def build_app(engine, fake_verifier, fake_mailer):
    def _build(today: dt.date = TODAY, **overrides):
        return create_app(
            make_settings(**overrides),
            verifier=fake_verifier,
            mailer=fake_mailer,
            today=lambda: today,
            engine=engine,
        )

    return _build


@pytest.fixture
async def client(build_app):
    async with open_client(build_app()) as c:
        yield c
