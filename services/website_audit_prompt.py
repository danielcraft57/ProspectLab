"""
Construction du prompt de rédaction du rapport d'audit PDF (analyse complète, production distante).
"""

from __future__ import annotations

import json
from typing import Any, Dict


def _json_pretty(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


def build_audit_report_prompt(
    *,
    website: str,
    company_name: str,
    recipient_email: str,
    audit_payload: Dict[str, Any],
    remote_output_dir: str,
) -> str:
    """
    Prompt de rédaction : rapport HTML + PDF d'audit complet,
    calé sur les données mesurées et enrichi par une revue multi-pages du site live.
    """
    data_block = _json_pretty(audit_payload)
    return f"""## Rôle et niveau d'expertise

Tu incarnes un **expert senior pluridisciplinaire** en :
- **Architecture et analyse technique** web (HTTP, TLS, en-têtes, performance perçue, stack, hébergement).
- **SEO technique et éditorial** (crawlabilité, indexation, contenu, structure, Core Web Vitals / signaux).
- **Pentest et posture de sécurité** applicative (surface d'attaque, vulnérabilités, durcissement, priorisation).
- **OSINT** (exposition publique, emails, personnes, réseaux, sous-domaines — toujours dans un cadre légal et éthique).

Tu rédiges un **rapport d'audit complet** pour un décideur ou une équipe technique, avec un ton professionnel, précis et actionnable.

---

## Contexte livré

- **Site** : {website}
- **Organisation / libellé** : {company_name}
- **Destinataire du rapport** : {recipient_email}

---

## Données d'analyse complète déjà réalisée (OBLIGATOIRE)

Ces données ont été produites **en amont** par le pipeline automatisé (scraping, technique, SEO, captures, OSINT, pentest).  
C'est ta **source de vérité chiffrée et factuelle** : scores, compteurs, listes de vulnérabilités, statuts de pipeline, résumés, quick wins, chemins de captures, etc.

```json
{data_block}
```

**Règles strictes sur les données :**
- Tu **ne fabriques pas** de scores, pourcentages, ni de listes de vulnérabilités absentes du JSON.
- Tu peux **citer, agréger, comparer et prioriser** uniquement à partir de ce JSON pour tout ce qui est métrique ou issu des modules automatisés.
- Si une section du JSON est vide ou marquée « never » / manquante, tu l'indiques clairement et tu proposes des **actions de collecte** (relance d'analyse, périmètre à étendre) plutôt que d'inventer des résultats.

---

## Revue du site internet (complément vivant)

En **complément** du JSON (pas à la place), tu dois **explorer le site live** de façon exhaustive dans le cadre raisonnable :

1. **Périmètre** : rester sur le **même domaine** que `{website}` (pas de domaines tiers sauf liens signalés comme externes dans ton analyse narrative).
2. **Profondeur** : parcourir le site comme un auditeur — **menu principal, pied de page, pages clés** (accueil, offres, à propos, contact, blog, légal si présent), et **suivre les liens internes** pour couvrir le **maximum de pages utiles** (vise **au moins 8 à 15 pages** si le site le permet ; si le site est très petit, documente tout ce qui existe).
3. **Objectif** : corréler ce que tu vois (structure HTML, titres, formulaires, médias, navigation, accessibilité grossière, cohérence UX) avec les **constats du JSON** (SEO, technique, pentest, OSINT).
4. **Cohérence** : si le terrain contredit une donnée datée du JSON, écris une courte note du type « observation à date du rapport vs données d'analyse du » + date du jour, **sans modifier** les chiffres officiels du JSON dans les tableaux de synthèse.

---

## Contenu attendu du rapport (complet + solutions)

Le livrable doit être un **audit complet** avec **solutions détaillées** pour améliorer le site, structuré au minimum comme suit (tu peux enrichir avec des sous-sections) :

### A. Synthèse exécutive (1 page équivalent)
- Contexte, périmètre de l'audit, méthode (données automatisées + revue multi-pages).
- **Verdict global** en 5–8 puces, basé sur le JSON + ton parcours.
- **Top 5 risques** et **Top 5 opportunités** (priorisés).

### B. Carte de santé et scores
- Tableau type dashboard : SEO, sécurité technique, performance, pentest / risque, OSINT / exposition, cohérence avec `health_rows` si présent.
- Badges couleur (vert / jaune / rouge) alignés sur la logique du rapport.

### C. Technique & performance
- Synthèse à partir du JSON (et corrélée au site visité).
- **Plan d'action** : pour chaque thème majeur, **problème → impact → solution complète** (étapes concrètes, ordre de grandeur d'effort si déductible, responsable type « dev / infra / marketing »).

### D. SEO
- Diagnostic technique + contenu / structure, calé sur les données JSON + observations crawl manuel.
- **Roadmap SEO** : quick wins (0–2 sem), chantiers moyens (1–3 mois), fondations long terme ; critères de succès mesurables.

### E. Sécurité & pentest
- Restituer les éléments du JSON (vulnérabilités, sévérités, en-têtes, risques).
- Pour **chaque** vulnérabilité ou famille de risques identifiée dans les données : **description**, **risque métier**, **remédiation complète** (configuration, code, process, tests de non-régression, veille).

### F. OSINT & surface d'exposition (cadre professionnel)
- Ce que disent les données (contacts, sous-domaines, etc.) sans dépasser le cadre d'un rapport client.
- Recommandations de **réduction de surface**, classification des données, bonnes pratiques.

### G. UX / conversion (données automatisées + site parcouru)
- Utilise le bloc `pipeline.ux` s'il est présent (score, findings, verdict, corpus @clea_ux).
- Corréle avec ta revue live : parcours, friction, confiance, CTA/CTV, mobile, loi de Hick, empty states.
- **Liste de recommandations** calées sur les principes @clea_ux (onboarding, TTV, CTV, erreurs qui guident, Peak-End, etc.) avec maquettes textuelles ou wireframes ASCII si utile.

### H. Plan de remédiation global
- Tableau **priorisé** : id, thème, action, priorité (P0–P3), effort, dépendances, indicateur de succès.
- **Budget d'effort** indicatif (S / M / L) si tu ne peux pas chiffrer en j/h.

---

## PDF de référence interne (OBLIGATOIRE — combiner et agencer)

Le pipeline a déjà produit un **PDF de base** ReportLab (`local_pdf_path` dans le JSON, fichier `audit_report_reference_baseline.pdf` si fourni en argument `--local-baseline-pdf`).

**Tu dois :**
1. **Lire** ce PDF de référence : structure, scores KPI, tableaux `detail_tables`, carte de santé, captures, annexes vulnérabilités.
2. **Conserver** toutes les **données chiffrées et tableaux** du JSON et du PDF de base (ne pas les supprimer ni les remplacer par des chiffres inventés).
3. **Réagencer** le livrable final : mise en page plus riche, sections narrative expert, graphiques Chart.js, corrélations avec ta **revue live** du site.
4. Le **`audit_report.pdf` final** doit être un document **combiné** : fond factuel mesuré + synthèse experte et recommandations, **8 à 15 pages** utiles à l'impression.

Si le PDF de base est inaccessible, produire le rapport uniquement à partir du JSON en indiquant l'absence du fichier de référence.

---

## Présentation (UX/UI du document)

- Style **dashboard corporate** : palette bleu marine #1a2f4a, lavande #7d6b9e, rose #d4a5b5, fonds #f0e4ea / blanc — **cohérent** avec le PDF de référence.
- Bannière titre, sous-titre, **date du jour**.
- Graphiques (Chart.js CDN ou SVG) : synthèse des scores, comparatifs, avancement pipeline si les données le permettent.
- Intégrer les **screenshots** si des chemins `screenshot_file_paths` ou équivalent existent dans le JSON (`<img>` avec chemins locaux Windows si fournis).
- Document **long et dense** : vise **au minimum l'équivalent de 4–6 pages A4** à l'impression (pas un one-pager minimal).
- Pied de page : *Rapport généré pour DanielCraft*.
- **Ne jamais** mentionner dans le PDF livrable : Cursor, agent IA, noms d'outils internes ou de pipeline — ton professionnel « audit digital » / DanielCraft uniquement.

---

## Fichiers à produire

1. Créer le dossier : `{remote_output_dir}`
2. Y écrire **`audit_report.html`** (HTML autonome, CSS dans `<style>` ou fichier lié si tu préfères, mais un seul dossier de sortie).
3. Générer **`audit_report.pdf`** dans le **même** dossier, fidèle au HTML (graphiques et couleurs conservés).

**Conversion PDF** (selon outils disponibles sur la machine) : Playwright `page.pdf()`, Edge headless `--print-to-pdf`, ou équivalent fiable.

---

## Réponse finale

À la fin de ta session, confirme le chemin absolu du PDF produit (`audit_report.pdf`) et résume en 3–5 lignes les constats majeurs.

"""
