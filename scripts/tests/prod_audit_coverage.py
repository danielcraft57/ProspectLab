#!/usr/bin/env python3
"""Stats rapides couverture scraping / technique (prod ou local)."""
from __future__ import annotations

from services.database import Database


def main() -> None:
    db = Database()
    conn = db.get_connection()
    c = conn.cursor()

    db.execute_sql(
        c,
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN website IS NOT NULL AND TRIM(website) <> '' THEN 1 ELSE 0 END) AS avec_site,
          SUM(CASE WHEN score_securite IS NOT NULL THEN 1 ELSE 0 END) AS avec_score_tech,
          SUM(CASE WHEN score_seo IS NOT NULL THEN 1 ELSE 0 END) AS avec_score_seo
        FROM entreprises
        """,
    )
    r = c.fetchone()
    print("entreprises:", dict(r) if hasattr(r, "keys") else r)

    db.execute_sql(
        c,
        """
        SELECT COUNT(DISTINCT e.id) AS n
        FROM entreprises e
        WHERE e.website IS NOT NULL AND TRIM(e.website) <> ''
          AND NOT EXISTS (SELECT 1 FROM scrapers s WHERE s.entreprise_id = e.id)
        """,
    )
    print("avec_site_sans_scraper:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(DISTINCT e.id) AS n
        FROM entreprises e
        WHERE e.website IS NOT NULL AND TRIM(e.website) <> ''
          AND e.score_securite IS NULL
          AND NOT EXISTS (SELECT 1 FROM analyses_techniques at WHERE at.entreprise_id = e.id)
        """,
    )
    print("avec_site_sans_analyse_technique:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(*) AS n
        FROM entreprises e
        WHERE e.score_securite IS NULL
          AND EXISTS (SELECT 1 FROM analyses_techniques at WHERE at.entreprise_id = e.id)
        """,
    )
    print("analyse_tech_en_bdd_mais_score_null:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(DISTINCT s.entreprise_id) AS n
        FROM scrapers s
        WHERE NOT EXISTS (SELECT 1 FROM scraper_emails se WHERE se.scraper_id = s.id)
          AND NOT EXISTS (SELECT 1 FROM scraper_phones sp WHERE sp.scraper_id = s.id)
        """,
    )
    print("scrapers_sans_email_ni_tel:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(*) AS n FROM entreprises WHERE score_securite IS NULL
        """,
    )
    print("entreprises_score_securite_null:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(*) AS n FROM entreprises
        WHERE score_seo IS NULL
        """,
    )
    print("entreprises_score_seo_null:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT e.id, e.nom, e.website,
               (SELECT COUNT(*) FROM scrapers s WHERE s.entreprise_id = e.id) AS nb_scrapers,
               e.score_securite
        FROM entreprises e
        WHERE e.score_securite IS NULL
        ORDER BY e.id DESC
        LIMIT 8
        """,
    )
    rows = c.fetchall()
    print("echantillon_sans_score_tech:")
    for row in rows:
        print(" ", dict(row) if hasattr(row, "keys") else row)

    conn.close()


if __name__ == "__main__":
    main()
