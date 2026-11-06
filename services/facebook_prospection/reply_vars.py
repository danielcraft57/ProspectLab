"""
Variables d'entreprise dans les reponses Q/R (tchatche + Messenger).

Placeholders : {{ville}}, {ville}, et blocs {{#if_ville}}...{{/if_ville}}.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

from utils.email_subject import normalize_template_value

_VAR_DBL = re.compile(r'\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}')
_VAR_SGL = re.compile(r'(?<!\{)\{([a-zA-Z][a-zA-Z0-9_]*)\}(?!\})')
_IF_NAMED = re.compile(
    r'\{\{#if_([a-zA-Z][a-zA-Z0-9_]*)\}\}(.*?)\{\{/?if_\1\}\}',
    re.DOTALL,
)
_IF_ENDIF = re.compile(
    r'\{\{#if_([a-zA-Z][a-zA-Z0-9_]*)\}\}(.*?)\{\{#endif\}\}',
    re.DOTALL,
)
_IF_SGL = re.compile(
    r'\{#if_([a-zA-Z][a-zA-Z0-9_]*)\}(.*?)\{#endif\}',
    re.DOTALL,
)

# Fallbacks oraux (Messenger / tel), pas des emails.
_DEFAULTS = {
    'nom': 'vous',
    'prenom': 'vous',
    'responsable': '',
    'entreprise': 'votre entreprise',
    'ville': 'votre secteur',
    'code_postal': '',
    'adresse': '',
    'telephone': '',
    'email': '',
    'website': 'votre site',
    'secteur': '',
    'metier': '',
    'categorie': '',
}

# Cles affichees par groupe dans le tchatche (aligne emails prospect).
PROSPECT_VAR_GROUPS: list[dict[str, Any]] = [
    {
        'id': 'crm',
        'label': 'CRM',
        'keys': [
            'entreprise',
            'nom',
            'prenom',
            'responsable',
            'email',
            'telephone',
            'ville',
            'code_postal',
            'adresse',
            'website',
            'secteur',
            'metier',
            'categorie',
            'ville_ou_secteur',
            'opportunite',
            'statut',
        ],
    },
    {
        'id': 'tech',
        'label': 'Technique & SEO',
        'keys': [
            'framework',
            'cms',
            'hosting_provider',
            'performance_score',
            'security_score',
            'risk_score',
            'score_seo',
            'score_pentest',
            'score_securite',
            'meta_title',
            'meta_description',
            'seo_issues',
            'security_issues',
            'vulnerabilities_count',
        ],
    },
    {
        'id': 'gemini',
        'label': 'Audit Gemini',
        'keys': [
            'gemini_score',
            'gemini_pitch',
            'gemini_summary',
            'gemini_refonte',
            'gemini_problem_1',
            'gemini_problem_2',
            'gemini_problem_3',
            'gemini_action_1',
            'gemini_action_2',
            'gemini_works_1',
        ],
    },
    {
        'id': 'links',
        'label': 'Liens (emails)',
        'keys': ['analysis_url', 'dc_contact_url', 'unsubscribe_url', 'base_url'],
    },
    {
        'id': 'vitrine',
        'label': 'Vitrine & echantillons',
        'keys': [
            'secteur_label',
            'echantillon_slug',
            'landing_variant_url',
            'landing_variants_count',
        ],
    },
]

_SKIP_MERGE_KEYS = frozenset(
    {
        'total_social',
        'related_cards_html',
        'echantillons_cards_html',
    }
)

_HTML_VAR_SUFFIX = '_html'


def _first_name(value: str) -> str:
    """Premier mot d'un nom affiche."""
    parts = (value or '').strip().split()
    return parts[0] if parts else ''


