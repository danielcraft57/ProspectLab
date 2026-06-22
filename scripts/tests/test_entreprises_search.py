#!/usr/bin/env python
# Exécution recommandée : conda run -n prospectlab python scripts/tests/test_entreprises_search.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.database.entreprises import (  # noqa: E402
    EntrepriseManager,
    SEARCH_SCORE_NOM_ALL_TOKENS,
    SEARCH_SCORE_NOM_EXACT,
    SEARCH_SCORE_NOM_FIRST_TOKEN,
    SEARCH_SCORE_NOM_PHRASE,
    SEARCH_SCORE_NOM_PREFIX,
    SEARCH_TAGS_BLOCKLIST,
    SEARCH_TAGS_MIN_TOKEN_LEN,
    SEARCH_WEBSITE_BLOCKLIST,
    SEARCH_WEBSITE_MIN_TOKEN_LEN,
)


def test_tokenize_search():
    """Découpe correcte des termes de recherche."""
    assert EntrepriseManager._tokenize_search('  Agence   Web  ') == ['agence', 'web']
    assert EntrepriseManager._tokenize_search('') == []


def test_website_blocklist():
    """Les tokens ambigus ne doivent pas chercher dans website."""
    for token in ('web', 'seo', 'cms', 'com', 'app'):
        assert token in SEARCH_WEBSITE_BLOCKLIST
        assert not EntrepriseManager._token_allows_website_search(token)


def test_tags_blocklist_is_stricter():
    """Les tags bloquent aussi les sous-chaînes type wordpress/javascript."""
    assert SEARCH_TAGS_BLOCKLIST.issuperset(SEARCH_WEBSITE_BLOCKLIST)
    assert 'press' in SEARCH_TAGS_BLOCKLIST
    assert not EntrepriseManager._token_allows_tags_search('press')
    assert EntrepriseManager._token_allows_website_search('press')


def test_website_threshold_lower_than_tags():
    """Website accepte des tokens plus courts que les tags."""
    assert SEARCH_WEBSITE_MIN_TOKEN_LEN < SEARCH_TAGS_MIN_TOKEN_LEN
    assert EntrepriseManager._token_allows_website_search('lyon')
    assert not EntrepriseManager._token_allows_tags_search('lyon')


def test_short_token_excludes_tags_and_website():
    """« web » ne cherche pas dans tags/website."""
    clause, _ = EntrepriseManager._build_token_field_clause(
        'e', '%web%', 'web',
        include_tags=True,
        include_website=True,
        include_scraper_emails=True,
    )
    assert 'tags' not in clause
    assert 'website' not in clause
    assert 'nom' in clause


def test_medium_token_includes_website_only():
    """Un token de 4 lettres peut chercher dans website mais pas tags."""
    clause, params = EntrepriseManager._build_token_field_clause(
        'e', '%lyon%', 'lyon',
        include_tags=True,
        include_website=True,
        include_scraper_emails=True,
    )
    assert 'website' in clause
    assert 'tags' not in clause
    assert len(params) == 8


def test_long_token_includes_tags_and_website():
    """Un token long et non bloqué peut chercher dans tags et website."""
    clause, params = EntrepriseManager._build_token_field_clause(
        'e', '%wordpress%', 'wordpress',
        include_tags=True,
        include_website=True,
        include_scraper_emails=True,
    )
    assert 'tags' in clause
    assert 'website' in clause
    assert len(params) == 9


def test_multi_word_search_has_phrase_clause():
    """Recherche multi-mots : clause phrase + tokens combinés."""
    sql, params = EntrepriseManager._build_search_filter_sql('agence web')
    assert sql.startswith(' AND (')
    assert 'agence web' in params[0]
    assert '%agence%' in params
    assert '%web%' in params


def test_search_order_uses_tuned_scores():
    """Le tri SQL expose les scores ajustés et le boost premier token."""
    sql, params = EntrepriseManager._build_search_order_sql('e.', 'agence web')
    assert f'THEN {SEARCH_SCORE_NOM_EXACT}' in sql
    assert f'THEN {SEARCH_SCORE_NOM_PREFIX}' in sql
    assert f'THEN {SEARCH_SCORE_NOM_FIRST_TOKEN}' in sql
    assert f'THEN {SEARCH_SCORE_NOM_PHRASE}' in sql
    assert f'THEN {SEARCH_SCORE_NOM_ALL_TOKENS}' in sql
    assert params[0] == 'agence web'
    assert params[2] == 'agence%'
    assert '%agence%' in params
    assert '%web%' in params


def test_search_integration_agence_web():
    """
    « agence web » ne doit pas matcher une agence immo taguée wordpress
    si « web » n'apparaît ni dans le nom ni dans l'adresse.
    """
    from services.database import Database

    db = Database()
    conn = db.get_connection()
    cursor = conn.cursor()
    immo_id = None
    web_id = None
    noise_id = None
    partial_id = None
    try:
        db.execute_sql(
            cursor,
            '''
            INSERT INTO entreprises (nom, secteur, tags, date_analyse)
            VALUES (?, ?, ?, datetime('now'))
            ''',
            ('Agence Immobilière Test', 'immobilier', '["wordpress", "immobilier"]'),
        )
        immo_id = cursor.lastrowid

        db.execute_sql(
            cursor,
            '''
            INSERT INTO entreprises (nom, secteur, tags, date_analyse)
            VALUES (?, ?, ?, datetime('now'))
            ''',
            ('Agence web Splitfire', 'technologie', '["services"]'),
        )
        web_id = cursor.lastrowid

        db.execute_sql(
            cursor,
            '''
            INSERT INTO entreprises (nom, secteur, website, date_analyse)
            VALUES (?, ?, ?, datetime('now'))
            ''',
            ('Agence bruit', 'services', 'https://agence-bruit-lyon.fr'),
        )
        noise_id = cursor.lastrowid

        db.execute_sql(
            cursor,
            '''
            INSERT INTO entreprises (nom, secteur, date_analyse)
            VALUES (?, ?, datetime('now'))
            ''',
            ('Agence immobilière web design', 'immobilier'),
        )
        partial_id = cursor.lastrowid
        conn.commit()

        results = db.get_entreprises(filters={'search': 'agence web'})
        result_ids = [e['id'] for e in results]

        assert web_id in result_ids
        assert immo_id not in result_ids
        assert noise_id not in result_ids
        assert partial_id in result_ids
        assert result_ids[0] == web_id
        assert result_ids.index(web_id) < result_ids.index(partial_id)
    finally:
        ids = [i for i in (immo_id, web_id, noise_id, partial_id) if i is not None]
        if ids:
            placeholders = ','.join(['?'] * len(ids))
            db.execute_sql(cursor, f'DELETE FROM entreprises WHERE id IN ({placeholders})', tuple(ids))
            conn.commit()
        conn.close()


def main():
    test_tokenize_search()
    test_website_blocklist()
    test_tags_blocklist_is_stricter()
    test_website_threshold_lower_than_tags()
    test_short_token_excludes_tags_and_website()
    test_medium_token_includes_website_only()
    test_long_token_includes_tags_and_website()
    test_multi_word_search_has_phrase_clause()
    test_search_order_uses_tuned_scores()
    test_search_integration_agence_web()
    print('OK test_entreprises_search')


if __name__ == '__main__':
    main()
