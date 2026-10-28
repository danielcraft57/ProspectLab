"""
Variables d'entreprise dans les reponses Q/R (tchatche + Messenger).

Placeholders : {{ville}}, {ville}, et blocs {{#if_ville}}...{{/if_ville}}.
"""

from __future__ import annotations

import re
from typing import Any

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
    return build_reply_vars(fiche, contact_name=contact_name), fiche


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
) -> tuple[str, list[dict[str, Any]]]:
    """
    Place les phrases personnalisees en tete des suggestions.

    @param tag: Intent
    @param variables: Variables entreprise
    @param suggestions: Chips deja rendus
    @param score: Score intent
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

    seen: set[str] = set(rendered)
    chips: list[dict[str, Any]] = []
    for idx, text in enumerate(rendered):
        chips.append(
            {
                'text': text[:2000],
                'score': round(float(score), 4),
                'kind': 'template_var',
                'intent_id': tag,
                'label': str(tag or '') + ('' if idx == 0 else f' #{idx + 1}'),
            }
        )
    for item in suggestions:
        text = str(item.get('text') or '').strip()
        if not text or text in seen:
            continue
        seen.add(text)
        chips.append(item)
    return rendered[0], chips


def public_var_catalog() -> list[dict[str, str]]:
    """
    Liste des variables documentees pour l'UI tchatche.

    @returns: {key, label}
    """
    return [
        {'key': 'entreprise', 'label': 'Nom de l\'entreprise'},
        {'key': 'nom', 'label': 'Interlocuteur (Messenger ou responsable)'},
        {'key': 'prenom', 'label': 'Prenom'},
        {'key': 'ville', 'label': 'Ville'},
        {'key': 'code_postal', 'label': 'Code postal'},
        {'key': 'adresse', 'label': 'Adresse'},
        {'key': 'website', 'label': 'Site web'},
        {'key': 'telephone', 'label': 'Telephone'},
        {'key': 'email', 'label': 'Email principal'},
        {'key': 'secteur', 'label': 'Secteur'},
        {'key': 'metier', 'label': 'Metier / categorie'},
        {'key': 'responsable', 'label': 'Responsable fiche'},
        {'key': 'score_seo', 'label': 'Score SEO (si analyse)'},
        {'key': 'score_pentest', 'label': 'Score pentest (si analyse)'},
    ]
