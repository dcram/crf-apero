import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.mailer import Mailer
from app.ratelimit import RateLimiter
from app.sessions import Meeting
from app.turnstile import Verifier


@dataclass
class AppDeps:
    settings: Settings
    meetings: list[Meeting]
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    verifier: Verifier
    mailer: Mailer
    limiter: RateLimiter
    today: Callable[[], dt.date]

    def upcoming(self) -> list[Meeting]:
        today = self.today()
        return [m for m in self.meetings if m.date > today]

    def meeting_on(self, day: dt.date) -> Meeting | None:
        return next((m for m in self.meetings if m.date == day), None)
