"""
Classification heuristique d’un site externe (homepage) : agence web, éditeur, personne,
entreprise, association, administration, etc. — à partir du HTML, JSON-LD et du domaine.
"""

from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def _host_key(netloc: str) -> str:
    h = (netloc or '').lower().split(':')[0]
    if h.startswith('www.'):
        h = h[4:]
    return h


def _flatten_jsonld_nodes(data: Any) -> List[dict]:
    out: List[dict] = []
    if isinstance(data, list):
        for x in data:
            out.extend(_flatten_jsonld_nodes(x))
        return out
    if isinstance(data, dict):
        if '@graph' in data:
            out.extend(_flatten_jsonld_nodes(data['@graph']))
        else:
            out.append(data)
    return out


def _types_of(node: dict) -> Set[str]:
    t = node.get('@type')
    if isinstance(t, list):
        return {str(x).lower() for x in t if x}
    if isinstance(t, str):
        return {t.lower()}
    return set()


def _collect_jsonld_types(soup: BeautifulSoup) -> List[str]:
    found: List[str] = []
    seen: Set[str] = set()
    for script in soup.find_all('script', attrs={'type': lambda x: x and 'ld+json' in x.lower()}):
        raw = (script.string or script.get_text() or '').strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for node in _flatten_jsonld_nodes(data):
            if not isinstance(node, dict):
                continue
            for t in _types_of(node):
                if t and t not in seen:
                    seen.add(t)
                    found.append(t)
    return found


# (catégorie_id, mots-clés titre/description — minuscules)
_TEXT_CATEGORY_KEYWORDS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    ('web_agency', (
        'agence web', 'agence digitale', 'agence digital', 'web agency', 'digital agency',
        'studio web', 'studio digital', 'création de site', 'creation de site', 'site internet',
        'site web sur mesure', 'refonte web', 'développeur web freelance', 'developpeur web freelance',
        'intégrateur web', 'integrateur web', 'freelance web', 'designer web', 'ux/ui', 'ui/ux',
        'wordpress agency', 'création digitale', 'accompagnement digital', 'conseil digital',
    )),
    ('cms_platform_credit', (
        'wix', 'squarespace', 'shopify', 'webflow', 'elementor', 'jimdo', 'strikingly',
    )),
    ('hosting_provider', (
        'hébergement web', 'hebergement web', 'cloud hosting', 'serveur dédié', 'serveur dedie',
        'nom de domaine', 'registrar', 'infomaniak', 'ovh', 'ionos',
    )),
    ('nonprofit_association', (
        'association loi 1901', 'association déclarée', 'association declaree', 'association —',
        'ong ', 'fondation ', 'fédération', 'federation', 'syndicat ', 'collectif ',
        'bénévole', 'benevole', 'adhérent', 'adherent',
    )),
    ('public_administration', (
        'mairie', 'métropole', 'metropole', 'commune de', 'département', 'departement',
        'région ', 'region ', 'préfecture', 'prefecture', 'service public', 'administration',
        'république française', 'gouvernement', 'ministère', 'ministere', 'collectivité',
    )),
    ('education_research', (
        'université', 'universite', 'école ', 'ecole ', 'institut ', 'laboratoire de recherche',
        'formation professionnelle', 'campus',
    )),
    ('media_publisher', (
        'éditeur ', 'editeur ', 'presse ', 'média', 'media ', 'journal ', 'magazine ',
        'rédaction', 'redaction',
    )),
    ('software_editor', (
        'éditeur de logiciel', 'editeur de logiciel', 'software editor', 'saas ', 'erp ',
        'solution métier', 'solution metier',
    )),
    ('person_portfolio', (
        'graphiste freelance', 'développeur freelance', 'developpeur freelance', 'photographe',
        'consultant indépendant', 'cv ', 'curriculum', 'portfolio de',
    )),
    ('company_commercial', (
        ' sarl', ' sas ', ' sa ', ' eurl', ' sci ', 'société par actions', 'societe par actions',
        'capital social', 'rcs ', 'siret', 'siren',
    )),
    ('ecommerce_retail', (
        'boutique en ligne', 'e-commerce', 'ecommerce', 'vente en ligne', 'marketplace',
        'ajouter au panier', 'panier', 'commander en ligne', 'livraison à domicile',
        'shop now', 'online store',
    )),
    ('finance_insurance', (
        'assurance ', 'banque ', 'crédit immobilier', 'credit immobilier', 'mutuelle ',
        'courtier en', 'gestion de patrimoine',
    )),
    ('health_medical', (
        'cabinet médical', 'cabinet medical', 'clinique ', 'dentiste', 'pharmacie ',
        'orthodontiste', 'vétérinaire', 'veterinaire',
    )),
    ('realestate_construction', (
        'promoteur immobilier', 'agence immobilière', 'agence immobiliere', 'constructeur de maisons',
        'bâtiment ', 'batiment ', 'travaux publics',
    )),
    ('tourism_hospitality', (
        'hôtel ', 'hotel ', 'chambre d\'hôte', 'gîte ', 'gite ', 'réservation ', 'reservation ',
        'tourisme', 'restaurant ',
    )),
    ('legal_services', (
        'avocat ', 'cabinet d\'avocats', 'notaire ', 'juridique', 'conseil juridique',
    )),
)


