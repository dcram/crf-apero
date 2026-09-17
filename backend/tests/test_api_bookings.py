import asyncio
import datetime as dt
import logging

from sqlalchemy import func, select

from app.db import Booking
from app.turnstile import TurnstileUnavailable
from tests.conftest import CLIENT_IP, open_client

VALID = {
    "date": "2030-01-15",
    "name": "Jean Dupont",
    "phone": "06 12 34 56 78",
    "turnstile_token": "tok",
    "website": "",
}


def payload(**overrides) -> dict:
    return {**VALID, **overrides}


async def all_bookings(sessionmaker) -> list[Booking]:
    async with sessionmaker() as session:
        return list(await session.scalars(select(Booking)))


async def booking_count(sessionmaker) -> int:
    async with sessionmaker() as session:
        return await session.scalar(select(func.count()).select_from(Booking))


async def test_success_stores_booking_and_notifies(
    client, sessionmaker, fake_verifier, fake_mailer
):
    response = await client.post("/api/bookings", json=payload())
    assert response.status_code == 201
    assert response.json() == {"date": "2030-01-15", "theme": "Thème B", "name": "Jean Dupont"}

    [booking] = await all_bookings(sessionmaker)
    assert booking.tuesday == dt.date(2030, 1, 15)
    assert booking.name == "Jean Dupont"
    assert booking.phone == "0612345678"

    assert fake_verifier.calls == [("tok", CLIENT_IP)]
    [email] = fake_mailer.sent
    assert email.subject == "[CRF] Apéro du mardi 15 janvier 2030 : Jean Dupont"
    assert email.recipients == ["orga1@example.org", "orga2@example.org"]
    assert email.reply_to == "orgas@example.org"
    assert email.sender == "crf@fsspnantes.fr"


async def test_second_booking_same_date_is_409(client, fake_mailer):
    assert (await client.post("/api/bookings", json=payload())).status_code == 201
    response = await client.post("/api/bookings", json=payload(name="Marie Martin"))
    assert response.status_code == 409
    assert response.json() == {"detail": "Ce mardi vient d'être réservé, choisissez-en un autre."}
    assert len(fake_mailer.sent) == 1


async def test_concurrent_bookings_only_one_wins(client, sessionmaker):
    responses = await asyncio.gather(
        client.post("/api/bookings", json=payload(name="Jean Dupont")),
        client.post("/api/bookings", json=payload(name="Marie Martin")),
    )
    assert sorted(r.status_code for r in responses) == [201, 409]
    assert await booking_count(sessionmaker) == 1


async def test_honeypot_fakes_success_silently(client, sessionmaker, fake_verifier, fake_mailer):
    response = await client.post("/api/bookings", json=payload(website="http://spam.example"))
    assert response.status_code == 201
    assert await booking_count(sessionmaker) == 0
    assert fake_verifier.calls == []
    assert fake_mailer.sent == []


async def test_invalid_name_is_422_before_turnstile(client, fake_verifier):
    response = await client.post("/api/bookings", json=payload(name="J"))
    assert response.status_code == 422
    assert response.json() == {"detail": "Merci d'indiquer votre nom (2 à 80 caractères)."}
    assert fake_verifier.calls == []


async def test_malformed_json_is_422(client):
    response = await client.post(
        "/api/bookings", content="pas du json", headers={"content-type": "application/json"}
    )
    assert response.status_code == 422


async def test_failed_turnstile_is_403(client, sessionmaker, fake_verifier):
    fake_verifier.result = False
    response = await client.post("/api/bookings", json=payload())
    assert response.status_code == 403
    assert "anti-robot" in response.json()["detail"]
    assert await booking_count(sessionmaker) == 0


async def test_turnstile_unavailable_is_503(client, sessionmaker, fake_verifier):
    fake_verifier.error = TurnstileUnavailable("timeout")
    response = await client.post("/api/bookings", json=payload())
    assert response.status_code == 503
    assert await booking_count(sessionmaker) == 0


async def test_tuesday_not_in_program_is_404(client):
    response = await client.post("/api/bookings", json=payload(date="2030-01-08"))
    assert response.status_code == 404


async def test_past_session_is_404(client):
    response = await client.post("/api/bookings", json=payload(date="2020-01-07"))
    assert response.status_code == 404


async def test_session_today_is_404(build_app):
    async with open_client(build_app(today=dt.date(2030, 1, 15))) as client:
        response = await client.post("/api/bookings", json=payload())
    assert response.status_code == 404


async def test_rate_limit_after_five_attempts(client):
    for _ in range(5):
        assert (await client.post("/api/bookings", json=payload(name="J"))).status_code == 422
    response = await client.post("/api/bookings", json=payload())
    assert response.status_code == 429
    assert response.json() == {"detail": "Trop de tentatives, réessayez dans un moment."}


async def test_mail_failure_keeps_booking(client, sessionmaker, fake_mailer, caplog):
    fake_mailer.error = RuntimeError("SES indisponible")
    response = await client.post("/api/bookings", json=payload())
    assert response.status_code == 201
    assert await booking_count(sessionmaker) == 1
    assert any(r.levelno == logging.ERROR for r in caplog.records)


async def test_logs_never_contain_phone(client, caplog):
    caplog.set_level(logging.DEBUG)
    await client.post("/api/bookings", json=payload())
    assert "0612345678" not in caplog.text
    assert "06 12 34 56 78" not in caplog.text
