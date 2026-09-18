import datetime as dt
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, field_validator

from app.db import consume_code, fetch_code, register_failed_attempt, replace_code
from app.deps import AppDeps
from app.mailer import build_code_email, send_safely
from app.tokens import code_matches, generate_code, hash_code, sign_session, verify_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin")

COOKIE_NAME = "crf_admin"
# Un seul message pour « adresse inconnue », « code faux » et « code expiré » :
# la page ne doit rien laisser deviner.
BAD_CODE = "Code incorrect ou expiré."


class LoginIn(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        email = value.strip().lower()
        if not email:
            raise ValueError("adresse manquante")
        return email


class CodeIn(LoginIn):
    code: str

    @field_validator("code")
    @classmethod
    def _check_code(cls, value: str) -> str:
        code = value.strip()
        if not code.isdigit() or len(code) != 6:
            raise ValueError("code invalide")
        return code


def get_deps(request: Request) -> AppDeps:
    return request.app.state.deps


def _allowed(deps: AppDeps, email: str) -> str | None:
    """Renvoie l'adresse telle qu'elle est configurée, ou None si elle n'est pas admin."""
    return next((a for a in deps.settings.admin_emails if a.lower() == email), None)


async def require_admin(request: Request) -> str:
    deps = get_deps(request)
    token = request.cookies.get(COOKIE_NAME, "")
    email = verify_session(deps.settings.admin_secret, token, deps.now()) if token else None
    # Retirer une adresse d'ADMIN_EMAILS doit déconnecter immédiatement : on revalide
    # l'allowlist à chaque requête plutôt que de tenir une table de sessions.
    if email is None or _allowed(deps, email.lower()) is None:
        raise HTTPException(401, "Connexion requise.")
    return email


@router.post("/login", status_code=204)
async def request_code(request: Request, payload: LoginIn) -> Response:
    deps = get_deps(request)
    if not deps.code_limiter.hit(payload.email):
        raise HTTPException(429, "Trop de demandes, réessayez dans un moment.")

    recipient = _allowed(deps, payload.email)
    if recipient is None:
        logger.info("Demande de code pour une adresse non autorisée")
        return Response(status_code=204)

    code = generate_code()
    settings = deps.settings
    expires_at = deps.now() + dt.timedelta(minutes=settings.admin_code_ttl_minutes)
    async with deps.sessionmaker() as session:
        await replace_code(
            session,
            email=payload.email,
            code_hash=hash_code(settings.admin_secret, payload.email, code),
            expires_at=expires_at,
            now=deps.now(),
        )
    email = build_code_email(
        code=code,
        ttl_minutes=settings.admin_code_ttl_minutes,
        recipient=recipient,
        sender=settings.mail_from,
        reply_to=settings.mail_reply_to,
    )
    send_safely(deps.mailer, email, deps.today())
    return Response(status_code=204)


@router.post("/session", status_code=204)
async def open_session(request: Request, payload: CodeIn) -> Response:
    deps = get_deps(request)
    settings = deps.settings
    now = deps.now()
    async with deps.sessionmaker() as session:
        stored = await fetch_code(session, payload.email)
        if stored is None or stored.expires_at <= now:
            raise HTTPException(403, BAD_CODE)
        if not code_matches(settings.admin_secret, payload.email, payload.code, stored.code_hash):
            await register_failed_attempt(
                session, stored, max_attempts=settings.admin_code_max_attempts
            )
            raise HTTPException(403, BAD_CODE)
        await consume_code(session, stored)

    token = sign_session(
        settings.admin_secret,
        payload.email,
        now + dt.timedelta(days=settings.admin_session_days),
    )
    response = Response(status_code=204)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=settings.admin_session_days * 86400,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        path="/",
    )
    logger.info("Connexion à l'administration réussie")
    return response


@router.delete("/session", status_code=204)
async def close_session(request: Request) -> Response:
    response = Response(status_code=204)
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        secure=get_deps(request).settings.admin_cookie_secure,
        samesite="strict",
        path="/",
    )
    return response
