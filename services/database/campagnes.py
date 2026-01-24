"""
Module de gestion des campagnes email
Contient toutes les méthodes liées aux campagnes email
"""

import json
from .base import DatabaseBase


class CampagneManager(DatabaseBase):
    """
    Gère toutes les opérations sur les campagnes email
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module campagnes"""
        super().__init__(*args, **kwargs)
    
    def create_campagne(self, nom, template_id=None, sujet=None, total_destinataires=0, statut='draft'):
        """
        Crée une nouvelle campagne email.

        Args:
            nom (str): Nom de la campagne
            template_id (str|None): ID du template utilisé (optionnel)
            sujet (str|None): Sujet de l'email (optionnel)
            total_destinataires (int): Nombre total de destinataires
            statut (str): Statut ('draft', 'scheduled', 'running', 'completed', 'failed')

        Returns:
            int: ID de la campagne créée
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        self.execute_sql(cursor,
            '''
            INSERT INTO campagnes_email (nom, template_id, sujet, total_destinataires, total_envoyes, total_reussis, statut)
            VALUES (?, ?, ?, ?, 0, 0, ?)
            ''',
            (nom, template_id, sujet, total_destinataires, statut)
        )

        campagne_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return campagne_id

    def update_campagne(
        self,
        campagne_id,
        nom=None,
        template_id=None,
        sujet=None,
        total_destinataires=None,
        total_envoyes=None,
        total_reussis=None,
        statut=None
    ):
        """
        Met à jour une campagne email.

        Args:
            campagne_id (int): ID de la campagne
            nom (str|None): Nouveau nom (optionnel)
            template_id (str|None): Nouveau template_id (optionnel)
            sujet (str|None): Nouveau sujet (optionnel)
            total_destinataires (int|None): Nouveau total (optionnel)
            total_envoyes (int|None): Nouveau total envoyés (optionnel)
            total_reussis (int|None): Nouveau total réussis (optionnel)
            statut (str|None): Nouveau statut (optionnel)

        Returns:
            bool: True si mis à jour, False sinon
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        updates = []
        values = []

        if nom is not None:
            updates.append('nom = ?')
            values.append(nom)
        if template_id is not None:
            updates.append('template_id = ?')
            values.append(template_id)
        if sujet is not None:
            updates.append('sujet = ?')
            values.append(sujet)
        if total_destinataires is not None:
            updates.append('total_destinataires = ?')
            values.append(total_destinataires)
        if total_envoyes is not None:
            updates.append('total_envoyes = ?')
            values.append(total_envoyes)
        if total_reussis is not None:
            updates.append('total_reussis = ?')
            values.append(total_reussis)
        if statut is not None:
            updates.append('statut = ?')
            values.append(statut)

        if not updates:
            conn.close()
            return False

        values.append(campagne_id)
        query = f'UPDATE campagnes_email SET {", ".join(updates)} WHERE id = ?'

        self.execute_sql(cursor,query, values)
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def get_campagne(self, campagne_id):
        """
        Récupère une campagne par son ID.

        Args:
            campagne_id (int): ID de la campagne

        Returns:
            dict|None: Données de la campagne ou None
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        self.execute_sql(cursor,'SELECT * FROM campagnes_email WHERE id = ?', (campagne_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return dict(row)
        return None

    def list_campagnes(self, statut=None, limit=100, offset=0):
        """
        Liste les campagnes.

        Args:
            statut (str|None): Filtrer par statut (optionnel)
            limit (int): Nombre maximum de résultats
            offset (int): Offset pour la pagination

        Returns:
            list[dict]: Liste des campagnes
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        if statut:
            self.execute_sql(cursor,
                '''
                SELECT * FROM campagnes_email
                WHERE statut = ?
                ORDER BY date_creation DESC
                LIMIT ? OFFSET ?
                ''',
                (statut, limit, offset)
            )
        else:
            self.execute_sql(cursor,
                '''
                SELECT * FROM campagnes_email
                ORDER BY date_creation DESC
                LIMIT ? OFFSET ?
                ''',
                (limit, offset)
            )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_email_envoye(
        self,
        campagne_id,
        entreprise_id=None,
        email=None,
        nom_destinataire=None,
        entreprise=None,
        sujet=None,
        statut='sent',
        erreur=None,
        tracking_token=None
    ):
        """
        Sauvegarde un email envoyé dans la base.

        Args:
            campagne_id (int): ID de la campagne
            entreprise_id (int|None): ID de l'entreprise (optionnel)
            email (str|None): Adresse email du destinataire
            nom_destinataire (str|None): Nom du destinataire (optionnel)
            entreprise (str|None): Nom entreprise (optionnel - compat)
            sujet (str|None): Sujet de l'email
            statut (str): Statut ('pending', 'sent', 'failed', 'bounced')
            erreur (str|None): Message d'erreur si échec (optionnel)
            tracking_token (str|None): Token de tracking unique (optionnel)

        Returns:
            int: ID de l'email enregistré
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # On s'adapte au schéma existant (certains environnements n'ont pas encore tracking_token)
        self.execute_sql(cursor,"PRAGMA table_info(emails_envoyes)")
        cols = {row[1] for row in cursor.fetchall()}

        if 'tracking_token' in cols:
            self.execute_sql(cursor,
                '''
                INSERT INTO emails_envoyes
                (campagne_id, entreprise_id, email, nom_destinataire, entreprise, sujet, statut, erreur, tracking_token)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (campagne_id, entreprise_id, email, nom_destinataire, entreprise, sujet, statut, erreur, tracking_token)
            )
        else:
            self.execute_sql(cursor,
                '''
                INSERT INTO emails_envoyes
                (campagne_id, entreprise_id, email, nom_destinataire, entreprise, sujet, statut, erreur)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (campagne_id, entreprise_id, email, nom_destinataire, entreprise, sujet, statut, erreur)
            )

        email_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return email_id

    def update_email_tracking_token(self, email_id, tracking_token):
        """
        Met à jour le token de tracking d'un email.

        Args:
            email_id (int): ID de l'email
            tracking_token (str): Token de tracking unique

        Returns:
            bool: True si mis à jour
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Si la colonne n'existe pas encore, on ne fait rien (schéma pas migré)
        self.execute_sql(cursor,"PRAGMA table_info(emails_envoyes)")
        cols = {row[1] for row in cursor.fetchall()}
        if 'tracking_token' not in cols:
            conn.close()
            return False

        self.execute_sql(cursor,'UPDATE emails_envoyes SET tracking_token = ? WHERE id = ?', (tracking_token, email_id))
        conn.commit()
        updated = cursor.rowcount > 0
        conn.close()
        return updated

    def get_emails_campagne(self, campagne_id):
        """
        Récupère tous les emails d'une campagne.

        Args:
            campagne_id (int): ID de la campagne

        Returns:
            list[dict]: Liste des emails envoyés
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        self.execute_sql(cursor,
            '''
            SELECT
                e.*,
                ent.nom as entreprise_nom
            FROM emails_envoyes e
            LEFT JOIN entreprises ent ON e.entreprise_id = ent.id
            WHERE e.campagne_id = ?
            ORDER BY e.date_envoi DESC
            ''',
            (campagne_id,)
        )

        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def save_tracking_event(self, tracking_token, event_type, event_data=None, ip_address=None, user_agent=None):
        """
        Enregistre un événement de tracking.

        Args:
            tracking_token (str): Token de tracking unique
            event_type (str): Type d'événement ('open', 'click', 'read_time')
            event_data (str|dict|None): Données supplémentaires
            ip_address (str|None): IP du client
            user_agent (str|None): User agent du client

        Returns:
            int|None: ID de l'événement enregistré
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Table pas encore créée -> tracking désactivé
        try:
            self.execute_sql(cursor,"SELECT 1 FROM email_tracking_events LIMIT 1")
        except Exception:
            import logging
            logging.getLogger(__name__).warning('Table email_tracking_events n\'existe pas encore')
            conn.close()
            return None

        self.execute_sql(cursor,'SELECT id FROM emails_envoyes WHERE tracking_token = ?', (tracking_token,))
        row = cursor.fetchone()
        if not row:
            import logging
            logging.getLogger(__name__).warning(f'Token de tracking non trouvé: {tracking_token[:10]}...')
            conn.close()
            return None

        email_id = row[0]

        if isinstance(event_data, dict):
            event_data = json.dumps(event_data)

        self.execute_sql(cursor,
            '''
            INSERT INTO email_tracking_events
            (email_id, tracking_token, event_type, event_data, ip_address, user_agent)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (email_id, tracking_token, event_type, event_data, ip_address, user_agent)
        )

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return event_id

    def get_email_tracking_stats(self, email_id):
        """
        Récupère les stats de tracking pour un email.

        Args:
            email_id (int): ID de l'email

        Returns:
            dict: Statistiques de tracking
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        # Si la table n'existe pas, on renvoie un résultat vide
        try:
            self.execute_sql(cursor,"SELECT 1 FROM email_tracking_events LIMIT 1")
        except Exception:
            conn.close()
            return {
                'email_id': email_id,
                'events_by_type': {},
                'total_opens': 0,
                'total_clicks': 0,
                'avg_read_time': None,
                'first_open': None,
                'last_open': None,
                'events': []
            }

        self.execute_sql(cursor,
            '''
            SELECT event_type, COUNT(*) as count, MIN(date_event) as first_event, MAX(date_event) as last_event
            FROM email_tracking_events
            WHERE email_id = ?
            GROUP BY event_type
            ''',
            (email_id,)
        )

        events_by_type = {}
        for row in cursor.fetchall():
            events_by_type[row['event_type']] = {
                'count': row['count'],
                'first_event': row['first_event'],
                'last_event': row['last_event']
            }

        self.execute_sql(cursor,
            '''
            SELECT AVG(CAST(json_extract(event_data, '$.read_time') AS REAL)) as avg_read_time
            FROM email_tracking_events
            WHERE email_id = ? AND event_type = 'read_time' AND event_data IS NOT NULL
            ''',
            (email_id,)
        )
        avg_read_time_row = cursor.fetchone()
        avg_read_time = avg_read_time_row['avg_read_time'] if avg_read_time_row and avg_read_time_row['avg_read_time'] else None

        self.execute_sql(cursor,
            '''
            SELECT * FROM email_tracking_events
            WHERE email_id = ?
            ORDER BY date_event ASC
            ''',
            (email_id,)
        )
        events = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return {
            'email_id': email_id,
            'events_by_type': events_by_type,
            'total_opens': events_by_type.get('open', {}).get('count', 0),
            'total_clicks': events_by_type.get('click', {}).get('count', 0),
            'avg_read_time': avg_read_time,
            'first_open': events_by_type.get('open', {}).get('first_event'),
            'last_open': events_by_type.get('open', {}).get('last_event'),
            'events': events
        }

    def get_campagne_tracking_stats(self, campagne_id):
        """
        Récupère les stats de tracking agrégées pour une campagne.

        Args:
            campagne_id (int): ID de la campagne

        Returns:
            dict: Stats agrégées + détails par email
        """
        conn = self.get_connection()
        # row_factory est déjà configuré dans get_connection() (SQLite) ou via RealDictCursor (PostgreSQL)
        cursor = conn.cursor()

        self.execute_sql(cursor,
            '''
            SELECT
                e.id,
                e.email,
                e.nom_destinataire,
                e.entreprise,
                e.sujet,
                e.date_envoi,
                e.statut,
                e.erreur,
                e.entreprise_id,
                ent.nom as entreprise_nom
            FROM emails_envoyes e
            LEFT JOIN entreprises ent ON e.entreprise_id = ent.id
            WHERE e.campagne_id = ?
            ORDER BY e.date_envoi DESC
            ''',
            (campagne_id,)
        )

        emails = [dict(row) for row in cursor.fetchall()]
        email_ids = [e['id'] for e in emails]

        # Pas d'emails => stats vides
        if not email_ids:
            conn.close()
            return {
                'campagne_id': campagne_id,
                'total_emails': 0,
                'total_opens': 0,
                'total_clicks': 0,
                'open_rate': 0,
                'click_rate': 0,
                'avg_read_time': None,
                'emails': []
            }

        # Si la table n'existe pas, on renvoie juste la liste
        try:
            self.execute_sql(cursor,"SELECT 1 FROM email_tracking_events LIMIT 1")
        except Exception:
            conn.close()
            return {
                'campagne_id': campagne_id,
                'total_emails': len(emails),
                'total_opens': 0,
                'total_clicks': 0,
                'open_rate': 0,
                'click_rate': 0,
                'avg_read_time': None,
                'emails': emails
            }

        placeholders = ','.join(['?'] * len(email_ids))

        self.execute_sql(cursor,
            f'''
            SELECT
                email_id,
                event_type,
                COUNT(*) as count,
                MIN(date_event) as first_event,
                MAX(date_event) as last_event
            FROM email_tracking_events
            WHERE email_id IN ({placeholders})
            GROUP BY email_id, event_type
            ''',
            email_ids
        )

        stats_by_email = {}
        for row in cursor.fetchall():
            email_id = row['email_id']
            if email_id not in stats_by_email:
                stats_by_email[email_id] = {}
            stats_by_email[email_id][row['event_type']] = {
                'count': row['count'],
                'first_event': row['first_event'],
                'last_event': row['last_event']
            }

        self.execute_sql(cursor,
            f'''
            SELECT
                event_type,
                COUNT(DISTINCT email_id) as unique_emails,
                COUNT(*) as total_events
            FROM email_tracking_events
            WHERE email_id IN ({placeholders})
            GROUP BY event_type
            ''',
            email_ids
        )

        stats_by_type = {}
        for row in cursor.fetchall():
            stats_by_type[row['event_type']] = {
                'unique_emails': row['unique_emails'],
                'total_events': row['total_events']
            }

        self.execute_sql(cursor,
            f'''
            SELECT AVG(CAST(json_extract(event_data, '$.read_time') AS REAL)) as avg_read_time
            FROM email_tracking_events
            WHERE email_id IN ({placeholders}) AND event_type = 'read_time' AND event_data IS NOT NULL
            ''',
            email_ids
        )
        avg_read_time_row = cursor.fetchone()
        avg_read_time = avg_read_time_row['avg_read_time'] if avg_read_time_row and avg_read_time_row['avg_read_time'] else None

        for email in emails:
            email_id = email['id']
            email_stats = stats_by_email.get(email_id, {})
            email['opens'] = email_stats.get('open', {}).get('count', 0)
            email['clicks'] = email_stats.get('click', {}).get('count', 0)
            email['first_open'] = email_stats.get('open', {}).get('first_event')
            email['last_open'] = email_stats.get('open', {}).get('last_event')
            email['has_opened'] = email['opens'] > 0
            email['has_clicked'] = email['clicks'] > 0

        conn.close()

        total_emails = len(emails)
        total_opens = stats_by_type.get('open', {}).get('unique_emails', 0)
        total_clicks = stats_by_type.get('click', {}).get('unique_emails', 0)

        return {
            'campagne_id': campagne_id,
            'total_emails': total_emails,
            'total_opens': total_opens,
            'total_clicks': total_clicks,
            'open_rate': (total_opens / total_emails * 100) if total_emails > 0 else 0,
            'click_rate': (total_clicks / total_emails * 100) if total_emails > 0 else 0,
            'avg_read_time': avg_read_time,
            'stats_by_type': stats_by_type,
            'emails': emails
        }
