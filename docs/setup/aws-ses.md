# AWS SES — envoi depuis crf@fsspnantes.fr

L'application envoie les notifications via **SES en `eu-west-3`** (compte déjà sorti du bac à
sable). Il faut : vérifier le domaine `fsspnantes.fr` (3 CNAME DKIM chez PlanetHoster) et créer
un utilisateur IAM limité à l'expéditeur `crf@fsspnantes.fr`. Durée : ~20 minutes + propagation DNS.

Prérequis : AWS CLI configurée avec un profil administrateur.

## 1. Vérifier que le compte peut envoyer

```bash
aws sesv2 get-account --region eu-west-3 --query ProductionAccessEnabled
```

Attendu : `true`.

## 2. Créer l'identité de domaine (Easy DKIM)

```bash
aws sesv2 create-email-identity --region eu-west-3 \
  --email-identity fsspnantes.fr \
  --dkim-signing-attributes NextSigningKeyLength=RSA_2048_BIT

aws sesv2 get-email-identity --region eu-west-3 \
  --email-identity fsspnantes.fr \
  --query 'DkimAttributes.Tokens' --output text
```

La seconde commande affiche **3 jetons**. Chacun donne un enregistrement :

```
<JETON>._domainkey.fsspnantes.fr.   CNAME   <JETON>.dkim.amazonses.com.
```

Reporter les 3 jetons dans `docs/setup/mail-webmaster.md` et envoyer ce mail au gestionnaire DNS.

> Équivalent console : SES → *Configuration → Identities → Create identity → Domain* →
> `fsspnantes.fr`, *Easy DKIM*, *RSA_2048_BIT*, décocher *Publish DNS records to Route53*.

**Ce qui ne change pas** : le SPF (`include:_spf.google.com include:spf.sendinblue.com …`), les
MX Google et le DMARC existant. SES utilise son propre domaine d'enveloppe (`amazonses.com`) et
l'alignement DMARC est assuré par la signature DKIM `d=fsspnantes.fr`.

## 3. Attendre la vérification

```bash
dig +short CNAME <JETON_1>._domainkey.fsspnantes.fr
aws sesv2 get-email-identity --region eu-west-3 --email-identity fsspnantes.fr \
  --query '[VerifiedForSendingStatus, DkimAttributes.Status]'
```

Attendu : le CNAME répond `<JETON_1>.dkim.amazonses.com.`, puis `[true, "SUCCESS"]`
(de quelques minutes à 72 h ; SES revérifie automatiquement).

## 4. Créer l'utilisateur IAM de l'application

La policy `homelan/cluster/apps/crf/ses-policy.json` n'autorise que `ses:SendEmail` sur
l'identité `fsspnantes.fr` **et seulement avec l'expéditeur `crf@fsspnantes.fr`** : même si
les clés fuitaient, elles ne permettraient pas d'écrire au nom d'une autre adresse de la paroisse.

```bash
cd ~/git/homelan/cluster/apps/crf
aws iam create-user --user-name ses-crf
aws iam put-user-policy --user-name ses-crf --policy-name CrfSendEmail \
  --policy-document file://ses-policy.json
aws iam create-access-key --user-name ses-crf
```

La dernière commande affiche `AccessKeyId` et `SecretAccessKey` **une seule fois** : les saisir
dans `create-sealed-secret-crf.sh`.

## 5. Tester l'envoi

Avec le profil administrateur :

```bash
aws sesv2 send-email --region eu-west-3 \
  --from-email-address crf@fsspnantes.fr \
  --destination ToAddresses=<TON_ADRESSE> \
  --content 'Simple={Subject={Data="Test CRF apéro",Charset=UTF-8},Body={Text={Data="Test d envoi SES",Charset=UTF-8}}}'
```

Dans Gmail, ouvrir le message → *⋮ → Afficher l'original* : **DKIM : PASS** (domaine
`fsspnantes.fr`) et **DMARC : PASS**.

## À savoir

- Une fois le domaine vérifié, un administrateur du compte AWS peut techniquement envoyer au nom
  de n'importe quelle adresse `@fsspnantes.fr`. À signaler à la paroisse ; l'application, elle,
  est bridée par la policy IAM.
- Rebonds et plaintes : visibles dans SES → *Reputation metrics*. Aucun traitement automatique
  en v1.
