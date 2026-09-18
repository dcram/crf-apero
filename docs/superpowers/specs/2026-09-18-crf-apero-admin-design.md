# CRF Apéro — Administration des réservations

Date : 2026-09-18
État : validé, prêt pour le plan d'implémentation

## Objet

Donner aux organisateurs une page protégée pour **ajouter, remplacer et supprimer** une
réservation à la main, sans passer par `psql`. Aujourd'hui, libérer un mardi ou corriger une
saisie impose une requête SQL sur la base `crf` (voir « Opérations courantes » dans le dépôt
`homelan`, `cluster/apps/crf/Readme.md`).

L'authentification se fait par **code à six chiffres envoyé par e-mail** à une liste d'adresses
connue d'avance.

## Périmètre

Dans le périmètre :

- authentification des organisateurs par code à usage unique ;
- session admin portée par un cookie signé ;
- écran `/admin` listant la saison complète et permettant les trois opérations.

Hors périmètre, décidé explicitement :

- **l'édition du programme.** `backend/app/sessions.yaml` reste la source de vérité des mardis
  et des thèmes ; il est chargé au démarrage et n'est pas modifiable en ligne. `app/sessions.py`
  n'est pas touché. Corriger un thème reste un cycle commit → image → déploiement.
- **toute notification e-mail des actions d'admin.** Le mail aux organisateurs ne signale qu'une
  réservation entrante de paroissien. `build_notification` et le gabarit existant ne changent pas ;
  `app/mailer.py` gagne seulement l'envoi du code.
- **le journal d'audit.** Deux à cinq organisateurs qui se parlent ne le justifient pas.
- **plusieurs réservations le même mardi.** La contrainte `uq_bookings_tuesday` est conservée
  telle quelle : un mardi, un réservataire.

## Choix d'authentification

AWS Cognito et une fédération OIDC (Google Workspace `fsspnantes.fr`) ont été envisagés puis
écartés : pour deux à cinq organisateurs connus d'avance, ils ajoutent une dépendance externe,
un flux OAuth et une console à administrer, là où l'infrastructure d'envoi (AWS SES) et la liste
d'adresses existent déjà dans l'application.

Le **code à six chiffres** a été préféré au **lien magique** pour deux raisons :

1. les scanners d'e-mail (Outlook Safe Links, antivirus) pré-visitent les URL et consomment le
   jeton avant l'humain, ce qui produit des « lien expiré » impossibles à diagnostiquer ;
2. le cas réel est « je lis mes mails sur mon téléphone, j'administre depuis mon PC » : un code se
   recopie d'un appareil à l'autre, un lien ouvre la session sur le mauvais appareil.

En contrepartie, six chiffres ne font que 10⁶ possibilités : la **limite de cinq tentatives** et
la durée de vie de dix minutes ne sont pas des options de confort, ce sont elles qui rendent
l'entropie suffisante.

Risque accepté : qui contrôle la boîte mail d'un organisateur contrôle l'administration. Avec un
Google Workspace protégé par MFA et un enjeu limité à la gestion d'apéros, c'est acceptable.

## Modèle de données

Une seule table ajoutée, migration Alembic `0002` :

```
admin_codes
  id          Integer, PK
  email       Text, not null, index
  code_hash   Text, not null
  expires_at  DateTime(timezone=True), not null
  attempts    Integer, not null, default 0
  created_at  DateTime(timezone=True), not null, server_default now()
```

`code_hash` vaut `HMAC-SHA256(admin_secret, email + code)` en hexadécimal. Le code n'est jamais
stocké en clair, et un hachage simple ne suffirait pas : six chiffres, ce sont 10⁶ préimages
qu'un `sha256` épuise en une seconde sur un dump de base. Le secret serveur rend le dump
inexploitable seul.

Les codes expirés sont purgés à l'occasion d'une nouvelle demande. Aucune tâche de fond pour une
table qui contiendra trois lignes.

La table `bookings` ne change pas.

## Session

La session est portée par un **cookie signé sans état**, pas par une table de sessions :
`email|expiration|HMAC-SHA256(admin_secret, email|expiration)`, en base64url.

