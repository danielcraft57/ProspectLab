#!/usr/bin/env python
# Exécution recommandée : conda run -n prospectlab python scripts/tests/test_entreprises_graph.py

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from services.database.external_links import (  # noqa: E402
    _assign_agency_centric_layout,
    _website_host_key,
)


def test_website_host_key():
    assert _website_host_key('https://www.example.com/path') == 'example.com'
    assert _website_host_key('client.fr') == 'client.fr'
    assert _website_host_key('') is None


def test_agency_centric_layout_star():
    nodes = {
        'a:agence.test': {
            'id': 'a:agence.test',
            'group': 'agency',
            'label': 'Agence',
            'domain': 'agence.test',
        },
        'e:1': {'id': 'e:1', 'group': 'entreprise', 'label': 'A'},
        'e:2': {'id': 'e:2', 'group': 'entreprise', 'label': 'B'},
        'e:3': {'id': 'e:3', 'group': 'entreprise', 'label': 'C'},
    }
    edges = [
        {'from': 'e:1', 'to': 'a:agence.test'},
        {'from': 'e:2', 'to': 'a:agence.test'},
        {'from': 'a:agence.test', 'to': 'e:3', 'dashes': True},
    ]
    _assign_agency_centric_layout(nodes, edges)
    assert 'x' in nodes['a:agence.test'] and 'y' in nodes['a:agence.test']
    for eid in ('e:1', 'e:2', 'e:3'):
        assert 'x' in nodes[eid] and 'y' in nodes[eid]


def test_get_graph_empty_db():
    from services.database import Database

    g = Database().get_entreprises_link_graph()
    assert g.get('success') is True
    assert 'nodes' in g and 'edges' in g and 'stats' in g
    assert 'agencies' in g['stats'] and 'enterprises' in g['stats']
    assert 'graph_scope' in g
    assert g['graph_scope'].get('total_link_rows_in_db') is not None


def main():
    test_website_host_key()
    test_agency_centric_layout_star()
    test_get_graph_empty_db()
    print('OK test_entreprises_graph')


if __name__ == '__main__':
    main()
