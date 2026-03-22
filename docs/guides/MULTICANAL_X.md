# Multicanal X (Twitter)

Ce guide explique comment tester un envoi de message prive X avec le module `services/multicanal`.

## Prerequis

- Dependances Python installees (incluant `tweepy`)
- Un compte/app X avec des credentials OAuth1 valides
- Le destinataire autorise les DM du compte emetteur

## Variables d'environnement

Configurer ces variables dans `.env` (ou dans l'environnement shell):

- `X_API_KEY`
- `X_API_SECRET`
- `X_ACCESS_TOKEN`
- `X_ACCESS_TOKEN_SECRET`

## Script de test unifie (recommande)

Script principal:

- `scripts/tests/test_multicanal_send.py`

### Test canal X

```bash
python scripts/tests/test_multicanal_send.py --channel x --recipient-id 123456789 --body "Bonjour, test X ProspectLab." --entreprise-id 42
```

### Test canal Meta

```bash
python scripts/tests/test_multicanal_send.py --channel meta --recipient-id <PSID> --body "Bonjour, test Meta ProspectLab." --entreprise-id 42
```

## Scripts de test dedies

Scripts fournis:

- `scripts/tests/test_multicanal_x_dm.py`
- `scripts/tests/test_multicanal_meta_dm.py`

Exemple:

```bash
python scripts/tests/test_multicanal_x_dm.py --recipient-id 123456789 --body "Bonjour, test DM ProspectLab." --entreprise-id 42
```

Sortie attendue:

- `success: True` si l'envoi a fonctionne
- sinon `success: False` avec `error` detaille

## Notes importantes

- `recipient-id` doit etre un identifiant utilisateur X numerique (pas un @username).
- L'envoi DM peut echouer meme avec des credentials valides si:
  - le destinataire n'accepte pas les DM
  - le compte emetteur est restreint
  - les limites API X sont atteintes

## Integration applicative

Le provider se trouve dans:

- `services/multicanal/providers.py` (`XDirectMessageProvider`)

Orchestrateur:

- `services/multicanal/dispatcher.py` (`MultiCanalService`)

## Test Meta Messenger

Variables attendues:

- `META_PAGE_ID`
- `META_PAGE_ACCESS_TOKEN`
- `META_GRAPH_API_VERSION` (optionnel, defaut `v20.0`)

Script dedie:

- `scripts/tests/test_multicanal_meta_dm.py`

Exemple:

```bash
python scripts/tests/test_multicanal_meta_dm.py --recipient-id <PSID> --body "Bonjour, test Meta ProspectLab." --entreprise-id 42
```

## Test en lot (CSV + fallback)

Script:

- `scripts/tests/test_multicanal_batch.py`

Colonnes CSV attendues:

- `entreprise_id`
- `body`
- `x_recipient_id` (optionnel)
- `meta_recipient_id` (optionnel)
- `channel_order` (optionnel, ex: `x,meta` ou `meta,x`)

Exemple d'execution:

```bash
python scripts/tests/test_multicanal_batch.py --csv "data/multicanal_batch.csv" --default-order "x,meta" --dry-run --output-json "logs/multicanal_batch_report.json"
```

Exemple de CSV:

```csv
entreprise_id,body,x_recipient_id,meta_recipient_id,channel_order
42,"Bonjour, est-ce le bon contact pour vos besoins web ?",123456789,,"x,meta"
43,"Bonjour, je vous contacte suite a votre page Facebook.",,987654321,"meta,x"
```

