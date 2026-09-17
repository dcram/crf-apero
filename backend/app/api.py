import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import ValidationError

from app.db import DateAlreadyTaken, create_booking, taken_dates
from app.deps import AppDeps
from app.mailer import build_notification, send_safely
from app.schemas import BookingIn, validation_message
from app.turnstile import TurnstileUnavailable

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

INVALID_FORM = "Le formulaire est invalide."


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
        "event_address": settings.event_address,
        "event_map_url": settings.event_map_url,
        "contact_email": settings.contact_email,
        "apero_start_time": settings.apero_start_time,
        "turnstile_site_key": settings.turnstile_site_key,
        "sessions": [
            {"date": m.date.isoformat(), "theme": m.theme, "available": m.date not in taken}
            for m in deps.upcoming()
        ],
    }


@router.post("/bookings", status_code=201)
async def create_booking_endpoint(request: Request, background: BackgroundTasks) -> dict:
    deps = get_deps(request)
    try:
        payload = await request.json()
    except ValueError:
        raise HTTPException(422, INVALID_FORM) from None
    if not isinstance(payload, dict):
        raise HTTPException(422, INVALID_FORM)

    # 1. Champ piège : faux succès, rien n'est écrit ni envoyé.
    if payload.get("website"):
        logger.warning("Champ piège rempli : réservation ignorée")
        return {
            "date": str(payload.get("date", "")),
            "theme": "",
            "name": str(payload.get("name", "")),
        }

    # 2. Limite de débit par IP.
    client_ip = request.client.host if request.client else None
    if not deps.limiter.hit(client_ip or "inconnue"):
        raise HTTPException(429, "Trop de tentatives, réessayez dans un moment.")

    # 3. Validation.
    try:
        booking = BookingIn.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, validation_message(exc)) from None

    # 4. Turnstile.
    try:
        human = await deps.verifier.verify(booking.turnstile_token, client_ip)
    except TurnstileUnavailable:
        logger.error("Cloudflare Turnstile injoignable", exc_info=True)
        raise HTTPException(
            503, "Le service est momentanément indisponible, réessayez plus tard."
        ) from None
    if not human:
        raise HTTPException(403, "La vérification anti-robot a échoué, merci de réessayer.")

    # 5. Date proposée et future.
    meeting = deps.meeting_on(booking.date)
    if meeting is None or meeting.date <= deps.today():
        raise HTTPException(404, "Ce mardi n'est pas proposé à la réservation.")

    # 6. Écriture (la contrainte d'unicité arbitre les clics simultanés).
    async with deps.sessionmaker() as session:
        try:
            await create_booking(
                session, tuesday=meeting.date, name=booking.name, phone=booking.phone
            )
        except DateAlreadyTaken:
            raise HTTPException(
                409, "Ce mardi vient d'être réservé, choisissez-en un autre."
            ) from None

    # 7. Notification après la réponse ; un échec n'annule pas la réservation.
    settings = deps.settings
    email = build_notification(
        tuesday=meeting.date,
        theme=meeting.theme,
        name=booking.name,
        phone=booking.phone,
        sender=settings.mail_from,
        recipients=settings.organizer_emails,
        reply_to=settings.mail_reply_to,
    )
    background.add_task(send_safely, deps.mailer, email, meeting.date)
    logger.info("Réservation enregistrée pour le mardi %s", meeting.date.isoformat())
    return {"date": meeting.date.isoformat(), "theme": meeting.theme, "name": booking.name}
