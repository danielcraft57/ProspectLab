# Diagnostic couverture emails (production)

Date du diagnostic: 2026-03-21

## Contexte

Le filtre "Entreprises avec email uniquement" affichait initialement un volume beaucoup trop faible, car il se basait seulement sur `entreprises.email_principal`.

Correction appliquee dans le code:
- prise en compte de `email_principal` **ou** des emails de `scraper_emails`
- alignement de la logique dans `get_entreprises` et `count_entreprises`
- extension de la recherche texte pour inclure aussi `scraper_emails.email`

## Chiffres production constates

Source: requetes SQL et script Python executes contre PostgreSQL (`node15.lan`).

- Total entreprises: `8561`
- Avec email principal: `759`
- Avec email depuis scraping: `5526`
- Avec email global (principal ou scraping): `5584`
- Couverture email globale: `65.23%`
- Sans website: `0`
- Jamais scrapees: `4`
- Scrapees mais sans email: `2974`

Interpretation:
- le probleme du filtre UI est corrige
- la non-couverture restante vient majoritairement de sites ou aucun email exploitable n'a ete trouve

## Chiffres telephone

- Entreprises avec telephone global: `8450` (`98.70%`)
- Telephone principal (`entreprises.telephone`): `8146`
- Telephone scraping (`scraper_phones`): `7252`
- Sans email mais avec telephone: `2896`

## Chiffres reseaux sociaux

- Entreprises avec au moins un profil social: `5937` (`69.35%`)
- Sans email mais avec social: `1508`
- Sans email mais avec social + telephone: `1490`

Top plateformes detectees:
- Facebook: `4894`
- Instagram: `3310`
- LinkedIn: `2862`
- Twitter: `2517`
- YouTube: `1707`

## Pourquoi on n'est pas a 100% emails

Raisons principales:
- beaucoup de sites n'exposent plus d'email public
- usage de formulaires de contact sans adresse visible
- pages proteges / anti-bot / JS lourd
- donnees de contact indirectes (social, tel) sans email explicite
- qualite variable des pages source

## Pistes d'amelioration prioritaires

### 1) Enrichissement cible "sans email + telephone + social"

Cible immediate: `1490` entreprises.

Action:
- exporter ce segment en CSV
- enrichir via API B2B (Dropcontact, FullEnrich, Apollo, etc.)
- verifier format + MX + statut SMTP si disponible

### 2) Re-scraping intelligent des "scrapees sans email"

Cible: `2974` entreprises.

Action:
- prioriser pages: contact, about, legal, mentions
- revisiter robots/timeout/profondeur sur ce segment
- exclure rapidement les domaines morts

### 3) Qualification par score de recuperabilite

Construire un score simple pour prioriser:
- +2: website valide
- +2: telephone present
- +2: LinkedIn present
- +1: autres reseaux presents
- +1: nom/prenom personne detecte

Traiter d'abord les plus hauts scores.

## Requetes SQL utiles

### Couverture emails globale

```sql
SELECT
  COUNT(*) AS total_entreprises,
  SUM(
    CASE
      WHEN (
        (e.email_principal IS NOT NULL AND TRIM(e.email_principal) <> '')
        OR EXISTS (
          SELECT 1
          FROM scraper_emails se
          WHERE se.entreprise_id = e.id
            AND se.email IS NOT NULL
            AND TRIM(se.email) <> ''
        )
      ) THEN 1 ELSE 0
    END
  ) AS entreprises_avec_email
FROM entreprises e;
```

### Sans email mais avec telephone

```sql
SELECT COUNT(DISTINCT e.id) AS sans_email_avec_phone
FROM entreprises e
WHERE NOT (
  (e.email_principal IS NOT NULL AND TRIM(e.email_principal) <> '')
  OR EXISTS (
    SELECT 1 FROM scraper_emails se
    WHERE se.entreprise_id=e.id
      AND se.email IS NOT NULL
      AND TRIM(se.email) <> ''
  )
)
AND (
  (e.telephone IS NOT NULL AND TRIM(e.telephone) <> '')
  OR EXISTS (
    SELECT 1 FROM scraper_phones sp
    WHERE sp.entreprise_id=e.id
      AND sp.phone IS NOT NULL
      AND TRIM(sp.phone) <> ''
  )
);
```

### Sans email mais avec social

```sql
SELECT COUNT(DISTINCT e.id) AS sans_email_avec_social
FROM entreprises e
WHERE NOT (
  (e.email_principal IS NOT NULL AND TRIM(e.email_principal) <> '')
  OR EXISTS (
    SELECT 1 FROM scraper_emails se
    WHERE se.entreprise_id=e.id
      AND se.email IS NOT NULL
      AND TRIM(se.email) <> ''
  )
)
AND EXISTS (
  SELECT 1 FROM scraper_social_profiles sp
  WHERE sp.entreprise_id=e.id
    AND sp.url IS NOT NULL
    AND TRIM(sp.url) <> ''
);
```

## Script de diagnostic disponible

Un script est disponible pour relancer le diagnostic facilement:

- `scripts/diagnose_email_coverage_postgres.py`

Exemple:

```bash
python scripts/diagnose_email_coverage_postgres.py --host node15.lan --port 5432 --db prospectlab --user prospectlab
```