Ce choix donne la révocation gratuitement : `require_admin` revalide l'adresse contre
`admin_emails` **à chaque requête**, donc retirer quelqu'un de la variable d'environnement le
déconnecte au déploiement suivant, sans table ni session serveur. Changer `ADMIN_SECRET`
déconnecte tout le monde — c'est le bouton d'urgence.

Aucune dépendance nouvelle : `hmac`, `hashlib`, `secrets` et `base64` de la bibliothèque
standard suffisent, dans l'esprit des dépendances actuelles du backend.

Cookie `crf_admin` : `HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, durée `admin_session_days`.

## Configuration

Ajouts à `app/config.py` :

| Réglage | Type | Défaut | Rôle |
|---|---|---|---|
| `admin_emails` | `list[str]` | — (obligatoire) | allowlist ; même validateur `_split_emails` que `organizer_emails` |
| `admin_secret` | `str` | — (obligatoire) | HMAC des codes **et** signature des cookies |
| `admin_session_days` | `int` | `30` | durée de vie du cookie |
| `admin_code_ttl_minutes` | `int` | `10` | durée de vie d'un code |
| `admin_code_max_attempts` | `int` | `5` | tentatives avant destruction du code |
| `admin_codes_per_hour` | `int` | `3` | demandes de code par adresse et par heure |
| `admin_cookie_secure` | `bool` | `True` | passé à `false` en dev local, sinon le cookie ne part pas sur `http://` |

`admin_emails` est **distinct** d'`organizer_emails` : être notifié des réservations et pouvoir
les supprimer sont deux droits différents.