def build_reply_vars(
    entreprise: dict[str, Any] | None = None,
    *,
    contact_name: str | None = None,
) -> dict[str, str]:
    """
    Construit le dictionnaire de variables pour une reponse type.

    @param entreprise: Fiche CRM (get_entreprise)
    @param contact_name: Nom Messenger / interlocuteur
    @returns: Cles -> valeurs texte
    """
    ent = entreprise if isinstance(entreprise, dict) else {}
    nom_ent = normalize_template_value(str(ent.get('nom') or ''), '')
    ville = normalize_template_value(str(ent.get('ville') or ''), '')
    cp = normalize_template_value(str(ent.get('code_postal') or ''), '')
    addr1 = normalize_template_value(str(ent.get('address_1') or ''), '')
    tel = normalize_template_value(str(ent.get('telephone') or ''), '')
    email = normalize_template_value(
        str(ent.get('email_principal') or ent.get('email') or ''), ''
    )
    website = normalize_template_value(str(ent.get('website') or ''), '')
    secteur = normalize_template_value(
        str(ent.get('secteur') or ent.get('secteur_raw') or ''), ''
    )
    categorie = normalize_template_value(str(ent.get('categorie') or ''), '')
    responsable = normalize_template_value(str(ent.get('responsable') or ''), '')
    contact = normalize_template_value(contact_name or '', '')

    nom = contact or responsable or _DEFAULTS['nom']
    prenom = _first_name(nom) if nom != _DEFAULTS['nom'] else _DEFAULTS['prenom']

    adresse_parts = [p for p in (addr1, ' '.join(x for x in (cp, ville) if x).strip()) if p]
    vars_map: dict[str, str] = {
        'nom': nom,
        'prenom': prenom,
        'responsable': responsable,
        'entreprise': nom_ent or _DEFAULTS['entreprise'],
        'ville': ville or _DEFAULTS['ville'],
        'code_postal': cp,
        'adresse': ', '.join(adresse_parts),
        'telephone': tel,
        'email': email,
        'website': website or _DEFAULTS['website'],
        'secteur': secteur,
        'metier': categorie or secteur,
        'categorie': categorie,
        'contact': contact or nom,
    }
    if ent.get('id') is not None:
        vars_map['entreprise_id'] = str(ent.get('id'))
    score_seo = ent.get('score_seo')
    if score_seo is not None and str(score_seo).strip():
        vars_map['score_seo'] = str(score_seo)
    score_pentest = ent.get('score_pentest')
    if score_pentest is not None and str(score_pentest).strip():
        vars_map['score_pentest'] = str(score_pentest)

    for key, val in list(vars_map.items()):
        vars_map[f'has_{key}'] = '1' if (val or '').strip() and val not in (
            _DEFAULTS.get(key, ''),
        ) else ''
    # has_* plus strict : vraie donnee fiche, pas le fallback oral
    vars_map['has_ville'] = '1' if ville else ''
    vars_map['has_entreprise'] = '1' if nom_ent else ''
    vars_map['has_website'] = '1' if website else ''
    vars_map['has_telephone'] = '1' if tel else ''
    vars_map['has_email'] = '1' if email else ''
    vars_map['has_responsable'] = '1' if responsable else ''
    vars_map['has_secteur'] = '1' if secteur else ''
    vars_map['has_metier'] = '1' if (categorie or secteur) else ''
    return vars_map


def _scalar_channel_value(value: Any) -> str:
    """
    Convertit une valeur email extended en texte utilisable Messenger / tchatche.

    @param value: Valeur brute (analyse, gemini, etc.)
    @returns: Chaine ou vide
    """
    if value is None:
        return ''
    if isinstance(value, bool):
        return '1' if value else ''
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, dict)):
        return ''
    return str(value).strip()


