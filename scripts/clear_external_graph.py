#!/usr/bin/env python
"""Vide les tables du graphe externe (domaines, liens, pages mini-scrapées)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.database import Database  # noqa: E402


def main() -> None:
    Database().clear_external_graph_data()
    print('OK : tables du graphe externe vidées.')


if __name__ == '__main__':
    main()
