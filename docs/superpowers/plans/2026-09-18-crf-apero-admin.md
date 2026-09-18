# Administration des réservations — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner aux organisateurs une page `/admin`, protégée par un code à six chiffres envoyé par e-mail, pour ajouter, remplacer ou supprimer une réservation sans passer par `psql`.

**Architecture :** Une table `admin_codes` stocke le HMAC des codes à usage unique. Après vérification, un cookie signé sans état (`email|expiration|HMAC`) porte la session ; il est revalidé contre `ADMIN_EMAILS` à chaque requête, ce qui donne la révocation sans table de sessions. Les routes vivent dans un routeur `app/admin.py` distinct du routeur public `app/api.py`, et le front monte un second composant racine `Admin.svelte` selon `location.pathname`.

**Tech Stack :** FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL, pytest/pytest-asyncio, Svelte 5 (runes), Vite, vitest. Cryptographie : `hmac`, `hashlib`, `secrets`, `base64` de la bibliothèque standard — **aucune dépendance nouvelle, ni côté Python ni côté npm**.

**Spec :** `docs/superpowers/specs/2026-09-18-crf-apero-admin-design.md`

## Global Constraints

- **Aucune dépendance ajoutée** à `backend/pyproject.toml` ni à `frontend/package.json`.
- **`backend/app/sessions.yaml` et `backend/app/sessions.py` ne sont pas modifiés.** Le programme reste en YAML ; l'admin ne le modifie pas.
- **Aucun e-mail n'est envoyé par les routes d'administration des réservations.** Le mailer ne sert qu'à envoyer le code de connexion. `build_notification` n'est pas modifié.
- **La contrainte `uq_bookings_tuesday` est conservée** : un mardi, un réservataire.
- Python 3.13, `ruff` en `line-length = 100`, cible `py313`. Toute tâche finit par `uv run ruff check . && uv run ruff format .` avant le commit.
- Le code, les commentaires, les messages d'erreur destinés à l'utilisateur et les messages de commit sont **en français**, comme le reste du dépôt.
- Les messages d'erreur d'authentification ne doivent **jamais** permettre de distinguer « adresse inconnue » de « code faux ».
- Les tests backend tournent sur la base `crf_test` (`docker compose up -d --wait db` requis).
- Commandes de vérification : `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .` et `cd frontend && npm run check && npm test`.
- Branche de travail : `feat/admin-auth` (déjà créée, la spec y est commitée).

---

### Task 1 : Réglages d'administration

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/tests/conftest.py:25-40` (`make_settings`)
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Consumes: rien.
- Produces: `Settings.admin_emails: list[str]`, `Settings.admin_secret: str`, `Settings.admin_session_days: int`, `Settings.admin_code_ttl_minutes: int`, `Settings.admin_code_max_attempts: int`, `Settings.admin_codes_per_hour: int`, `Settings.admin_cookie_secure: bool`. `tests.conftest.make_settings()` fournit désormais `admin_emails="admin1@example.org,admin2@example.org"` et `admin_secret="secret-admin-de-test"`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à la fin de `backend/tests/test_config.py` :

```python
def test_admin_settings_defaults():
    settings = Settings(
        **BASE,
        organizer_emails="a@example.org",
        admin_emails=" admin@example.org , ",
        admin_secret="s",
    )
    assert settings.admin_emails == ["admin@example.org"]
    assert settings.admin_session_days == 30
    assert settings.admin_code_ttl_minutes == 10
    assert settings.admin_code_max_attempts == 5
    assert settings.admin_codes_per_hour == 3
    assert settings.admin_cookie_secure is True


def test_rejects_empty_admin_emails():
    with pytest.raises(ValidationError):
        Settings(**BASE, organizer_emails="a@example.org", admin_emails="", admin_secret="s")


def test_admin_secret_is_required():
    with pytest.raises(ValidationError):
        Settings(**BASE, organizer_emails="a@example.org", admin_emails="admin@example.org")
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_config.py -v`
Expected: FAIL — `Settings` refuse les champs inconnus au sens où `admin_emails` n'existe pas encore (`extra="ignore"` les ignore, donc `test_admin_settings_defaults` échoue sur `AttributeError`).

- [ ] **Step 3 : Ajouter les réglages**

Dans `backend/app/config.py`, à l'intérieur de `class Settings`, après `rate_limit_per_hour` :

```python
    admin_emails: Annotated[list[str], NoDecode]
    admin_secret: str
    admin_session_days: int = 30
    admin_code_ttl_minutes: int = 10
    admin_code_max_attempts: int = 5
    admin_codes_per_hour: int = 3
    admin_cookie_secure: bool = True
```

Puis élargir le validateur existant pour qu'il couvre les deux listes — remplacer sa ligne de décorateur :

```python
    @field_validator("organizer_emails", "admin_emails", mode="before")
```

- [ ] **Step 4 : Fournir les valeurs aux tests existants**

Dans `backend/tests/conftest.py`, dans le dictionnaire `values` de `make_settings`, ajouter :

```python
        admin_emails="admin1@example.org,admin2@example.org",
        admin_secret="secret-admin-de-test",
```

- [ ] **Step 5 : Lancer toute la suite**

Run: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: PASS — les nouveaux tests passent et aucun test existant ne casse.

- [ ] **Step 6 : Commit**

```bash
git add backend/app/config.py backend/tests/test_config.py backend/tests/conftest.py
git commit -m "feat(config): réglages de l'administration"
```

---

### Task 2 : Codes et cookies signés (module pur)

Module sans base ni HTTP : tout ce qui touche à la cryptographie, testable en isolation.

**Files:**
- Create: `backend/app/tokens.py`
- Test: `backend/tests/test_tokens.py`

**Interfaces:**
- Consumes: rien.
- Produces:
  - `generate_code() -> str` — six chiffres, zéros de tête compris.
  - `hash_code(secret: str, email: str, code: str) -> str` — HMAC-SHA256 hexadécimal.
  - `code_matches(secret: str, email: str, code: str, expected: str) -> bool` — comparaison en temps constant.
  - `sign_session(secret: str, email: str, expires_at: dt.datetime) -> str`
  - `verify_session(secret: str, token: str, now: dt.datetime) -> str | None` — renvoie l'adresse ou `None`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_tokens.py` :

```python
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
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_tokens.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.tokens'`

- [ ] **Step 3 : Écrire le module**

Créer `backend/app/tokens.py` :

```python
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
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_tokens.py -v && uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/app/tokens.py backend/tests/test_tokens.py
git commit -m "feat(admin): génération des codes et signature des sessions"
```

---

### Task 3 : Table `admin_codes` et accès en base

**Files:**
- Create: `backend/alembic/versions/0002_create_admin_codes.py`
- Modify: `backend/app/db.py`
- Modify: `backend/tests/conftest.py:83-90` (fixture `engine`)
- Test: `backend/tests/test_db_admin_codes.py`

**Interfaces:**
- Consumes: `app.tokens.hash_code` (Task 2).
- Produces, dans `app.db` :
  - `class AdminCode(Base)` — `id`, `email`, `code_hash`, `expires_at`, `attempts`, `created_at`.
  - `async def replace_code(session, *, email: str, code_hash: str, expires_at: dt.datetime, now: dt.datetime) -> None` — efface les codes de cette adresse, purge les expirés, insère le nouveau.
  - `async def fetch_code(session, email: str) -> AdminCode | None`
  - `async def register_failed_attempt(session, code: AdminCode, *, max_attempts: int) -> None` — incrémente, et supprime la ligne au `max_attempts`-ième échec.
  - `async def consume_code(session, code: AdminCode) -> None` — supprime la ligne.

- [ ] **Step 1 : Écrire la migration**

Créer `backend/alembic/versions/0002_create_admin_codes.py` :

```python
"""Création de la table admin_codes

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-18
"""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.Text, nullable=False, index=True),
        sa.Column("code_hash", sa.Text, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_codes")
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Créer `backend/tests/test_db_admin_codes.py` :

```python
import datetime as dt

