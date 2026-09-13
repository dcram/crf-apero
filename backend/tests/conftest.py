import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import text

from alembic import command
from app.db import make_engine, make_sessionmaker

BACKEND_DIR = Path(__file__).resolve().parent.parent
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://crf:crf@localhost:5433/crf_test"
)


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
