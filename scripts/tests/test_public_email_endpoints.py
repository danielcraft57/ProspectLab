import json
import sys
from typing import Optional

import requests

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from services.database import Database


def _pick_token(db: Database) -> Optional[str]:
    conn = db.get_connection()
    cur = conn.cursor()
    db.execute_sql(
        cur,
        """
        SELECT token
        FROM api_tokens
        WHERE is_active = 1
          AND can_read_entreprises = 1
          AND can_read_emails = 1
        ORDER BY id DESC
        LIMIT 1
        """,
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    if isinstance(row, dict):
        return row.get("token")
    return row[0]


def _pick_email(db: Database) -> Optional[str]:
    conn = db.get_connection()
    cur = conn.cursor()

    try:
        db.execute_sql(
            cur,
            """
            SELECT email
            FROM scraper_emails
            WHERE email IS NOT NULL AND TRIM(email) <> ''
            ORDER BY date_found DESC
            LIMIT 1
            """,
        )
        row = cur.fetchone()
        if row:
            conn.close()
            return row.get("email") if isinstance(row, dict) else row[0]
    except Exception:
        pass

    db.execute_sql(
        cur,
        """
        SELECT email_principal
        FROM entreprises
        WHERE email_principal IS NOT NULL AND TRIM(email_principal) <> ''
        LIMIT 1
        """,
    )
    row = cur.fetchone()
    conn.close()
    if not row:
        return None
    return row.get("email_principal") if isinstance(row, dict) else row[0]


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    db = Database()

    token = _pick_token(db)
    if not token:
        print("ERROR: no api token found with can_read_entreprises=1 and can_read_emails=1")
        return 2

    email = _pick_email(db)
    if not email:
        print("ERROR: no email found in scraper_emails or entreprises.email_principal")
        return 3

    base = "http://127.0.0.1:5000"
    headers = {"Authorization": f"Bearer {token}"}

    print("EMAIL_SAMPLE:", email)

    r = requests.get(
        f"{base}/api/public/entreprises/by-email",
        headers=headers,
        params={"email": email, "include_emails": "1"},
        timeout=30,
    )
    print("by-email status:", r.status_code)
    try:
        js = r.json()
    except Exception:
        print("by-email body (text):", r.text[:500])
        return 4

    print("by-email success:", js.get("success"))
    ent = (js.get("data") or {}).get("entreprise") or {}
    ent_id = ent.get("id")
    match = (js.get("data") or {}).get("match") or {}
    print("entreprise_id:", ent_id, "match_source:", match.get("source"))
    print("emails_count:", (js.get("data") or {}).get("emails_count"))

    if not ent_id:
        print("ERROR: by-email did not return entreprise.id")
        print(json.dumps(js, ensure_ascii=True)[:2000])
        return 5

    r2 = requests.get(
        f"{base}/api/public/entreprises/{ent_id}/emails/all",
        headers=headers,
        timeout=30,
    )
    print("emails/all status:", r2.status_code)
    try:
        js2 = r2.json()
    except Exception:
        print("emails/all body (text):", r2.text[:500])
        return 6

    print("emails/all count:", js2.get("count"))
    data = js2.get("data") or []
    if data:
        sample = data[0]
        print("emails/all sample keys:", sorted(sample.keys()))
        print("emails/all sample person:", sample.get("person"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

