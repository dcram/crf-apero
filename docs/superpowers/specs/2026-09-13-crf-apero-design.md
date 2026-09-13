# CRF Apéro — Design

> Date : 2026-09-13 · Statut : en relecture

## 1. Contexte et objectif

Le groupe **« Commencer – Recommencer dans la Foi » (CRF)** de la Fraternité Saint-Pierre à
Nantes (<https://fsspnantes.fr/service/parcours-commencer-recommencer-dans-la-foi/>) se réunit
un mardi sur deux : 45 min d'enseignement par un abbé sur un thème, 15 min de questions, puis
30 min de moment convivial (apéro).

Chaque apéro est organisé par **un paroissien différent**, qui apporte les vivres et repart
avec. Le but est de faire se rencontrer paroissiens et catéchumènes.

**L'application** permet à n'importe quel paroissien, via un lien publié sur fsspnantes.fr,
de choisir un mardi libre de la saison, de laisser son nom (et éventuellement son téléphone).
Le mardi devient indisponible pour les autres et les organisateurs du CRF sont prévenus par
e-mail.

### Hors périmètre (v1)

- Interface d'administration (les corrections se font en SQL, cf. §4.3).
- E-mail de confirmation ou de rappel au paroissien (aucun e-mail ne lui est demandé).
- Annulation en libre-service par le paroissien.
- Affichage des noms des personnes inscrites.
- Tests end-to-end navigateur.

## 2. Décisions de cadrage

| Sujet | Décision |
|---|---|
| Programme de la saison | Liste de mardis + thèmes dans `backend/app/sessions.yaml`, versionnée dans le code |
| Administration | Aucune ; corrections en SQL |
| Anti-spam | Cloudflare Turnstile + honeypot + rate limit par IP |
| Domaine | `crf.fsspnantes.fr` (DNS de la paroisse chez PlanetHoster) |
| Données saisies | Nom (obligatoire) + téléphone (facultatif) |
| Notification | E-mail aux organisateurs uniquement |
| Grille publique | Un mardi réservé affiche seulement « Pris » |
| Envoi d'e-mails | AWS SES `eu-west-3`, expéditeur `crf@fsspnantes.fr` |
| Architecture | Front Svelte + API FastAPI dans un même dépôt, **une seule image Docker** |
| Registre | `ghcr.io/dcram/crf-apero` (paquet public) |
| Hébergement | K3S du VPS OVH (dépôt `homelan`), base sur le CloudNativePG `pg-cluster` |

## 3. Architecture

```
Paroissien ──HTTPS──▶ Traefik (K3S) ──▶ Pod crf-apero (FastAPI + front statique)
                                              │
                        ┌─────────────────────┼──────────────────────┐
                        ▼                     ▼                      ▼
             pg-cluster (CNPG, base crf)  Cloudflare Turnstile   AWS SES eu-west-3
                                          (siteverify)           (e-mail organisateurs)
```

- Un seul processus FastAPI (uvicorn) sert l'API sous `/api/*`, le endpoint `/healthz`, et
  les fichiers statiques du front compilé pour toutes les autres routes.
- Pas de CORS : front et API partagent la même origine.

## 4. Données

### 4.1 Programme de la saison — `backend/app/sessions.yaml`

```yaml
sessions:
  - date: 2026-09-22
    theme: "Qui est Dieu ?"
  - date: 2026-10-06
    theme: "La Création et la Chute"
```

Règles de validation, appliquées **au démarrage** (l'application refuse de démarrer si une
règle est violée) et par un test pytest en CI :

- chaque `date` est une date ISO valide et tombe un **mardi** ;
- aucune date en double ;
- chaque `theme` est une chaîne non vide.

Modifier le programme = commit sur ce fichier → nouvelle image → déploiement.

Le fichier livré en v1 contient des sessions d'exemple ; **le programme réel de la saison
2026–2027 est fourni par le porteur du projet avant la mise en production**.

### 4.2 Table `bookings`

```sql
CREATE TABLE bookings (
  id          serial PRIMARY KEY,
  tuesday     date        NOT NULL UNIQUE,
  name        text        NOT NULL,
  phone       text,
  created_at  timestamptz NOT NULL DEFAULT now()
);
```

- Un mardi est **pris** si et seulement si une ligne existe pour sa date.
- La contrainte `UNIQUE` garantit « premier arrivé, premier servi » en cas de clics simultanés.
- Une réservation dont la date ne figure plus dans `sessions.yaml` est ignorée (non affichée).
- Schéma géré par **Alembic** ; `alembic upgrade head` est exécuté au démarrage du conteneur.
- Accès via SQLAlchemy 2 (async) + `asyncpg`.

### 4.3 Opérations manuelles (documentées dans le Readme)

```sql
-- Lister les réservations à venir
SELECT tuesday, name, phone, created_at FROM bookings WHERE tuesday >= current_date ORDER BY tuesday;
-- Libérer un mardi (désistement, erreur)
DELETE FROM bookings WHERE tuesday = '2026-10-06';
```

## 5. Configuration

Variables d'environnement lues au démarrage (pydantic-settings) :

| Variable | Source K8s | Exemple / rôle |
|---|---|---|
| `DATABASE_URL` | Secret | `postgresql+asyncpg://crf:…@pg-cluster-rw.pg.svc.cluster.local:5432/crf` |
| `TURNSTILE_SITE_KEY` | ConfigMap | Clé publique du widget |
| `TURNSTILE_SECRET` | Secret | Clé secrète de vérification |
| `ORGANIZER_EMAILS` | ConfigMap | Liste séparée par des virgules |
| `MAIL_FROM` | ConfigMap | `crf@fsspnantes.fr` |
| `MAIL_REPLY_TO` | ConfigMap | Adresse des organisateurs |
| `AWS_REGION` | ConfigMap | `eu-west-3` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Secret | Utilisateur IAM `ses-crf` |
| `EVENT_INFO` | ConfigMap | Texte libre affiché (horaire, lieu) |
| `APERO_START_TIME` | ConfigMap | `21:30` — heure de début de l'apéro (`HH:MM`), utilisée pour le `.ics` (durée 30 min) |
| `CONTACT_EMAIL` | ConfigMap | Contact affiché en cas d'erreur |
| `MAIL_BACKEND` | ConfigMap | `ses` (prod) ou `console` (dev : e-mail écrit dans les logs) |
| `TIMEZONE` | ConfigMap | `Europe/Paris` (défaut) |

Les valeurs réelles (destinataires, horaire, lieu) sont renseignées dans le dépôt `homelan`
au moment du déploiement.

## 6. API

### 6.1 `GET /api/calendar`

Aucune donnée personnelle. Ne renvoie que les sessions dont la date est **strictement
postérieure** à la date du jour (fuseau `TIMEZONE`), triées par date.

```json
{
  "event_info": "Mardi 20h30 – Sainte-Élisabeth, 43 rue de Coulmiers",
  "contact_email": "…",
  "apero_start_time": "21:30",
  "turnstile_site_key": "…",
  "sessions": [
    { "date": "2026-09-22", "theme": "Qui est Dieu ?", "available": false },
    { "date": "2026-10-06", "theme": "La Création et la Chute", "available": true }
  ]
}
```

### 6.2 `POST /api/bookings`

Corps :

```json
{ "date": "2026-10-06", "name": "Jean Dupont", "phone": "06 12 34 56 78",
  "turnstile_token": "…", "website": "" }
```

Traitement, dans cet ordre :

| # | Contrôle | Échec → |
|---|---|---|
| 1 | Honeypot : `website` non vide | `201` factice, rien n'est écrit ni envoyé |
| 2 | Rate limit : 5 requêtes / heure / IP (slowapi, mémoire) | `429` |
| 3 | Validation : `name` 2–80 caractères après trim ; `phone` facultatif — après suppression des espaces, points et tirets, doit correspondre à `0[1-9]\d{8}` ou `\+33[1-9]\d{8}` ; stocké tel que normalisé (sans séparateurs) | `422` |
| 4 | Turnstile `siteverify` (httpx, timeout 5 s, `remoteip` transmise) | jeton invalide `403` ; Cloudflare injoignable `503` |
| 5 | `date` présente dans `sessions.yaml` et strictement future | `404` |
| 6 | `INSERT` dans `bookings` | violation d'unicité `409` |
| 7 | Envoi de l'e-mail aux organisateurs | voir §6.3 |

Succès : `201` avec `{ "date": "…", "theme": "…", "name": "…" }`.

Les erreurs renvoient `{ "detail": "<message en français affichable>" }`.

**IP client** : lue depuis `X-Forwarded-For` (uvicorn `--proxy-headers`, `--forwarded-allow-ips`
limité au réseau des pods). Vérifier au déploiement que Traefik K3S transmet l'IP réelle
(`externalTrafficPolicy: Local` sur le service Traefik) ; à défaut, le rate limit s'applique
à une IP partagée et doit être relevé.

### 6.3 E-mail aux organisateurs

- Envoyé via l'API **SES v2** (`boto3`, `send_email`) après commit de la réservation, dans une
  tâche d'arrière-plan FastAPI.
- De `MAIL_FROM`, à `ORGANIZER_EMAILS`, `Reply-To: MAIL_REPLY_TO`.
- Objet : `[CRF] Apéro du mardi 6 octobre 2026 : Jean Dupont`.
- Corps texte + HTML simple : date, thème, nom, téléphone (ou « non renseigné »).
- **En cas d'échec** : la réservation est conservée, l'erreur est journalisée au niveau
  `ERROR`, pas de renvoi automatique. La base fait foi (§4.3).

### 6.4 Divers

- `GET /healthz` : `200` si la base répond.
- En-têtes de sécurité : CSP (scripts et frames autorisés uniquement depuis
  `challenges.cloudflare.com`, `frame-ancestors 'self' https://fsspnantes.fr https://*.fsspnantes.fr`),
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`.
- Les numéros de téléphone ne sont jamais écrits dans les logs.

## 7. Interface

### 7.1 Principes

- Mobile d'abord ; texte ≥ 17 px ; contraste WCAG AA ; grandes zones tactiles.
- Une seule page, aucun compte.
- Style cohérent avec fsspnantes.fr : bleu marine, crème, blanc ; titres en serif classique ;
  polices auto-hébergées (pas de Google Fonts). Pas de logo FSSP sans accord de la paroisse.

### 7.2 Page

1. En-tête : « Apéro des CRF · 2026–2027 », court texte expliquant le rôle de l'organisateur
   de l'apéro, puis `event_info`.
2. Grille des mardis à venir, regroupés par mois (1 colonne en mobile, 2–3 sur ordinateur).
   Chaque carte : « Mardi 6 octobre », thème, et soit un bouton **« Je m'en charge »**,
   soit un badge **« Pris »** (carte grisée, non cliquable).
3. Clic sur « Je m'en charge » → fenêtre (`<dialog>` ; panneau montant du bas en mobile) :
   rappel date + thème, champ **Nom**, champ **Téléphone (facultatif)**, widget Turnstile,
   champ honeypot invisible, bouton **« Confirmer »**.
4. Succès : « Merci Jean ! Vous accueillez l'apéro du mardi 6 octobre. Les organisateurs sont
   prévenus. » + bouton **« Ajouter à mon agenda »** (fichier `.ics` généré côté client :
   événement « Apéro CRF – je m'en charge » le mardi à `apero_start_time`, fuseau
   `Europe/Paris`, durée 30 min, description = thème + `event_info`).
   La grille est rechargée à la fermeture.

### 7.3 États

| Situation | Affichage |
|---|---|
| Chargement | Cartes « squelette » |
| `409` | Message dans la fenêtre, rechargement de la grille (la carte passe à « Pris ») |
| `403` | « La vérification anti-robot a échoué, merci de réessayer. » (widget réinitialisé) |
| `429` | « Trop de tentatives, réessayez dans un moment. » |
| `503` / réseau | Message d'indisponibilité + `contact_email` |
| Aucun mardi libre | « Tous les apéros de la saison ont trouvé preneur, merci ! » |

### 7.4 Accessibilité

`lang="fr"`, navigation clavier complète, focus piégé dans la fenêtre et restitué à la
fermeture, messages annoncés via `aria-live`.

### 7.5 Technique

Svelte 5 + Vite + TypeScript, CSS pur avec variables, aucune bibliothèque de composants.
Le build produit des fichiers statiques copiés dans l'image et servis par FastAPI.

## 8. Organisation du dépôt

```
crf-apero/
├── backend/
│   ├── pyproject.toml          # uv, ruff, pytest
│   ├── app/
│   │   ├── main.py             # app FastAPI, montage statique, en-têtes, /healthz
│   │   ├── config.py           # pydantic-settings
│   │   ├── sessions.py         # chargement + validation de sessions.yaml
│   │   ├── sessions.yaml
│   │   ├── db.py               # engine, modèle Booking
│   │   ├── api.py              # /api/calendar, /api/bookings
│   │   ├── turnstile.py        # vérification siteverify
│   │   └── mailer.py           # backends ses / console
│   ├── alembic/
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/
├── Dockerfile                  # node:22 (build front) → python:3.13-slim (uv), non-root
├── compose.yaml                # dev : postgres + app, clés Turnstile de test, MAIL_BACKEND=console
├── docs/
│   ├── setup/                  # guides services externes (§11)
│   └── superpowers/specs/
└── .github/workflows/
    ├── ci.yml
    └── release.yml
```

## 9. Tests

### Backend (pytest)

Exécutés contre un **vrai PostgreSQL** (service container en CI, `compose` en local).

- `sessions.yaml` : fichier livré valide ; rejet d'une date non-mardi, d'un doublon, d'un
  thème vide.
- `GET /api/calendar` : sessions passées exclues, `available` reflète la table.
- `POST /api/bookings` : succès `201` + e-mail envoyé (faux mailer) ; second envoi même date
  `409` ; honeypot → `201` sans écriture ni e-mail ; `422` (nom, téléphone) ; `404` (date
  passée, date inconnue) ; rate limit `429`.
- Turnstile simulé avec `respx` : jeton valide, invalide (`403`), timeout (`503`).
- Échec du mailer : réservation conservée, réponse `201`, log `ERROR`.

### Frontend (vitest)

Formatage français des dates, regroupement par mois, génération du fichier `.ics`.
`svelte-check` en CI.

### Vérification manuelle

`docker compose up`, réservation de bout en bout avec les clés Turnstile de test de
Cloudflare (site key `1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA`).

## 10. CI/CD et déploiement

### 10.1 GitHub Actions (`dcram/crf-apero`)

- **`ci.yml`** (pull requests et push) : ruff + pytest (service Postgres) ; `svelte-check`,
  vitest, build front ; `docker build` sans push.
- **`release.yml`** (push sur `main` et tags `v*`) : build et push vers
  `ghcr.io/dcram/crf-apero` avec le tag `sha-<7 caractères>` ; en plus `X.Y.Z` pour un tag
  `vX.Y.Z`. Authentification par `GITHUB_TOKEN`. Pas de tag `latest` utilisé en production.
- Le paquet GHCR est rendu **public** (l'image ne contient aucun secret) : pas
  d'`imagePullSecret` côté cluster.
- **La CI n'accède pas au cluster.** Le déploiement reste manuel depuis `homelan`
  (mise à jour du tag d'image puis `kubectl apply`).

### 10.2 Manifests dans `homelan`

`cluster/apps/crf/` :

- `namespace.yaml` — namespace `crf`
- `configmap.yaml` — variables non sensibles (§5)
- `sealed-secret-crf.yaml` — `DATABASE_URL`, `TURNSTILE_SECRET`, clés IAM `ses-crf`
- `deployment.yaml` — 1 replica ; requests 50m / 128Mi, limit mémoire 256Mi ; probes
  `/healthz` ; `runAsNonRoot`, `readOnlyRootFilesystem` (volume `emptyDir` sur `/tmp`)
- `service.yaml`, `certificate.yaml` et `ingress.yaml` — `crf.fsspnantes.fr`,
  `letsencrypt-prod` (HTTP-01), Traefik `websecure`
- `create-sealed-secret-crf.sh` — non commité (motif déjà dans le `.gitignore` de `homelan`)
- `Readme.md` — procédure de déploiement, requêtes SQL du §4.3

`cluster/apps/cloudnative-pg/` :

- rôle `crf` ajouté dans `cluster-postgres.yaml`
- `database-crf.yaml`, `sealed-secret-crf-db.yaml`

Mise à jour d'`ARCHITECTURE.md` (dont le schéma mermaid §1) et de `CLAUDE.md` de `homelan`
dans le même commit.

Sauvegardes : la base `crf` est couverte par les backups CNPG existants vers S3.

### 10.3 Ordre de mise en service

1. Mail au webmaster de la paroisse : enregistrement A `crf` + 3 CNAME DKIM SES (+ alias
   `crf@` Google Workspace).
2. Création du widget Cloudflare Turnstile, de l'identité SES et de l'utilisateur IAM.
3. Génération des sealed secrets ; rôle et base CNPG.
4. Application des manifests ; attente de l'émission du certificat (après propagation DNS).
5. Réservation de test réelle (vérification de la réception de l'e-mail), puis suppression
   en SQL.
6. Ajout du lien sur la page du parcours CRF de fsspnantes.fr.

## 11. Mise en place des services externes

Chaque service fait l'objet d'un guide pas à pas dans `docs/setup/`, rédigé pendant
l'implémentation.

### 11.1 `docs/setup/cloudflare-turnstile.md`

- Création d'un compte gratuit sur dash.cloudflare.com. **Le domaine n'est pas transféré chez
  Cloudflare** : le DNS reste chez PlanetHoster.
- Section Turnstile → *Add widget* : nom « CRF apéro », hostnames `crf.fsspnantes.fr` et
  `localhost`, mode *Managed*.
- Récupération de la site key (ConfigMap) et de la secret key (sealed secret).

### 11.2 `docs/setup/aws-ses.md`

- Console SES `eu-west-3` (compte déjà sorti du bac à sable) → *Identities* → *Create
  identity* → domaine `fsspnantes.fr`, Easy DKIM RSA 2048 bits → 3 enregistrements CNAME à
  transmettre au webmaster.
- Le SPF existant n'est pas modifié ; l'alignement DMARC est assuré par DKIM (politique
  actuelle de la paroisse : `p=none`).
- Utilisateur IAM `ses-crf`, policy limitée à `ses:SendEmail` sur l'identité
  `fsspnantes.fr` avec la condition `ses:FromAddress = crf@fsspnantes.fr` (le compte AWS ne
  peut ainsi pas envoyer au nom d'une autre adresse de la paroisse).
- Création de la clé d'accès, saisie dans `create-sealed-secret-crf.sh`.
- Vérification : envoi de test depuis la console SES.

### 11.3 `docs/setup/google-workspace.md`

- Aucune configuration obligatoire : SES envoie sans passer par Google, et les sélecteurs
  DKIM SES ne rentrent pas en conflit avec `google._domainkey`.
- Recommandé : l'administrateur Workspace de la paroisse crée `crf@fsspnantes.fr` comme alias
  ou groupe redirigeant vers les organisateurs, afin que réponses et rebonds ne soient pas
  perdus.

### 11.4 `docs/setup/mail-webmaster.md`

Mail prêt à envoyer au gestionnaire DNS de la paroisse, listant l'enregistrement A, les
CNAME DKIM (valeurs à compléter après création de l'identité SES) et la demande d'alias.

## 12. Sécurité et données personnelles

- Données collectées : nom, téléphone facultatif, date de création. Aucune adresse IP stockée.
- Aucune donnée personnelle exposée publiquement ; seuls les organisateurs reçoivent nom et
  téléphone.
- Mention en bas de page : finalité (organisation des apéros CRF), destinataires
  (organisateurs), contact pour suppression (`contact_email`).
- Secrets uniquement dans des sealed secrets ; utilisateur IAM à privilège minimal.
