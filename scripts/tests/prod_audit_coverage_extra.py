#!/usr/bin/env python3
"""Complément stats prod (imports récents, files Celery via BDD)."""
from __future__ import annotations

from services.database import Database


def main() -> None:
    db = Database()
    c = db.get_connection().cursor()

    db.execute_sql(
        c,
        """
        SELECT COUNT(*) AS n
        FROM entreprises e
        WHERE e.id >= 21000
          AND NOT EXISTS (SELECT 1 FROM scrapers s WHERE s.entreprise_id = e.id)
        """,
    )
    print("id_ge_21000_sans_scraper:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(*) AS n
        FROM entreprises e
        WHERE e.id >= 21000 AND e.score_securite IS NULL
        """,
    )
    print("id_ge_21000_sans_score_tech:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(*) AS n FROM entreprises WHERE id >= 21000
        """,
    )
    print("total_id_ge_21000:", c.fetchone())

    db.execute_sql(
        c,
        """
        SELECT COUNT(DISTINCT e.id) AS n
        FROM entreprises e
        INNER JOIN scrapers s ON s.entreprise_id = e.id
        WHERE NOT EXISTS (SELECT 1 FROM scraper_emails se WHERE se.scraper_id = s.id)
          AND NOT EXISTS (SELECT 1 FROM scraper_phones sp WHERE sp.scraper_id = s.id)
          AND NOT EXISTS (SELECT 1 FROM analyses_techniques at WHERE at.entreprise_id = e.id)
        """,
    )
    print("scrape_vide_et_sans_analyse_tech:", c.fetchone())


if __name__ == "__main__":
    main()
