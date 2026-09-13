# Cloudflare Turnstile

Turnstile protège le formulaire contre les robots. **Aucun domaine n'est transféré chez
Cloudflare** : le DNS de fsspnantes.fr reste chez PlanetHoster. Durée : ~10 minutes.

## 1. Créer le compte

1. Aller sur <https://dash.cloudflare.com/sign-up>, saisir une adresse e-mail et un mot de passe.
2. Valider l'adresse via le lien reçu par e-mail.
3. Si l'assistant d'accueil propose d'« ajouter un site » ou un domaine : **ignorer** cette
   étape (lien « Skip » ou retour au tableau de bord).
4. Activer la double authentification : *My Profile → Authentication*.

## 2. Créer le widget

1. Menu de gauche : **Turnstile** (selon la version du tableau de bord, il peut être rangé sous
   *Application security* ou *Protect & Connect*).
2. **Add widget** :
   - *Widget name* : `CRF apéro`
   - *Hostname management* → **Add hostnames** : `crf.fsspnantes.fr` puis `localhost`
   - *Widget Mode* : **Managed**
   - *Pre-clearance* : **No**
3. **Create**.

## 3. Récupérer les clés

| Clé | Où la mettre |
|---|---|
| **Site Key** (publique) | `TURNSTILE_SITE_KEY` dans `homelan/cluster/apps/crf/configmap.yaml` |
| **Secret Key** | saisie dans `homelan/cluster/apps/crf/create-sealed-secret-crf.sh` — **jamais commitée en clair** |

## 4. Vérifier après déploiement

- Sur <https://crf.fsspnantes.fr>, ouvrir « Je m'en charge » : le widget s'affiche puis se valide.
- Tableau de bord Turnstile → *Analytics* du widget : les résolutions apparaissent.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| Widget en erreur « domaine non autorisé » (code 110200) | Hostname manquant dans le widget |
| Widget absent, erreur CSP dans la console du navigateur | En-tête CSP modifié : `script-src` et `frame-src` doivent autoriser `https://challenges.cloudflare.com` |
| Toutes les réservations répondent 403 | Secret Key erronée dans le sealed secret |

## Changer la clé secrète

Widget → *Settings* → **Rotate secret key**, puis relancer `create-sealed-secret-crf.sh`,
`kubectl apply -f sealed-secret-crf.yaml` et `kubectl rollout restart deployment/crf-apero -n crf`.
