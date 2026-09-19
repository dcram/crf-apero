import datetime as dt

import pytest

from app.db import create_booking, make_engine
from app.main import create_app
from app.sessions import SessionsFileError
from tests.conftest import FakeMailer, FakeVerifier, make_settings, open_client


async def test_calendar_returns_public_config_and_upcoming_sessions(client):
    response = await client.get("/api/calendar")
    assert response.status_code == 200
    assert response.json() == {
        "event_info": "Mardi 20h30 – Sainte-Élisabeth",
        "event_address": "43 rue de Coulmiers, 44000 Nantes",
        "event_map_url": "https://example.org/plan",
        "contact_email": "contact@example.org",
        "apero_start_time": "21:30",
        "turnstile_site_key": "1x00000000000000000000AA",
        "sessions": [
            {"date": "2030-01-01", "theme": "Thème A", "available": True},
            {"date": "2030-01-15", "theme": "Thème B", "available": True},
        ],
    }


async def test_calendar_marks_taken_dates_without_personal_data(client, sessionmaker):
    async with sessionmaker() as session:
        await create_booking(
            session, tuesday=dt.date(2030, 1, 15), name="Jean Dupont", phone="0612345678"
        )
    response = await client.get("/api/calendar")
    sessions = {s["date"]: s["available"] for s in response.json()["sessions"]}
    assert sessions == {"2030-01-01": True, "2030-01-15": False}
    assert "Jean" not in response.text
    assert "0612345678" not in response.text


async def test_session_on_today_is_not_listed(build_app):
    async with open_client(build_app(today=dt.date(2030, 1, 1))) as client:
        dates = [s["date"] for s in (await client.get("/api/calendar")).json()["sessions"]]
    assert dates == ["2030-01-15"]


async def test_healthz_ok(client):
    response = await client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_healthz_503_when_database_unreachable(migrated_db):
    broken = make_engine("postgresql+asyncpg://crf:crf@127.0.0.1:1/nope")
    app = create_app(make_settings(), verifier=FakeVerifier(), mailer=FakeMailer(), engine=broken)
    async with open_client(app) as client:
        response = await client.get("/healthz")
    await broken.dispose()
    assert response.status_code == 503


async def test_security_headers(client):
    response = await client.get("/api/calendar")
    csp = response.headers["content-security-policy"]
    assert "frame-ancestors 'self' https://fsspnantes.fr https://*.fsspnantes.fr" in csp
    assert "script-src 'self' https://challenges.cloudflare.com" in csp
    assert "frame-src https://challenges.cloudflare.com" in csp
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


async def test_serves_frontend_when_static_dir_exists(build_app, tmp_path):
    (tmp_path / "index.html").write_text("<h1>CRF</h1>", encoding="utf-8")
    async with open_client(build_app(static_dir=tmp_path)) as client:
        response = await client.get("/")
        api = await client.get("/api/calendar")
    assert response.status_code == 200
    assert "<h1>CRF</h1>" in response.text
    assert api.status_code == 200


def test_invalid_sessions_file_prevents_startup(tmp_path):
    bad = tmp_path / "sessions.yaml"
    bad.write_text("sessions:\n  - date: 2030-01-02\n    theme: A\n", encoding="utf-8")
    with pytest.raises(SessionsFileError):
        create_app(make_settings(sessions_file=bad), verifier=FakeVerifier(), mailer=FakeMailer())


async def test_now_is_injectable(engine, fake_verifier, fake_mailer):
    moment = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
    app = create_app(
        make_settings(),
        verifier=fake_verifier,
        mailer=fake_mailer,
        now=lambda: moment,
        engine=engine,
    )
    assert app.state.deps.now() == moment
    assert app.state.deps.code_limiter is not app.state.deps.limiter


async def test_admin_responses_are_never_cached_nor_indexed(client):
    response = await client.get("/api/admin/bookings")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex"


async def test_public_responses_keep_their_headers(client):
    response = await client.get("/api/calendar")
    assert "Cache-Control" not in response.headers
    assert "X-Robots-Tag" not in response.headers


async def test_admin_page_serves_the_spa(build_app, tmp_path):
    (tmp_path / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    async with open_client(build_app(static_dir=tmp_path)) as client:
        response = await client.get("/admin")
        assert response.status_code == 200
        assert "spa" in response.text
        assert response.headers["X-Robots-Tag"] == "noindex"


async def test_neighboring_paths_dont_get_admin_headers(client):
    # /api/administrateurs (chemin voisin) ne doit PAS recevoir les en-têtes admin
    response = await client.get("/api/administrateurs")
    assert response.status_code == 404
    assert "Cache-Control" not in response.headers
    assert "X-Robots-Tag" not in response.headers
    # /api/admin/bookings (chemin admin réel) DOIT recevoir les en-têtes admin
    response = await client.get("/api/admin/bookings")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex"
