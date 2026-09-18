import datetime as dt

from app.admin import COOKIE_NAME
from app.db import fetch_code
from tests.conftest import open_client

ADMIN = "admin1@example.org"
NOW = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)


def code_from(mailer) -> str:
    return mailer.sent[-1].subject.split(": ")[-1]


async def login(client, fake_mailer, email: str = ADMIN) -> str:
    assert (await client.post("/api/admin/login", json={"email": email})).status_code == 204
    code = code_from(fake_mailer)
    response = await client.post("/api/admin/session", json={"email": email, "code": code})
    assert response.status_code == 204
    return code


async def test_login_sends_a_six_digit_code(client, fake_mailer):
    response = await client.post("/api/admin/login", json={"email": ADMIN})
    assert response.status_code == 204
    [email] = fake_mailer.sent
    assert email.recipients == [ADMIN]
    assert code_from(fake_mailer).isdigit()


async def test_unknown_email_answers_204_without_sending(client, fake_mailer):
    response = await client.post("/api/admin/login", json={"email": "pirate@example.org"})
    assert response.status_code == 204
    assert fake_mailer.sent == []


async def test_organizer_who_is_not_admin_gets_nothing(client, fake_mailer):
    response = await client.post("/api/admin/login", json={"email": "orga1@example.org"})
    assert response.status_code == 204
    assert fake_mailer.sent == []


async def test_email_is_matched_case_insensitively(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": "  ADMIN1@Example.ORG "})
    [email] = fake_mailer.sent
    assert email.recipients == [ADMIN]


async def test_valid_code_sets_the_cookie(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": ADMIN})
    code = code_from(fake_mailer)
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": code})
    assert response.status_code == 204
    cookie_header = response.headers.get("set-cookie", "").lower()
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "path=/" in cookie_header
    assert client.cookies.get(COOKIE_NAME)


async def test_wrong_code_is_403(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": ADMIN})
    wrong = "000000" if code_from(fake_mailer) != "000000" else "111111"
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": wrong})
    assert response.status_code == 403
    assert client.cookies.get(COOKIE_NAME) is None


async def test_fifth_attempt_destroys_the_code(client, fake_mailer, sessionmaker):
    await client.post("/api/admin/login", json={"email": ADMIN})
    good = code_from(fake_mailer)
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(5):
        response = await client.post("/api/admin/session", json={"email": ADMIN, "code": wrong})
        assert response.status_code == 403
    async with sessionmaker() as session:
        assert await fetch_code(session, ADMIN) is None
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": good})
    assert response.status_code == 403


async def test_code_is_single_use(client, fake_mailer):
    code = await login(client, fake_mailer)
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": code})
    assert response.status_code == 403


async def test_expired_code_is_refused(build_app, fake_mailer):
    async with open_client(build_app(now=NOW)) as client:
        await client.post("/api/admin/login", json={"email": ADMIN})
        code = code_from(fake_mailer)
    async with open_client(build_app(now=NOW + dt.timedelta(minutes=11))) as client:
        response = await client.post("/api/admin/session", json={"email": ADMIN, "code": code})
        assert response.status_code == 403


async def test_new_code_invalidates_the_previous_one(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": ADMIN})
    first = code_from(fake_mailer)
    await client.post("/api/admin/login", json={"email": ADMIN})
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": first})
    assert response.status_code == 403


async def test_fourth_code_request_is_rate_limited(client, fake_mailer):
    for _ in range(3):
        assert (await client.post("/api/admin/login", json={"email": ADMIN})).status_code == 204
    response = await client.post("/api/admin/login", json={"email": ADMIN})
    assert response.status_code == 429
    assert len(fake_mailer.sent) == 3


async def test_logout_clears_the_cookie(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.delete("/api/admin/session")
    assert response.status_code == 204
    cookie_header = response.headers.get("set-cookie", "").lower()
    assert "httponly" in cookie_header
    assert "samesite=strict" in cookie_header
    assert "path=/" in cookie_header
    assert not client.cookies.get(COOKIE_NAME)


async def test_malformed_payload_is_422(client):
    assert (await client.post("/api/admin/login", json={})).status_code == 422
    assert (await client.post("/api/admin/session", json={"email": ADMIN})).status_code == 422
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": "abc"})
    assert response.status_code == 422
