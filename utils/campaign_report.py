"""
Libellés expressifs pour les rapports de campagnes ProspectLab.

Fournit titres, sujets et impressions de résultats avec un vocabulaire varié.
"""

from __future__ import annotations

from datetime import date
from typing import Mapping, Sequence, Tuple


def _phrase_from_threshold(value: float, buckets: Sequence[Tuple[float, str]], default: str = '') -> str:
    """
    Retourne la phrase associée au premier seuil atteint (buckets décroissants).

    @param value: Valeur numérique à comparer
    @param buckets: Liste (seuil_min, phrase)
    @param default: Fallback si aucun seuil
    @returns: Libellé choisi
    """
    for threshold, phrase in buckets:
        if value >= threshold:
            return phrase
    return default or (buckets[-1][1] if buckets else '')


def impression_open(rate: float) -> str:
    """Impression qualitative du taux d'ouverture."""
    return _phrase_from_threshold(
        float(rate or 0),
        [
            (45, 'boîte mail en ébullition'),
            (35, 'curiosité vive'),
            (25, 'belle accroche'),
            (15, 'intérêt mesuré'),
            (5, 'filtrage sélectif'),
            (0, 'silence relatif'),
        ],
    )


def impression_click(rate: float) -> str:
    """Impression qualitative du taux de clic."""
    return _phrase_from_threshold(
        float(rate or 0),
        [
            (12, 'clic irrésistible'),
            (8, 'forte intention'),
            (5, 'engagement net'),
            (2, 'quelques curieux'),
            (0.5, 'clics timides'),
            (0, 'pas encore de réaction'),
        ],
    )


def impression_campaign(cs: Mapping) -> str:
    """
    Synthèse expressive pour une campagne.

    @param cs: Dict avec open_rate, click_rate, total_emails
    @returns: Phrase d'impression
    """
    open_rate = float(cs.get('open_rate') or 0)
    click_rate = float(cs.get('click_rate') or 0)
    total_emails = int(cs.get('total_emails') or 0)
    open_txt = impression_open(open_rate)
    click_txt = impression_click(click_rate)

    if open_rate >= 35 and click_rate >= 5:
        verdict = 'séquence en pleine forme'
    elif open_rate >= 25 and click_rate >= 2:
        verdict = 'bonne dynamique'
    elif open_rate >= 15:
        verdict = 'premiers signaux encourageants'
    elif total_emails >= 20 and open_rate < 5:
        verdict = 'diffusion large, écho encore discret'
    elif total_emails < 3:
        verdict = 'échantillon léger'
    else:
        verdict = 'mise en place en cours de mesure'

    return f'{verdict} — {open_txt}, {click_txt}'


def short_impression(campagnes_stats: Sequence[Mapping]) -> str:
    """Accroche courte pour l'objet d'email."""
    if not campagnes_stats:
        return 'période calme'
    avg_open = sum(float(cs.get('open_rate') or 0) for cs in campagnes_stats) / len(campagnes_stats)
    if avg_open >= 35:
        return 'les boîtes s\'ouvrent'
    if avg_open >= 22:
        return 'belle curiosité'
    if avg_open >= 10:
        return 'signaux timides'
    return 'échos en gestation'


def global_impression(campagnes_stats: Sequence[Mapping]) -> str:
    """Paragraphe de synthèse globale sur la période."""
    if not campagnes_stats:
        return 'Période calme : aucun envoi significatif à raconter pour l\'instant.'

    avg_open = sum(float(cs.get('open_rate') or 0) for cs in campagnes_stats) / len(campagnes_stats)
    avg_click = sum(float(cs.get('click_rate') or 0) for cs in campagnes_stats) / len(campagnes_stats)
    total = sum(int(cs.get('total_emails') or 0) for cs in campagnes_stats)
    count = len(campagnes_stats)

    if avg_open >= 30 and avg_click >= 4:
        mood = 'La prospection respire fort'
    elif avg_open >= 20:
        mood = 'Belle visibilité sur cette tranche'
    elif total >= 50:
        mood = 'Volume solide, patience sur les retours'
    else:
        mood = 'Premiers bilans en construction'

    return (
        f'{mood} : {count} campagne(s), {total} envois, '
        f'ouverture {impression_open(avg_open)} ({avg_open:.1f} %), '
        f'clics {impression_click(avg_click)} ({avg_click:.1f} %).'
    )


def compose_periodic_report_header(
    report_type: str,
    period_date: date,
    campagnes_stats: Sequence[Mapping],
) -> Tuple[str, str, str]:
    """
    Construit titre, sujet et impression globale pour les rapports matin/soir.

    @param report_type: 'evening' (campagnes du matin) ou 'morning' (PM veille)
    @param period_date: Date de la période couverte
    @param campagnes_stats: Stats des campagnes incluses
    @returns: (title, subject, global_impression_text)
    """
    date_label = period_date.strftime('%d/%m/%Y')
    count = len(campagnes_stats) if campagnes_stats else 0
    impression = global_impression(campagnes_stats)

    if report_type == 'evening':
        if count == 0:
            title = f'Relevé du matin — {date_label}'
            subject = f'[ProspectLab] Matinée tranquille · {date_label}'
        elif count == 1:
            title = f'Point chaud du matin — {date_label}'
            subject = f'[ProspectLab] Bilan matinal · {date_label} — {short_impression(campagnes_stats)}'
        else:
            title = f'Radiographie du matin — {date_label}'
            subject = f'[ProspectLab] {count} campagnes ce matin · {date_label} — {short_impression(campagnes_stats)}'
    else:
        if count == 0:
            title = f'Écho de l\'après-midi — {date_label}'
            subject = f'[ProspectLab] Soirée calme · {date_label}'
        elif count == 1:
            title = f'Flash de fin de journée — {date_label}'
            subject = f'[ProspectLab] Retour du créneau PM · {date_label} — {short_impression(campagnes_stats)}'
        else:
            title = f'Carnet de l\'après-midi — {date_label}'
            subject = f'[ProspectLab] {count} envois hier PM · {date_label} — {short_impression(campagnes_stats)}'

    return title, subject, impression


def compose_single_campagne_header(
    nom: str,
    campagne_id: int,
    open_rate: float,
    click_rate: float,
    date_label: str,
) -> Tuple[str, str, str]:
    """
    Titre, sujet et impression pour le rapport détaillé d'une campagne.

    @returns: (title, subject, impression)
    """
    label = nom or f'Campagne #{campagne_id}'
    stats = {'open_rate': open_rate, 'click_rate': click_rate, 'total_emails': 0}
    impression = impression_campaign(stats)
    title = f'Fiche résultats — {label}'
    hook = impression.split('—')[0].strip()
    subject = f'[ProspectLab] {label} · {hook} — {date_label}'
    return title, subject, impression


def compose_stabilization_header(count: int) -> Tuple[str, str]:
    """Titre et sujet pour le rapport de stabilisation."""
    if count <= 1:
        title = 'Pulse campagne — stabilisation confirmée'
        subject = '[ProspectLab] Stabilisation · une séquence au point'
    else:
        title = f'Pulse campagne — {count} stabilisations confirmées'
        subject = f'[ProspectLab] Stabilisation · {count} séquences au point'
    return title, subject
