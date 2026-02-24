"""
Module de gestion des groupes d'entreprises.

Contient les opérations CRUD sur les groupes et l'association
many-to-many entre entreprises et groupes.
"""

from .base import DatabaseBase


class GroupeEntrepriseManager(DatabaseBase):
    """
    Gère les groupes d'entreprises et leurs associations.
    """

    def get_groupes_entreprises(self, entreprise_id=None):
        """
        Récupère la liste des groupes d'entreprises.

        Args:
            entreprise_id (int|None): Si fourni, ajoute un indicateur is_member
                pour savoir si l'entreprise donnée appartient à chaque groupe.

        Returns:
            list[dict]: Liste des groupes avec métadonnées.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if entreprise_id:
            self.execute_sql(
                cursor,
                '''
                SELECT
                    g.*,
                    (SELECT COUNT(*) FROM entreprise_groupes egc WHERE egc.groupe_id = g.id) AS entreprises_count,
                    EXISTS(
                        SELECT 1
                        FROM entreprise_groupes eg
                        WHERE eg.groupe_id = g.id AND eg.entreprise_id = ?
                    ) AS is_member
                FROM groupes_entreprises g
                ORDER BY g.date_creation DESC
                ''',
                (entreprise_id,),
            )
        else:
            self.execute_sql(
                cursor,
                '''
                SELECT
                    g.*,
                    (SELECT COUNT(*) FROM entreprise_groupes egc WHERE egc.groupe_id = g.id) AS entreprises_count
                FROM groupes_entreprises g
                ORDER BY g.date_creation DESC
                ''',
            )

        rows = cursor.fetchall()
        conn.close()

        groupes = [self.clean_row_dict(dict(row)) for row in rows]

        # Nettoyer pour la sérialisation JSON
        from utils.helpers import clean_json_dict

        return clean_json_dict(groupes)

    def create_groupe_entreprise(self, nom, description=None, couleur=None):
        """
        Crée un nouveau groupe d'entreprises.

        Args:
            nom (str): Nom du groupe.
            description (str|None): Description optionnelle.
            couleur (str|None): Couleur optionnelle (hex ou nom CSS).

        Returns:
            dict: Groupe créé.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        self.execute_sql(
            cursor,
            '''
            INSERT INTO groupes_entreprises (nom, description, couleur)
            VALUES (?, ?, ?)
            ''',
            (nom, description, couleur),
        )
        groupe_id = cursor.lastrowid
        try:
            conn.commit()
        except Exception:
            pass

        self.execute_sql(
            cursor,
            'SELECT * FROM groupes_entreprises WHERE id = ?',
            (groupe_id,),
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        groupe = self.clean_row_dict(dict(row))
        from utils.helpers import clean_json_dict

        return clean_json_dict(groupe)

    def delete_groupe_entreprise(self, groupe_id):
        """
        Supprime un groupe d'entreprises et toutes ses associations.

        Args:
            groupe_id (int): ID du groupe à supprimer.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Supprimer les associations d'abord (par sécurité, même si ON DELETE CASCADE)
        self.execute_sql(
            cursor,
            'DELETE FROM entreprise_groupes WHERE groupe_id = ?',
            (groupe_id,),
        )
        self.execute_sql(
            cursor,
            'DELETE FROM groupes_entreprises WHERE id = ?',
            (groupe_id,),
        )

        try:
            conn.commit()
        except Exception:
            pass
        conn.close()

    def add_entreprise_to_groupe(self, entreprise_id, groupe_id):
        """
        Ajoute une entreprise à un groupe (idempotent).

        Args:
            entreprise_id (int): ID de l'entreprise.
            groupe_id (int): ID du groupe.

        Returns:
            bool: True si l'association a été créée ou existait déjà, False si
                  l'entreprise ou le groupe n'existe pas (base incohérente).
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Vérifier que l'entreprise existe bien dans la même base
        self.execute_sql(
            cursor,
            'SELECT 1 FROM entreprises WHERE id = ?',
            (entreprise_id,),
        )
        entreprise_exists = cursor.fetchone() is not None

        # Vérifier que le groupe existe bien dans la même base
        self.execute_sql(
            cursor,
            'SELECT 1 FROM groupes_entreprises WHERE id = ?',
            (groupe_id,),
        )
        groupe_exists = cursor.fetchone() is not None

        if not (entreprise_exists and groupe_exists):
            conn.close()
            return False

        self.execute_sql(
            cursor,
            '''
            INSERT OR IGNORE INTO entreprise_groupes (entreprise_id, groupe_id)
            VALUES (?, ?)
            ''',
            (entreprise_id, groupe_id),
        )
        try:
            conn.commit()
        except Exception:
            pass
        conn.close()
        return True

    def remove_entreprise_from_groupe(self, entreprise_id, groupe_id):
        """
        Retire une entreprise d'un groupe.

        Args:
            entreprise_id (int): ID de l'entreprise.
            groupe_id (int): ID du groupe.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        self.execute_sql(
            cursor,
            'DELETE FROM entreprise_groupes WHERE entreprise_id = ? AND groupe_id = ?',
            (entreprise_id, groupe_id),
        )

        try:
            conn.commit()
        except Exception:
            pass
        conn.close()

