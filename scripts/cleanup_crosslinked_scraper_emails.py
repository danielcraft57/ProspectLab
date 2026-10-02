#!/usr/bin/env python3
"""
Detecte (et optionnellement supprime) les emails scraper mal rattaches a une entreprise.

Heuristique :
- si l'entreprise a un website
- et l'email n'est pas un webmail libre (gmail, orange…)
- et le domaine mail ne matche pas le domaine du site
→ candidat au detach (DELETE scraper_emails pour ce couple)

Par defaut : dry-run. Passer --apply pour ecrire.

Usage:
  python scripts/cleanup_crosslinked_scraper_emails.py
  python scripts/cleanup_crosslinked_scraper_emails.py --limit 50
  python scripts/cleanup_crosslinked_scraper_emails.py --apply
  python scripts/cleanup_crosslinked_scraper_emails.py --entreprise-id 123 --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.database import Database  # noqa: E402
from utils.domain_match import domains_compatible  # noqa: E402
from utils.email_quality import (  # noqa: E402
    email_domain,
    is_campaign_risky_email,
    is_excluded_campaign_domain,
    is_role_or_support_localpart,
)
from utils.url_utils import normalize_website_domain  # noqa: E402

# Domaines clairement parasites (trackers / demos / builders)
NOISE_MAIL_DOMAINS = frozenset({
    'sentry.wixpress.com',
    'sentry-next.wixpress.com',
    'wixpress.com',
    'example.com',
    'example.fr',
    'exemple.fr',
    'exemple.com',
    'domain.com',
    'domaine.fr',
    'email.com',
    'test.com',
    'sentry.io',
})

NOISE_MAIL_SUFFIXES = (
    '.wixpress.com',
    '.sentry.io',
    '.wix.com',
)


def is_noise_mail_domain(mail_domain: str) -> bool:
    """True si le domaine email est un tracker / placeholder evident."""
    d = (mail_domain or '').strip().lower()
    if not d:
        return True
    if d in NOISE_MAIL_DOMAINS:
        return True
    if any(d.endswith(suf) for suf in NOISE_MAIL_SUFFIXES):
        return True
    # local-part hash-like @ random
    return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Cleanup emails scraper cross-links.')
    p.add_argument('--apply', action='store_true', help='Supprime les lignes scraper_emails detectees.')
    p.add_argument('--limit', type=int, default=0, help='Limite de candidats a traiter (0 = tous).')
    p.add_argument('--entreprise-id', type=int, default=None, help='Restreindre a une entreprise.')
    p.add_argument(
        '--mode',
        choices=('noise', 'mismatch', 'risky', 'all'),
        default='noise',
        help='noise=trackers/demos (defaut sur), mismatch=domaines incompatibles, risky=gouv/saas, all=tout',
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    db = Database()
    conn = db.get_connection()
    cur = conn.cursor()

    sql = '''
        SELECT se.id AS scraper_id, se.email, se.domain, se.entreprise_id,
               e.nom AS entreprise, e.website
        FROM scraper_emails se
        JOIN entreprises e ON e.id = se.entreprise_id
        WHERE se.email IS NOT NULL AND TRIM(se.email) <> ''
          AND e.website IS NOT NULL AND TRIM(e.website) <> ''
    '''
    params = []
    if args.entreprise_id:
        sql += ' AND se.entreprise_id = ?'
        params.append(int(args.entreprise_id))
    sql += ' ORDER BY se.entreprise_id, se.id'

    db.execute_sql(cur, sql, tuple(params) if params else None)
    rows = [dict(r) for r in (cur.fetchall() or [])]

    candidates = []
    for r in rows:
        email = (r.get('email') or '').strip()
        mail_dom = email_domain(email) or (r.get('domain') or '').strip().lower()
        site_dom = normalize_website_domain(r.get('website'))
        mismatch = not domains_compatible(site_dom, mail_dom)
        excluded_domain = is_excluded_campaign_domain(email)
        role_local = is_role_or_support_localpart(email)
        # Role email OK s'il appartient au domaine du site ; dangereux sinon
        risky_safe = excluded_domain or (role_local and mismatch) or (
            is_campaign_risky_email(email) and mismatch
        )
        noise = is_noise_mail_domain(mail_dom)

        mode = args.mode
        keep = False
        reason = ''
        if mode == 'noise' and noise:
            keep = True
            reason = 'noise'
        elif mode == 'mismatch' and mismatch:
            keep = True
            reason = 'domain_mismatch'
        elif mode == 'risky' and risky_safe:
            keep = True
            reason = 'excluded_domain' if excluded_domain else 'risky_mismatch'
        elif mode == 'all' and (noise or mismatch or risky_safe):
            keep = True
            reason = 'noise' if noise else ('domain_mismatch' if mismatch else 'risky')

        if keep:
            candidates.append({
                **r,
                'mail_domain': mail_dom,
                'site_domain': site_dom,
                'reason': reason,
            })

    if args.limit and args.limit > 0:
        candidates = candidates[: int(args.limit)]

    print(f'Candidats: {len(candidates)} (mode={args.mode}, apply={bool(args.apply)})')
    for c in candidates[:40]:
        print(
            f"- se#{c.get('scraper_id')} ent#{c.get('entreprise_id')} "
            f"{c.get('email')} | site={c.get('site_domain')} | reason={c.get('reason')} | {c.get('entreprise')}"
        )
    if len(candidates) > 40:
        print(f'... +{len(candidates) - 40} autres')

    if not args.apply:
        print('Dry-run. Relancer avec --apply pour supprimer.')
        conn.close()
        return 0

    deleted = 0
    for c in candidates:
        sid = c.get('scraper_id')
        if not sid:
            continue
        db.execute_sql(cur, 'DELETE FROM scraper_emails WHERE id = ?', (sid,))
        deleted += 1
    conn.commit()
    conn.close()
    print(f'Supprimes: {deleted}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
