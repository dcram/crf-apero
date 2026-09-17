import datetime as dt
import logging

import boto3
from botocore.stub import Stubber

from app.config import Settings
from app.mailer import (
    ConsoleMailer,
    OutgoingEmail,
    SesMailer,
    build_notification,
    make_mailer,
    send_safely,
)

DAY = dt.date(2026, 10, 6)


def notification(name="Jean Dupont", phone="0612345678") -> OutgoingEmail:
    return build_notification(
        tuesday=DAY,
        theme="La Création et la Chute",
        name=name,
        phone=phone,
        sender="crf@fsspnantes.fr",
        recipients=["a@example.org", "b@example.org"],
        reply_to="orgas@example.org",
    )


def test_subject_and_text_body():
    email = notification()
    assert email.subject == "[CRF] Apéro du mardi 6 octobre 2026 : Jean Dupont"
    assert "Date : mardi 6 octobre 2026" in email.text
    assert "Thème : La Création et la Chute" in email.text
    assert "Organisateur : Jean Dupont" in email.text
    assert "Téléphone : 06 12 34 56 78" in email.text
    assert email.sender == "crf@fsspnantes.fr"
    assert email.recipients == ["a@example.org", "b@example.org"]
    assert email.reply_to == "orgas@example.org"


def test_missing_phone_and_international_format():
    assert "Téléphone : non renseigné" in notification(phone=None).text
    assert "Téléphone : +33612345678" in notification(phone="+33612345678").text


def test_html_body_escapes_user_input():
    email = notification(name="Jean <script>")
    assert "<script>" not in email.html
    assert "Jean &lt;script&gt;" in email.html


def test_ses_mailer_calls_send_email():
    client = boto3.client(
        "sesv2", region_name="eu-west-3", aws_access_key_id="x", aws_secret_access_key="x"
    )
    email = notification()
    stubber = Stubber(client)
    stubber.add_response(
        "send_email",
        {"MessageId": "msg-1"},
        {
            "FromEmailAddress": "crf@fsspnantes.fr",
            "Destination": {"ToAddresses": ["a@example.org", "b@example.org"]},
            "ReplyToAddresses": ["orgas@example.org"],
            "Content": {
                "Simple": {
                    "Subject": {"Data": email.subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": email.text, "Charset": "UTF-8"},
                        "Html": {"Data": email.html, "Charset": "UTF-8"},
                    },
                }
            },
        },
    )
    with stubber:
        SesMailer(client).send(email)
    stubber.assert_no_pending_responses()


def test_console_mailer_never_logs_phone(caplog):
    caplog.set_level(logging.INFO)
    ConsoleMailer().send(notification())
    assert "[CRF] Apéro du mardi 6 octobre 2026" in caplog.text
    assert "0612345678" not in caplog.text
    assert "06 12 34 56 78" not in caplog.text


class BrokenMailer:
    def send(self, email: OutgoingEmail) -> None:
        raise RuntimeError("SES indisponible")


def test_send_safely_logs_error_without_raising(caplog):
    send_safely(BrokenMailer(), notification(), DAY)
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert "2026-10-06" in errors[0].getMessage()
    assert "0612345678" not in caplog.text


def test_make_mailer_selects_backend(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")
    base = dict(
        database_url="postgresql+asyncpg://u:p@h/db",
        turnstile_site_key="k",
        turnstile_secret="s",
        organizer_emails="a@example.org",
        mail_reply_to="r@example.org",
        contact_email="c@example.org",
    )
    assert isinstance(make_mailer(Settings(**base, mail_backend="console")), ConsoleMailer)
    assert isinstance(make_mailer(Settings(**base, mail_backend="ses")), SesMailer)
