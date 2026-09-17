# Mail au gestionnaire DNS de fsspnantes.fr

À envoyer **après** l'étape 2 de `aws-ses.md`, en remplaçant `<JETON_1>`, `<JETON_2>`,
`<JETON_3>` par les jetons DKIM affichés par SES, et `<ORGANISATEURS>` par les adresses des
organisateurs.

---

**Objet :** Configuration DNS pour l'application des apéros CRF (crf.fsspnantes.fr)

Bonjour,

Pour le parcours *Commencer – Recommencer dans la Foi*, j'ai développé une petite application
qui permet aux paroissiens de choisir le mardi où ils offrent l'apéro. Elle sera accessible à
l'adresse **crf.fsspnantes.fr** (lien à ajouter sur la page du parcours) et préviendra les
organisateurs par e-mail depuis **crf@fsspnantes.fr**.

Pourriez-vous ajouter les enregistrements suivants dans la zone DNS de fsspnantes.fr
(PlanetHoster) ?

**1. Adresse de l'application**

| Nom | Type | Valeur | TTL |
|---|---|---|---|
| `crf` | A | `57.131.34.159` | 3600 |

**2. Signature des e-mails (DKIM Amazon SES)**

| Nom | Type | Valeur | TTL |
|---|---|---|---|
| `<JETON_1>._domainkey` | CNAME | `<JETON_1>.dkim.amazonses.com` | 3600 |
| `<JETON_2>._domainkey` | CNAME | `<JETON_2>.dkim.amazonses.com` | 3600 |
| `<JETON_3>._domainkey` | CNAME | `<JETON_3>.dkim.amazonses.com` | 3600 |

Ces ajouts ne modifient ni le site, ni la messagerie Google Workspace, ni les envois Brevo :
les enregistrements SPF, MX et DMARC existants restent inchangés.

**3. Adresse crf@fsspnantes.fr (Google Workspace)**

Si vous administrez aussi Google Workspace : pourriez-vous créer un groupe
`crf@fsspnantes.fr` ouvert aux messages extérieurs, avec pour membres : <ORGANISATEURS> ?

Merci beaucoup,

Damien
