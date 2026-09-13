from typing import Protocol

import httpx

SITEVERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileUnavailable(Exception):
    """Cloudflare n'a pas pu vérifier le jeton (réseau, timeout, réponse inattendue)."""


class Verifier(Protocol):
    async def verify(self, token: str, remote_ip: str | None) -> bool: ...


class TurnstileVerifier:
    def __init__(self, secret: str, timeout: float = 5.0) -> None:
        self._secret = secret
        self._timeout = timeout

    async def verify(self, token: str, remote_ip: str | None) -> bool:
        data = {"secret": self._secret, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(SITEVERIFY_URL, data=data)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TurnstileUnavailable(str(exc)) from exc
        return payload.get("success") is True
