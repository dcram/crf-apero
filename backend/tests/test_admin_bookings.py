import asyncio
import datetime as dt

from sqlalchemy import func, select

from app.db import Booking, create_booking
from tests.test_admin_auth import ADMIN, login

PAST = "2020-01-07"
FREE = "2030-01-01"
TAKEN = "2030-01-15"
UNKNOWN = "2031-06-10"


async def seed(sessionmaker, date: str = TAKEN, name: str = "Jean Dupont") -> None:
    async with sessionmaker() as session:
        await create_booking(
            session, tuesday=dt.date.fromisoformat(date), name=name, phone="0612345678"
        )


async def booking_count(sessionmaker, tuesday: str) -> int:
    async with sessionmaker() as session:
        return await session.scalar(
            select(func.count())
            .select_from(Booking)
            .where(Booking.tuesday == dt.date.fromisoformat(tuesday))
        )


async def test_all_routes_require_the_cookie(client):
    assert (await client.get("/api/admin/bookings")).status_code == 401
    response = await client.put(
        f"/api/admin/bookings/{FREE}", json={"name": "Jean Dupont", "phone": None}
    )
    assert response.status_code == 401
    assert (await client.delete(f"/api/admin/bookings/{FREE}")).status_code == 401


async def test_listing_covers_the_whole_season_including_the_past(
    client, fake_mailer, sessionmaker
):
    await seed(sessionmaker)
    await login(client, fake_mailer)
    body = (await client.get("/api/admin/bookings")).json()
    assert body["email"] == ADMIN
    assert [s["date"] for s in body["sessions"]] == [PAST, FREE, TAKEN]
    assert body["sessions"][0]["booking"] is None
    assert body["sessions"][2]["booking"]["name"] == "Jean Dupont"
    assert body["sessions"][2]["booking"]["phone"] == "0612345678"
    assert body["orphans"] == []


async def test_booking_outside_the_programme_is_listed_as_orphan(client, fake_mailer, sessionmaker):
    await seed(sessionmaker, date="2029-01-02", name="Marie Martin")
    await login(client, fake_mailer)
    body = (await client.get("/api/admin/bookings")).json()
    assert [o["date"] for o in body["orphans"]] == ["2029-01-02"]
    assert body["orphans"][0]["name"] == "Marie Martin"


async def test_put_on_a_free_tuesday_creates(client, fake_mailer, sessionmaker):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{FREE}", json={"name": "Marie Martin", "phone": "06 12 34 56 78"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Marie Martin"
    assert response.json()["phone"] == "0612345678"
    assert response.json()["theme"] == "Thème A"
    body = (await client.get("/api/admin/bookings")).json()
    assert body["sessions"][1]["booking"]["name"] == "Marie Martin"


async def test_put_on_a_taken_tuesday_replaces(client, fake_mailer, sessionmaker):
    await seed(sessionmaker)
    await login(client, fake_mailer)
    before = (await client.get("/api/admin/bookings")).json()
    previous_created_at = before["sessions"][2]["booking"]["created_at"]
    response = await client.put(
        f"/api/admin/bookings/{TAKEN}", json={"name": "Marie Martin", "phone": None}
    )
    assert response.status_code == 200
    body = (await client.get("/api/admin/bookings")).json()
    assert body["sessions"][2]["booking"]["name"] == "Marie Martin"
    assert body["sessions"][2]["booking"]["phone"] is None
    assert len(body["orphans"]) == 0
    # created_at doit décrire le titulaire courant, pas celui qu'on a remplacé.
    assert body["sessions"][2]["booking"]["created_at"] != previous_created_at
    assert response.json()["created_at"] != previous_created_at


async def test_put_works_on_a_past_tuesday(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{PAST}", json={"name": "Jean Dupont", "phone": None}
    )
    assert response.status_code == 200


async def test_concurrent_puts_on_a_free_tuesday_both_succeed(client, fake_mailer, sessionmaker):
    await login(client, fake_mailer)
    responses = await asyncio.gather(
        client.put(f"/api/admin/bookings/{FREE}", json={"name": "Jean Dupont", "phone": None}),
        client.put(f"/api/admin/bookings/{FREE}", json={"name": "Marie Martin", "phone": None}),
    )
    assert [r.status_code for r in responses] == [200, 200]
    assert await booking_count(sessionmaker, FREE) == 1
    body = (await client.get("/api/admin/bookings")).json()
    assert body["sessions"][1]["booking"]["name"] in {"Jean Dupont", "Marie Martin"}


async def test_put_on_a_date_outside_the_programme_is_404(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{UNKNOWN}", json={"name": "Jean Dupont", "phone": None}
    )
    assert response.status_code == 404


async def test_put_rejects_an_invalid_name(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(f"/api/admin/bookings/{FREE}", json={"name": "J", "phone": None})
    assert response.status_code == 422
    assert response.json() == {"detail": "Merci d'indiquer votre nom (2 à 80 caractères)."}


async def test_put_rejects_malformed_json(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{FREE}",
        content="pas du json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422


async def test_delete_then_delete_again(client, fake_mailer, sessionmaker):
    await seed(sessionmaker)
    await login(client, fake_mailer)
    assert (await client.delete(f"/api/admin/bookings/{TAKEN}")).status_code == 204
    assert (await client.delete(f"/api/admin/bookings/{TAKEN}")).status_code == 404


async def test_delete_removes_an_orphan(client, fake_mailer, sessionmaker):
    await seed(sessionmaker, date="2029-01-02", name="Marie Martin")
    await login(client, fake_mailer)
    assert (await client.delete("/api/admin/bookings/2029-01-02")).status_code == 204
    body = (await client.get("/api/admin/bookings")).json()
    assert body["orphans"] == []


async def test_admin_actions_send_no_email(client, fake_mailer, sessionmaker):
    await login(client, fake_mailer)
    sent_after_login = len(fake_mailer.sent)
    put_response = await client.put(
        f"/api/admin/bookings/{FREE}", json={"name": "Marie Martin", "phone": None}
    )
    assert put_response.status_code == 200
    delete_response = await client.delete(f"/api/admin/bookings/{FREE}")
    assert delete_response.status_code == 204
    assert len(fake_mailer.sent) == sent_after_login


async def test_cookie_of_a_removed_admin_is_refused(build_app, fake_mailer):
    from tests.conftest import open_client

    async with open_client(build_app()) as client:
        await login(client, fake_mailer)
        cookie = client.cookies
    # Contrôle positif : le même jar, rejoué contre une app inchangée, doit
    # authentifier — sinon un 401 ci-dessous ne prouverait rien sur la révocation.
    async with open_client(build_app()) as client:
        client.cookies = cookie
        assert (await client.get("/api/admin/bookings")).status_code == 200
    async with open_client(build_app(admin_emails="quelquun.dautre@example.org")) as client:
        client.cookies = cookie
        assert (await client.get("/api/admin/bookings")).status_code == 401


async def test_tampered_cookie_is_refused(client):
    client.cookies.set("crf_admin", "ZmF1eA.deadbeef")
    assert (await client.get("/api/admin/bookings")).status_code == 401


async def test_expired_cookie_is_refused(build_app, fake_mailer):
    from tests.conftest import open_client

    moment = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
    async with open_client(build_app(now=moment)) as client:
        await login(client, fake_mailer)
        cookie = client.cookies
    async with open_client(build_app(now=moment + dt.timedelta(days=31))) as client:
        client.cookies = cookie
        assert (await client.get("/api/admin/bookings")).status_code == 401
