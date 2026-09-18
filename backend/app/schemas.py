import datetime as dt
import re

from pydantic import BaseModel, ValidationError, field_validator

_PHONE_SEPARATORS = re.compile(r"[\s.\-]")
_PHONE = re.compile(r"0[1-9]\d{8}|\+33[1-9]\d{8}")
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

_MESSAGES = {
    "name": "Merci d'indiquer votre nom (2 à 80 caractères).",
    "phone": "Le numéro de téléphone n'est pas valide.",
    "date": "La date choisie n'est pas valide.",
    "turnstile_token": "La vérification anti-robot est manquante, merci de réessayer.",
}


class BookingFields(BaseModel):
    name: str
    phone: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        name = " ".join(value.split())
        if not 2 <= len(name) <= 80 or _CONTROL_CHARS.search(name):
            raise ValueError("nom invalide")
        return name

    @field_validator("phone", mode="before")
    @classmethod
    def _normalize_phone(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("téléphone invalide")
        compact = _PHONE_SEPARATORS.sub("", value)
        if not compact:
            return None
        if not _PHONE.fullmatch(compact):
            raise ValueError("téléphone invalide")
        return compact


class BookingIn(BookingFields):
    date: dt.date
    turnstile_token: str
    website: str = ""

    @field_validator("turnstile_token")
    @classmethod
    def _check_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("jeton manquant")
        return value


def validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Le formulaire est invalide."

    # Collect all fields with errors
    error_fields = {str(error["loc"][0]) for error in errors if error["loc"]}

    # Priority order (pre-inheritance field order): date, name, phone, turnstile_token
    priority = ["date", "name", "phone", "turnstile_token"]
    for field in priority:
        if field in error_fields:
            return _MESSAGES.get(field, "Le formulaire est invalide.")

    # Fallback if none of the priority fields are in error
    return "Le formulaire est invalide."