def _build_prospect_link_vars(
    vars_map: dict[str, str],
    *,
    brand_host: str = 'danielcraft.fr',
) -> dict[str, str]:
    """
    Liens analysis / contact / desabonnement (meme logique que les emails).

    @param vars_map: Variables de base deja fusionnees
    @param brand_host: Domaine marque
    @returns: Sous-dict URL
    """
    try:
        from config import BASE_URL, normalize_public_base_url, normalize_website_url_for_query
    except Exception:
        normalize_public_base_url = None
        normalize_website_url_for_query = None
        BASE_URL = ''

    if normalize_public_base_url:
        base_url = normalize_public_base_url(BASE_URL or '', source='tchatche_vars') or ''
    else:
        base_url = (BASE_URL or '').strip() or 'http://localhost:5000'

    brand = (brand_host or 'danielcraft.fr').strip().lower()
    brand = re.sub(r'^https?://', '', brand).rstrip('/')
    brand_base = f'https://{brand}'

    website_raw = vars_map.get('website') or ''
    if normalize_website_url_for_query and website_raw:
        website_val = normalize_website_url_for_query(website_raw)
    elif website_raw.strip():
        website_val = website_raw.strip()
        if not website_val.lower().startswith('http'):
            website_val = f'https://{website_val.lstrip("/")}'
        elif website_val.lower().startswith('http://'):
            website_val = f'https://{website_val[7:]}'
    else:
        website_val = ''

    email = (vars_map.get('email') or '').strip()
    nom = (vars_map.get('nom') or vars_map.get('prenom') or '').strip()
    encoded_email = quote(email, safe='') if email else ''
    encoded_name = quote(nom, safe='') if nom and nom not in ('vous', 'Monsieur/Madame') else ''

    analysis_url = ''
    if website_val:
        parts = [f'website={quote(website_val, safe="")}', 'full=1']
        if encoded_email:
            parts.append(f'email={encoded_email}')
        if encoded_name:
            parts.append(f'name={encoded_name}')
        analysis_url = f'{brand_base}/analyse?{"&".join(parts)}'

    unsubscribe_url = ''
    if website_val:
        q = f'website={quote(website_val, safe="")}'
        if encoded_email:
            unsubscribe_url = f'{brand_base}/desabonnement?{q}&email={encoded_email}'
        else:
            unsubscribe_url = f'{brand_base}/desabonnement?{q}'

    if encoded_email:
        dc_contact_url = f'{brand_base}/?email={encoded_email}#contact'
    else:
        dc_contact_url = f'{brand_base}/#contact'

    return {
        'base_url': base_url,
        'analysis_url': analysis_url,
        'unsubscribe_url': unsubscribe_url,
        'dc_contact_url': dc_contact_url,
    }


def merge_prospect_email_vars(
    base: dict[str, str],
    entreprise_id: int | None,
) -> dict[str, str]:
    """
    Enrichit les variables tchatche avec le meme jeu que les emails prospect.

    @param base: Variables CRM (build_reply_vars)
    @param entreprise_id: ID fiche
    @returns: Dict fusionne (texte)
    """
    out = dict(base)
    if not entreprise_id:
        return out
    extended: dict[str, Any] = {}
    try:
        from services.template_manager import TemplateManager

        extended = TemplateManager()._get_entreprise_extended_data(int(entreprise_id)) or {}
    except Exception:
        extended = {}

    for key, raw in extended.items():
        if key in _SKIP_MERGE_KEYS:
            continue
        if key.endswith(_HTML_VAR_SUFFIX):
            plain = re.sub(r'<[^>]+>', ' ', _scalar_channel_value(raw))
            plain = re.sub(r'\s+', ' ', plain).strip()
            if plain:
                out[key] = plain[:500] + ('…' if len(plain) > 500 else '')
            continue
        text = _scalar_channel_value(raw)
        if text or key.startswith('has_'):
            out[key] = text

    out.update(_build_prospect_link_vars(out))

    if extended.get('performance_score') is not None:
        out['performance'] = '1'
    if extended.get('security_score') is not None:
        out['security'] = '1'
    if extended.get('risk_score') is not None:
        out['risk'] = '1'
        out['pentest'] = '1'
    if extended.get('gemini_has_report') or extended.get('gemini'):
        out['gemini'] = '1'

    for key, val in list(out.items()):
        if key.startswith('has_'):
            continue
        if (val or '').strip() and val not in (_DEFAULTS.get(key, ''),):
            out[f'has_{key}'] = out.get(f'has_{key}') or '1'

    return out


