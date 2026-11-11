"""Resolution d'URL avec suivi de redirections (fallback http si https mort)."""

from __future__ import annotations

from utils.url_utils import (
    _navigation_url_candidates,
    canonical_website_https_url,
    normalize_url_for_analysis,
    resolve_website_url_following_redirects,
)


def test_candidates_order():
    c = _navigation_url_candidates("pps4.fr")
    assert c[0] == "https://pps4.fr/"
    assert "http://pps4.fr/" in c


def test_resolve_pps4_live():
    """Live : https apex mort, http redirige vers spider."""
    final = resolve_website_url_following_redirects("pps4.fr", timeout=12.0)
    assert final
    assert "spider.pps4.fr" in final.lower()
    assert final.lower().startswith("https://")


def test_canonical_unchanged():
    assert canonical_website_https_url("pps4.fr") == "https://pps4.fr"


def test_normalize_alias_live():
    a = normalize_url_for_analysis("pps4.fr", timeout=12.0)
    b = resolve_website_url_following_redirects("pps4.fr", timeout=12.0)
    assert a == b


if __name__ == "__main__":
    test_candidates_order()
    test_canonical_unchanged()
    test_resolve_pps4_live()
    print("ok")
