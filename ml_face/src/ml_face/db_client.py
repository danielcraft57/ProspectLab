from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from services.database.base import DatabaseBase


@dataclass(frozen=True)
class MLRun:
    id: int
    name: str


def _b64_encode_f32(vec: np.ndarray) -> str:
    v = np.asarray(vec, dtype=np.float32)
    return base64.b64encode(v.tobytes()).decode("ascii")


def _b64_decode_f32(payload: str, dim: int) -> np.ndarray:
    raw = base64.b64decode(payload.encode("ascii"))
    arr = np.frombuffer(raw, dtype=np.float32)
    if int(arr.shape[0]) != int(dim):
        raise ValueError("Dimension embedding incoherente")
    return arr


class MLFaceDB(DatabaseBase):
    """
    Client BDD pour la partie reconnaissance faciale.
    Utilise la meme detection SQLite/dev vs PostgreSQL/prod que le reste de l'app.
    """

    def ensure_schema(self) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                """
                CREATE TABLE IF NOT EXISTS ml_face_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """,
            )
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_runs_created_at ON ml_face_runs(created_at)")
            if self.is_postgresql():
                conn.commit()

            self.execute_sql(
                cursor,
                """
                CREATE TABLE IF NOT EXISTS ml_face_embeddings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    image_id INTEGER,
                    entreprise_id INTEGER,
                    source_path TEXT NOT NULL,
                    source_url TEXT,
                    face_index INTEGER NOT NULL,
                    crop_path TEXT,
                    probability REAL,
                    box_json TEXT,
                    image_width INTEGER,
                    image_height INTEGER,
                    embedding_b64 TEXT NOT NULL,
                    embedding_dim INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES ml_face_runs(id) ON DELETE CASCADE,
                    FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE,
                    FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE SET NULL
                )
                """,
            )
            # Sur certains contextes Postgres, mieux vaut "verrouiller" la DDL
            # avec un commit avant de creer les indexes.
            if self.is_postgresql():
                conn.commit()
            # Migration douce si la table existait deja
            self.safe_execute_sql(cursor, "ALTER TABLE ml_face_embeddings ADD COLUMN image_id INTEGER")
            self.safe_execute_sql(cursor, "ALTER TABLE ml_face_embeddings ADD COLUMN entreprise_id INTEGER")
            self.safe_execute_sql(cursor, "ALTER TABLE ml_face_embeddings ADD COLUMN source_url TEXT")
            self.safe_execute_sql(cursor, "ALTER TABLE ml_face_embeddings ADD COLUMN image_width INTEGER")
            self.safe_execute_sql(cursor, "ALTER TABLE ml_face_embeddings ADD COLUMN image_height INTEGER")
            self.execute_sql(
                cursor,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_ml_face_embeddings_run_source_face ON ml_face_embeddings(run_id, source_path, face_index)",
            )
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_embeddings_run_id ON ml_face_embeddings(run_id)")
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_embeddings_image_id ON ml_face_embeddings(image_id)")
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_embeddings_entreprise_id ON ml_face_embeddings(entreprise_id)")

            self.execute_sql(
                cursor,
                """
                CREATE TABLE IF NOT EXISTS ml_face_identities (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id INTEGER NOT NULL,
                    identity_index INTEGER NOT NULL,
                    threshold REAL,
                    size INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (run_id) REFERENCES ml_face_runs(id) ON DELETE CASCADE
                )
                """,
            )
            self.execute_sql(
                cursor,
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_ml_face_identities_run_identity ON ml_face_identities(run_id, identity_index)",
            )
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_identities_run_id ON ml_face_identities(run_id)")

            self.execute_sql(
                cursor,
                """
                CREATE TABLE IF NOT EXISTS ml_face_identity_members (
                    identity_id INTEGER NOT NULL,
                    embedding_id INTEGER NOT NULL,
                    rank INTEGER,
                    PRIMARY KEY (identity_id, embedding_id),
                    FOREIGN KEY (identity_id) REFERENCES ml_face_identities(id) ON DELETE CASCADE,
                    FOREIGN KEY (embedding_id) REFERENCES ml_face_embeddings(id) ON DELETE CASCADE
                )
                """,
            )
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_members_identity ON ml_face_identity_members(identity_id)")
            self.execute_sql(cursor, "CREATE INDEX IF NOT EXISTS idx_ml_face_members_embedding ON ml_face_identity_members(embedding_id)")

            conn.commit()
        finally:
            conn.close()

    def create_run(self, name: str) -> MLRun:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(cursor, "INSERT INTO ml_face_runs (name) VALUES (?)", (name,))
            conn.commit()
            run_id = self._last_insert_id(cursor)
            return MLRun(id=run_id, name=name)
        finally:
            conn.close()

    def _last_insert_id(self, cursor) -> int:
        if self.is_postgresql():
            cursor.execute("SELECT LASTVAL()")
            row = cursor.fetchone()
            if isinstance(row, dict):
                return int(list(row.values())[0])
            return int(row[0])
        return int(cursor.lastrowid)

    def upsert_embedding(
        self,
        run_id: int,
        image_id: int | None,
        entreprise_id: int | None,
        source_path: str,
        source_url: str | None,
        face_index: int,
        crop_path: str | None,
        probability: float | None,
        box: list[float] | None,
        image_width: int | None,
        image_height: int | None,
        embedding: np.ndarray,
    ) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            box_json = None if box is None else json.dumps(box, ensure_ascii=False)
            emb_b64 = _b64_encode_f32(embedding)
            emb_dim = int(np.asarray(embedding).shape[-1])

            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    """
                    INSERT INTO ml_face_embeddings
                        (run_id, image_id, entreprise_id, source_path, source_url, face_index, crop_path, probability, box_json, image_width, image_height, embedding_b64, embedding_dim)
                    VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (run_id, source_path, face_index)
                    DO UPDATE SET
                        image_id = EXCLUDED.image_id,
                        entreprise_id = EXCLUDED.entreprise_id,
                        source_url = EXCLUDED.source_url,
                        crop_path = EXCLUDED.crop_path,
                        probability = EXCLUDED.probability,
                        box_json = EXCLUDED.box_json,
                        image_width = EXCLUDED.image_width,
                        image_height = EXCLUDED.image_height,
                        embedding_b64 = EXCLUDED.embedding_b64,
                        embedding_dim = EXCLUDED.embedding_dim
                    """,
                    (
                        run_id,
                        image_id,
                        entreprise_id,
                        source_path,
                        source_url,
                        int(face_index),
                        crop_path,
                        probability,
                        box_json,
                        image_width,
                        image_height,
                        emb_b64,
                        emb_dim,
                    ),
                )
            else:
                self.execute_sql(
                    cursor,
                    """
                    INSERT OR REPLACE INTO ml_face_embeddings
                        (run_id, image_id, entreprise_id, source_path, source_url, face_index, crop_path, probability, box_json, image_width, image_height, embedding_b64, embedding_dim)
                    VALUES
                        (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        image_id,
                        entreprise_id,
                        source_path,
                        source_url,
                        int(face_index),
                        crop_path,
                        probability,
                        box_json,
                        image_width,
                        image_height,
                        emb_b64,
                        emb_dim,
                    ),
                )

            conn.commit()
            # Recuperer l'id
            self.execute_sql(
                cursor,
                "SELECT id FROM ml_face_embeddings WHERE run_id=? AND source_path=? AND face_index=?",
                (run_id, source_path, int(face_index)),
            )
            row = cursor.fetchone()
            if isinstance(row, dict):
                return int(row["id"])
            return int(row[0])
        finally:
            conn.close()

    def create_identity(self, run_id: int, identity_index: int, threshold: float | None, size: int) -> int:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    """
                    INSERT INTO ml_face_identities (run_id, identity_index, threshold, size)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT (run_id, identity_index)
                    DO UPDATE SET threshold = EXCLUDED.threshold, size = EXCLUDED.size
                    """,
                    (run_id, int(identity_index), threshold, int(size)),
                )
            else:
                self.execute_sql(
                    cursor,
                    """
                    INSERT OR REPLACE INTO ml_face_identities (run_id, identity_index, threshold, size)
                    VALUES (?, ?, ?, ?)
                    """,
                    (run_id, int(identity_index), threshold, int(size)),
                )
            conn.commit()

            self.execute_sql(
                cursor,
                "SELECT id FROM ml_face_identities WHERE run_id=? AND identity_index=?",
                (run_id, int(identity_index)),
            )
            row = cursor.fetchone()
            if isinstance(row, dict):
                return int(row["id"])
            return int(row[0])
        finally:
            conn.close()

    def add_identity_member(self, identity_id: int, embedding_id: int, rank: int | None = None) -> None:
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            # Insert ignore (PK composite)
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    """
                    INSERT INTO ml_face_identity_members (identity_id, embedding_id, rank)
                    VALUES (?, ?, ?)
                    ON CONFLICT (identity_id, embedding_id) DO UPDATE SET rank = EXCLUDED.rank
                    """,
                    (int(identity_id), int(embedding_id), None if rank is None else int(rank)),
                )
            else:
                self.execute_sql(
                    cursor,
                    """
                    INSERT OR REPLACE INTO ml_face_identity_members (identity_id, embedding_id, rank)
                    VALUES (?, ?, ?)
                    """,
                    (int(identity_id), int(embedding_id), None if rank is None else int(rank)),
                )
            conn.commit()
        finally:
            conn.close()

