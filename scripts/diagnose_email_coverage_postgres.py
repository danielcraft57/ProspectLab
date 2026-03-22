"""
Diagnostic de couverture email sur PostgreSQL.

Ce script calcule:
- total d'entreprises
- entreprises avec email principal
- entreprises avec email de scraping
- entreprises avec au moins un email (principal OU scraping)
- entreprises sans website
- entreprises jamais scrapees
- entreprises scrapees mais sans email
"""

from __future__ import annotations

import argparse
import getpass
import sys
from typing import Dict

import psycopg2
from psycopg2.extras import RealDictCursor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnostique le taux d'entreprises avec email dans PostgreSQL."
    )
    parser.add_argument("--host", default="node15.lan", help="Hote PostgreSQL (defaut: node15.lan)")
    parser.add_argument("--port", type=int, default=5432, help="Port PostgreSQL (defaut: 5432)")
    parser.add_argument("--db", default="prospectlab", help="Nom de la base (defaut: prospectlab)")
    parser.add_argument("--user", default="prospectlab", help="Utilisateur PostgreSQL (defaut: prospectlab)")
    parser.add_argument(
        "--password",
        default=None,
        help="Mot de passe PostgreSQL (si absent, saisie interactive).",
    )
    return parser.parse_args()


def fetch_scalar(cursor: RealDictCursor, sql: str) -> int:
    cursor.execute(sql)
    row = cursor.fetchone() or {}
    if not row:
        return 0
    first_value = next(iter(row.values()))
    return int(first_value or 0)


def run_diagnostic(connection) -> Dict[str, int]:
    queries = {
        "total_entreprises": """
            SELECT COUNT(*) AS value
            FROM entreprises
        """,
        "avec_email_principal": """
            SELECT COUNT(*) AS value
            FROM entreprises e
            WHERE e.email_principal IS NOT NULL
              AND TRIM(e.email_principal) <> ''
        """,
        "avec_email_scraper": """
            SELECT COUNT(DISTINCT e.id) AS value
            FROM entreprises e
            WHERE EXISTS (
                SELECT 1
                FROM scraper_emails se
                WHERE se.entreprise_id = e.id
                  AND se.email IS NOT NULL
                  AND TRIM(se.email) <> ''
            )
        """,
        "avec_email_global": """
            SELECT COUNT(DISTINCT e.id) AS value
            FROM entreprises e
            WHERE
                (e.email_principal IS NOT NULL AND TRIM(e.email_principal) <> '')
                OR EXISTS (
                    SELECT 1
                    FROM scraper_emails se
                    WHERE se.entreprise_id = e.id
                      AND se.email IS NOT NULL
                      AND TRIM(se.email) <> ''
                )
        """,
        "sans_website": """
            SELECT COUNT(*) AS value
            FROM entreprises e
            WHERE e.website IS NULL OR TRIM(e.website) = ''
        """,
        "jamais_scrapees": """
            SELECT COUNT(*) AS value
            FROM entreprises e
            WHERE NOT EXISTS (
                SELECT 1
                FROM scrapers s
                WHERE s.entreprise_id = e.id
            )
        """,
        "scrapees_sans_email": """
            SELECT COUNT(*) AS value
            FROM entreprises e
            WHERE EXISTS (
                SELECT 1
                FROM scrapers s
                WHERE s.entreprise_id = e.id
            )
              AND NOT EXISTS (
                SELECT 1
                FROM scraper_emails se
                WHERE se.entreprise_id = e.id
                  AND se.email IS NOT NULL
                  AND TRIM(se.email) <> ''
            )
              AND (e.email_principal IS NULL OR TRIM(e.email_principal) = '')
        """,
    }

    results: Dict[str, int] = {}
    with connection.cursor(cursor_factory=RealDictCursor) as cursor:
        for key, sql in queries.items():
            results[key] = fetch_scalar(cursor, sql)
    return results


def main() -> int:
    args = parse_args()
    password = args.password or getpass.getpass("Mot de passe PostgreSQL: ")

    try:
        conn = psycopg2.connect(
            host=args.host,
            port=args.port,
            dbname=args.db,
            user=args.user,
            password=password,
            connect_timeout=10,
        )
    except Exception as exc:
        print(f"[ERREUR] Connexion impossible a PostgreSQL: {exc}", file=sys.stderr)
        return 1

    try:
        stats = run_diagnostic(conn)
    except Exception as exc:
        print(f"[ERREUR] Echec du diagnostic SQL: {exc}", file=sys.stderr)
        return 2
    finally:
        conn.close()

    total = stats.get("total_entreprises", 0)
    with_email = stats.get("avec_email_global", 0)
    pct = (with_email * 100.0 / total) if total else 0.0

    print("=== Diagnostic emails ProspectLab (PostgreSQL) ===")
    print(f"Total entreprises          : {total}")
    print(f"Avec email principal       : {stats.get('avec_email_principal', 0)}")
    print(f"Avec email scraper         : {stats.get('avec_email_scraper', 0)}")
    print(f"Avec email (global)        : {with_email}")
    print(f"Couverture emails          : {pct:.2f}%")
    print(f"Sans website               : {stats.get('sans_website', 0)}")
    print(f"Jamais scrapees            : {stats.get('jamais_scrapees', 0)}")
    print(f"Scrapees mais sans email   : {stats.get('scrapees_sans_email', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

