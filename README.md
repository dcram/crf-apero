# CRF Apéro

Réservation des apéros du parcours **Commencer – Recommencer dans la Foi** (FSSP Nantes) :
chaque paroissien choisit un mardi de la saison, les organisateurs sont prévenus par e-mail.

Production : <https://crf.fsspnantes.fr> · Spec : `docs/superpowers/specs/2026-09-13-crf-apero-design.md`

## Structure

- `backend/` — API FastAPI (Python 3.13, uv), migrations Alembic, programme `app/sessions.yaml`
- `frontend/` — page Svelte 5 + Vite
- `Dockerfile` — image unique (front compilé servi par FastAPI)
- `docs/setup/` — mise en place de Cloudflare Turnstile, AWS SES, Google Workspace, DNS

## Modifier le programme de la saison

Éditer `backend/app/sessions.yaml` (un mardi par entrée, thème obligatoire), puis :

```bash
cd backend && uv run pytest tests/test_sessions.py
```

Commit sur `main` → la CI publie `ghcr.io/dcram/crf-apero:sha-<commit>` → mettre à jour le tag
dans `homelan/cluster/apps/crf/deployment.yaml` et `kubectl apply`.

## Développement local

```bash
docker compose up -d --wait db

# API (terminal 1)
cd backend
export DATABASE_URL=postgresql+asyncpg://crf:crf@localhost:5433/crf \
  TURNSTILE_SITE_KEY=1x00000000000000000000AA \
  TURNSTILE_SECRET=1x0000000000000000000000000000000AA \
  ORGANIZER_EMAILS=orga@example.org MAIL_REPLY_TO=orga@example.org \
  CONTACT_EMAIL=contact@example.org
uv run alembic upgrade head && uv run uvicorn --factory app.main:create_app --reload

# Front (terminal 2) — http://localhost:5173, /api est relayé vers :8000
cd frontend && npm install && npm run dev
```

Les clés Turnstile ci-dessus sont les clés de test officielles de Cloudflare (toujours valides).
En local, `MAIL_BACKEND=console` (défaut) : l'e-mail n'est pas envoyé, son objet est journalisé.

Image complète : `docker compose up --build` → <http://localhost:8000>.

## Tests

```bash
cd backend && uv run pytest && uv run ruff check . && uv run ruff format --check .
cd frontend && npm run check && npm test
```

Les tests backend utilisent la base `crf_test` du conteneur `db` (`TEST_DATABASE_URL` pour
en changer).

## Publication

- Push sur `main` → image `sha-<7 caractères>`.
- Tag `vX.Y.Z` → image `X.Y.Z` en plus.
- La CI n'a aucun accès au cluster : le déploiement se fait depuis le dépôt `homelan`
  (`cluster/apps/crf/Readme.md`).
