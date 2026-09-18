import datetime as dt

import pytest
from pydantic import ValidationError

from app.schemas import BookingFields, BookingIn, validation_message

VALID = {"date": "2030-01-01", "name": "Jean Dupont", "turnstile_token": "tok"}


def parse(**overrides) -> BookingIn:
    return BookingIn.model_validate({**VALID, **overrides})


def test_valid_minimal_payload():
    booking = parse()
    assert booking.date == dt.date(2030, 1, 1)
    assert booking.phone is None
    assert booking.website == ""


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("06 12.34-56 78", "0612345678"),
        ("+33 6 12 34 56 78", "+33612345678"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_phone_normalization(raw, expected):
    assert parse(phone=raw).phone == expected


@pytest.mark.parametrize("raw", ["12345", "0012345678", "+44612345678", "06123456789", "abc"])
def test_rejects_invalid_phone(raw):
    with pytest.raises(ValidationError) as exc:
        parse(phone=raw)
    assert validation_message(exc.value) == "Le numéro de téléphone n'est pas valide."


def test_name_whitespace_is_normalized():
    assert parse(name="  Jean \n  Dupont ").name == "Jean Dupont"


@pytest.mark.parametrize("raw", ["J", " ", "x" * 81, "Jean\x00"])
def test_rejects_invalid_name(raw):
    with pytest.raises(ValidationError) as exc:
        parse(name=raw)
    assert validation_message(exc.value) == "Merci d'indiquer votre nom (2 à 80 caractères)."


def test_rejects_empty_token():
    with pytest.raises(ValidationError) as exc:
        parse(turnstile_token=" ")
    assert "anti-robot" in validation_message(exc.value)


def test_rejects_bad_date():
    with pytest.raises(ValidationError) as exc:
        parse(date="pas-une-date")
    assert validation_message(exc.value) == "La date choisie n'est pas valide."


def test_booking_fields_validate_name_and_phone_alone():
    fields = BookingFields(name="  Jean   Dupont ", phone="06 12 34 56 78")
    assert fields.name == "Jean Dupont"
    assert fields.phone == "0612345678"


def test_booking_fields_reject_short_name():
    with pytest.raises(ValidationError):
        BookingFields(name="J")


def test_booking_in_still_requires_the_turnstile_token():
    with pytest.raises(ValidationError):
        BookingIn(date="2030-01-15", name="Jean Dupont")


def test_validation_message_prefers_date_over_name():
    """Ensure date error is returned even if name is also invalid (priority order)."""
    with pytest.raises(ValidationError) as exc:
        parse(date="pas-une-date", name="J")
    assert validation_message(exc.value) == "La date choisie n'est pas valide."


def test_validation_message_prefers_name_over_turnstile():
    """Ensure name error is returned even if turnstile_token is also invalid."""
    with pytest.raises(ValidationError) as exc:
        parse(name="J", turnstile_token=" ")
    assert validation_message(exc.value) == "Merci d'indiquer votre nom (2 à 80 caractères)."
