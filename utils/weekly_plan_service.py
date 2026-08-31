"""Génération des campagnes pour plans hebdomadaires (récurrence, rotation)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from utils.campaign_exclusions import split_recipients_for_rotation
from utils.campaign_recipients import filter_campagne_recipients
from utils.email_subject import clean_email_subject
from utils.weekly_plan_recipients import build_recipients_from_groupe

PARIS = ZoneInfo('Europe/Paris')


def build_slot_pattern_from_slots(slots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extrait un motif récurrent (jour/heure/modèle) depuis des créneaux absolus.

    @param slots: Créneaux avec scheduled_at ISO
    @returns: Pattern [{weekday, hour, minute, template_id, sujet, enabled}]
    """
    pattern = []
    for slot in slots or []:
        scheduled_at = slot.get('scheduled_at') or slot.get('scheduled_at_iso')
        if not scheduled_at:
            continue
        try:
            dt = datetime.fromisoformat(str(scheduled_at).replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local = dt.astimezone(PARIS)
        except (ValueError, TypeError):
            continue
        pattern.append({
            'weekday': local.isoweekday(),
            'hour': local.hour,
            'minute': local.minute,
            'template_id': slot.get('template_id'),
            'sujet': slot.get('sujet'),
            'enabled': slot.get('enabled', True),
            'label': slot.get('label'),
        })
    return pattern


def compute_week_monday(reference: Optional[datetime] = None) -> datetime:
    """Lundi 00:00 (heure Paris) de la semaine cible pour la génération."""
    ref = reference or datetime.now(PARIS)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=PARIS)
    monday = ref - timedelta(days=ref.isoweekday() - 1)
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)


def compute_next_week_monday(reference: Optional[datetime] = None) -> datetime:
    """Lundi de la semaine suivante (heure Paris)."""
    return compute_week_monday(reference) + timedelta(days=7)


def slot_datetimes_for_week(
    slot_pattern: List[Dict[str, Any]],
    week_monday: datetime,
) -> List[Dict[str, Any]]:
    """
    Calcule les datetimes UTC pour chaque créneau actif d'une semaine.

    @param slot_pattern: Motif récurrent
    @param week_monday: Lundi 00:00 Paris de la semaine
    @returns: Liste enrichie avec scheduled_at (UTC ISO)
    """
    result = []
    for slot in slot_pattern or []:
        if slot.get('enabled') is False:
            continue
        weekday = int(slot.get('weekday') or 1)
        hour = int(slot.get('hour') or 9)
        minute = int(slot.get('minute') or 0)
        local_dt = week_monday + timedelta(days=weekday - 1)
        local_dt = local_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        utc_dt = local_dt.astimezone(timezone.utc)
        result.append({
            **slot,
            'scheduled_at': utc_dt.strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        })
    return result