def build_var_groups_for_ui(vars_map: dict[str, str] | None) -> list[dict[str, Any]]:
    """
    Regroupe les variables pour le panneau tchatche.

    @param vars_map: Variables fusionnees
    @returns: Groupes {id, label, items: [{key, value}]}
    """
    data = vars_map or {}
    groups: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in PROSPECT_VAR_GROUPS:
        items: list[dict[str, str]] = []
        for key in block.get('keys') or []:
            seen.add(key)
            val = data.get(key, '')
            if not str(val or '').strip():
                continue
            items.append({'key': key, 'value': str(val)})
        if items:
            groups.append(
                {
                    'id': block.get('id'),
                    'label': block.get('label'),
                    'items': items,
                }
            )
    extra: list[dict[str, str]] = []
    for key, val in sorted(data.items()):
        if key in seen or key.startswith('has_'):
            continue
        if not str(val or '').strip():
            continue
        if key.endswith(_HTML_VAR_SUFFIX):
            continue
        extra.append({'key': key, 'value': str(val)[:120]})
    if extra:
        groups.append({'id': 'other', 'label': 'Autres', 'items': extra[:40]})
    return groups


def load_entreprise_reply_vars(
    entreprise_id: int | None,
    *,
    contact_name: str | None = None,
) -> tuple[dict[str, str], dict[str, Any] | None]:
    """
    Charge une fiche et produit les variables.

    @param entreprise_id: ID CRM
    @param contact_name: Nom Messenger
    @returns: (vars, fiche ou None)
    """
    fiche = None
    if entreprise_id:
        try:
            from services.database import Database

            fiche = Database().get_entreprise(int(entreprise_id))
        except (TypeError, ValueError):
            fiche = None
        except Exception:
            fiche = None
    base = build_reply_vars(fiche, contact_name=contact_name)
    if entreprise_id and fiche:
        base = merge_prospect_email_vars(base, int(entreprise_id))
    return base, fiche


def render_reply_template(text: str, variables: dict[str, str] | None) -> str:
    """
    Remplace les placeholders dans une phrase KB.

    @param text: Reponse brute (VocalGuard)
    @param variables: Dict de remplacement
    @returns: Phrase personnalisee
    """
    raw = text or ''
    if not raw:
        return ''
    vars_map = variables or {}

    def _truthy(key: str) -> bool:
        if key == 'tech_data':
            return any(
                bool((vars_map.get(k) or '').strip())
                for k in ('framework', 'cms', 'hosting_provider', 'performance_score')
            )
        if key == 'scraping_data':
            return any(
                str(vars_map.get(k) or '').strip() not in ('', '0')
                for k in ('total_emails', 'total_people', 'total_phones', 'total_social_count')
            )
        if key == 'all_data':
            return _truthy('tech_data') or _truthy('scraping_data') or _truthy('gemini')
        if key == 'performance':
            if (vars_map.get('performance') or '').strip() in ('1', 'true', 'yes'):
                return True
            return bool((vars_map.get('performance_score') or '').strip())
        if key == 'security':
            if (vars_map.get('security') or '').strip() in ('1', 'true', 'yes'):
                return True
            return bool((vars_map.get('security_score') or '').strip())
        if key in ('risk', 'pentest'):
            if (vars_map.get(key) or '').strip() in ('1', 'true', 'yes'):
                return True
            return bool((vars_map.get('risk_score') or '').strip())
        if key == 'gemini':
            if (vars_map.get('gemini') or '').strip() in ('1', 'true', 'yes'):
                return True
            return bool((vars_map.get('gemini_has_report') or vars_map.get('gemini_score') or '').strip())
        val = (vars_map.get(key) or '').strip()
        if key.startswith('has_'):
            return val in ('1', 'true', 'yes', 'on')
        if not val:
            return False
        return val not in (
            _DEFAULTS.get(key, ''),
            'vous',
            'votre entreprise',
            'votre secteur',
            'votre site',
        )

    def _if_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        inner = match.group(2)
        return inner if _truthy(key) else ''

    out = _IF_NAMED.sub(_if_sub, raw)
    out = _IF_ENDIF.sub(_if_sub, out)
    out = _IF_SGL.sub(_if_sub, out)

    def _var_sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in vars_map:
            return str(vars_map.get(key) or '')
        return match.group(0)

    out = _VAR_DBL.sub(_var_sub, out)
    out = _VAR_SGL.sub(_var_sub, out)
    out = re.sub(r'[ \t]{2,}', ' ', out)
    out = re.sub(r' ?\n ?', '\n', out)
    return out.strip()


