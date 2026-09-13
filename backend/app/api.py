from fastapi import APIRouter, Request

from app.db import taken_dates
from app.deps import AppDeps

router = APIRouter(prefix="/api")


def get_deps(request: Request) -> AppDeps:
    return request.app.state.deps


@router.get("/calendar")
async def calendar(request: Request) -> dict:
    deps = get_deps(request)
    async with deps.sessionmaker() as session:
        taken = await taken_dates(session)
    settings = deps.settings
    return {
        "event_info": settings.event_info,
        "contact_email": settings.contact_email,
        "apero_start_time": settings.apero_start_time,
        "turnstile_site_key": settings.turnstile_site_key,
        "sessions": [
            {"date": m.date.isoformat(), "theme": m.theme, "available": m.date not in taken}
            for m in deps.upcoming()
        ],
    }
