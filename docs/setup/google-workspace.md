# Google Workspace — adresse crf@fsspnantes.fr

**Aucune configuration Google n'est nécessaire pour que l'application envoie ses e-mails** : SES
signe les messages avec ses propres clés DKIM, dont les sélecteurs (`<jeton>._domainkey`) ne
rentrent pas en conflit avec celui de Google (`google._domainkey`).

## Recommandé : faire exister l'adresse

Les notifications partent de `crf@fsspnantes.fr` avec un `Reply-To` vers les organisateurs.
Si quelqu'un écrit malgré tout directement à `crf@fsspnantes.fr` et que l'adresse n'existe pas
dans Workspace, son message est rejeté. À faire par l'administrateur Workspace de la paroisse :

### Option A — Groupe (recommandée, plusieurs organisateurs)

1. <https://admin.google.com> → **Annuaire → Groupes → Créer un groupe**.
2. Nom : `CRF apéro` ; adresse e-mail du groupe : `crf@fsspnantes.fr`.
3. Membres : les organisateurs du CRF.
4. Paramètres d'accès → *Qui peut publier des messages* : **Tout le monde sur le Web**
   (sinon les réponses de paroissiens extérieurs au domaine sont refusées).

### Option B — Alias d'un compte existant

<https://admin.google.com> → **Annuaire → Utilisateurs** → choisir l'organisateur →
*Informations sur l'utilisateur* → **Autres adresses e-mail** → ajouter `crf`.

## Vérifier

Envoyer un e-mail depuis une adresse personnelle à `crf@fsspnantes.fr` : il doit arriver chez
les organisateurs.
