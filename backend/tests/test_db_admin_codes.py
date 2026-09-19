import datetime as dt

from app.db import consume_code, fetch_code, register_failed_attempt, replace_code

EMAIL = "admin@example.org"
NOW = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
LATER = NOW + dt.timedelta(minutes=10)


async def test_replace_code_stores_one_row(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None
        assert code.code_hash == "h1"
        assert code.attempts == 0


async def test_new_code_invalidates_the_previous_one(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h2", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None and code.code_hash == "h2"


async def test_replace_code_purges_expired_rows_of_other_emails(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(
            session,
            email="vieux@example.org",
            code_hash="h0",
            expires_at=NOW - dt.timedelta(minutes=1),
            now=NOW,
        )
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        assert await fetch_code(session, "vieux@example.org") is None


async def test_failed_attempts_delete_the_code_at_the_limit(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    for expected in (1, 2):
        async with sessionmaker() as session:
            code = await fetch_code(session, EMAIL)
            assert code is not None
            await register_failed_attempt(session, code, max_attempts=3)
        async with sessionmaker() as session:
            code = await fetch_code(session, EMAIL)
            assert code is not None and code.attempts == expected
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None
        await register_failed_attempt(session, code, max_attempts=3)
    async with sessionmaker() as session:
        assert await fetch_code(session, EMAIL) is None


async def test_consume_code_removes_it(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None
        await consume_code(session, code)
    async with sessionmaker() as session:
        assert await fetch_code(session, EMAIL) is None
