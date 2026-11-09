"""Tags HTTP : 404, 502, timeout, et nettoyage des tags inutiles si le site est mort."""

from services.http_reachability import (
    outcome_from_error_message,
    outcome_from_status,
    sync_reachability_tags,
)


def test_status_codes():
    assert outcome_from_status(200)['ok'] is True
    assert outcome_from_status(404)['tag'] == 'http:404'
    assert outcome_from_status(502)['tag'] == 'http:502'
    assert outcome_from_status(503)['ok'] is False


def test_timeout_and_dns():
    timeout = outcome_from_error_message('HTTPSConnectionPool: Read timed out. (read timeout=15)')
    assert timeout['tag'] == 'http:timeout'
    dns = outcome_from_error_message('Failed to resolve example.test: Name or service not known')
    assert dns['tag'] == 'http:dns'


class _Cursor:
    def __init__(self, tags):
        self.tags = tags
        self.updated = None

    def fetchone(self):
        return {'tags': self.tags}


class _Db:
    def execute_sql(self, cursor, sql, params=None):
        if sql.strip().upper().startswith('SELECT'):
            return
        cursor.updated = params[0]


def test_sync_replaces_noise_tags_on_502():
    cursor = _Cursor('["fort_potentiel_refonte", "perf:low", "blog"]')
    ok = sync_reachability_tags(_Db(), cursor, 7, outcome_from_status(502))
    assert ok is True
    saved = cursor.updated
    assert 'fort_potentiel_refonte' not in saved
    assert 'perf:low' not in saved
    assert 'http:502' in saved
    assert 'site_injoignable' in saved
    assert 'blog' in saved


def test_sync_clears_http_tags_when_site_answers():
    cursor = _Cursor('["http:404", "site_injoignable", "blog"]')
    sync_reachability_tags(_Db(), cursor, 7, outcome_from_status(200))
    saved = cursor.updated
    assert 'http:404' not in saved
    assert 'site_injoignable' not in saved
    assert 'blog' in saved


if __name__ == '__main__':
    test_status_codes()
    test_timeout_and_dns()
    test_sync_replaces_noise_tags_on_502()
    test_sync_clears_http_tags_when_site_answers()
    print('ok')
