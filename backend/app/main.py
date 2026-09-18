import datetime as dt
import logging
from collections.abc import Callable
from contextlib import asynccontextmanager
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncEngine

from app.admin import router as admin_router
from app.api import router
from app.config import Settings
from app.db import make_engine, make_sessionmaker, ping
from app.deps import AppDeps
from app.mailer import Mailer, make_mailer
from app.ratelimit import RateLimiter
from app.sessions import load_sessions
from app.turnstile import TurnstileVerifier, Verifier

logger = logging.getLogger(__name__)

CLOUDFLARE = "https://challenges.cloudflare.com"
SECURITY_HEADERS = {
    "Content-Security-Policy": "; ".join(
        [
            "default-src 'self'",
            f"script-src 'self' {CLOUDFLARE}",
            f"frame-src {CLOUDFLARE}",
            "connect-src 'self'",
            "style-src 'self' 'unsafe-inline'",
            "img-src 'self' data:",
            "font-src 'self'",
            "base-uri 'self'",
            "form-action 'self'",
            "frame-ancestors 'self' https://fsspnantes.fr https://*.fsspnantes.fr",
        ]
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}


def create_app(
    settings: Settings | None = None,
    *,
    verifier: Verifier | None = None,
    mailer: Mailer | None = None,
    today: Callable[[], dt.date] | None = None,
    now: Callable[[], dt.datetime] | None = None,
    engine: AsyncEngine | None = None,
) -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
    # Les requêtes SQL et leurs paramètres (téléphone) ne doivent jamais apparaître dans les logs.
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    settings = settings or Settings()
    meetings = load_sessions(settings.sessions_file)
    engine = engine or make_engine(settings.database_url)
    tz = ZoneInfo(settings.timezone)

    deps = AppDeps(
        settings=settings,
        meetings=meetings,
        engine=engine,
        sessionmaker=make_sessionmaker(engine),
        verifier=verifier or TurnstileVerifier(settings.turnstile_secret),
        mailer=mailer or make_mailer(settings),
        limiter=RateLimiter(settings.rate_limit_per_hour, window_seconds=3600),
        code_limiter=RateLimiter(settings.admin_codes_per_hour, window_seconds=3600),
        today=today or (lambda: dt.datetime.now(tz).date()),
        now=now or (lambda: dt.datetime.now(tz)),
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(
        title="CRF Apéro", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.deps = deps

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    @app.get("/healthz")
    async def healthz():
        try:
            await ping(engine)
        except Exception:
            logger.error("Base de données injoignable", exc_info=True)
            return JSONResponse({"status": "error"}, status_code=503)
        return {"status": "ok"}

    app.include_router(router)
    app.include_router(admin_router)

    if settings.static_dir and settings.static_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")

    logger.info("%d rencontres chargées depuis %s", len(meetings), settings.sessions_file)
    return app