def _domain_category_hints(host: str) -> Dict[str, int]:
    scores: Dict[str, int] = defaultdict(int)
    h = host.lower()
    if not h:
        return scores
    if h.endswith('.gouv.fr') or '.gouv.' in h:
        scores['public_administration'] += 10
    if h.endswith('.asso.fr') or h.endswith('.association'):
        scores['nonprofit_association'] += 8
    if any(h.endswith(s) for s in ('.edu', '.ac.uk', '.univ-')):
        scores['education_research'] += 6
    return scores


def _jsonld_type_to_categories(types: List[str]) -> Dict[str, int]:
    scores: Dict[str, int] = defaultdict(int)
    flat = ' '.join(types).lower()
    if 'person' in flat:
        scores['person_individual'] += 8
    if any(x in flat for x in ('localbusiness', 'organization', 'corporation', 'airline', 'store')):
        scores['schema_organization'] += 4
    if 'governmentorganization' in flat or 'governmentbuilding' in flat:
        scores['public_administration'] += 10
    if re.search(r'\bnonprofit', flat) or re.search(r'\bcharitableorganization\b', flat):
        scores['nonprofit_association'] += 8
    if 'educationalorganization' in flat or 'collegeoruniversity' in flat or 'school' in flat:
        scores['education_research'] += 7
    if 'professional' in flat and 'service' in flat:
        scores['web_agency'] += 2
    return scores


def classify_external_homepage(
    soup: Optional[BeautifulSoup],
    title: Optional[str],
    description: Optional[str],
    final_url: str,
) -> Dict[str, Any]:
    """
    Retourne au minimum :
      - categories: liste triée par score décroissant (ids stables)
      - jsonld_types: types @type vus dans la page
      - graph_group: agency | public | nonprofit | person | external (pour le graphe UI)
    """
    host = _host_key(urlparse(final_url or '').netloc)
    blob = f'{title or ""} {description or ""}'.lower()
    scores: Dict[str, int] = defaultdict(int)

    for cat, kws in _TEXT_CATEGORY_KEYWORDS:
        for kw in kws:
            if kw in blob:
                scores[cat] += 4

    for k, v in _domain_category_hints(host).items():
        scores[k] += v

    jsonld_types: List[str] = []
    if soup:
        try:
            jsonld_types = _collect_jsonld_types(soup)
        except Exception as e:
            logger.debug('jsonld types: %s', e)
        for k, v in _jsonld_type_to_categories(jsonld_types).items():
            scores[k] += v

    # Seuil minimal pour apparaître dans la liste
    threshold = 3
    ranked = sorted(
        ((c, s) for c, s in scores.items() if s >= threshold),
        key=lambda x: -x[1],
    )
    categories = [c for c, _ in ranked][:24]

    if not categories:
        if jsonld_types:
            categories.append('schema_unknown')
        else:
            categories.append('unclassified')

    # Groupe graphe : priorité décroissante (affichage couleur / forme)
    graph_group = 'external'
    if scores.get('web_agency', 0) >= 4:
        graph_group = 'agency'
    elif scores.get('cms_platform_credit', 0) >= 4:
        graph_group = 'saas_cms'
    elif scores.get('hosting_provider', 0) >= 5:
        graph_group = 'hosting'
    elif scores.get('public_administration', 0) >= 6:
        graph_group = 'public'
    elif scores.get('nonprofit_association', 0) >= 6:
        graph_group = 'nonprofit'
    elif scores.get('education_research', 0) >= 6:
        graph_group = 'education'
    elif scores.get('media_publisher', 0) >= 5:
        graph_group = 'media'
    elif scores.get('software_editor', 0) >= 5:
        graph_group = 'software'
    elif scores.get('ecommerce_retail', 0) >= 5:
        graph_group = 'ecommerce'
    elif scores.get('company_commercial', 0) >= 8:
        graph_group = 'company'
    elif scores.get('finance_insurance', 0) >= 5:
        graph_group = 'finance'
    elif scores.get('health_medical', 0) >= 5:
        graph_group = 'health'
    elif scores.get('realestate_construction', 0) >= 5:
        graph_group = 'realestate'
    elif scores.get('tourism_hospitality', 0) >= 5:
        graph_group = 'tourism'
    elif scores.get('legal_services', 0) >= 5:
        graph_group = 'legal'
    elif scores.get('person_individual', 0) >= 6 or scores.get('person_portfolio', 0) >= 4:
        graph_group = 'person'

    return {
        'categories': categories,
        'category_scores': {c: int(scores[c]) for c in categories if c in scores},
        'jsonld_types': jsonld_types[:40],
        'graph_group': graph_group,
    }
