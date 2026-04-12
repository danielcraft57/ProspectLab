"""
Liens externes site client → domaines tiers (graphe, mini-scrape, catégories).

Schéma relationnel : ``external_domains`` (métadonnées par hôte normalisé),
``entreprise_external_links`` (occurrences par run de scraper),
``external_link_pages`` (pages mini-scrapées),
tables filles en 1-n (catégories, JSON-LD, portfolio ; OG, images, lieu structuré) avec CASCADE.
"""

import json
import logging
import math
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple
from utils.url_utils import normalize_website_domain

from .base import DatabaseBase

logger = logging.getLogger(__name__)


def _website_host_key(website: str):
    """Host normalisé (aligné sur ``entreprises.website`` / dédoublonnage)."""
    return normalize_website_domain(website)


def _eid_sort_key(eid) -> int:
    s = str(eid)
    if s.startswith('e:'):
        try:
            return int(s[2:])
        except ValueError:
            pass
    return hash(s) % 1_000_000


def _repel_enterprise_positions(nodes_map: dict, ent_ids: list, min_dist: float = 365.0, iterations: int = 18) -> None:
    """Écarte les fiches entreprise trop proches (répulsion type « molécules »)."""
    positions = {}
    for eid in ent_ids:
        n = nodes_map.get(eid)
        if not n or 'x' not in n or 'y' not in n:
            continue
        positions[eid] = [float(n['x']), float(n['y'])]
    ids = list(positions.keys())
    for _ in range(iterations):
        for i, a in enumerate(ids):
            pa = positions[a]
            for b in ids[i + 1 :]:
                pb = positions[b]
                dx = pa[0] - pb[0]
                dy = pa[1] - pb[1]
                dist = math.hypot(dx, dy) or 1e-6
                if dist >= min_dist:
                    continue
                push = (min_dist - dist) * 0.66
                nx = dx / dist * push
                ny = dy / dist * push
                pa[0] += nx
                pa[1] += ny
                pb[0] -= nx
                pb[1] -= ny
    for eid, p in positions.items():
        nodes_map[eid]['x'] = float(p[0])
        nodes_map[eid]['y'] = float(p[1])


def _assign_agency_centric_layout(nodes_map: dict, edges_list: list) -> None:
    """
    Grille large pour domaines ``a:`` ; entreprises en anneau lâche autour du barycentre
    de leurs agences (meilleure lecture des domaines en commun).
    """
    if not nodes_map or not edges_list:
        return

    ent_to_agencies = defaultdict(set)
    for e in edges_list:
        f, t = e.get('from'), e.get('to')
        if not f or not t:
            continue
        if f.startswith('e:') and t.startswith('a:'):
            ent_to_agencies[f].add(t)
        elif f.startswith('a:') and t.startswith('e:'):
            ent_to_agencies[t].add(f)

    agencies = sorted(
        [
            nid
            for nid, n in nodes_map.items()
            if str(nid).startswith('a:') and n.get('group') != 'entreprise'
        ],
        key=lambda x: str(x),
    )
    if not agencies:
        return

    n_ag = len(agencies)
    cols = max(1, int(math.ceil(math.sqrt(n_ag * 1.55))))
    cell_w, cell_h = 1280.0, 900.0
    margin_x, margin_y = 680.0, 560.0
    agency_center = {}
    for idx, aid in enumerate(agencies):
        row, col = divmod(idx, cols)
        cx = margin_x + col * cell_w
        cy = margin_y + row * cell_h
        agency_center[aid] = (cx, cy)
        nodes_map[aid]['x'] = float(cx)
        nodes_map[aid]['y'] = float(cy)

    if agency_center:
        gcx = sum(p[0] for p in agency_center.values()) / len(agency_center)
        gcy = sum(p[1] for p in agency_center.values()) / len(agency_center)
    else:
        gcx = gcy = 0.0

    phi = (1.0 + math.sqrt(5.0)) / 2.0
    ent_list = sorted(ent_to_agencies.keys(), key=_eid_sort_key)

    for eid in ent_list:
        if eid not in nodes_map:
            continue
        aids_l = [a for a in ent_to_agencies[eid] if a in agency_center]
        if not aids_l:
            continue
        acx = sum(agency_center[a][0] for a in aids_l) / len(aids_l)
        acy = sum(agency_center[a][1] for a in aids_l) / len(aids_l)
        vx, vy = acx - gcx, acy - gcy
        norm = math.hypot(vx, vy) or 1.0
        vx, vy = vx / norm, vy / norm

        k = _eid_sort_key(eid)
        t = (k * 2654435761 % 1_000_000) / 1_000_000.0
        angle = t * 2.0 * math.pi * phi

        n_links = len(aids_l)
        base_r = 565.0 + 208.0 * math.sqrt(max(0, n_links - 1)) + (k % 73) * 5.5
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        ex = acx + base_r * cos_a * 0.9 + base_r * vx * 0.45
        ey = acy + base_r * sin_a * 0.9 + base_r * vy * 0.45
        nodes_map[eid]['x'] = float(ex)
        nodes_map[eid]['y'] = float(ey)

    _repel_enterprise_positions(nodes_map, [eid for eid in ent_list if eid in nodes_map])