def apply_vars_to_suggestions(
    suggestions: list[dict[str, Any]],
    variables: dict[str, str] | None,
) -> list[dict[str, Any]]:
    """
    Personnalise le texte de chaque suggestion.

    @param suggestions: Liste chips
    @param variables: Variables entreprise
    @returns: Suggestions copiees
    """
    out: list[dict[str, Any]] = []
    for item in suggestions or []:
        row = dict(item)
        row['text'] = render_reply_template(str(row.get('text') or ''), variables)
        if row['text']:
            out.append(row)
    return out


# Phrases Messenger / tchatche (pas le WAV telephone VocalGuard).
INTENT_TEMPLATES: dict[str, list[str]] = {
    'out_presentation': [
        (
            "Bonjour{{#if_prenom}} {{prenom}}{{/if_prenom}}, "
            "je vous contacte pour {{entreprise}}"
            "{{#if_ville}} a {{ville}}{{/if_ville}}. "
            "On aide les boites locales a etre mieux trouvees en ligne. "
            "Vous avez trente secondes ?"
        ),
        (
            "Allo, assistante DanielCraft. Je vous appelle au sujet de {{entreprise}}"
            "{{#if_metier}}, {{metier}}{{/if_metier}}"
            "{{#if_ville}} a {{ville}}{{/if_ville}}. "
            "Je fais tres court : un mini point sur votre presence web, sans pression."
        ),
        (
            "Bonjour, c'est DanielCraft. J'ai {{entreprise}} sous les yeux"
            "{{#if_website}} ({{website}}){{/if_website}}. "
            "Ca vous va si je pose deux questions rapides ?"
        ),
    ],
    'out_qualify_website': [
        (
            "Ok pour {{entreprise}}. "
            "{{#if_website}}J'ai vu {{website}} — {{/if_website}}"
            "vous avez l'impression que ca vous amene vraiment des demandes, ou c'est plus une vitrine ?"
        ),
        (
            "D'accord. {{#if_ville}}A {{ville}}, {{/if_ville}}"
            "est-ce que le site est a jour, facile a appeler depuis le mobile, avec les infos utiles bien visibles ?"
        ),
        (
            "{{#if_website}}Sur {{website}}, {{/if_website}}"
            "souvent les gens ne trouvent pas le bon numero ou l'horaire. Ca vous parle pour {{entreprise}} ?"
        ),
    ],
    'out_objection_has_site': [
        (
            "Tant mieux s'il y en a un pour {{entreprise}}. "
            "La question c'est surtout : est-ce qu'il vous amene des demandes, ou il dort un peu ?"
        ),
        (
            "Ok, on ne repart pas de zero"
            "{{#if_website}} — on part de {{website}}{{/if_website}}. "
            "Souvent on ameliore ce qui existe : clarte, mobile, appels. Sans tout casser."
        ),
        (
            "Je comprends. {{#if_ville}}A {{ville}}, {{/if_ville}}"
            "un site peut etre recent et rater quand meme des details. "
            "Un regard exterieur sur {{entreprise}}, ca aide parfois."
        ),
    ],
    'out_who_are_you': [
        (
            "DanielCraft, agence web fondee par Loic Daniel. "
            "On aide les PME locales : site clair, visibilite Google, sans discours commercial lourd."
        ),
        (
            "C'est DanielCraft : petite structure, projets sur mesure. "
            "Je vous parlais de {{entreprise}}"
            "{{#if_ville}} a {{ville}}{{/if_ville}} parce que votre secteur nous interesse."
        ),
        (
            "Assistants et equipe DanielCraft — on fait du concret : audit rapide, "
            "corrections utiles, pas de promesses vagues. Vous vouliez savoir qui ecrit ?"
        ),
    ],
    'out_go_ahead': [
        (
            "Merci. Je fais court : pour {{entreprise}}, "
            "{{#if_website}}avec {{website}}{{/if_website}} "
            "est-ce que vous recevez des demandes, ou c'est surtout une vitrine ?"
        ),
        (
            "Parfait. Premier point concret : votre site vous apporte des appels ou des contacts, "
            "ou il sert surtout a dire que vous existez ?"
        ),
        (
            "Super. {{#if_ville}}A {{ville}}, {{/if_ville}}"
            "beaucoup de sites sont jolis mais invisibles sur Google. "
            "C'est plutot votre cas pour {{entreprise}} ?"
        ),
    ],
    'out_audit_offer': [
        (
            "On peut regarder "
            "{{#if_website}}{{website}}{{/if_website}}"
            " votre presence en ligne "
            "sans engagement : ce qui bloque les appels pour {{entreprise}}."
        ),
        (
            "Si vous voulez, je vous envoie un mini diagnostic gratuit sur {{entreprise}} "
            "{{#if_ville}}({{ville}}){{/if_ville}} — deux points actionnables, pas un roman."
        ),
    ],
}