from app.db import consume_code, fetch_code, register_failed_attempt, replace_code

EMAIL = "admin@example.org"
NOW = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
LATER = NOW + dt.timedelta(minutes=10)


async def test_replace_code_stores_one_row(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None
        assert code.code_hash == "h1"
        assert code.attempts == 0


async def test_new_code_invalidates_the_previous_one(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h2", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None and code.code_hash == "h2"


async def test_replace_code_purges_expired_rows_of_other_emails(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(
            session,
            email="vieux@example.org",
            code_hash="h0",
            expires_at=NOW - dt.timedelta(minutes=1),
            now=NOW,
        )
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        assert await fetch_code(session, "vieux@example.org") is None


async def test_failed_attempts_delete_the_code_at_the_limit(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    for expected in (1, 2):
        async with sessionmaker() as session:
            code = await fetch_code(session, EMAIL)
            assert code is not None
            await register_failed_attempt(session, code, max_attempts=3)
        async with sessionmaker() as session:
            code = await fetch_code(session, EMAIL)
            assert code is not None and code.attempts == expected
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None
        await register_failed_attempt(session, code, max_attempts=3)
    async with sessionmaker() as session:
        assert await fetch_code(session, EMAIL) is None


async def test_consume_code_removes_it(sessionmaker):
    async with sessionmaker() as session:
        await replace_code(session, email=EMAIL, code_hash="h1", expires_at=LATER, now=NOW)
    async with sessionmaker() as session:
        code = await fetch_code(session, EMAIL)
        assert code is not None
        await consume_code(session, code)
    async with sessionmaker() as session:
        assert await fetch_code(session, EMAIL) is None
```

- [ ] **Step 3 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_db_admin_codes.py -v`
Expected: FAIL avec `ImportError: cannot import name 'consume_code' from 'app.db'`

- [ ] **Step 4 : Ajouter le modèle et les accès**

Dans `backend/app/db.py`, ajouter `delete` à l'import SQLAlchemy (`from sqlalchemy import Date, DateTime, Integer, Text, UniqueConstraint, delete, func, select, text`), puis après la classe `Booking` :

```python
class AdminCode(Base):
    __tablename__ = "admin_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
```

et à la fin du fichier :

```python
async def replace_code(
    session: AsyncSession,
    *,
    email: str,
    code_hash: str,
    expires_at: dt.datetime,
    now: dt.datetime,
) -> None:
    """Un seul code valable par adresse : le précédent est effacé, les expirés aussi."""
    await session.execute(delete(AdminCode).where(AdminCode.email == email))
    await session.execute(delete(AdminCode).where(AdminCode.expires_at <= now))
    session.add(AdminCode(email=email, code_hash=code_hash, expires_at=expires_at))
    await session.commit()


async def fetch_code(session: AsyncSession, email: str) -> AdminCode | None:
    return await session.scalar(select(AdminCode).where(AdminCode.email == email))


async def register_failed_attempt(
    session: AsyncSession, code: AdminCode, *, max_attempts: int
) -> None:
    code.attempts += 1
    if code.attempts >= max_attempts:
        await session.delete(code)
    await session.commit()


async def consume_code(session: AsyncSession, code: AdminCode) -> None:
    await session.delete(code)
    await session.commit()
```

- [ ] **Step 5 : Vider la nouvelle table entre les tests**

Dans `backend/tests/conftest.py`, fixture `engine`, remplacer la ligne de `TRUNCATE` par :

```python
        await conn.execute(text("TRUNCATE bookings, admin_codes RESTART IDENTITY"))
```

- [ ] **Step 6 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: PASS — la fixture `migrated_db` applique `0002` automatiquement (`command.upgrade(cfg, "head")`).

- [ ] **Step 7 : Commit**

```bash
git add backend/alembic/versions/0002_create_admin_codes.py backend/app/db.py backend/tests/test_db_admin_codes.py backend/tests/conftest.py
git commit -m "feat(admin): table admin_codes et accès en base"
```

---

### Task 4 : E-mail du code de connexion

**Files:**
- Modify: `backend/app/mailer.py`
- Test: `backend/tests/test_mailer.py`

**Interfaces:**
- Consumes: `OutgoingEmail` (existant).
- Produces: `build_code_email(*, code: str, ttl_minutes: int, recipient: str, sender: str, reply_to: str) -> OutgoingEmail`.

> `build_notification` n'est pas touché : c'est la notification des réservations entrantes, hors périmètre.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_mailer.py` :

```python
def test_build_code_email():
    email = build_code_email(
        code="012345",
        ttl_minutes=10,
        recipient="admin@example.org",
        sender="crf@fsspnantes.fr",
        reply_to="orgas@example.org",
    )
    assert email.recipients == ["admin@example.org"]
    assert email.subject == "[CRF] Votre code de connexion : 012345"
    assert "012345" in email.text
    assert "012345" in email.html
    assert "10 minutes" in email.text


def test_code_email_goes_to_a_single_recipient():
    email = build_code_email(
        code="000001",
        ttl_minutes=5,
        recipient="admin@example.org",
        sender="crf@fsspnantes.fr",
        reply_to="orgas@example.org",
    )
    assert len(email.recipients) == 1
```

Compléter la ligne d'import du fichier pour y ajouter `build_code_email`.

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_mailer.py -v`
Expected: FAIL avec `ImportError: cannot import name 'build_code_email'`

- [ ] **Step 3 : Écrire la fonction**

Dans `backend/app/mailer.py`, après `build_notification` :

```python
def build_code_email(
    *, code: str, ttl_minutes: int, recipient: str, sender: str, reply_to: str
) -> OutgoingEmail:
    intro = "Voici votre code de connexion à l'administration de CRF Apéro."
    validity = f"Il est valable {ttl_minutes} minutes et ne sert qu'une fois."
    warning = "Si vous n'avez pas demandé ce code, ignorez ce message."
    return OutgoingEmail(
        sender=sender,
        recipients=[recipient],
        reply_to=reply_to,
        subject=f"[CRF] Votre code de connexion : {code}",
        text=f"{intro}\n\n{code}\n\n{validity}\n{warning}\n",
        html=f"<p>{intro}</p><p style=\"font-size:2em;letter-spacing:.2em\">"
        f"<strong>{code}</strong></p><p>{validity}</p><p>{warning}</p>",
    )
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_mailer.py -v && uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/app/mailer.py backend/tests/test_mailer.py
git commit -m "feat(admin): e-mail du code de connexion"
```

---

### Task 5 : Horloge et limiteur dédiés dans `AppDeps`

Les tests d'expiration ont besoin d'une horloge injectable, et le rate-limit des codes ne doit pas partager son compteur avec celui des réservations.

**Files:**
- Modify: `backend/app/deps.py`
- Modify: `backend/app/main.py:56-66` (construction de `AppDeps`) et sa signature `create_app`
- Test: `backend/tests/test_app.py`

**Interfaces:**
- Consumes: `Settings.admin_codes_per_hour` (Task 1).
- Produces: `AppDeps.now: Callable[[], dt.datetime]`, `AppDeps.code_limiter: RateLimiter`, et le paramètre `create_app(..., now: Callable[[], dt.datetime] | None = None)`.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `backend/tests/test_app.py` :

```python
async def test_now_is_injectable(engine, fake_verifier, fake_mailer):
    moment = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
    app = create_app(
        make_settings(),
        verifier=fake_verifier,
        mailer=fake_mailer,
        now=lambda: moment,
        engine=engine,
    )
    assert app.state.deps.now() == moment
    assert app.state.deps.code_limiter is not app.state.deps.limiter
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `cd backend && uv run pytest tests/test_app.py::test_now_is_injectable -v`
Expected: FAIL avec `TypeError: create_app() got an unexpected keyword argument 'now'`

- [ ] **Step 3 : Ajouter les deux champs**

Dans `backend/app/deps.py`, ajouter à la dataclasse `AppDeps`, après `limiter` :

```python
    code_limiter: RateLimiter
```

et après `today` :

```python
    now: Callable[[], dt.datetime]
```

Dans `backend/app/main.py`, ajouter le paramètre à `create_app` (après `today`) :

```python
    now: Callable[[], dt.datetime] | None = None,
```

et compléter la construction de `deps` :

```python
        limiter=RateLimiter(settings.rate_limit_per_hour, window_seconds=3600),
        code_limiter=RateLimiter(settings.admin_codes_per_hour, window_seconds=3600),
        today=today or (lambda: dt.datetime.now(tz).date()),
        now=now or (lambda: dt.datetime.now(tz)),
```

- [ ] **Step 4 : Propager dans la fixture de tests**

Dans `backend/tests/conftest.py`, fixture `build_app`, remplacer la fonction interne par :

```python
    def _build(today: dt.date = TODAY, now: dt.datetime | None = None, **overrides):
        return create_app(
            make_settings(**overrides),
            verifier=fake_verifier,
            mailer=fake_mailer,
            today=lambda: today,
            now=(lambda: now) if now else None,
            engine=engine,
        )
```

- [ ] **Step 5 : Lancer toute la suite**

Run: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 6 : Commit**

```bash
git add backend/app/deps.py backend/app/main.py backend/tests/test_app.py backend/tests/conftest.py
git commit -m "feat(admin): horloge injectable et limiteur dédié aux codes"
```

---

### Task 6 : Connexion — demande de code, vérification, cookie

**Files:**
- Create: `backend/app/admin.py`
- Modify: `backend/app/main.py` (inclusion du routeur)
- Test: `backend/tests/test_admin_auth.py`

**Interfaces:**
- Consumes: `app.tokens` (Task 2), `app.db.replace_code/fetch_code/register_failed_attempt/consume_code` (Task 3), `app.mailer.build_code_email` (Task 4), `AppDeps.now/code_limiter` (Task 5).
- Produces, dans `app.admin` : `router` (préfixe `/api/admin`), `COOKIE_NAME = "crf_admin"`, `async def require_admin(request: Request) -> str` (renvoie l'adresse connectée, lève `401` sinon).

**Contrat des routes :**

| Route | Corps | Réponses |
|---|---|---|
| `POST /api/admin/login` | `{"email": str}` | `204` toujours (même adresse inconnue), `429` si rate-limit |
| `POST /api/admin/session` | `{"email": str, "code": str}` | `204` + cookie, ou `403` |
| `DELETE /api/admin/session` | — | `204`, cookie effacé |

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_admin_auth.py` :

```python
import datetime as dt

from app.admin import COOKIE_NAME
from app.db import fetch_code
from app.tokens import sign_session
from tests.conftest import open_client

ADMIN = "admin1@example.org"
NOW = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
SECRET = "secret-admin-de-test"


def code_from(mailer) -> str:
    return mailer.sent[-1].subject.split(": ")[-1]


async def login(client, fake_mailer, email: str = ADMIN) -> str:
    assert (await client.post("/api/admin/login", json={"email": email})).status_code == 204
    code = code_from(fake_mailer)
    response = await client.post("/api/admin/session", json={"email": email, "code": code})
    assert response.status_code == 204
    return code


async def test_login_sends_a_six_digit_code(client, fake_mailer):
    response = await client.post("/api/admin/login", json={"email": ADMIN})
    assert response.status_code == 204
    [email] = fake_mailer.sent
    assert email.recipients == [ADMIN]
    assert code_from(fake_mailer).isdigit()


async def test_unknown_email_answers_204_without_sending(client, fake_mailer):
    response = await client.post("/api/admin/login", json={"email": "pirate@example.org"})
    assert response.status_code == 204
    assert fake_mailer.sent == []


async def test_organizer_who_is_not_admin_gets_nothing(client, fake_mailer):
    response = await client.post("/api/admin/login", json={"email": "orga1@example.org"})
    assert response.status_code == 204
    assert fake_mailer.sent == []


async def test_email_is_matched_case_insensitively(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": "  ADMIN1@Example.ORG "})
    [email] = fake_mailer.sent
    assert email.recipients == [ADMIN]


async def test_valid_code_sets_the_cookie(client, fake_mailer):
    await login(client, fake_mailer)
    assert client.cookies.get(COOKIE_NAME)


async def test_wrong_code_is_403(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": ADMIN})
    wrong = "000000" if code_from(fake_mailer) != "000000" else "111111"
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": wrong})
    assert response.status_code == 403
    assert client.cookies.get(COOKIE_NAME) is None


async def test_fifth_attempt_destroys_the_code(client, fake_mailer, sessionmaker):
    await client.post("/api/admin/login", json={"email": ADMIN})
    good = code_from(fake_mailer)
    wrong = "000000" if good != "000000" else "111111"
    for _ in range(5):
        response = await client.post("/api/admin/session", json={"email": ADMIN, "code": wrong})
        assert response.status_code == 403
    async with sessionmaker() as session:
        assert await fetch_code(session, ADMIN) is None
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": good})
    assert response.status_code == 403


async def test_code_is_single_use(client, fake_mailer):
    code = await login(client, fake_mailer)
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": code})
    assert response.status_code == 403


async def test_expired_code_is_refused(build_app, fake_mailer):
    async with open_client(build_app(now=NOW)) as client:
        await client.post("/api/admin/login", json={"email": ADMIN})
        code = code_from(fake_mailer)
    async with open_client(build_app(now=NOW + dt.timedelta(minutes=11))) as client:
        response = await client.post("/api/admin/session", json={"email": ADMIN, "code": code})
        assert response.status_code == 403


async def test_new_code_invalidates_the_previous_one(client, fake_mailer):
    await client.post("/api/admin/login", json={"email": ADMIN})
    first = code_from(fake_mailer)
    await client.post("/api/admin/login", json={"email": ADMIN})
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": first})
    assert response.status_code == 403


async def test_fourth_code_request_is_rate_limited(client, fake_mailer):
    for _ in range(3):
        assert (
            await client.post("/api/admin/login", json={"email": ADMIN})
        ).status_code == 204
    response = await client.post("/api/admin/login", json={"email": ADMIN})
    assert response.status_code == 429
    assert len(fake_mailer.sent) == 3


async def test_logout_clears_the_cookie(client, fake_mailer):
    await login(client, fake_mailer)
    assert (await client.delete("/api/admin/session")).status_code == 204
    assert not client.cookies.get(COOKIE_NAME)


async def test_malformed_payload_is_422(client):
    assert (await client.post("/api/admin/login", json={})).status_code == 422
    assert (await client.post("/api/admin/session", json={"email": ADMIN})).status_code == 422
    response = await client.post("/api/admin/session", json={"email": ADMIN, "code": "abc"})
    assert response.status_code == 422
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_admin_auth.py -v`
Expected: FAIL avec `ModuleNotFoundError: No module named 'app.admin'`

- [ ] **Step 3 : Écrire le routeur d'authentification**

Créer `backend/app/admin.py` :

```python
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
```

> `send_safely` est réutilisé pour que l'échec d'envoi soit journalisé sans faire échouer la requête — la réponse doit rester `204` dans tous les cas.

- [ ] **Step 4 : Inclure le routeur**

Dans `backend/app/main.py`, ajouter `from app.admin import router as admin_router` aux imports et, juste après `app.include_router(router)` :

```python
    app.include_router(admin_router)
```

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_admin_auth.py -v`
Expected: PASS

- [ ] **Step 6 : Lancer toute la suite et commit**

Run: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`

```bash
git add backend/app/admin.py backend/app/main.py backend/tests/test_admin_auth.py
git commit -m "feat(admin): connexion par code à six chiffres"
```

---

### Task 7 : Champs de réservation partagés

Le nom et le téléphone doivent obéir aux mêmes règles côté public et côté admin, sans duplication.

**Files:**
- Modify: `backend/app/schemas.py:20-28`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Consumes: rien.
- Produces: `class BookingFields(BaseModel)` avec `name: str` et `phone: str | None = None` et leurs validateurs ; `class BookingIn(BookingFields)` ajoutant `date`, `turnstile_token`, `website`.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `backend/tests/test_schemas.py` :

```python
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
```

Compléter la ligne d'import du fichier pour y ajouter `BookingFields`.

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_schemas.py -v`
Expected: FAIL avec `ImportError: cannot import name 'BookingFields'`

- [ ] **Step 3 : Scinder le schéma**

Dans `backend/app/schemas.py`, remplacer la déclaration de `BookingIn` et ses deux validateurs de champs par :

```python
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
```

- [ ] **Step 4 : Vérifier la non-régression du parcours public**

Run: `cd backend && uv run pytest tests/test_schemas.py tests/test_api_bookings.py -v`
Expected: PASS — Turnstile, champ piège, rate-limit et messages d'erreur inchangés.

- [ ] **Step 5 : Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py
git commit -m "refactor(schemas): champs de réservation partagés avec l'admin"
```

---

### Task 8 : Lecture et écriture des réservations par l'admin

**Files:**
- Modify: `backend/app/db.py`
- Modify: `backend/app/admin.py`
- Test: `backend/tests/test_admin_bookings.py`

**Interfaces:**
- Consumes: `require_admin` (Task 6), `BookingFields` (Task 7), `AppDeps.meetings` (existant).
- Produces, dans `app.db` : `async def all_bookings(session) -> list[Booking]`, `async def upsert_booking(session, *, tuesday, name, phone) -> Booking`, `async def delete_booking(session, tuesday) -> bool`.

**Contrat des routes :**

```
GET /api/admin/bookings → 200
{
  "email": "admin1@example.org",
  "sessions": [
    {"date": "2020-01-07", "theme": "Thème passé", "booking": null},
    {"date": "2030-01-15", "theme": "Thème B",
     "booking": {"name": "Jean Dupont", "phone": "0612345678",
                 "created_at": "2026-09-18T12:00:00+00:00"}}
  ],
  "orphans": [{"date": "2029-01-02", "name": "…", "phone": null, "created_at": "…"}]
}

PUT /api/admin/bookings/{date}  {"name": str, "phone": str | null} → 200
{"date": "2030-01-15", "theme": "Thème B", "name": "…", "phone": "…",
 "created_at": "…"}

DELETE /api/admin/bookings/{date} → 204, ou 404
```

- [ ] **Step 1 : Écrire les tests qui échouent**

Créer `backend/tests/test_admin_bookings.py` :

```python
import datetime as dt

from app.db import create_booking
from tests.test_admin_auth import ADMIN, login

PAST = "2020-01-07"
FREE = "2030-01-01"
TAKEN = "2030-01-15"
UNKNOWN = "2031-06-10"


async def seed(sessionmaker, date: str = TAKEN, name: str = "Jean Dupont") -> None:
    async with sessionmaker() as session:
        await create_booking(
            session, tuesday=dt.date.fromisoformat(date), name=name, phone="0612345678"
        )


async def test_all_routes_require_the_cookie(client):
    assert (await client.get("/api/admin/bookings")).status_code == 401
    response = await client.put(
        f"/api/admin/bookings/{FREE}", json={"name": "Jean Dupont", "phone": None}
    )
    assert response.status_code == 401
    assert (await client.delete(f"/api/admin/bookings/{FREE}")).status_code == 401


async def test_listing_covers_the_whole_season_including_the_past(
    client, fake_mailer, sessionmaker
):
    await seed(sessionmaker)
    await login(client, fake_mailer)
    body = (await client.get("/api/admin/bookings")).json()
    assert body["email"] == ADMIN
    assert [s["date"] for s in body["sessions"]] == [PAST, FREE, TAKEN]
    assert body["sessions"][0]["booking"] is None
    assert body["sessions"][2]["booking"]["name"] == "Jean Dupont"
    assert body["sessions"][2]["booking"]["phone"] == "0612345678"
    assert body["orphans"] == []


async def test_booking_outside_the_programme_is_listed_as_orphan(
    client, fake_mailer, sessionmaker
):
    await seed(sessionmaker, date="2029-01-02", name="Marie Martin")
    await login(client, fake_mailer)
    body = (await client.get("/api/admin/bookings")).json()
    assert [o["date"] for o in body["orphans"]] == ["2029-01-02"]
    assert body["orphans"][0]["name"] == "Marie Martin"


async def test_put_on_a_free_tuesday_creates(client, fake_mailer, sessionmaker):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{FREE}", json={"name": "Marie Martin", "phone": "06 12 34 56 78"}
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Marie Martin"
    assert response.json()["phone"] == "0612345678"
    assert response.json()["theme"] == "Thème A"
    body = (await client.get("/api/admin/bookings")).json()
    assert body["sessions"][1]["booking"]["name"] == "Marie Martin"


async def test_put_on_a_taken_tuesday_replaces(client, fake_mailer, sessionmaker):
    await seed(sessionmaker)
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{TAKEN}", json={"name": "Marie Martin", "phone": None}
    )
    assert response.status_code == 200
    body = (await client.get("/api/admin/bookings")).json()
    assert body["sessions"][2]["booking"]["name"] == "Marie Martin"
    assert body["sessions"][2]["booking"]["phone"] is None
    assert len(body["orphans"]) == 0


async def test_put_works_on_a_past_tuesday(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{PAST}", json={"name": "Jean Dupont", "phone": None}
    )
    assert response.status_code == 200


async def test_put_on_a_date_outside_the_programme_is_404(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(
        f"/api/admin/bookings/{UNKNOWN}", json={"name": "Jean Dupont", "phone": None}
    )
    assert response.status_code == 404


async def test_put_rejects_an_invalid_name(client, fake_mailer):
    await login(client, fake_mailer)
    response = await client.put(f"/api/admin/bookings/{FREE}", json={"name": "J", "phone": None})
    assert response.status_code == 422


async def test_delete_then_delete_again(client, fake_mailer, sessionmaker):
    await seed(sessionmaker)
    await login(client, fake_mailer)
    assert (await client.delete(f"/api/admin/bookings/{TAKEN}")).status_code == 204
    assert (await client.delete(f"/api/admin/bookings/{TAKEN}")).status_code == 404


async def test_admin_actions_send_no_email(client, fake_mailer, sessionmaker):
    await login(client, fake_mailer)
    sent_after_login = len(fake_mailer.sent)
    await client.put(f"/api/admin/bookings/{FREE}", json={"name": "Marie Martin", "phone": None})
    await client.delete(f"/api/admin/bookings/{FREE}")
    assert len(fake_mailer.sent) == sent_after_login


async def test_cookie_of_a_removed_admin_is_refused(build_app, fake_mailer):
    from tests.conftest import open_client

    async with open_client(build_app()) as client:
        await login(client, fake_mailer)
        cookie = client.cookies
    async with open_client(build_app(admin_emails="quelquun.dautre@example.org")) as client:
        client.cookies = cookie
        assert (await client.get("/api/admin/bookings")).status_code == 401


async def test_tampered_cookie_is_refused(client):
    client.cookies.set("crf_admin", "ZmF1eA.deadbeef")
    assert (await client.get("/api/admin/bookings")).status_code == 401


async def test_expired_cookie_is_refused(build_app, fake_mailer):
    from tests.conftest import open_client

    moment = dt.datetime(2026, 9, 18, 12, 0, tzinfo=dt.UTC)
    async with open_client(build_app(now=moment)) as client:
        await login(client, fake_mailer)
        cookie = client.cookies
    async with open_client(build_app(now=moment + dt.timedelta(days=31))) as client:
        client.cookies = cookie
        assert (await client.get("/api/admin/bookings")).status_code == 401
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_admin_bookings.py -v`
Expected: FAIL — `401` partout puis `404`, les routes n'existent pas encore.

- [ ] **Step 3 : Ajouter les accès en base**

À la fin de `backend/app/db.py` :

```python
async def all_bookings(session: AsyncSession) -> list[Booking]:
    return list(await session.scalars(select(Booking).order_by(Booking.tuesday)))


async def upsert_booking(
    session: AsyncSession, *, tuesday: dt.date, name: str, phone: str | None
) -> Booking:
    """Crée la réservation du mardi, ou remplace son titulaire si elle existe déjà."""
    booking = await session.scalar(select(Booking).where(Booking.tuesday == tuesday))
    if booking is None:
        booking = Booking(tuesday=tuesday, name=name, phone=phone)
        session.add(booking)
    else:
        booking.name = name
        booking.phone = phone
    await session.commit()
    return booking


async def delete_booking(session: AsyncSession, tuesday: dt.date) -> bool:
    booking = await session.scalar(select(Booking).where(Booking.tuesday == tuesday))
    if booking is None:
        return False
    await session.delete(booking)
    await session.commit()
    return True
```

- [ ] **Step 4 : Ajouter les trois routes**

Dans `backend/app/admin.py`, ajouter `Depends` à l'import FastAPI (`from fastapi import APIRouter, Depends, HTTPException, Request, Response`), puis compléter les imports de données :

```python
from app.db import (
    all_bookings,
    consume_code,
    delete_booking,
    fetch_code,
    register_failed_attempt,
    replace_code,
    upsert_booking,
)
from app.schemas import BookingFields, validation_message
```

et ajouter à la fin du fichier :

```python
def _booking_payload(booking) -> dict:
    return {
        "name": booking.name,
        "phone": booking.phone,
        "created_at": booking.created_at.isoformat(),
    }


@router.get("/bookings")
async def list_bookings(request: Request, email: str = Depends(require_admin)) -> dict:
    deps = get_deps(request)
    async with deps.sessionmaker() as session:
        bookings = await all_bookings(session)
    by_date = {b.tuesday: b for b in bookings}
    programme = {m.date for m in deps.meetings}
    return {
        "email": email,
        "sessions": [
            {
                "date": m.date.isoformat(),
                "theme": m.theme,
                "booking": _booking_payload(by_date[m.date]) if m.date in by_date else None,
            }
            for m in deps.meetings
        ],
        # Une réservation dont le mardi a disparu de sessions.yaml resterait invisible
        # — donc insupprimable — si on ne la listait pas à part.
        "orphans": [
            {"date": b.tuesday.isoformat(), **_booking_payload(b)}
            for b in bookings
            if b.tuesday not in programme
        ],
    }


@router.put("/bookings/{day}")
async def save_booking(
    request: Request, day: dt.date, payload: BookingFields, _: str = Depends(require_admin)
) -> dict:
    deps = get_deps(request)
    meeting = deps.meeting_on(day)
    if meeting is None:
        raise HTTPException(404, "Ce mardi ne figure pas au programme de la saison.")
    async with deps.sessionmaker() as session:
        booking = await upsert_booking(
            session, tuesday=day, name=payload.name, phone=payload.phone
        )
        result = {"date": day.isoformat(), "theme": meeting.theme, **_booking_payload(booking)}
    logger.info("Réservation du mardi %s enregistrée par un organisateur", day.isoformat())
    return result


@router.delete("/bookings/{day}", status_code=204)
async def remove_booking(
    request: Request, day: dt.date, _: str = Depends(require_admin)
) -> Response:
    deps = get_deps(request)
    async with deps.sessionmaker() as session:
        if not await delete_booking(session, day):
            raise HTTPException(404, "Aucune réservation pour ce mardi.")
    logger.info("Réservation du mardi %s supprimée par un organisateur", day.isoformat())
    return Response(status_code=204)
```

> Ces trois routes n'envoient aucun e-mail et ne passent ni par Turnstile, ni par le rate-limit, ni par le champ piège : le cookie admin est la preuve.

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest tests/test_admin_bookings.py -v`
Expected: PASS

- [ ] **Step 6 : Lancer toute la suite et commit**

Run: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`

```bash
git add backend/app/db.py backend/app/admin.py backend/tests/test_admin_bookings.py
git commit -m "feat(admin): ajout, remplacement et suppression des réservations"
```

---

### Task 9 : Page `/admin` servie et jamais mise en cache

**Files:**
- Modify: `backend/app/main.py:78-99` (middleware et montage des fichiers statiques)
- Test: `backend/tests/test_app.py`

**Interfaces:**
- Consumes: rien.
- Produces: route `GET /admin` renvoyant `index.html` ; en-têtes `Cache-Control: no-store` et `X-Robots-Tag: noindex` sur `/admin` et `/api/admin/*`.

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `backend/tests/test_app.py` :

```python
async def test_admin_responses_are_never_cached_nor_indexed(client):
    response = await client.get("/api/admin/bookings")
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Robots-Tag"] == "noindex"


async def test_public_responses_keep_their_headers(client):
    response = await client.get("/api/calendar")
    assert "Cache-Control" not in response.headers
    assert "X-Robots-Tag" not in response.headers


async def test_admin_page_serves_the_spa(build_app, tmp_path):
    (tmp_path / "index.html").write_text("<html>spa</html>", encoding="utf-8")
    async with open_client(build_app(static_dir=tmp_path)) as client:
        response = await client.get("/admin")
        assert response.status_code == 200
        assert "spa" in response.text
        assert response.headers["X-Robots-Tag"] == "noindex"
```

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd backend && uv run pytest tests/test_app.py -v -k admin`
Expected: FAIL avec `KeyError: 'Cache-Control'` puis un `404` sur `/admin`.

- [ ] **Step 3 : Ajouter les en-têtes et la route**

Dans `backend/app/main.py`, ajouter `from fastapi.responses import FileResponse, JSONResponse` (compléter l'import existant), puis dans le middleware `security_headers`, avant le `return response` :

```python
        # La page d'administration affiche des numéros de téléphone.
        if request.url.path == "/admin" or request.url.path.startswith("/api/admin"):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Robots-Tag"] = "noindex"
```

et remplacer le bloc de montage des fichiers statiques par :

```python
    if settings.static_dir and settings.static_dir.is_dir():
        index = settings.static_dir / "index.html"

        # StaticFiles ne sert index.html que sur un répertoire : la seconde page de
        # l'application a besoin de sa propre route.
        @app.get("/admin", include_in_schema=False)
        async def admin_page():
            return FileResponse(index)

        app.mount("/", StaticFiles(directory=settings.static_dir, html=True), name="static")
```

- [ ] **Step 4 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .`
Expected: PASS

- [ ] **Step 5 : Commit**

```bash
git add backend/app/main.py backend/tests/test_app.py
git commit -m "feat(admin): route /admin et en-têtes no-store/noindex"
```

---

### Task 10 : Client HTTP d'administration (front)

**Files:**
- Create: `frontend/src/lib/admin.ts`
- Create: `frontend/src/lib/admin.test.ts`
- Modify: `frontend/src/lib/types.ts`

**Interfaces:**
- Consumes: les routes des Tasks 6 et 8.
- Produces, dans `lib/admin.ts` :
  - `requestCode(email, fetchFn?) : Promise<AdminResult<null>>`
  - `openSession(email, code, fetchFn?) : Promise<AdminResult<null>>`
  - `closeSession(fetchFn?) : Promise<void>`
  - `fetchAdminBookings(fetchFn?) : Promise<AdminResult<AdminCalendar>>`
  - `saveBooking(date, fields, fetchFn?) : Promise<AdminResult<AdminBooking>>`
  - `deleteBooking(date, fetchFn?) : Promise<AdminResult<null>>`

Et dans `lib/types.ts` : `AdminBooking`, `AdminSessionItem`, `AdminOrphan`, `AdminCalendar`, `AdminFields`, `AdminResult<T>`.

- [ ] **Step 1 : Écrire les types**

Ajouter à la fin de `frontend/src/lib/types.ts` :

```ts
export interface AdminBooking {
  name: string;
  phone: string | null;
  created_at: string;
}

export interface AdminSessionItem {
  date: string;
  theme: string;
  booking: AdminBooking | null;
}

export interface AdminOrphan extends AdminBooking {
  date: string;
}

export interface AdminCalendar {
  email: string;
  sessions: AdminSessionItem[];
  orphans: AdminOrphan[];
}

export interface AdminFields {
  name: string;
  phone: string | null;
}

export type AdminResult<T> =
  | { kind: 'ok'; value: T }
  | { kind: 'unauthorized' }
  | { kind: 'error'; message: string };
```

- [ ] **Step 2 : Écrire les tests qui échouent**

Créer `frontend/src/lib/admin.test.ts` :

```ts
import { describe, expect, it } from 'vitest';
import {
  deleteBooking,
  fetchAdminBookings,
  openSession,
  requestCode,
  saveBooking,
} from './admin';

function fakeFetch(status: number, body: unknown = {}, calls: RequestInit[] = []): typeof fetch {
  return (async (_url: string | URL | Request, init?: RequestInit) => {
    calls.push(init ?? {});
    return new Response(status === 204 ? null : JSON.stringify(body), { status });
  }) as typeof fetch;
}

describe('requestCode', () => {
  it('renvoie ok sur 204', async () => {
    expect(await requestCode('a@b.org', fakeFetch(204))).toEqual({ kind: 'ok', value: null });
  });

  it('remonte le message sur 429', async () => {
    const outcome = await requestCode('a@b.org', fakeFetch(429, { detail: 'Trop de demandes' }));
    expect(outcome).toEqual({ kind: 'error', message: 'Trop de demandes' });
  });
});

describe('openSession', () => {
  it('envoie adresse et code', async () => {
    const calls: RequestInit[] = [];
    await openSession('a@b.org', '123456', fakeFetch(204, {}, calls));
    expect(JSON.parse(calls[0].body as string)).toEqual({ email: 'a@b.org', code: '123456' });
  });

  it('remonte le message sur 403', async () => {
    const outcome = await openSession('a@b.org', '000000', fakeFetch(403, { detail: 'Code incorrect ou expiré.' }));
    expect(outcome).toEqual({ kind: 'error', message: 'Code incorrect ou expiré.' });
  });
});

describe('fetchAdminBookings', () => {
  it('renvoie le calendrier', async () => {
    const calendar = { email: 'a@b.org', sessions: [], orphans: [] };
    expect(await fetchAdminBookings(fakeFetch(200, calendar))).toEqual({
      kind: 'ok',
      value: calendar,
    });
  });

  it('signale la déconnexion sur 401', async () => {
    expect(await fetchAdminBookings(fakeFetch(401))).toEqual({ kind: 'unauthorized' });
  });
});

describe('saveBooking', () => {
  it('fait un PUT sur la date', async () => {
    const calls: RequestInit[] = [];
    const booking = { date: '2026-10-06', theme: 'T', name: 'Jean', phone: null, created_at: '' };
    const outcome = await saveBooking(
      '2026-10-06',
      { name: 'Jean', phone: null },
      fakeFetch(200, booking, calls),
    );
    expect(calls[0].method).toBe('PUT');
    expect(outcome).toEqual({ kind: 'ok', value: booking });
  });
});

describe('deleteBooking', () => {
  it('renvoie ok sur 204', async () => {
    expect(await deleteBooking('2026-10-06', fakeFetch(204))).toEqual({ kind: 'ok', value: null });
  });

  it('signale la déconnexion sur 401', async () => {
    expect(await deleteBooking('2026-10-06', fakeFetch(401))).toEqual({ kind: 'unauthorized' });
  });
});
```

- [ ] **Step 3 : Lancer les tests pour vérifier qu'ils échouent**

Run: `cd frontend && npm test`
Expected: FAIL — `Failed to resolve import "./admin"`

- [ ] **Step 4 : Écrire le client**

Créer `frontend/src/lib/admin.ts` :

```ts
import type { AdminBooking, AdminCalendar, AdminFields, AdminResult } from './types';

export const UNAVAILABLE_MESSAGE = 'Le service est momentanément indisponible, réessayez plus tard.';

async function call<T>(
  url: string,
  init: RequestInit,
  fetchFn: typeof fetch,
): Promise<AdminResult<T>> {
  let response: Response;
  try {
    response = await fetchFn(url, { ...init, headers: { Accept: 'application/json', ...init.headers } });
  } catch {
    return { kind: 'error', message: UNAVAILABLE_MESSAGE };
  }
  if (response.status === 401) {
    return { kind: 'unauthorized' };
  }
  if (response.status === 204) {
    return { kind: 'ok', value: null as T };
  }
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }
  if (!response.ok) {
    const detail = (body as { detail?: unknown } | null)?.detail;
    return { kind: 'error', message: typeof detail === 'string' ? detail : UNAVAILABLE_MESSAGE };
  }
  return { kind: 'ok', value: body as T };
}

function json(method: string, payload: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) };
}

export function requestCode(email: string, fetchFn: typeof fetch = fetch) {
  return call<null>('/api/admin/login', json('POST', { email }), fetchFn);
}

export function openSession(email: string, code: string, fetchFn: typeof fetch = fetch) {
  return call<null>('/api/admin/session', json('POST', { email, code }), fetchFn);
}

export async function closeSession(fetchFn: typeof fetch = fetch): Promise<void> {
  await call<null>('/api/admin/session', { method: 'DELETE' }, fetchFn);
}

export function fetchAdminBookings(fetchFn: typeof fetch = fetch) {
  return call<AdminCalendar>('/api/admin/bookings', { method: 'GET' }, fetchFn);
}

export function saveBooking(date: string, fields: AdminFields, fetchFn: typeof fetch = fetch) {
  return call<AdminBooking & { date: string; theme: string }>(
    `/api/admin/bookings/${date}`,
    json('PUT', fields),
    fetchFn,
  );
}

export function deleteBooking(date: string, fetchFn: typeof fetch = fetch) {
  return call<null>(`/api/admin/bookings/${date}`, { method: 'DELETE' }, fetchFn);
}
```

- [ ] **Step 5 : Lancer les tests pour vérifier qu'ils passent**

Run: `cd frontend && npm test && npm run check`
Expected: PASS

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/lib/admin.ts frontend/src/lib/admin.test.ts frontend/src/lib/types.ts
git commit -m "feat(frontend): client HTTP de l'administration"
```

---

### Task 11 : Écran de connexion et routage de la seconde page

**Files:**
- Create: `frontend/src/components/AdminLogin.svelte`
- Create: `frontend/src/Admin.svelte`
- Modify: `frontend/src/main.ts`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: `requestCode`, `openSession`, `fetchAdminBookings` (Task 10).
- Produces: `Admin.svelte` (composant racine de `/admin`), `AdminLogin.svelte` avec la prop `onconnected: () => void`.

- [ ] **Step 1 : Écrire l'écran de connexion**

Créer `frontend/src/components/AdminLogin.svelte` :

```svelte
<script lang="ts">
  import { openSession, requestCode } from '../lib/admin';

  let { onconnected }: { onconnected: () => void } = $props();

  let step = $state<'email' | 'code'>('email');
  let email = $state('');
  let code = $state('');
  let error = $state('');
  let notice = $state('');
  let busy = $state(false);

  async function askCode(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    busy = true;
    const outcome = await requestCode(email.trim());
    busy = false;
    if (outcome.kind === 'error') {
      error = outcome.message;
      return;
    }
    // La réponse est identique pour une adresse inconnue : le message reste neutre.
    notice = `Si ${email.trim()} est une adresse d'organisateur, un code vient d'y être envoyé.`;
    step = 'code';
  }

  async function submitCode(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (!/^\d{6}$/.test(code.trim())) {
      error = 'Le code comporte six chiffres.';
      return;
    }
    busy = true;
    const outcome = await openSession(email.trim(), code.trim());
    busy = false;
    if (outcome.kind === 'ok') {
      onconnected();
      return;
    }
    error = outcome.kind === 'unauthorized' ? 'Connexion refusée.' : outcome.message;
    code = '';
  }

  function restart() {
    step = 'email';
    code = '';
    error = '';
    notice = '';
  }
</script>

<section class="login">
  <h1>Administration</h1>
  {#if step === 'email'}
    <form onsubmit={askCode}>
      <label for="admin-email">Votre adresse d'organisateur</label>
      <input
        id="admin-email"
        type="email"
        bind:value={email}
        autocomplete="email"
        required
        disabled={busy}
      />
      <button type="submit" disabled={busy || !email.trim()}>Recevoir un code</button>
    </form>
  {:else}
    <form onsubmit={submitCode}>
      <p class="notice">{notice}</p>
      <label for="admin-code">Code à six chiffres</label>
      <input
        id="admin-code"
        bind:value={code}
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        required
        disabled={busy}
      />
      <button type="submit" disabled={busy || !code.trim()}>Se connecter</button>
      <button type="button" class="link" onclick={restart}>Changer d'adresse</button>
    </form>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
```

- [ ] **Step 2 : Écrire la coquille `Admin.svelte`**

Créer `frontend/src/Admin.svelte` — pour l'instant, connexion puis simple confirmation ; le tableau arrive en Task 12 :

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import AdminLogin from './components/AdminLogin.svelte';
  import { fetchAdminBookings } from './lib/admin';
  import type { AdminCalendar } from './lib/types';

  let calendar = $state<AdminCalendar | null>(null);
  let connected = $state(false);
  let loadError = $state('');

  async function load() {
    const outcome = await fetchAdminBookings();
    if (outcome.kind === 'ok') {
      calendar = outcome.value;
      connected = true;
      loadError = '';
      return;
    }
    connected = false;
    calendar = null;
    loadError = outcome.kind === 'error' ? outcome.message : '';
  }

  onMount(load);
</script>

<div class="page admin">
  {#if !connected}
    <AdminLogin onconnected={load} />
    {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}
  {:else if calendar}
    <p>Connecté en tant que {calendar.email} — {calendar.sessions.length} mardis au programme.</p>
  {/if}
</div>
```

- [ ] **Step 3 : Router sur `location.pathname`**

Dans `frontend/src/main.ts`, remplacer les deux dernières lignes par :

```ts
import Admin from './Admin.svelte';

// Deux pages seulement : un routeur serait disproportionné.
const root = window.location.pathname.replace(/\/$/, '') === '/admin' ? Admin : App;

const app = mount(root, { target: document.getElementById('app')! });

export default app;
```

- [ ] **Step 4 : Ajouter les styles**

Dans `frontend/src/app.css`, à la fin, en réutilisant les variables de couleur déjà définies dans le fichier (ne pas en introduire de nouvelles) :

```css
.admin .login {
  max-width: 24rem;
  margin: 4rem auto;
}

.admin .login form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.admin .login input {
  padding: 0.6rem;
  font: inherit;
}

.admin .error {
  color: #a11;
}

.admin .notice {
  font-size: 0.95rem;
}
```

- [ ] **Step 5 : Vérifier**

Run: `cd frontend && npm run check && npm test && npm run build`
Expected: PASS, et `npm run build` produit `dist/index.html`.

- [ ] **Step 6 : Vérifier à la main**

Lancer le backend et le front (voir la section « Développement local » du README, avec `ADMIN_EMAILS` et `ADMIN_SECRET` exportés et `ADMIN_COOKIE_SECURE=false`), ouvrir <http://localhost:5173/admin>, saisir l'adresse, lire le code dans les journaux du backend (`MAIL_BACKEND=console` affiche l'objet, qui contient le code), le saisir, et vérifier le message « Connecté en tant que… ».

- [ ] **Step 7 : Commit**

```bash
git add frontend/src/Admin.svelte frontend/src/components/AdminLogin.svelte frontend/src/main.ts frontend/src/app.css
git commit -m "feat(frontend): écran de connexion à l'administration"
```

---

### Task 12 : Tableau de la saison et édition

**Files:**
- Create: `frontend/src/components/AdminBookingForm.svelte`
- Modify: `frontend/src/Admin.svelte`
- Modify: `frontend/src/app.css`

**Interfaces:**
- Consumes: `saveBooking`, `deleteBooking`, `closeSession` (Task 10), `groupByMonth` et `formatTuesday` (`lib/dates.ts`, existants).
- Produces: `AdminBookingForm.svelte` avec les props `{ date: string; theme: string; booking: AdminBooking | null; onsaved: () => void; oncancel: () => void }`.

> Composant distinct de `BookingDialog.svelte` : ni Turnstile, ni champ piège, ni export `.ics` ici.

- [ ] **Step 1 : Écrire le formulaire**

Créer `frontend/src/components/AdminBookingForm.svelte` :

```svelte
<script lang="ts">
  import { saveBooking } from '../lib/admin';
  import { formatTuesday } from '../lib/dates';
  import type { AdminBooking } from '../lib/types';

  let {
    date,
    theme,
    booking,
    onsaved,
    oncancel,
  }: {
    date: string;
    theme: string;
    booking: AdminBooking | null;
    onsaved: () => void;
    oncancel: () => void;
  } = $props();

  let name = $state(booking?.name ?? '');
  let phone = $state(booking?.phone ?? '');
  let error = $state('');
  let busy = $state(false);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    error = '';
    if (name.trim().length < 2) {
      error = "Merci d'indiquer un nom (2 à 80 caractères).";
      return;
    }
    busy = true;
    const outcome = await saveBooking(date, { name, phone: phone.trim() || null });
    busy = false;
    if (outcome.kind === 'ok') {
      onsaved();
      return;
    }
    error = outcome.kind === 'unauthorized' ? 'Session expirée, reconnectez-vous.' : outcome.message;
  }
</script>

<form class="admin-form" onsubmit={submit}>
  <h3>{formatTuesday(date)} — {theme}</h3>
  <label for="form-name">Nom</label>
  <input id="form-name" bind:value={name} required disabled={busy} />
  <label for="form-phone">Téléphone (facultatif)</label>
  <input id="form-phone" bind:value={phone} inputmode="tel" disabled={busy} />
  <div class="actions">
    <button type="submit" disabled={busy}>Enregistrer</button>
    <button type="button" class="link" onclick={oncancel} disabled={busy}>Annuler</button>
  </div>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</form>
```

- [ ] **Step 2 : Afficher le tableau dans `Admin.svelte`**

Remplacer la branche `{:else if calendar}` de `frontend/src/Admin.svelte` par le tableau, et compléter le `<script>` :

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import AdminBookingForm from './components/AdminBookingForm.svelte';
  import AdminLogin from './components/AdminLogin.svelte';
  import { closeSession, deleteBooking, fetchAdminBookings } from './lib/admin';
  import { formatTuesday, groupByMonth } from './lib/dates';
  import type { AdminCalendar, AdminSessionItem } from './lib/types';

  let calendar = $state<AdminCalendar | null>(null);
  let connected = $state(false);
  let loadError = $state('');
  let editing = $state<AdminSessionItem | null>(null);

  const groups = $derived(calendar ? groupByMonth(calendar.sessions) : []);

  async function load() {
    const outcome = await fetchAdminBookings();
    if (outcome.kind === 'ok') {
      calendar = outcome.value;
      connected = true;
      loadError = '';
      return;
    }
    connected = false;
    calendar = null;
    loadError = outcome.kind === 'error' ? outcome.message : '';
  }

  async function remove(date: string, name: string) {
    if (!confirm(`Supprimer la réservation de ${name} pour le ${formatTuesday(date)} ?`)) return;
    const outcome = await deleteBooking(date);
    if (outcome.kind === 'error') {
      loadError = outcome.message;
      return;
    }
    await load();
  }

  async function logout() {
    await closeSession();
    await load();
  }

  function saved() {
    editing = null;
    load();
  }

  onMount(load);
</script>

<div class="page admin">
  {#if !connected}
    <AdminLogin onconnected={load} />
    {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}
  {:else if calendar}
    <header class="admin-head">
      <h1>Administration</h1>
      <p>
        Connecté : {calendar.email}
        <button type="button" class="link" onclick={logout}>Se déconnecter</button>
      </p>
    </header>

    {#if loadError}<p class="error" role="alert">{loadError}</p>{/if}

    {#each groups as group (group.key)}
      <section aria-labelledby="admin-{group.key}">
        <h2 id="admin-{group.key}">{group.label}</h2>
        <ul class="admin-list">
          {#each group.items as session (session.date)}
            <li>
              <div class="who">
                <strong>{formatTuesday(session.date)}</strong>
                <span class="theme">{session.theme}</span>
                {#if session.booking}
                  <span class="name">{session.booking.name}</span>
                  <span class="phone">{session.booking.phone ?? 'téléphone non renseigné'}</span>
                {:else}
                  <span class="free">libre</span>
                {/if}
              </div>
              <div class="actions">
                <button type="button" onclick={() => (editing = session)}>
                  {session.booking ? 'Modifier' : 'Ajouter'}
                </button>
                {#if session.booking}
                  <button
                    type="button"
                    class="danger"
                    onclick={() => remove(session.date, session.booking!.name)}
                  >
                    Supprimer
                  </button>
                {/if}
              </div>
              {#if editing?.date === session.date}
                <AdminBookingForm
                  date={session.date}
                  theme={session.theme}
                  booking={session.booking}
                  onsaved={saved}
                  oncancel={() => (editing = null)}
                />
              {/if}
            </li>
          {/each}
        </ul>
      </section>
    {/each}

    {#if calendar.orphans.length > 0}
      <section aria-labelledby="orphans">
        <h2 id="orphans">Réservations hors programme</h2>
        <p class="notice">
          Ces mardis ne figurent plus dans le programme de la saison. Vous pouvez les supprimer.
        </p>
        <ul class="admin-list">
          {#each calendar.orphans as orphan (orphan.date)}
            <li>
              <div class="who">
                <strong>{formatTuesday(orphan.date)}</strong>
                <span class="name">{orphan.name}</span>
              </div>
              <div class="actions">
                <button type="button" class="danger" onclick={() => remove(orphan.date, orphan.name)}>
                  Supprimer
                </button>
              </div>
            </li>
          {/each}
        </ul>
      </section>
    {/if}
  {/if}
</div>
```

- [ ] **Step 3 : Ajouter les styles**

Dans `frontend/src/app.css`, à la suite des styles de la Task 11 :

```css
.admin-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.admin-list li {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 0.5rem 1rem;
  padding: 0.6rem 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.12);
}

.admin-list .who {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem 0.75rem;
}

.admin-list .free {
  font-style: italic;
}

.admin-form {
  flex-basis: 100%;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 0.75rem 0;
}
```

- [ ] **Step 4 : Vérifier**

Run: `cd frontend && npm run check && npm test && npm run build`
Expected: PASS

- [ ] **Step 5 : Vérifier à la main le cycle complet**

Backend + front lancés : sur <http://localhost:5173/admin>, se connecter, **ajouter** une réservation sur un mardi libre, vérifier qu'elle apparaît sur la page publique comme réservée, la **modifier**, la **supprimer**, vérifier que le mardi redevient disponible côté public, puis **se déconnecter** et constater le retour à l'écran de connexion.

- [ ] **Step 6 : Commit**

```bash
git add frontend/src/Admin.svelte frontend/src/components/AdminBookingForm.svelte frontend/src/app.css
git commit -m "feat(frontend): tableau de la saison et édition des réservations"
```

---

### Task 13 : Documentation et déploiement

**Files:**
- Modify: `README.md`
- Modify: `.env.dev.sh` (non versionné — modification locale seulement)

**Interfaces:**
- Consumes: les réglages de la Task 1.
- Produces: rien de consommé par du code.

- [ ] **Step 1 : Compléter le bloc de développement local**

Dans `README.md`, section « Développement local », ajouter aux variables exportées pour l'API :

```
  ADMIN_EMAILS=admin@example.org ADMIN_SECRET=dev-secret-non-sensible \
  ADMIN_COOKIE_SECURE=false
```

- [ ] **Step 2 : Remplacer « Suites envisagées » par « Administration »**

Dans `README.md`, remplacer toute la section `## Suites envisagées` par :

```markdown
## Administration

<https://crf.fsspnantes.fr/admin> permet aux organisateurs d'ajouter, de remplacer ou de
supprimer une réservation à la main, sans passer par `psql`.

La connexion se fait sans mot de passe : on saisit son adresse, on reçoit un **code à six
chiffres** valable dix minutes et utilisable une seule fois, on le saisit. Cinq erreurs
détruisent le code, et trois demandes par heure et par adresse sont autorisées.

Seules les adresses listées dans `ADMIN_EMAILS` peuvent se connecter. Cette liste est
**distincte** d'`ORGANIZER_EMAILS`, qui ne fait que recevoir les notifications de réservation.
Retirer une adresse d'`ADMIN_EMAILS` déconnecte la personne au redémarrage suivant, sans autre
action. Changer `ADMIN_SECRET` déconnecte tout le monde, immédiatement.

| Variable | Rôle |
|---|---|
| `ADMIN_EMAILS` | adresses autorisées, séparées par des virgules |
| `ADMIN_SECRET` | secret de signature des codes et des cookies — `Secret` Kubernetes, jamais en clair |
| `ADMIN_SESSION_DAYS` | durée de la session (30 par défaut) |
| `ADMIN_COOKIE_SECURE` | `false` en développement local, `true` (défaut) en production |

Générer le secret : `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

Le programme de la saison ne se modifie **pas** depuis cette page : il reste dans
`backend/app/sessions.yaml` (voir « Modifier le programme de la saison » ci-dessus).
```

- [ ] **Step 3 : Compléter le script local**

Dans `.env.dev.sh` (ignoré par git, à faire sur sa machine), ajouter avant `uv run alembic` :

```bash
export ADMIN_EMAILS="admin@example.org"
export ADMIN_SECRET="dev-secret-non-sensible"
export ADMIN_COOKIE_SECURE="false"
```

- [ ] **Step 4 : Vérifier l'image complète**

Run: `docker compose up --build` puis ouvrir <http://localhost:8000/admin>
Expected: la page de connexion s'affiche — c'est ce qui valide la route `GET /admin` de la Task 9 sur le front compilé, que le serveur de développement Vite masquait.

- [ ] **Step 5 : Commit**

```bash
git add README.md
git commit -m "docs: administration des réservations"
```

- [ ] **Step 6 : Déploiement (hors dépôt)**

Dans le dépôt `homelan`, `cluster/apps/crf/deployment.yaml` : ajouter `ADMIN_EMAILS` en variable d'environnement et `ADMIN_SECRET` via un `Secret` Kubernetes. Mettre ensuite à jour le tag d'image comme d'habitude et appliquer. La section « Opérations courantes » de `cluster/apps/crf/Readme.md` peut renvoyer vers `/admin` au lieu des requêtes SQL.

---

## Vérification finale

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd ../frontend && npm run check && npm test && npm run build
```

Puis relire la spec (`docs/superpowers/specs/2026-09-18-crf-apero-admin-design.md`) et vérifier
point par point que le comportement livré y correspond.
