"""
Pose les tags HTTP (404, 502, timeout, DNS...) sur les entreprises deja en base.

A lancer une fois apres deploiement, depuis la racine du projet :

    python scripts/tag_sites_http_status.py

Les prochains scrapings posent le tag tout seuls. Ce script rattrape l'existant
a partir de la derniere analyse technique, puis des scrapings qui n'ont visite aucune page.
"""

from services.database import Database


def main():
    """
    Relit les analyses techniques et met a jour les tags.

    @returns: None
    """
    db = Database()
    stats = db.backfill_reachability_tags()
    print(
        'Termine. Analyses techniques: {from_technical}, '
        'scrapings vides: {from_scrape}, sans info: {skipped}'.format(**stats)
    )


if __name__ == '__main__':
    main()