def templates_for_tag(tag: str | None) -> list[str]:
    """
    Phrases a variables pour un intent commercial.

    @param tag: Tag VocalGuard
    @returns: Modeles bruts
    """
    key = str(tag or '').strip()
    return list(INTENT_TEMPLATES.get(key) or [])


def merge_template_suggestions(
    tag: str | None,
    variables: dict[str, str] | None,
    suggestions: list[dict[str, Any]],
    *,
    score: float = 0.0,
    template_index: int = 0,
    avoid_replies: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Place les phrases personnalisees en tete des suggestions.

    @param tag: Intent
    @param variables: Variables entreprise
    @param suggestions: Chips deja rendus
    @param score: Score intent
    @param template_index: Variante INTENT_TEMPLATES (0..n)
    @param avoid_replies: Phrases bot deja dites (anti-boucle)
    @returns: (reply principale, suggestions)
    """
    rendered: list[str] = []
    for tpl in templates_for_tag(tag):
        text = render_reply_template(tpl, variables)
        if text and text not in rendered:
            rendered.append(text)
    if not rendered:
        reply = (suggestions[0].get('text') if suggestions else '') or ''
        return str(reply), suggestions

    def _norm_avoid(t: str) -> str:
        return re.sub(r'\s+', ' ', (t or '').strip().lower())

    avoid = {_norm_avoid(t) for t in (avoid_replies or []) if t}

    primary_idx = max(0, min(int(template_index), len(rendered) - 1))
    primary = rendered[primary_idx]
    if _norm_avoid(primary) in avoid:
        for idx, text in enumerate(rendered):
            if _norm_avoid(text) not in avoid:
                primary = text
                primary_idx = idx
                break

    seen: set[str] = set(rendered)
    chips: list[dict[str, Any]] = []
    for idx, text in enumerate(rendered):
        chips.append(
            {
                'text': text[:2000],
                'score': round(float(score), 4),
                'kind': 'template_var',
                'intent_id': tag,
                'label': str(tag or '') + ('' if idx == primary_idx else f' #{idx + 1}'),
            }
        )
    for item in suggestions:
        text = str(item.get('text') or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        chips.append(item)
    return primary, chips


def public_var_catalog() -> list[dict[str, str]]:
    """
    Liste des variables documentees pour l'UI tchatche.

    @returns: {key, label}
    """
    items: list[dict[str, str]] = []
    for block in PROSPECT_VAR_GROUPS:
        for key in block.get('keys') or []:
            items.append({'key': key, 'label': f"{block.get('label')} · {key}"})
    return items
