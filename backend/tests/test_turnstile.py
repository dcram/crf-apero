from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.turnstile import SITEVERIFY_URL, TurnstileUnavailable, TurnstileVerifier


@respx.mock
async def test_valid_token_sends_secret_token_and_ip():
    route = respx.post(SITEVERIFY_URL).mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    assert await TurnstileVerifier("s3cret").verify("tok", "203.0.113.7") is True
    sent = parse_qs(route.calls.last.request.content.decode())
    assert sent == {"secret": ["s3cret"], "response": ["tok"], "remoteip": ["203.0.113.7"]}


@respx.mock
async def test_ip_is_optional():
    route = respx.post(SITEVERIFY_URL).mock(
        return_value=httpx.Response(200, json={"success": True})
    )
    await TurnstileVerifier("s").verify("tok", None)
    assert "remoteip" not in parse_qs(route.calls.last.request.content.decode())


@respx.mock
async def test_invalid_token_returns_false():
    respx.post(SITEVERIFY_URL).mock(
        return_value=httpx.Response(
            200, json={"success": False, "error-codes": ["invalid-input-response"]}
        )
    )
    assert await TurnstileVerifier("s").verify("bad", None) is False


@respx.mock
async def test_timeout_raises_unavailable():
    respx.post(SITEVERIFY_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
    with pytest.raises(TurnstileUnavailable):
        await TurnstileVerifier("s").verify("tok", None)


@respx.mock
async def test_server_error_raises_unavailable():
    respx.post(SITEVERIFY_URL).mock(return_value=httpx.Response(502))
    with pytest.raises(TurnstileUnavailable):
        await TurnstileVerifier("s").verify("tok", None)


@respx.mock
async def test_non_json_raises_unavailable():
    respx.post(SITEVERIFY_URL).mock(return_value=httpx.Response(200, text="<html>"))
    with pytest.raises(TurnstileUnavailable):
        await TurnstileVerifier("s").verify("tok", None)
