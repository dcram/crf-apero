import datetime as dt

from app.tokens import code_matches, generate_code, hash_code, sign_session, verify_session

SECRET = "secret-de-test"
EMAIL = "admin@example.org"
NOW = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
LATER = NOW + dt.timedelta(days=30)


def test_generate_code_is_six_digits():
    for _ in range(200):
        code = generate_code()
        assert len(code) == 6
        assert code.isdigit()


def test_hash_depends_on_secret_email_and_code():
    base = hash_code(SECRET, EMAIL, "123456")
    assert base != hash_code("autre", EMAIL, "123456")
    assert base != hash_code(SECRET, "autre@example.org", "123456")
    assert base != hash_code(SECRET, EMAIL, "123457")


def test_hash_never_contains_the_code():
    assert "123456" not in hash_code(SECRET, EMAIL, "123456")


def test_code_matches():
    expected = hash_code(SECRET, EMAIL, "123456")
    assert code_matches(SECRET, EMAIL, "123456", expected)
    assert not code_matches(SECRET, EMAIL, "654321", expected)


def test_session_round_trip():
    token = sign_session(SECRET, EMAIL, LATER)
    assert verify_session(SECRET, token, NOW) == EMAIL


def test_session_rejects_expiration_passed():
    token = sign_session(SECRET, EMAIL, NOW - dt.timedelta(seconds=1))
    assert verify_session(SECRET, token, NOW) is None


def test_session_rejects_tampered_payload():
    token = sign_session(SECRET, EMAIL, LATER)
    payload, signature = token.split(".")
    forged = sign_session(SECRET, "pirate@example.org", LATER).split(".")[0]
    assert verify_session(SECRET, f"{forged}.{signature}", NOW) is None


def test_session_rejects_another_secret():
    token = sign_session("autre-secret", EMAIL, LATER)
    assert verify_session(SECRET, token, NOW) is None


def test_session_rejects_garbage():
    for token in ["", "sans-point", "a.b", "!!!.!!!"]:
        assert verify_session(SECRET, token, NOW) is None
