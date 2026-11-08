#!/usr/bin/env python3
"""Etat Gemini pour une entreprise (id argv[1])."""
import json
import sys

from services.database import Database


def main() -> None:
    eid = int(sys.argv[1])
    db = Database()
    c = db.get_connection().cursor()

    db.execute_sql(c, "SELECT id, nom, website FROM entreprises WHERE id = ?", (eid,))
    print("entreprise:", dict(c.fetchone()))

    if hasattr(db, "get_latest_entreprise_gemini_report"):
        latest = db.get_latest_entreprise_gemini_report(eid)
        if latest:
            keys = {k: latest.get(k) for k in (
                "id", "source", "overall_score", "date_creation", "date_modification", "status"
            ) if k in latest}
            print("latest_report:", keys)
        else:
            print("latest_report: None")

    try:
        db.execute_sql(
            c,
            """
            SELECT id, source, overall_score, date_creation
            FROM entreprise_gemini_reports
            WHERE entreprise_id = ?
            ORDER BY id DESC LIMIT 3
            """,
            (eid,),
        )
        print("reports:", [dict(r) for r in c.fetchall()])
    except Exception as ex:
        print("reports query err:", ex)

    try:
        db.execute_sql(
            c,
            "SELECT COUNT(*) AS n FROM entreprise_screenshots WHERE entreprise_id = ?",
            (eid,),
        )
        print("screenshots:", c.fetchone())
    except Exception as ex:
        print("screenshots err:", ex)


if __name__ == "__main__":
    main()
