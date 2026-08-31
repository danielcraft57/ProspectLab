"""
Gestion des plans de campagnes hebdomadaires (plusieurs envois / semaine par groupe).
"""

import json
from .base import DatabaseBase


class WeeklyPlanManager(DatabaseBase):
    """CRUD pour les plans hebdomadaires et liaison avec les campagnes."""

    def create_plan(
        self,
        nom,
        groupe_id,
        slots_json,
        delay=2,
        mail_account_id=None,
        statut='active',
        recurrence_enabled=False,
        rotation_mode='all',
        slot_pattern_json=None,
    ):
        """
        Crée un plan hebdomadaire.

        @param nom: Nom du plan
        @param groupe_id: ID du groupe ciblé
        @param slots_json: JSON des créneaux absolus (première semaine)
        @param delay: Délai entre envois (secondes)
        @param mail_account_id: Compte SMTP optionnel
        @param statut: active | completed | cancelled
        @param recurrence_enabled: Reprogrammer chaque semaine
        @param rotation_mode: all | split (répartition A/B/C/D)
        @param slot_pattern_json: Motif récurrent (weekday, hour, template_id)
        @returns: ID du plan créé
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        params = (
            nom, groupe_id, statut, slots_json, delay, mail_account_id,
            1 if recurrence_enabled else 0, rotation_mode, slot_pattern_json,
        )
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                INSERT INTO plans_campagne_hebdo (
                    nom, groupe_id, statut, slots_json, delay, mail_account_id,
                    recurrence_enabled, rotation_mode, slot_pattern_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                ''',
                params,
            )
            row = cursor.fetchone()
            plan_id = row.get('id') if isinstance(row, dict) else (row[0] if row else None)
        else:
            self.execute_sql(
                cursor,
                '''
                INSERT INTO plans_campagne_hebdo (
                    nom, groupe_id, statut, slots_json, delay, mail_account_id,
                    recurrence_enabled, rotation_mode, slot_pattern_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                params,
            )
            plan_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return plan_id

    def get_plan(self, plan_id):
        """Récupère un plan par ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            'SELECT * FROM plans_campagne_hebdo WHERE id = ?',
            (plan_id,),
        )
        row = cursor.fetchone()
        conn.close()
        if not row:
            return None
        plan = dict(row)
        try:
            plan['slots'] = json.loads(plan.get('slots_json') or '[]')
        except (json.JSONDecodeError, TypeError):
            plan['slots'] = []
        try:
            plan['slot_pattern'] = json.loads(plan.get('slot_pattern_json') or '[]')
        except (json.JSONDecodeError, TypeError):
            plan['slot_pattern'] = []
        plan['recurrence_enabled'] = bool(plan.get('recurrence_enabled'))
        return plan

    def list_plans(self, groupe_id=None, statut=None, limit=50, recurrence_only=False):
        """Liste les plans hebdomadaires."""
        conn = self.get_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT p.*, g.nom AS groupe_nom,
                   (SELECT COUNT(*) FROM campagnes_email c WHERE c.plan_hebdo_id = p.id) AS campagnes_count
            FROM plans_campagne_hebdo p
            LEFT JOIN groupes_entreprises g ON g.id = p.groupe_id
            WHERE 1=1
        '''
        params = []
        if groupe_id is not None:
            sql += ' AND p.groupe_id = ?'
            params.append(groupe_id)
        if statut:
            sql += ' AND p.statut = ?'
            params.append(statut)
        if recurrence_only:
            sql += ' AND p.recurrence_enabled = 1'
        sql += ' ORDER BY p.date_creation DESC LIMIT ?'
        params.append(limit)
        self.execute_sql(cursor, sql, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        for plan in rows:
            try:
                plan['slots'] = json.loads(plan.get('slots_json') or '[]')
            except (json.JSONDecodeError, TypeError):
                plan['slots'] = []
            try:
                plan['slot_pattern'] = json.loads(plan.get('slot_pattern_json') or '[]')
            except (json.JSONDecodeError, TypeError):
                plan['slot_pattern'] = []
            plan['recurrence_enabled'] = bool(plan.get('recurrence_enabled'))
        return rows

    def list_active_recurring_plans(self):
        """Plans actifs avec récurrence hebdomadaire."""
        return self.list_plans(statut='active', recurrence_only=True, limit=200)

    def update_plan_statut(self, plan_id, statut):
        """Met à jour le statut d'un plan."""
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            'UPDATE plans_campagne_hebdo SET statut = ? WHERE id = ?',
            (statut, plan_id),
        )
        conn.commit()
        conn.close()

    def update_recurrence_meta(self, plan_id, last_recurrence_at=None, next_recurrence_at=None):
        """Met à jour les horodatages de récurrence."""
        conn = self.get_connection()
        cursor = conn.cursor()
        fields = []
        params = []
        if last_recurrence_at is not None:
            fields.append('last_recurrence_at = ?')
            params.append(last_recurrence_at)
        if next_recurrence_at is not None:
            fields.append('next_recurrence_at = ?')
            params.append(next_recurrence_at)
        if not fields:
            conn.close()
            return
        params.append(plan_id)
        self.execute_sql(
            cursor,
            f"UPDATE plans_campagne_hebdo SET {', '.join(fields)} WHERE id = ?",
            tuple(params),
        )
        conn.commit()
        conn.close()

    def get_campagnes_for_plan(self, plan_id):
        """Liste les campagnes liées à un plan."""
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(
            cursor,
            '''
            SELECT id, nom, template_id, sujet, statut, scheduled_at, total_destinataires
            FROM campagnes_email
            WHERE plan_hebdo_id = ?
            ORDER BY scheduled_at ASC, id ASC
            ''',
            (plan_id,),
        )
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows

    def get_calendar_events(self, date_from=None, date_to=None):
        """
        Événements calendrier : créneaux planifiés (campagnes liées aux plans actifs).

        @returns: Liste {plan_id, plan_nom, groupe_nom, campagne_id, scheduled_at, statut, template_id}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        sql = '''
            SELECT
                c.id AS campagne_id,
                c.nom AS campagne_nom,
                c.template_id,
                c.statut,
                c.scheduled_at,
                c.total_destinataires,
                p.id AS plan_id,
                p.nom AS plan_nom,
                p.rotation_mode,
                p.recurrence_enabled,
                g.nom AS groupe_nom
            FROM campagnes_email c
            INNER JOIN plans_campagne_hebdo p ON p.id = c.plan_hebdo_id
            LEFT JOIN groupes_entreprises g ON g.id = p.groupe_id
            WHERE c.plan_hebdo_id IS NOT NULL
              AND p.statut = 'active'
        '''
        params = []
        if date_from:
            sql += ' AND c.scheduled_at >= ?'
            params.append(date_from)
        if date_to:
            sql += ' AND c.scheduled_at <= ?'
            params.append(date_to)
        sql += ' ORDER BY c.scheduled_at ASC'
        self.execute_sql(cursor, sql, tuple(params))
        rows = [dict(r) for r in cursor.fetchall()]
        conn.close()
        return rows