class ExternalLinksManager(DatabaseBase):
    """``external_domains`` + ``entreprise_external_links`` + graphe entreprises / domaines tiers."""

    def _table_exists(self, cursor, table_name: str) -> bool:
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = ?
                LIMIT 1
                ''',
                (table_name,),
            )
        else:
            self.execute_sql(
                cursor,
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
                (table_name,),
            )
        return cursor.fetchone() is not None

    def _table_has_column(self, cursor, table: str, column: str) -> bool:
        """Indique si ``table`` possède la colonne ``column`` (SQLite / PostgreSQL)."""
        col_l = (column or '').lower()
        if not col_l:
            return False
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = ? AND LOWER(column_name) = ?
                LIMIT 1
                ''',
                (table, col_l),
            )
            return cursor.fetchone() is not None
        self.execute_sql(cursor, f'PRAGMA table_info({table})', ())
        for row in cursor.fetchall() or []:
            try:
                nm = (row['name'] or '').lower()
            except (KeyError, TypeError, IndexError):
                nm = (row[1] or '').lower() if row and len(row) > 1 else ''
            if nm == col_l:
                return True
        return False

    def _drop_legacy_web_indexes(self, cursor) -> None:
        for old in (
            'idx_web_credit_entreprise',
            'idx_web_credit_agency_domain',
            'idx_web_credit_scraper',
            'idx_web_external_entreprise',
            'idx_web_external_agency_domain',
            'idx_web_external_scraper',
            'idx_web_external_target_entreprise',
            'idx_web_external_likely_date',
            'idx_web_ext_pages_link',
            'idx_web_ext_pages_depth',
        ):
            self.safe_execute_sql(cursor, f'DROP INDEX IF EXISTS {old}')

    def _ensure_external_graph_indexes(self, cursor) -> None:
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_eel_entreprise ON entreprise_external_links(entreprise_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_eel_scraper ON entreprise_external_links(scraper_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_eel_domain ON entreprise_external_links(domain_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_eel_target ON entreprise_external_links(target_entreprise_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_eel_likely_date ON entreprise_external_links(likely_credit, date_creation)',
        )

    def _create_external_graph_tables(self, cursor) -> None:
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_domains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain_host TEXT NOT NULL UNIQUE,
                site_title TEXT,
                site_description TEXT,
                resolved_url TEXT,
                thumb_url TEXT,
                graph_group TEXT DEFAULT 'external',
                mini_scrape_error TEXT,
                mini_scraped_at TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''',
        )
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS entreprise_external_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                scraper_id INTEGER NOT NULL,
                domain_id INTEGER NOT NULL,
                client_site_url TEXT,
                external_href TEXT NOT NULL,
                source_page_url TEXT,
                anchor_text TEXT,
                likely_credit INTEGER DEFAULT 1,
                link_source TEXT,
                target_entreprise_id INTEGER,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (domain_id) REFERENCES external_domains(id) ON DELETE RESTRICT,
                CONSTRAINT uq_eel_scraper_external_href UNIQUE (scraper_id, external_href)
            )
            ''',
        )

    def ensure_web_external_links_table(self):
        """Crée le schéma relationnel externe ; supprime les anciennes tables ``web_*`` (données effacées)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if self._table_exists(cursor, 'external_domains') and self._table_exists(
                cursor, 'entreprise_external_links'
            ):
                self._ensure_external_domain_norm_tables(cursor)
                self._ensure_external_link_pages_schema(cursor)
                self._ensure_external_link_page_detail_tables(cursor)
                self._ensure_external_graph_indexes(cursor)
                conn.commit()
                return

            self._drop_legacy_web_indexes(cursor)
            self.safe_execute_sql(cursor, 'DROP TABLE IF EXISTS web_external_pages')
            self.safe_execute_sql(cursor, 'DROP TABLE IF EXISTS web_external_links')
            self.safe_execute_sql(cursor, 'DROP TABLE IF EXISTS web_credit_links')

            self._create_external_graph_tables(cursor)
            self._ensure_external_domain_norm_tables(cursor)
            self._ensure_external_graph_indexes(cursor)
            self._ensure_external_link_pages_schema(cursor)
            self._ensure_external_link_page_detail_tables(cursor)
            conn.commit()
            logger.info(
                'Schéma graphe externe : external_domains + entreprise_external_links '
                '(anciennes tables web_* supprimées)'
            )
        finally:
            conn.close()

    def _ensure_external_link_pages_schema(self, cursor) -> None:
        """Pages mini-scrapées (1er niveau) liées à ``entreprise_external_links``."""
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_link_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link_id INTEGER NOT NULL,
                page_url TEXT NOT NULL,
                depth INTEGER DEFAULT 0,
                http_status INTEGER,
                title TEXT,
                meta_description TEXT,
                fetched_at TEXT,
                fetch_error TEXT,
                FOREIGN KEY (link_id) REFERENCES entreprise_external_links(id) ON DELETE CASCADE,
                UNIQUE(link_id, page_url)
            )
            ''',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_ext_link_pages_link ON external_link_pages(link_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_ext_link_pages_depth ON external_link_pages(link_id, depth)',
        )
        self._migrate_external_link_pages_drop_legacy_json_columns(cursor)
        self._scrub_stale_google_thumb_urls(cursor)

    def _migrate_external_link_pages_drop_legacy_json_columns(self, cursor) -> None:
        """Retire les colonnes JSON obsolètes (données en tables filles : OG, images, lieu, téléphones)."""
        if not self._table_exists(cursor, 'external_link_pages'):
            return
        for col in ('og_json', 'image_urls_json', 'phones_json', 'location_json'):
            if not self._table_has_column(cursor, 'external_link_pages', col):
                continue
            if self.is_postgresql():
                self.safe_execute_sql(
                    cursor, f'ALTER TABLE external_link_pages DROP COLUMN IF EXISTS {col}'
                )
            else:
                self.safe_execute_sql(cursor, f'ALTER TABLE external_link_pages DROP COLUMN {col}')

    def _scrub_stale_google_thumb_urls(self, cursor) -> None:
        """Efface les vignettes pointant vers les services Google (s2 / gstatic) pour favoriser le re-scraping."""
        if not self._table_exists(cursor, 'external_domains'):
            return
        self.safe_execute_sql(
            cursor,
            '''
            UPDATE external_domains SET thumb_url = NULL
            WHERE thumb_url IS NOT NULL AND (
                LOWER(thumb_url) LIKE '%google.com/s2/favicons%'
                OR LOWER(thumb_url) LIKE '%gstatic.com/favicon%'
            )
            ''',
        )

    def _ensure_external_domain_norm_tables(self, cursor) -> None:
        """Catégories, types JSON-LD et hôtes portfolio : tables 1-n avec CASCADE vers ``external_domains``."""
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_domain_categories (
                domain_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                PRIMARY KEY (domain_id, category),
                FOREIGN KEY (domain_id) REFERENCES external_domains(id) ON DELETE CASCADE
            )
            ''',
        )
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_domain_jsonld_types (
                domain_id INTEGER NOT NULL,
                jsonld_type TEXT NOT NULL,
                PRIMARY KEY (domain_id, jsonld_type),
                FOREIGN KEY (domain_id) REFERENCES external_domains(id) ON DELETE CASCADE
            )
            ''',
        )
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_domain_portfolio_hosts (
                domain_id INTEGER NOT NULL,
                host TEXT NOT NULL,
                PRIMARY KEY (domain_id, host),
                FOREIGN KEY (domain_id) REFERENCES external_domains(id) ON DELETE CASCADE
            )
            ''',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_edc_domain ON external_domain_categories(domain_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_edj_domain ON external_domain_jsonld_types(domain_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_edp_domain ON external_domain_portfolio_hosts(domain_id)',
        )

    def _ensure_external_link_page_detail_tables(self, cursor) -> None:
        """Open Graph, images, lieu structuré (colonnes) : tables liées à ``external_link_pages`` (CASCADE)."""
        self.safe_execute_sql(cursor, 'DROP INDEX IF EXISTS idx_elph_page')
        self.safe_execute_sql(cursor, 'DROP TABLE IF EXISTS external_link_page_phones')
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_link_page_og_props (
                page_id INTEGER NOT NULL,
                prop_key TEXT NOT NULL,
                prop_value TEXT,
                PRIMARY KEY (page_id, prop_key),
                FOREIGN KEY (page_id) REFERENCES external_link_pages(id) ON DELETE CASCADE
            )
            ''',
        )
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_link_page_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                page_id INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                position INTEGER DEFAULT 0,
                FOREIGN KEY (page_id) REFERENCES external_link_pages(id) ON DELETE CASCADE,
                UNIQUE(page_id, image_url)
            )
            ''',
        )
        self.execute_sql(
            cursor,
            '''
            CREATE TABLE IF NOT EXISTS external_link_page_locations (
                page_id INTEGER PRIMARY KEY,
                source TEXT,
                location_page_url TEXT,
                street_address TEXT,
                postal_code TEXT,
                locality TEXT,
                country TEXT,
                latitude REAL,
                longitude REAL,
                geocoded INTEGER DEFAULT 0,
                FOREIGN KEY (page_id) REFERENCES external_link_pages(id) ON DELETE CASCADE
            )
            ''',
        )
        self._migrate_external_link_page_locations_columns(cursor)
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_elpog_page ON external_link_page_og_props(page_id)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_elimg_page ON external_link_page_images(page_id, position)',
        )
        self.execute_sql(
            cursor,
            'CREATE INDEX IF NOT EXISTS idx_elploc_locality ON external_link_page_locations(locality)',
        )

    def _migrate_external_link_page_locations_columns(self, cursor) -> None:
        """Bases créées avec ``raw_json`` seulement : ajoute les colonnes puis retire ``raw_json`` si possible."""
        if not self._table_exists(cursor, 'external_link_page_locations'):
            return
        for ddl in (
            'ALTER TABLE external_link_page_locations ADD COLUMN source TEXT',
            'ALTER TABLE external_link_page_locations ADD COLUMN location_page_url TEXT',
            'ALTER TABLE external_link_page_locations ADD COLUMN street_address TEXT',
            'ALTER TABLE external_link_page_locations ADD COLUMN postal_code TEXT',
            'ALTER TABLE external_link_page_locations ADD COLUMN locality TEXT',
            'ALTER TABLE external_link_page_locations ADD COLUMN country TEXT',
            'ALTER TABLE external_link_page_locations ADD COLUMN latitude REAL',
            'ALTER TABLE external_link_page_locations ADD COLUMN longitude REAL',
            'ALTER TABLE external_link_page_locations ADD COLUMN geocoded INTEGER',
        ):
            self.safe_execute_sql(cursor, ddl)
        if self._table_has_column(cursor, 'external_link_page_locations', 'raw_json'):
            self.safe_execute_sql(
                cursor, 'ALTER TABLE external_link_page_locations DROP COLUMN raw_json'
            )

    def clear_external_graph_data(self) -> None:
        """
        Vide toutes les données des tables du graphe externe (domaines, liens, pages, taxonomies).
        Ne supprime pas les tables. Ordre compatible contraintes FK.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_external_domain_norm_tables(cursor)
            self._ensure_external_link_pages_schema(cursor)
            self._ensure_external_link_page_detail_tables(cursor)
            stmts = [
                'DELETE FROM external_link_page_locations',
                'DELETE FROM external_link_page_og_props',
                'DELETE FROM external_link_page_images',
                'DELETE FROM external_link_pages',
                'DELETE FROM entreprise_external_links',
                'DELETE FROM external_domain_categories',
                'DELETE FROM external_domain_jsonld_types',
                'DELETE FROM external_domain_portfolio_hosts',
                'DELETE FROM external_domains',
            ]
            for sql in stmts:
                try:
                    self.execute_sql(cursor, sql, ())
                except Exception as e:
                    err = str(e).lower()
                    if 'no such table' in err or 'does not exist' in err:
                        continue
                    raise
            conn.commit()
            logger.info('Tables du graphe externe vidées (clear_external_graph_data).')
        finally:
            conn.close()

    def _sync_external_domain_list_rows(
        self,
        cursor,
        domain_id: int,
        categories: List[Any],
        jsonld_types: List[Any],
        portfolio_hosts: List[Any],
    ) -> None:
        for x in categories or []:
            s = str(x).strip()[:500]
            if not s:
                continue
            sql = self.insert_or_ignore_sql(
                'external_domain_categories',
                ['domain_id', 'category'],
                conflict_columns=['domain_id', 'category'],
            )
            self.execute_sql(cursor, sql, (domain_id, s))
        for x in jsonld_types or []:
            s = str(x).strip()[:500]
            if not s:
                continue
            sql = self.insert_or_ignore_sql(
                'external_domain_jsonld_types',
                ['domain_id', 'jsonld_type'],
                conflict_columns=['domain_id', 'jsonld_type'],
            )
            self.execute_sql(cursor, sql, (domain_id, s))
        for x in portfolio_hosts or []:
            h = normalize_website_domain(str(x)) or str(x).strip().lower()[:253]
            if not h:
                continue
            sql = self.insert_or_ignore_sql(
                'external_domain_portfolio_hosts',
                ['domain_id', 'host'],
                conflict_columns=['domain_id', 'host'],
            )
            self.execute_sql(cursor, sql, (domain_id, h))

    def _load_domain_taxonomy_maps(
        self, cursor, domain_ids: Set[int]
    ) -> Tuple[Dict[int, List[str]], Dict[int, List[str]], Dict[int, List[str]]]:
        cats_m: Dict[int, List[str]] = defaultdict(list)
        jl_m: Dict[int, List[str]] = defaultdict(list)
        port_m: Dict[int, List[str]] = defaultdict(list)
        if not domain_ids:
            return dict(cats_m), dict(jl_m), dict(port_m)
        ids = sorted(domain_ids)
        ph = ','.join('?' * len(ids))
        self.execute_sql(
            cursor,
            f'SELECT domain_id, category FROM external_domain_categories WHERE domain_id IN ({ph})',
            tuple(ids),
        )
        for raw in cursor.fetchall() or []:
            d = self.clean_row_dict(dict(raw))
            cats_m[int(d['domain_id'])].append(str(d['category']))
        self.execute_sql(
            cursor,
            f'SELECT domain_id, jsonld_type FROM external_domain_jsonld_types WHERE domain_id IN ({ph})',
            tuple(ids),
        )
        for raw in cursor.fetchall() or []:
            d = self.clean_row_dict(dict(raw))
            jl_m[int(d['domain_id'])].append(str(d['jsonld_type']))
        self.execute_sql(
            cursor,
            f'SELECT domain_id, host FROM external_domain_portfolio_hosts WHERE domain_id IN ({ph})',
            tuple(ids),
        )
        for raw in cursor.fetchall() or []:
            d = self.clean_row_dict(dict(raw))
            port_m[int(d['domain_id'])].append(str(d['host']))
        return dict(cats_m), dict(jl_m), dict(port_m)

    def _build_host_entreprise_ids_by_host(self, cursor) -> Dict[str, List[int]]:
        """Host normalisé → ids entreprises ayant ce site (pour lien externe → fiche existante)."""
        self.execute_sql(
            cursor,
            'SELECT id, website FROM entreprises WHERE website IS NOT NULL AND TRIM(website) != ?',
            ('',),
        )
        rows = cursor.fetchall() or []
        host_to_ids: Dict[str, List[int]] = defaultdict(list)
        for raw in rows:
            d = self.clean_row_dict(dict(raw))
            eid = d.get('id')
            web = d.get('website')
            if not eid or not web:
                continue
            h = normalize_website_domain(web)
            if h:
                host_to_ids[h].append(int(eid))
        out: Dict[str, List[int]] = {}
        for h, lst in host_to_ids.items():
            seen: List[int] = []
            for i in lst:
                if i not in seen:
                    seen.append(i)
            out[h] = seen
        return out

    @staticmethod
    def _unique_target_entreprise_for_external(
        host_to_ids: Dict[str, List[int]],
        domain: str,
        ext_url: str,
        source_entreprise_id: int,
    ) -> Optional[int]:
        """
        Si le domaine du lien externe correspond au site d’une autre fiche (hors entreprise source),
        et qu’il n’y a qu’une seule candidature, retourne son id.
        """
        h = normalize_website_domain(domain) or normalize_website_domain(ext_url)
        if not h:
            return None
        ids = [
            i
            for i in (host_to_ids.get(h) or [])
            if int(i) != int(source_entreprise_id)
        ]
        if len(ids) != 1:
            if len(ids) > 1:
                logger.debug(
                    'target_entreprise_id omis (domaine ambigu %s): %s',
                    h,
                    ids,
                )
            return None
        return ids[0]

    def _insert_external_domain_row(
        self,
        cursor,
        host: str,
        site_title: Any,
        site_description: Any,
        resolved_url: Any,
        thumb_url: Optional[str],
        graph_group: str,
        mini_scrape_error: Any,
        mini_scraped_at: Any,
    ) -> int:
        params = (
            host,
            site_title,
            site_description,
            resolved_url,
            thumb_url,
            graph_group,
            mini_scrape_error,
            mini_scraped_at,
        )
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                INSERT INTO external_domains (
                    domain_host, site_title, site_description, resolved_url, thumb_url,
                    graph_group, mini_scrape_error, mini_scraped_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                ''',
                params,
            )
            row = cursor.fetchone()
            if not row:
                raise RuntimeError('INSERT external_domains sans id')
            if isinstance(row, dict):
                return int(row['id'])
            return int(row[0])
        self.execute_sql(
            cursor,
            '''
            INSERT INTO external_domains (
                domain_host, site_title, site_description, resolved_url, thumb_url,
                graph_group, mini_scrape_error, mini_scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            params,
        )
        return int(cursor.lastrowid)

    def _get_or_merge_external_domain_id(
        self,
        cursor,
        domain_raw: str,
        snap: dict,
        classif: dict,
        portfolio_json: str,
        cats_json: str,
        jl_json: str,
        graph_group: str,
        likely_i: int,
    ) -> Optional[int]:
        host = normalize_website_domain(domain_raw) or normalize_website_domain(
            (snap.get('final_url') or '')
        )
        if not host:
            return None

        thumb_raw = (
            snap.get('favicon_url')
            or snap.get('thumbnail_url')
            or snap.get('og_image_url')
        )
        new_thumb = (str(thumb_raw).strip()[:2000] if thumb_raw else None)
        new_title = snap.get('title')
        new_desc = snap.get('description')
        new_resolved = snap.get('final_url')
        new_err = snap.get('error')
        new_fetched = snap.get('fetched_at')
        g_new = (
            'agency'
            if likely_i
            else ((classif.get('graph_group') or graph_group or 'external').strip() or 'external')
        )

        try:
            cats_list = json.loads(cats_json or '[]')
        except (TypeError, ValueError):
            cats_list = []
        if not isinstance(cats_list, list):
            cats_list = []
        try:
            jl_list = json.loads(jl_json or '[]')
        except (TypeError, ValueError):
            jl_list = []
        if not isinstance(jl_list, list):
            jl_list = []
        try:
            port_list = json.loads(portfolio_json or '[]')
        except (TypeError, ValueError):
            port_list = []
        if not isinstance(port_list, list):
            port_list = []

        self.execute_sql(
            cursor,
            '''
            SELECT id, site_title, site_description, resolved_url, thumb_url, graph_group,
                   mini_scrape_error, mini_scraped_at
            FROM external_domains WHERE domain_host = ?
            ''',
            (host,),
        )
        row = cursor.fetchone()
        d = self.clean_row_dict(dict(row)) if row is not None else None

        if d is None:
            new_id = self._insert_external_domain_row(
                cursor,
                host,
                new_title,
                new_desc,
                new_resolved,
                new_thumb,
                g_new,
                new_err,
                new_fetched,
            )
            self._sync_external_domain_list_rows(
                cursor, int(new_id), cats_list, jl_list, port_list
            )
            return int(new_id)

        did = int(d['id'])
        old_t = d.get('site_title') or ''
        m_title = new_title if new_title and (not old_t or len(str(new_title)) > len(str(old_t))) else d.get('site_title')
        old_d = d.get('site_description') or ''
        m_desc = (
            new_desc
            if new_desc and (not old_d or len(str(new_desc)) > len(str(old_d)))
            else d.get('site_description')
        )
        old_r = (d.get('resolved_url') or '').strip()
        m_res = old_r or (str(new_resolved).strip() if new_resolved else '') or None
        old_th = (d.get('thumb_url') or '').strip()
        m_thumb = old_th or (new_thumb or '') or None
        m_gg = (d.get('graph_group') or 'external').strip() or 'external'
        if self._graph_group_rank(g_new) > self._graph_group_rank(m_gg):
            m_gg = g_new
        m_err = d.get('mini_scrape_error') or new_err
        m_ft = new_fetched or d.get('mini_scraped_at')

        self.execute_sql(
            cursor,
            '''
            UPDATE external_domains SET
                site_title = ?, site_description = ?, resolved_url = ?, thumb_url = ?,
                graph_group = ?, mini_scrape_error = ?, mini_scraped_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            ''',
            (
                m_title,
                m_desc,
                m_res,
                m_thumb,
                m_gg,
                m_err,
                m_ft,
                did,
            ),
        )
        self._sync_external_domain_list_rows(cursor, did, cats_list, jl_list, port_list)
        return did

    def _insert_entreprise_external_link_returning_id(
        self,
        cursor,
        entreprise_id,
        scraper_id,
        domain_id: int,
        client_site_url,
        external_href,
        source_page_url,
        anchor_text,
        likely_i: int,
        link_source,
        target_eid,
    ) -> Optional[int]:
        params = (
            entreprise_id,
            scraper_id,
            domain_id,
            client_site_url,
            external_href,
            source_page_url,
            anchor_text,
            likely_i,
            link_source,
            target_eid,
        )
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                INSERT INTO entreprise_external_links (
                    entreprise_id, scraper_id, domain_id, client_site_url, external_href,
                    source_page_url, anchor_text, likely_credit, link_source, target_entreprise_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                ''',
                params,
            )
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return row.get('id')
            return row[0]
        self.execute_sql(
            cursor,
            '''
            INSERT INTO entreprise_external_links (
                entreprise_id, scraper_id, domain_id, client_site_url, external_href,
                source_page_url, anchor_text, likely_credit, link_source, target_entreprise_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            params,
        )
        return cursor.lastrowid

    def _insert_page_detail_rows(self, cursor, page_id: int, pg: dict) -> None:
        og = pg.get('open_graph') if isinstance(pg.get('open_graph'), dict) else {}
        for k, v in list(og.items())[:48]:
            ks = str(k).strip()[:120]
            if not ks:
                continue
            vs = None if v is None else str(v).strip()[:8000]
            sql = self.insert_or_ignore_sql(
                'external_link_page_og_props',
                ['page_id', 'prop_key', 'prop_value'],
                conflict_columns=['page_id', 'prop_key'],
            )
            self.execute_sql(cursor, sql, (page_id, ks, vs))
        imgs = pg.get('image_urls') or []
        if isinstance(imgs, list):
            for pos, u in enumerate(imgs[:60]):
                us = str(u).strip()[:4000]
                if not us:
                    continue
                sql = self.insert_or_ignore_sql(
                    'external_link_page_images',
                    ['page_id', 'image_url', 'position'],
                    conflict_columns=['page_id', 'image_url'],
                )
                self.execute_sql(cursor, sql, (page_id, us, pos))
        loc = pg.get('scraped_location')
        if loc is not None:
            self._upsert_external_link_page_location(cursor, page_id, loc)

    def _upsert_external_link_page_location(self, cursor, page_id: int, loc: Any) -> None:
        """Enregistre le lieu normalisé (champs de ``finalize_scraped_location``), sans téléphone ni JSON brut."""
        if not isinstance(loc, dict):
            return

        def clip_str(key: str, max_len: int) -> Optional[str]:
            v = loc.get(key)
            if v is None:
                return None
            s = str(v).strip()
            return (s[:max_len] if s else None) or None

        source = clip_str('source', 200)
        location_page_url = clip_str('page_url', 4000)
        street_address = clip_str('street_address', 2000)
        postal_code = clip_str('postal_code', 32)
        locality = clip_str('locality', 500)
        country = clip_str('country', 120)
        lat = lng = None
        try:
            if loc.get('latitude') is not None:
                lat = float(loc['latitude'])
            if loc.get('longitude') is not None:
                lng = float(loc['longitude'])
        except (TypeError, ValueError):
            lat = lng = None
        geocoded = 1 if loc.get('geocoded') else 0

        if not any(
            (source, location_page_url, street_address, postal_code, locality, country)
        ) and lat is None and lng is None:
            return

        params = (
            page_id,
            source,
            location_page_url,
            street_address,
            postal_code,
            locality,
            country,
            lat,
            lng,
            geocoded,
        )
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                INSERT INTO external_link_page_locations (
                    page_id, source, location_page_url, street_address, postal_code, locality, country,
                    latitude, longitude, geocoded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (page_id) DO UPDATE SET
                    source = EXCLUDED.source,
                    location_page_url = EXCLUDED.location_page_url,
                    street_address = EXCLUDED.street_address,
                    postal_code = EXCLUDED.postal_code,
                    locality = EXCLUDED.locality,
                    country = EXCLUDED.country,
                    latitude = EXCLUDED.latitude,
                    longitude = EXCLUDED.longitude,
                    geocoded = EXCLUDED.geocoded
                ''',
                params,
            )
        else:
            self.execute_sql(
                cursor,
                '''
                INSERT OR REPLACE INTO external_link_page_locations (
                    page_id, source, location_page_url, street_address, postal_code, locality, country,
                    latitude, longitude, geocoded
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                params,
            )

    def _insert_external_link_page_returning_id(
        self,
        cursor,
        link_id: int,
        page_url: str,
        depth: int,
        http_status: Any,
        title: Any,
        meta_description: Any,
        fetched_at: Any,
        fetch_error: Any,
    ) -> Optional[int]:
        params = (
            link_id,
            page_url,
            depth,
            http_status,
            title,
            meta_description,
            fetched_at,
            fetch_error,
        )
        if self.is_postgresql():
            self.execute_sql(
                cursor,
                '''
                INSERT INTO external_link_pages (
                    link_id, page_url, depth, http_status, title, meta_description,
                    fetched_at, fetch_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                RETURNING id
                ''',
                params,
            )
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return int(row['id'])
            return int(row[0])
        self.execute_sql(
            cursor,
            '''
            INSERT INTO external_link_pages (
                link_id, page_url, depth, http_status, title, meta_description,
                fetched_at, fetch_error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            params,
        )
        return int(cursor.lastrowid)

    def _insert_external_pages_for_link(self, cursor, link_id: int, pages: List[Any]) -> None:
        if not link_id or not pages:
            return
        seen: set = set()
        for pg in pages[:50]:
            if not isinstance(pg, dict):
                continue
            pu = (pg.get('page_url') or '').strip()
            if not pu or pu in seen:
                continue
            seen.add(pu)
            pid = self._insert_external_link_page_returning_id(
                cursor,
                link_id,
                pu[:4000],
                int(pg.get('depth') or 0),
                pg.get('http_status'),
                pg.get('title'),
                pg.get('meta_description'),
                pg.get('fetched_at'),
                pg.get('fetch_error'),
            )
            if pid:
                self._insert_page_detail_rows(cursor, int(pid), pg)

    @staticmethod
    def _graph_group_rank(g: Optional[str]) -> int:
        order = {
            'agency': 58,
            'saas_cms': 54,
            'hosting': 52,
            'software': 50,
            'ecommerce': 48,
            'education': 46,
            'media': 46,
            'company': 44,
            'finance': 43,
            'legal': 43,
            'health': 42,
            'realestate': 42,
            'tourism': 42,
            'public': 41,
            'nonprofit': 41,
            'person': 32,
            'external': 10,
        }
        return order.get((g or '').strip(), 5)

    @staticmethod
    def _escape_substring_like_pattern(raw: str, max_len: int) -> str:
        """Échappe ``%`` / ``_`` / ``\\`` pour LIKE / ILIKE."""
        t = str(raw).strip()[:max_len]
        return t.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    def _graph_entreprise_search_sql(self) -> str:
        """Prédicat recherche nom + site (SQLite : LOWER … LIKE, PostgreSQL : ILIKE)."""
        if self.is_postgresql():
            return (
                "(e.nom ILIKE ? ESCAPE '\\' OR COALESCE(e.website, '') ILIKE ? ESCAPE '\\')"
            )
        return (
            "(LOWER(e.nom) LIKE ? ESCAPE '\\' OR "
            "LOWER(COALESCE(e.website, '')) LIKE ? ESCAPE '\\')"
        )

    def _graph_domain_host_search_sql(self) -> str:
        if self.is_postgresql():
            return "d.domain_host ILIKE ? ESCAPE '\\'"
        return "LOWER(d.domain_host) LIKE ? ESCAPE '\\'"

    def _graph_like_contains_param(self, raw: str, max_len: int) -> str:
        frag = self._escape_substring_like_pattern(raw, max_len)
        inner = frag if self.is_postgresql() else frag.lower()
        return f'%{inner}%'

    def replace_web_external_links_for_scraper(
        self,
        entreprise_id,
        scraper_id,
        client_site_url,
        external_links,
    ):
        """Remplace les lignes du graphe pour un run de scraper."""
        if not entreprise_id or not scraper_id:
            return
        if external_links is None:
            return
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self._ensure_external_domain_norm_tables(cursor)
            self._ensure_external_link_pages_schema(cursor)
            self._ensure_external_link_page_detail_tables(cursor)
            self.execute_sql(
                cursor,
                'DELETE FROM entreprise_external_links WHERE scraper_id = ?',
                (scraper_id,),
            )
            self.execute_sql(
                cursor,
                '''DELETE FROM external_domains WHERE id NOT IN (
                    SELECT DISTINCT domain_id FROM entreprise_external_links
                )''',
                (),
            )
            if not external_links:
                conn.commit()
                return
            try:
                max_rows = max(30, int(os.environ.get('WEB_EXTERNAL_GRAPH_MAX_ROWS', '160')))
            except ValueError:
                max_rows = 160

            raw_items = [x for x in external_links if isinstance(x, dict) and x.get('url') and x.get('domain')]
            raw_items.sort(
                key=lambda it: (not bool(it.get('likely_credit')), (it.get('domain') or ''), (it.get('url') or '')),
            )
            items = raw_items[:max_rows]

            host_map = self._build_host_entreprise_ids_by_host(cursor)

            seen_urls = set()
            for item in items:
                domain = (item.get('domain') or '').strip()
                ext_url = (item.get('url') or '').strip()
                if not domain or not ext_url:
                    continue
                if ext_url in seen_urls:
                    continue
                seen_urls.add(ext_url)
                ext_snap = item.get('external_snapshot')
                snap = ext_snap if isinstance(ext_snap, dict) else {}
                if not snap:
                    leg = item.get('agency_snapshot')
                    snap = leg if isinstance(leg, dict) else {}
                classif = snap.get('classification') if isinstance(snap.get('classification'), dict) else {}
                portfolio_hosts = snap.get('portfolio_hosts') or []
                try:
                    portfolio_json = json.dumps(portfolio_hosts, ensure_ascii=False)
                except (TypeError, ValueError):
                    portfolio_json = '[]'
                try:
                    cats_json = json.dumps(classif.get('categories') or [], ensure_ascii=False)
                except (TypeError, ValueError):
                    cats_json = '[]'
                try:
                    jl_json = json.dumps(classif.get('jsonld_types') or [], ensure_ascii=False)
                except (TypeError, ValueError):
                    jl_json = '[]'

                srcs = item.get('link_sources')
                if isinstance(srcs, list) and srcs:
                    link_source = ','.join(str(s) for s in srcs)[:500]
                else:
                    link_source = (item.get('link_source') or 'anchor')[:500]

                likely_i = 1 if item.get('likely_credit') else 0
                graph_group = classif.get('graph_group') or 'external'
                if likely_i:
                    graph_group = 'agency'

                target_eid = self._unique_target_entreprise_for_external(
                    host_map, domain, ext_url, int(entreprise_id)
                )

                domain_id = self._get_or_merge_external_domain_id(
                    cursor,
                    domain,
                    snap,
                    classif,
                    portfolio_json,
                    cats_json,
                    jl_json,
                    graph_group,
                    likely_i,
                )
                if not domain_id:
                    continue

                link_id = self._insert_entreprise_external_link_returning_id(
                    cursor,
                    entreprise_id,
                    scraper_id,
                    int(domain_id),
                    client_site_url,
                    ext_url,
                    item.get('page_url'),
                    (item.get('text') or '')[:2000],
                    likely_i,
                    link_source,
                    target_eid,
                )
                pages = snap.get('pages') if isinstance(snap.get('pages'), list) else []
                if link_id and pages:
                    self._insert_external_pages_for_link(cursor, int(link_id), pages)
            conn.commit()
        except Exception as e:
            logger.warning('replace_web_external_links_for_scraper: %s', e, exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
        finally:
            conn.close()

    @staticmethod
    def _graph_int_env(name: str, default: int, min_v: int, max_v: int) -> int:
        try:
            v = int(os.environ.get(name, str(default)))
            return min(max_v, max(min_v, v))
        except ValueError:
            return default

    def suggest_entreprises_for_link_graph(self, q: str, limit: int = 15) -> List[Dict[str, Any]]:
        """Autocomplétion : entreprises ayant au moins un lien ``entreprise_external_links``."""
        q = (q or '').strip()
        if len(q) < 2:
            return []
        limit = min(50, max(1, int(limit)))
        term = self._graph_like_contains_param(q, 120)
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if self.is_postgresql():
                sql = '''
                SELECT e.id, e.nom, e.website
                FROM entreprises e
                WHERE EXISTS (SELECT 1 FROM entreprise_external_links w WHERE w.entreprise_id = e.id)
                  AND (e.nom ILIKE ? ESCAPE '\\' OR COALESCE(e.website, '') ILIKE ? ESCAPE '\\')
                ORDER BY e.nom ASC
                LIMIT ?
                '''
            else:
                sql = '''
                SELECT e.id, e.nom, e.website
                FROM entreprises e
                WHERE EXISTS (SELECT 1 FROM entreprise_external_links w WHERE w.entreprise_id = e.id)
                  AND (
                    LOWER(e.nom) LIKE ? ESCAPE '\\'
                    OR LOWER(COALESCE(e.website, '')) LIKE ? ESCAPE '\\'
                  )
                ORDER BY e.nom ASC
                LIMIT ?
                '''
            self.execute_sql(cursor, sql, (term, term, limit))
            raw = cursor.fetchall() or []
        finally:
            conn.close()
        out = []
        for r in raw:
            d = self.clean_row_dict(dict(r))
            out.append(
                {
                    'id': int(d['id']),
                    'nom': (d.get('nom') or '')[:120],
                    'website': (d.get('website') or '')[:200],
                }
            )
        return out

    def get_entreprises_link_graph(
        self,
        max_portfolio_edges_per_agency: Optional[int] = None,
        *,
        search: Optional[str] = None,
        entreprise_ids: Optional[Set[int]] = None,
        domain_contains: Optional[str] = None,
        only_credit: bool = False,
        max_link_rows: Optional[int] = None,
        max_enterprises: Optional[int] = None,
        meta_only: bool = False,
    ) -> dict:
        """
        Graphe entreprises ↔ domaines externes. Échelle : plafonds + filtres (recherche, IDs, domaine).

        Variables d’environnement (plafonds API) :
        - ``AGENCY_GRAPH_DEFAULT_MAX_LINK_ROWS`` (déf. 3000)
        - ``AGENCY_GRAPH_DEFAULT_MAX_ENTERPRISES`` (déf. 350)
        - ``AGENCY_GRAPH_API_MAX_LINK_ROWS`` (déf. 25000, dur)
        - ``AGENCY_GRAPH_API_MAX_ENTERPRISES`` (déf. 1200, dur)
        """
        if max_portfolio_edges_per_agency is None:
            try:
                max_portfolio_edges_per_agency = int(
                    os.environ.get('AGENCY_GRAPH_MAX_PORTFOLIO_EDGES_PER_AGENCY', '0')
                )
            except ValueError:
                max_portfolio_edges_per_agency = 0

        cap_links = self._graph_int_env('AGENCY_GRAPH_API_MAX_LINK_ROWS', 25000, 100, 500000)
        cap_ents = self._graph_int_env('AGENCY_GRAPH_API_MAX_ENTERPRISES', 1200, 10, 50000)
        def_links = self._graph_int_env('AGENCY_GRAPH_DEFAULT_MAX_LINK_ROWS', 3000, 50, cap_links)
        def_ents = self._graph_int_env('AGENCY_GRAPH_DEFAULT_MAX_ENTERPRISES', 350, 5, cap_ents)

        max_link_rows_eff = max(
            1, min(cap_links, max_link_rows if max_link_rows is not None else def_links)
        )
        max_enterprises_eff = max(
            1, min(cap_ents, max_enterprises if max_enterprises is not None else def_ents)
        )

        conn = self.get_connection()
        cursor = conn.cursor()
        cats_map: Dict[int, List[str]] = {}
        jl_map: Dict[int, List[str]] = {}
        port_map: Dict[int, List[str]] = {}
        try:
            self.execute_sql(cursor, 'SELECT COUNT(*) AS c FROM entreprise_external_links', ())
            r0 = cursor.fetchone()
            d0 = self.clean_row_dict(dict(r0)) if r0 is not None else {}
            total_links = int(d0.get('c') if d0.get('c') is not None else 0)

            self.execute_sql(
                cursor,
                'SELECT COUNT(DISTINCT entreprise_id) AS c FROM entreprise_external_links WHERE entreprise_id IS NOT NULL',
                (),
            )
            r1 = cursor.fetchone()
            d1 = self.clean_row_dict(dict(r1)) if r1 is not None else {}
            total_ent_with_links = int(d1.get('c') if d1.get('c') is not None else 0)

            if meta_only:
                return {
                    'success': True,
                    'nodes': [],
                    'edges': [],
                    'stats': {
                        'nodes': 0,
                        'edges': 0,
                        'agencies': 0,
                        'external_domains': 0,
                        'enterprises': 0,
                        'external_link_rows': 0,
                        'portfolio_edges': 0,
                    },
                    'graph_scope': {
                        'total_link_rows_in_db': total_links,
                        'total_enterprises_with_links': total_ent_with_links,
                        'max_link_rows_default': def_links,
                        'max_enterprises_default': def_ents,
                        'max_link_rows_cap': cap_links,
                        'max_enterprises_cap': cap_ents,
                        'meta_only': True,
                    },
                }

            where_sql = ['1=1']
            params: List[Any] = []

            if entreprise_ids is not None:
                if len(entreprise_ids) == 0:
                    return {
                        'success': True,
                        'nodes': [],
                        'edges': [],
                        'stats': {
                            'nodes': 0,
                            'edges': 0,
                            'agencies': 0,
                            'external_domains': 0,
                            'enterprises': 0,
                            'external_link_rows': 0,
                            'portfolio_edges': 0,
                        },
                        'graph_scope': {
                            'total_link_rows_in_db': total_links,
                            'total_enterprises_with_links': total_ent_with_links,
                            'max_link_rows': max_link_rows_eff,
                            'max_enterprises': max_enterprises_eff,
                            'filtered_link_rows': 0,
                            'enterprises_shown': 0,
                            'hit_link_row_cap': False,
                            'hit_enterprise_cap': False,
                            'filters': {
                                'search': search,
                                'entreprise_ids': [],
                                'domain_contains': domain_contains,
                                'only_credit': only_credit,
                            },
                        },
                    }
                placeholders = ','.join('?' * len(entreprise_ids))
                where_sql.append(f'w.entreprise_id IN ({placeholders})')
                params.extend(sorted(entreprise_ids))

            if search and str(search).strip():
                term = self._graph_like_contains_param(str(search), 120)
                where_sql.append(self._graph_entreprise_search_sql())
                params.extend([term, term])

            if domain_contains and str(domain_contains).strip():
                termd = self._graph_like_contains_param(str(domain_contains), 80)
                where_sql.append(self._graph_domain_host_search_sql())
                params.append(termd)

            if only_credit:
                where_sql.append('w.likely_credit = 1')

            where_clause = ' AND '.join(where_sql)
            order_date = (
                'w.date_creation DESC NULLS LAST'
                if self.is_postgresql()
                else 'w.date_creation DESC'
            )
            sql = f'''
                SELECT w.entreprise_id, w.domain_id, w.external_href, w.anchor_text,
                       w.likely_credit, w.link_source, w.target_entreprise_id,
                       d.domain_host, d.site_title, d.site_description, d.resolved_url,
                       d.graph_group, d.thumb_url,
                       e.nom, e.website, e.favicon AS entreprise_favicon
                FROM entreprise_external_links w
                JOIN external_domains d ON d.id = w.domain_id
                JOIN entreprises e ON e.id = w.entreprise_id
                WHERE {where_clause}
                ORDER BY w.likely_credit DESC, {order_date}
                LIMIT ?
            '''
            params.append(max_link_rows_eff)

            self.execute_sql(cursor, sql, tuple(params))
            rows_fetch = cursor.fetchall() or []

            hit_link_cap = len(rows_fetch) >= max_link_rows_eff

            row_dicts = [self.clean_row_dict(dict(raw)) for raw in rows_fetch]
            ent_counts = Counter(int(r['entreprise_id']) for r in row_dicts if r.get('entreprise_id'))

            hit_ent_cap = False
            if len(ent_counts) > max_enterprises_eff:
                hit_ent_cap = True
                top_ids = {eid for eid, _ in ent_counts.most_common(max_enterprises_eff)}
                row_dicts = [r for r in row_dicts if int(r['entreprise_id']) in top_ids]

            if row_dicts:
                self.execute_sql(
                    cursor,
                    'SELECT id, nom, website, favicon FROM entreprises WHERE website IS NOT NULL AND TRIM(website) != ?',
                    ('',),
                )
                ent_rows = cursor.fetchall() or []
            else:
                ent_rows = []

            domain_ids_for_tax: Set[int] = set()
            for r in row_dicts:
                dv = r.get('domain_id')
                if dv is not None:
                    try:
                        domain_ids_for_tax.add(int(dv))
                    except (TypeError, ValueError):
                        pass
            cats_map, jl_map, port_map = self._load_domain_taxonomy_maps(cursor, domain_ids_for_tax)
        finally:
            conn.close()

        host_to_ent_ids: Dict[str, List[dict]] = {}
        ent_by_id: Dict[int, dict] = {}
        for er in ent_rows:
            erd = self.clean_row_dict(dict(er))
            eid = erd.get('id')
            web = erd.get('website')
            nom = erd.get('nom')
            if eid:
                ent_by_id[int(eid)] = {
                    'nom': nom or '',
                    'website': web or '',
                    'favicon': (erd.get('favicon') or '').strip(),
                }
            hk = _website_host_key(web)
            if not hk or not eid:
                continue
            host_to_ent_ids.setdefault(hk, []).append(
                {'id': int(eid), 'nom': nom or '', 'website': web or ''}
            )

        nodes_map: Dict[str, Any] = {}
        edges_list: List[dict] = []
        edge_keys: set = set()
        agency_portfolio: Dict[str, set] = {}

        for row in row_dicts:
            eid = row['entreprise_id']
            d_host = (row.get('domain_host') or '').strip()
            atitle = row.get('site_title')
            enom = row['nom']
            eweb = row['website']
            likely_cred = bool(row.get('likely_credit'))
            try:
                did_int = int(row['domain_id'])
            except (TypeError, ValueError, KeyError):
                did_int = None
            cats = list(cats_map.get(did_int, []))[:80] if did_int is not None else []
            jl_types = list(jl_map.get(did_int, []))[:60] if did_int is not None else []
            ggrp = (row.get('graph_group') or '').strip() or 'external'
            if likely_cred:
                ggrp = 'agency'

            if not eid or not d_host:
                continue

            e_node_id = f'e:{int(eid)}'
            a_node_id = f'a:{d_host}'
            thumb = (row.get('thumb_url') or '').strip()
            efav_raw = (row.get('entreprise_favicon') or '').strip()
            efav = efav_raw if efav_raw.startswith(('http://', 'https://')) else ''

            if e_node_id not in nodes_map:
                nodes_map[e_node_id] = {
                    'id': e_node_id,
                    'label': (enom or f'#{eid}')[:48],
                    'group': 'entreprise',
                    'title': eweb or '',
                    'entreprise_id': int(eid),
                }
                if efav:
                    nodes_map[e_node_id]['thumb_url'] = efav[:2000]
                    nodes_map[e_node_id]['thumbnail_url'] = efav[:2000]
            elif efav and not (nodes_map[e_node_id].get('thumb_url') or '').strip():
                nodes_map[e_node_id]['thumb_url'] = efav[:2000]
                nodes_map[e_node_id]['thumbnail_url'] = efav[:2000]

            ext_url_row = (row.get('external_href') or '').strip()
            anch_row = (row.get('anchor_text') or '').strip()
            desc_row = (row.get('site_description') or '').strip()
            final_row = (row.get('resolved_url') or '').strip()

            if a_node_id not in nodes_map:
                nodes_map[a_node_id] = {
                    'id': a_node_id,
                    'label': (atitle or d_host)[:52],
                    'group': ggrp,
                    'title': d_host,
                    'domain': d_host,
                    'categories': list(cats)[:40],
                    'jsonld_types': list(jl_types)[:25],
                }
                if thumb:
                    nodes_map[a_node_id]['thumb_url'] = thumb
                    nodes_map[a_node_id]['thumbnail_url'] = thumb
                if ext_url_row:
                    nodes_map[a_node_id]['sample_external_url'] = ext_url_row[:600]
                if anch_row:
                    nodes_map[a_node_id]['sample_anchor_text'] = anch_row[:280]
                if desc_row:
                    nodes_map[a_node_id]['site_description'] = desc_row[:520]
                if final_row:
                    nodes_map[a_node_id]['resolved_url'] = final_row[:400]
            else:
                if atitle and (not nodes_map[a_node_id].get('label') or nodes_map[a_node_id]['label'] == d_host):
                    nodes_map[a_node_id]['label'] = str(atitle)[:52]
                prev_c = set(nodes_map[a_node_id].get('categories') or [])
                prev_c.update(cats)
                nodes_map[a_node_id]['categories'] = sorted(prev_c)[:40]
                prev_j = set(nodes_map[a_node_id].get('jsonld_types') or [])
                prev_j.update(jl_types)
                nodes_map[a_node_id]['jsonld_types'] = sorted(prev_j)[:25]
                cur_g = nodes_map[a_node_id].get('group') or 'external'
                if self._graph_group_rank(ggrp) > self._graph_group_rank(cur_g):
                    nodes_map[a_node_id]['group'] = ggrp
                if thumb and not (nodes_map[a_node_id].get('thumb_url') or '').strip():
                    nodes_map[a_node_id]['thumb_url'] = thumb
                    nodes_map[a_node_id]['thumbnail_url'] = thumb
                if ext_url_row and not (nodes_map[a_node_id].get('sample_external_url') or '').strip():
                    nodes_map[a_node_id]['sample_external_url'] = ext_url_row[:600]
                if anch_row and not (nodes_map[a_node_id].get('sample_anchor_text') or '').strip():
                    nodes_map[a_node_id]['sample_anchor_text'] = anch_row[:280]
                if desc_row and not (nodes_map[a_node_id].get('site_description') or '').strip():
                    nodes_map[a_node_id]['site_description'] = desc_row[:520]
                if final_row and not (nodes_map[a_node_id].get('resolved_url') or '').strip():
                    nodes_map[a_node_id]['resolved_url'] = final_row[:400]

            ek = ('ext_edge', e_node_id, a_node_id)
            if ek not in edge_keys:
                edge_keys.add(ek)
                edge_lbl = 'crédit' if likely_cred else 'lien'
                edges_list.append({
                    'from': e_node_id,
                    'to': a_node_id,
                    'label': edge_lbl,
                    'arrows': 'to',
                    'color': {'color': '#5b8cff' if likely_cred else '#a78bfa'},
                })

            tid_raw = row.get('target_entreprise_id')
            if tid_raw is not None and str(tid_raw).strip() != '':
                try:
                    tid_int = int(tid_raw)
                except (TypeError, ValueError):
                    tid_int = None
                if tid_int and tid_int != int(eid):
                    t_node_id = f'e:{tid_int}'
                    if t_node_id not in nodes_map:
                        info = ent_by_id.get(tid_int) or {}
                        tfav = (info.get('favicon') or '').strip()
                        nodes_map[t_node_id] = {
                            'id': t_node_id,
                            'label': (info.get('nom') or f'#{tid_int}')[:48],
                            'group': 'entreprise',
                            'title': info.get('website') or '',
                            'entreprise_id': tid_int,
                        }
                        if tfav.startswith(('http://', 'https://')):
                            nodes_map[t_node_id]['thumb_url'] = tfav[:2000]
                            nodes_map[t_node_id]['thumbnail_url'] = tfav[:2000]
                    fek = ('target_fiche', a_node_id, t_node_id)
                    if fek not in edge_keys:
                        edge_keys.add(fek)
                        edges_list.append({
                            'from': a_node_id,
                            'to': t_node_id,
                            'label': 'fiche en base',
                            'arrows': 'to',
                            'dashes': True,
                            'color': {'color': '#22c55e'},
                        })

            if did_int is not None:
                for h in port_map.get(did_int, []):
                    agency_portfolio.setdefault(d_host, set()).add(str(h).lower())

        portfolio_edge_count = 0
        for dom_host, hosts in agency_portfolio.items():
            a_node_id = f'a:{dom_host}'
            if a_node_id not in nodes_map:
                continue
            n_out = 0
            for hk in hosts:
                targets = host_to_ent_ids.get(hk) or []
                for t in targets:
                    tid = t['id']
                    t_node_id = f'e:{tid}'
                    if t_node_id not in nodes_map:
                        ei = ent_by_id.get(tid) or {}
                        pfav = (ei.get('favicon') or '').strip()
                        nodes_map[t_node_id] = {
                            'id': t_node_id,
                            'label': (t.get('nom') or f'#{tid}')[:48],
                            'group': 'entreprise',
                            'title': t.get('website') or '',
                            'entreprise_id': tid,
                        }
                        if pfav.startswith(('http://', 'https://')):
                            nodes_map[t_node_id]['thumb_url'] = pfav[:2000]
                            nodes_map[t_node_id]['thumbnail_url'] = pfav[:2000]
                    pek = ('portfolio', a_node_id, t_node_id)
                    if pek in edge_keys:
                        continue
                    edge_keys.add(pek)
                    edges_list.append({
                        'from': a_node_id,
                        'to': t_node_id,
                        'label': 'réf. site',
                        'arrows': 'to',
                        'dashes': True,
                        'color': {'color': '#94a3b8'},
                    })
                    n_out += 1
                    portfolio_edge_count += 1
                    if max_portfolio_edges_per_agency and n_out >= max_portfolio_edges_per_agency:
                        break
                if max_portfolio_edges_per_agency and n_out >= max_portfolio_edges_per_agency:
                    break

        agency_linked = defaultdict(set)
        for e in edges_list:
            f, t = e.get('from'), e.get('to')
            if f.startswith('e:') and t.startswith('a:'):
                agency_linked[t].add(f)
            elif f.startswith('a:') and t.startswith('e:'):
                agency_linked[f].add(t)
        for aid, ent_set in agency_linked.items():
            if aid in nodes_map:
                n_linked = len(ent_set)
                nodes_map[aid]['linked_enterprise_count'] = n_linked
                dom = nodes_map[aid].get('domain') or nodes_map[aid].get('title') or aid
                nodes_map[aid]['title'] = f'{dom}\n{n_linked} entreprise(s) liée(s)'
                if n_linked >= 2:
                    nodes_map[aid]['is_shared_external_hub'] = True

        shared_agency_ids = {aid for aid, ents in agency_linked.items() if len(ents) >= 2}
        for nid, n in nodes_map.items():
            if not str(nid).startswith('e:'):
                continue
            names: List[str] = []
            seen_dom: Set[str] = set()
            for edge in edges_list:
                oth = None
                if edge.get('from') == nid:
                    oth = edge.get('to')
                elif edge.get('to') == nid:
                    oth = edge.get('from')
                if not oth or not str(oth).startswith('a:') or oth not in shared_agency_ids:
                    continue
                dom = (nodes_map.get(oth) or {}).get('domain') or str(oth)[2:]
                if dom and dom not in seen_dom:
                    seen_dom.add(dom)
                    names.append(dom)
            n['shared_external_domains'] = names[:18]
            n['shared_external_domains_count'] = len(names)

        _assign_agency_centric_layout(nodes_map, edges_list)

        n_agency = sum(1 for n in nodes_map.values() if n.get('group') == 'agency')
        n_ext_nodes = sum(1 for n in nodes_map.values() if str(n.get('id') or '').startswith('a:'))
        n_ent = sum(1 for n in nodes_map.values() if n.get('group') == 'entreprise')
        n_shared_hubs = sum(1 for n in nodes_map.values() if n.get('is_shared_external_hub'))

        ent_ids_shown = len(
            {int(r['entreprise_id']) for r in row_dicts if r.get('entreprise_id')}
        )
        filt_ids = None
        if entreprise_ids is not None:
            filt_ids = sorted(entreprise_ids)[:500]

        return {
            'success': True,
            'nodes': list(nodes_map.values()),
            'edges': edges_list,
            'stats': {
                'nodes': len(nodes_map),
                'edges': len(edges_list),
                'agencies': n_agency,
                'external_domains': n_ext_nodes,
                'enterprises': n_ent,
                'external_link_rows': len(row_dicts),
                'portfolio_edges': portfolio_edge_count,
                'shared_external_hubs': n_shared_hubs,
            },
            'graph_scope': {
                'total_link_rows_in_db': total_links,
                'total_enterprises_with_links': total_ent_with_links,
                'max_link_rows': max_link_rows_eff,
                'max_enterprises': max_enterprises_eff,
                'max_link_rows_default': def_links,
                'max_enterprises_default': def_ents,
                'max_link_rows_cap': cap_links,
                'max_enterprises_cap': cap_ents,
                'sql_fetched_rows': len(rows_fetch),
                'link_rows_in_graph': len(row_dicts),
                'enterprises_shown': ent_ids_shown,
                'hit_link_row_cap': hit_link_cap,
                'hit_enterprise_cap': hit_ent_cap,
                'filters': {
                    'search': (search or '').strip() or None,
                    'entreprise_ids': filt_ids,
                    'domain_contains': (domain_contains or '').strip() or None,
                    'only_credit': bool(only_credit),
                },
            },
        }