`admin_secret` est obligatoire et sans défaut : un déploiement qui l'oublie ne démarre pas, comme
pour `turnstile_secret`. Un échec bruyant vaut mieux qu'une page d'administration silencieusement
ouverte. Génération : `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Flux d'authentification

1. **`POST /api/admin/login`** `{email}`
   - rate-limit : `admin_codes_per_hour` par adresse, via une **seconde instance** de
     `RateLimiter` ; celle des réservations reste dédiée aux IP ;
   - si l'adresse est dans `admin_emails` : suppression de ses codes précédents, tirage de six
     chiffres par `secrets.randbelow(1_000_000)` (formatés sur six caractères, zéros compris),
     enregistrement du HMAC avec `expires_at = maintenant + admin_code_ttl_minutes`, envoi du mail ;
   - **réponse `204` dans tous les cas**, adresse inconnue comprise : la page ne doit pas révéler
     qui est organisateur. Une adresse hors allowlist ne déclenche aucun envoi.
2. **`POST /api/admin/session`** `{email, code}`
   - comparaison par `hmac.compare_digest` ;
   - échec : `attempts += 1`, et au `admin_code_max_attempts`-ième le code est **supprimé** ;
   - code absent, expiré ou épuisé : `403`, message unique et non discriminant ;
   - succès : code consommé (supprimé), cookie posé, `204`.
3. **`Depends(require_admin)`** sur toutes les routes `/api/admin/*` sauf `login` et `session` :
   vérifie la signature, l'expiration, et la présence de l'adresse dans `admin_emails`.
   Sinon `401`.
4. **`DELETE /api/admin/session`** : cookie effacé, `204`.

## API d'administration

Routeur séparé dans un nouveau `app/admin.py` — `app/api.py` reste le domaine public et fait
déjà 113 lignes.

- **`GET /api/admin/bookings`** — la saison complète telle que `sessions.yaml` la décrit,
  **passé inclus** : `deps.meetings` en entier, pas `deps.upcoming()`, joint aux `bookings`.
  Une entrée par mardi : `date`, `theme`, et `booking` (`name`, `phone`, `created_at`) ou `null`.
  Une réservation ne correspondant à aucun mardi du programme (date retirée du YAML après coup)
  est renvoyée dans une liste `orphans` distincte plutôt que masquée : sinon elle devient
  invisible et insupprimable.
- **`PUT /api/admin/bookings/{date}`** `{name, phone}` — couvre **l'ajout et le remplacement** :
  mardi libre → insertion, mardi pris → écrasement du nom et du téléphone. Opération idempotente,
  qui évite deux endpoints faisant 90 % de la même chose, et qui satisfait toujours
  `uq_bookings_tuesday`. La date doit exister dans le programme (`404` sinon) mais **peut être
  passée**. Réponse `200` avec l'état résultant.
- **`DELETE /api/admin/bookings/{date}`** — `204`, ou `404` s'il n'y a rien à supprimer.

Ni Turnstile, ni rate-limit, ni champ piège sur ces trois routes : le cookie admin est la preuve.

**Validation partagée.** `BookingIn` est scindé : un `BookingFields` porte `name` et `phone` avec
leurs validateurs actuels, `BookingIn` en hérite en ajoutant `turnstile_token` et `website`, et
l'admin utilise `BookingFields`. Les règles de nom et de téléphone restent uniques.

**En-têtes.** `/admin` et `/api/admin/*` renvoient `Cache-Control: no-store` et
`X-Robots-Tag: noindex` : ces réponses contiennent des numéros de téléphone.

## Écran

L'application Svelte n'a pas de routeur et n'en a pas besoin pour une seconde page : `main.ts`
lit `location.pathname` et monte `Admin.svelte` sur `/admin`, `App.svelte` sinon.

Côté serveur, `StaticFiles(html=True)` ne sert pas `index.html` sur un chemin inconnu : une route
explicite `GET /admin` le renvoie. En développement, le fallback SPA de Vite s'en charge déjà.

`Admin.svelte` :

- si `GET /api/admin/bookings` répond `401`, écran de connexion en deux temps — adresse, puis code
  (`inputmode="numeric"`, `autocomplete="one-time-code"`) ;
- sinon, la saison groupée par mois avec le `groupByMonth` existant, une ligne par mardi :
  « Ajouter » si libre, « Modifier » et « Supprimer » si pris ; suppression confirmée ;
- un `401` survenant en cours de session ramène à l'écran de connexion ;
- le formulaire de saisie est un **composant distinct**, pas `BookingDialog.svelte` alourdi de
  conditions : il reprend les champs nom et téléphone sans le widget Turnstile ni le champ piège.

Nouveau client `frontend/src/lib/admin.ts`, sur le modèle de `lib/api.ts`.

## Tests

**Backend** (`tests/test_admin.py`), dans le style existant : `create_app` reçoit un faux mailer,
un `today` figé et une horloge injectable ; la base `crf_test` sert de support.

Authentification :

- code accepté ; code faux ;
- **cinquième tentative : le code est détruit, le bon code ne fonctionne plus** ;
- code expiré ;
- adresse hors allowlist : `204` mais **aucun mail envoyé** ;
- une nouvelle demande invalide la précédente ;
- rate-limit atteint à la quatrième demande.

Session :

- signature falsifiée → `401` ;
- cookie expiré → `401` ;
- **cookie valide mais adresse retirée d'`admin_emails` → `401`** (le test qui prouve la révocation).

Routes métier :

- les trois routes en `401` sans cookie ;
- `GET` liste bien le passé, les mardis libres, et les orphelins ;
- `PUT` : mardi libre → insertion ; mardi pris → écrasement ; date absente du programme → `404` ;
  **date passée → succès** ;
- `DELETE` puis `DELETE` → `204` puis `404` ;
- **aucun e-mail envoyé par `PUT` ni `DELETE`.**

Non-régression : `POST /api/bookings` conserve Turnstile, champ piège et rate-limit après le
découpage de `BookingIn`.

**Frontend** : `lib/admin.test.ts` en vitest, sur le modèle d'`api.test.ts` — correspondance des
statuts, `401` ramenant à l'écran de connexion. Pas de test de rendu : le projet n'en fait pas.

## Déploiement

- `ADMIN_EMAILS`, `ADMIN_SECRET`, `ADMIN_COOKIE_SECURE=false` à ajouter au bloc développement du
  README et au script local `.env.dev.sh` (non versionné).
- Dans `homelan`, `cluster/apps/crf/deployment.yaml` : `ADMIN_SECRET` en `Secret` Kubernetes,
  jamais en clair.
- La section « Suites envisagées » du README est remplacée par une section « Administration »
  décrivant la connexion et les trois opérations.
- La documentation `homelan` « Opérations courantes » pourra renvoyer vers `/admin` au lieu des
  requêtes SQL.
