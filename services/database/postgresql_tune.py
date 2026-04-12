"""
Optimisations ciblées PostgreSQL (extensions, index, contraintes, ANALYZE).
No-op si ``db_type != 'postgresql'``.
"""

import logging

from .base import DatabaseBase

logger = logging.getLogger(__name__)


def apply_postgresql_tuning(db: DatabaseBase) -> None:
    """
    - Extension ``pg_trgm`` + index GIN sur ``external_domains.domain_host`` (recherches ILIKE « contient »).
    - Index composite aligné sur le tri du graphe (likely_credit, date_creation).
    - Index partiel ``only_credit`` / liens par entreprise.
    - Contrainte CHECK sur ``likely_credit`` ∈ {0,1}.
    - ``ANALYZE`` sur les tables du graphe externe.
    """
    if not db.is_postgresql():
        return
    conn = db.get_connection()
    cursor = conn.cursor()
    try:
        try:
            db.execute_sql(cursor, 'CREATE EXTENSION IF NOT EXISTS pg_trgm', ())
        except Exception as exc:
            logger.info('PostgreSQL : extension pg_trgm non activée (%s)', exc)

        if _relation_exists(cursor, db, 'external_domains'):
            try:
                db.execute_sql(
                    cursor,
                    '''
                    CREATE INDEX IF NOT EXISTS idx_ext_dom_domain_gin_trgm
                    ON external_domains USING gin (domain_host gin_trgm_ops)
                    ''',
                    (),
                )
            except Exception as exc:
                logger.info('PostgreSQL : index GIN pg_trgm sur external_domains ignoré (%s)', exc)

        if _relation_exists(cursor, db, 'entreprises'):
            try:
                db.execute_sql(
                    cursor,
                    '''
                    CREATE INDEX IF NOT EXISTS idx_entreprises_website_btrim_lower
                    ON entreprises (lower(btrim(website)))
                    WHERE website IS NOT NULL AND btrim(website) <> ''
                    ''',
                    (),
                )
            except Exception as exc:
                logger.debug('PostgreSQL : index website entreprises : %s', exc)

        if _relation_exists(cursor, db, 'entreprise_external_links'):
            db.execute_sql(cursor, 'DROP INDEX IF EXISTS idx_eel_likely_date', ())
            db.execute_sql(
                cursor,
                '''
                CREATE INDEX IF NOT EXISTS idx_eel_graph_sort
                ON entreprise_external_links (likely_credit DESC, date_creation DESC)
                ''',
                (),
            )
            db.execute_sql(
                cursor,
                '''
                CREATE INDEX IF NOT EXISTS idx_eel_ent_credit_date
                ON entreprise_external_links (entreprise_id, date_creation DESC)
                WHERE likely_credit = 1
                ''',
                (),
            )
            db.execute_sql(
                cursor,
                '''
                CREATE INDEX IF NOT EXISTS idx_eel_ent_any_date
                ON entreprise_external_links (entreprise_id, date_creation DESC)
                ''',
                (),
            )

            try:
                db.execute_sql(
                    cursor,
                    '''
                    ALTER TABLE entreprise_external_links
                    ADD CONSTRAINT chk_eel_likely_credit
                    CHECK (likely_credit IN (0, 1)) NOT VALID
                    ''',
                    (),
                )
            except Exception as exc:
                err = str(exc).lower()
                if 'already exists' not in err and 'duplicate' not in err:
                    logger.debug('PostgreSQL : ADD chk_eel_likely_credit : %s', exc)
            try:
                db.execute_sql(
                    cursor,
                    '''
                    ALTER TABLE entreprise_external_links
                    VALIDATE CONSTRAINT chk_eel_likely_credit
                    ''',
                    (),
                )
            except Exception as exc:
                err = str(exc).lower()
                if 'does not exist' not in err:
                    logger.warning(
                        'PostgreSQL : VALIDATE chk_eel_likely_credit impossible '
                        '(contrainte absente ou données hors 0/1) : %s',
                        exc,
                    )

        for tbl in (
            'external_domains',
            'entreprise_external_links',
            'external_domain_categories',
            'external_domain_jsonld_types',
            'external_domain_portfolio_hosts',
            'external_link_pages',
            'external_link_page_og_props',
            'external_link_page_images',
            'external_link_page_locations',
        ):
            if _relation_exists(cursor, db, tbl):
                try:
                    db.execute_sql(cursor, f'ANALYZE {tbl}', ())
                except Exception as exc:
                    logger.debug('PostgreSQL : ANALYZE %s : %s', tbl, exc)

        conn.commit()
    except Exception:
        logger.warning('PostgreSQL : tuning partiellement échoué', exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        conn.close()


def _relation_exists(cursor, db: DatabaseBase, name: str) -> bool:
    db.execute_sql(
        cursor,
        '''
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ?
        LIMIT 1
        ''',
        (name,),
    )
    return cursor.fetchone() is not None
