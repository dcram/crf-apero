import base64
import binascii
import datetime as dt
import hashlib
import hmac
import secrets

CODE_DIGITS = 6


def generate_code() -> str:
    return f"{secrets.randbelow(10**CODE_DIGITS):0{CODE_DIGITS}d}"


def _sign(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def hash_code(secret: str, email: str, code: str) -> str:
    return _sign(secret, f"code|{email}|{code}")


def code_matches(secret: str, email: str, code: str, expected: str) -> bool:
    return hmac.compare_digest(hash_code(secret, email, code), expected)


def sign_session(secret: str, email: str, expires_at: dt.datetime) -> str:
    payload = f"{email}|{int(expires_at.timestamp())}"
    encoded = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    return f"{encoded}.{_sign(secret, encoded)}"


def verify_session(secret: str, token: str, now: dt.datetime) -> str | None:
    encoded, _, signature = token.partition(".")
    if not signature or not hmac.compare_digest(_sign(secret, encoded), signature):
        return None
    padding = "=" * (-len(encoded) % 4)
    try:
        payload = base64.urlsafe_b64decode(encoded + padding).decode()
        email, _, expires = payload.rpartition("|")
        if not email:
            return None
        deadline = dt.datetime.fromtimestamp(int(expires), tz=dt.UTC)
    except (binascii.Error, UnicodeDecodeError, ValueError, OverflowError, OSError):
        return None
    return email if deadline > now else None