def generate_weekly_plan_campaigns(
    plan: Dict[str, Any],
    *,
    week_monday: Optional[datetime] = None,
    templates_by_id: Optional[Dict[str, Dict]] = None,
) -> Dict[str, Any]:
    """
    Génère les campagnes programmées pour une semaine donnée.

    @param plan: Plan hebdomadaire (dict BDD)
    @param week_monday: Lundi de la semaine cible (Paris)
    @returns: {created: [...], skipped: bool, reason: str}
    """
    from services.database.campagnes import CampagneManager
    from services.database.weekly_plans import WeeklyPlanManager
    from services.database.groupes import GroupeEntrepriseManager
    from services.template_manager import TemplateManager

    plan_id = plan.get('id')
    groupe_id = plan.get('groupe_id')
    if not plan_id or not groupe_id:
        return {'created': [], 'skipped': True, 'reason': 'plan_invalide'}

    wm = week_monday or compute_next_week_monday()
    pattern = plan.get('slot_pattern') or []
    if not pattern:
        try:
            pattern = json.loads(plan.get('slot_pattern_json') or '[]')
        except (json.JSONDecodeError, TypeError):
            pattern = []
    if not pattern:
        slots_legacy = plan.get('slots') or []
        try:
            if not slots_legacy:
                slots_legacy = json.loads(plan.get('slots_json') or '[]')
        except (json.JSONDecodeError, TypeError):
            slots_legacy = []
        pattern = build_slot_pattern_from_slots(slots_legacy)

    active_slots = slot_datetimes_for_week(pattern, wm)
    if not active_slots:
        return {'created': [], 'skipped': True, 'reason': 'aucun_creneau'}

    now_utc = datetime.now(timezone.utc)
    active_slots = [
        s for s in active_slots
        if datetime.fromisoformat(s['scheduled_at'].replace('Z', '+00:00')) > now_utc
    ]
    if not active_slots:
        return {'created': [], 'skipped': True, 'reason': 'creneaux_passes'}

    plan_mgr = WeeklyPlanManager()
    existing = plan_mgr.get_campagnes_for_plan(plan_id)
    week_end = wm + timedelta(days=7)
    for camp in existing:
        sat = camp.get('scheduled_at')
        if not sat:
            continue
        try:
            dt = datetime.fromisoformat(str(sat).replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local = dt.astimezone(PARIS)
            if wm <= local < week_end and camp.get('statut') in ('scheduled', 'running', 'draft'):
                return {'created': [], 'skipped': True, 'reason': 'deja_genere'}
        except (ValueError, TypeError):
            continue

    groupe_mgr = GroupeEntrepriseManager()
    all_groupes = groupe_mgr.get_groupes_entreprises() or []
    groupe = next((g for g in all_groupes if g.get('id') == groupe_id), None)
    groupe_nom = (groupe or {}).get('nom') or 'Groupe'

    recipients = build_recipients_from_groupe(int(groupe_id))
    recipients, filter_stats = filter_campagne_recipients(
        recipients,
        exclude_risky=True,
        max_emails_per_entreprise=2,
        exclude_unreachable=True,
    )
    if not recipients:
        return {'created': [], 'skipped': True, 'reason': 'aucun_destinataire', 'filter_stats': filter_stats}

    if templates_by_id is None:
        tm = TemplateManager()
        templates_by_id = {t.get('id'): t for t in (tm.list_templates() or []) if t.get('id')}

    rotation_mode = (plan.get('rotation_mode') or 'all').strip().lower()
    delay = int(plan.get('delay') or 2)
    mail_account_id = plan.get('mail_account_id')
    campagne_mgr = CampagneManager()

    recipient_chunks = [recipients]
    if rotation_mode == 'split' and len(active_slots) > 1:
        recipient_chunks = split_recipients_for_rotation(recipients, len(active_slots))

    created = []
    for idx, slot in enumerate(active_slots):
        slot_recipients = recipient_chunks[idx] if idx < len(recipient_chunks) else []
        if not slot_recipients:
            continue
        template_id = (slot.get('template_id') or '').strip()
        if not template_id:
            continue
        tpl = templates_by_id.get(template_id) or {}
        sujet = clean_email_subject(str(slot.get('sujet') or tpl.get('subject') or 'Prospection')) or 'Prospection'
        tpl_name = tpl.get('name') or template_id
        date_label = slot['scheduled_at'][:10]
        campagne_nom = clean_email_subject(f"{tpl_name} — {groupe_nom} — {date_label}") or plan.get('nom', 'Plan')

        campaign_params = {
            'recipients': slot_recipients,
            'template_id': template_id,
            'subject': sujet,
            'delay': delay,
            'mail_account_id': mail_account_id,
            'groupe_ids': [int(groupe_id)],
            'groupe_id': int(groupe_id),
            'plan_hebdo_id': plan_id,
            'slot_index': idx,
            'rotation_mode': rotation_mode,
        }
        campagne_id = campagne_mgr.create_campagne(
            nom=campagne_nom,
            template_id=template_id,
            sujet=sujet,
            total_destinataires=len(slot_recipients),
            statut='scheduled',
            scheduled_at=slot['scheduled_at'],
            campaign_params_json=json.dumps(campaign_params),
            mail_account_id=mail_account_id,
            plan_hebdo_id=plan_id,
        )
        created.append({
            'campagne_id': campagne_id,
            'nom': campagne_nom,
            'scheduled_at': slot['scheduled_at'],
            'destinataires': len(slot_recipients),
        })

    if created:
        plan_mgr.update_recurrence_meta(
            plan_id,
            last_recurrence_at=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
            next_recurrence_at=(wm + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M:%S.000Z'),
        )

    return {
        'created': created,
        'skipped': False,
        'filter_stats': filter_stats,
        'week_monday': wm.strftime('%Y-%m-%d'),
    }
