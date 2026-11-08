#!/usr/bin/env python3
"""Recherche entreprise par fragment de nom (argv[1])."""
import sys
from services.database import Database


def main() -> None:
    q = sys.argv[1] if len(sys.argv) > 1 else "%SHG%"
    db = Database()
    c = db.get_connection().cursor()
    db.execute_sql(
        c,
        "SELECT id, nom, website FROM entreprises WHERE nom ILIKE ? LIMIT 10",
        (q,),
    )
    for row in c.fetchall():
        print(dict(row) if hasattr(row, "keys") else row)


if __name__ == "__main__":
    main()
