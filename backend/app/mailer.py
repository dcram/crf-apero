import datetime as dt
import html
import logging
from dataclasses import dataclass
from typing import Protocol

import boto3

from app.config import Settings
from app.frdate import format_date_fr

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OutgoingEmail:
    sender: str
    recipients: list[str]
    reply_to: str
    subject: str
    text: str
    html: str


class Mailer(Protocol):
    def send(self, email: OutgoingEmail) -> None: ...


def _display_phone(phone: str | None) -> str:
    if not phone:
        return "non renseigné"
    if len(phone) == 10 and phone.startswith("0"):
        return " ".join(phone[i : i + 2] for i in range(0, 10, 2))
    return phone


def build_notification(
    *,
    tuesday: dt.date,
    theme: str,
    name: str,
    phone: str | None,
    sender: str,
    recipients: list[str],
    reply_to: str,
) -> OutgoingEmail:
    date_label = format_date_fr(tuesday)
    rows = [
        ("Date", date_label),
        ("Thème", theme),
        ("Organisateur", name),
        ("Téléphone", _display_phone(phone)),
    ]
    intro = "Nouvelle inscription pour l'apéro du CRF."
    text = intro + "\n\n" + "\n".join(f"{label} : {value}" for label, value in rows) + "\n"
    items = "".join(
        f"<li><strong>{label} :</strong> {html.escape(value)}</li>" for label, value in rows
    )
    return OutgoingEmail(
        sender=sender,
        recipients=list(recipients),
        reply_to=reply_to,
        subject=f"[CRF] Apéro du {date_label} : {name}",
        text=text,
        html=f"<p>{intro}</p><ul>{items}</ul>",
    )


class ConsoleMailer:
    """Backend de développement : n'envoie rien, journalise l'objet (jamais le corps)."""

    def send(self, email: OutgoingEmail) -> None:
        logger.info("E-mail (console) à %s — %s", ", ".join(email.recipients), email.subject)


class SesMailer:
    def __init__(self, client) -> None:
        self._client = client

    def send(self, email: OutgoingEmail) -> None:
        self._client.send_email(
            FromEmailAddress=email.sender,
            Destination={"ToAddresses": email.recipients},
            ReplyToAddresses=[email.reply_to],
            Content={
                "Simple": {
                    "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": email.text, "Charset": "UTF-8"},
                        "Html": {"Data": email.html, "Charset": "UTF-8"},
                    },
                }
            },
        )


def make_mailer(settings: Settings) -> Mailer:
    if settings.mail_backend == "ses":
        return SesMailer(boto3.client("sesv2", region_name=settings.aws_region))
    return ConsoleMailer()


def send_safely(mailer: Mailer, email: OutgoingEmail, tuesday: dt.date) -> None:
    try:
        mailer.send(email)
    except Exception:
        logger.error(
            "Échec de l'envoi de la notification pour le mardi %s",
            tuesday.isoformat(),
            exc_info=True,
        )
