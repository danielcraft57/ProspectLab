"""
Persistance des jobs et conversations Facebook ProspectLab.
"""

from __future__ import annotations

import json
import re
from typing import Any

from .base import DatabaseBase

FACEBOOK_PAGE_MIN_MATCH_SCORE = 0.35


class FacebookProspectionManager(DatabaseBase):
    """CRUD tables facebook_prospection_*."""

    def create_facebook_prospection_job(
        self,
        entreprise_id: int,
        job_type: str,
        query: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """
        Cree un job en statut pending.

        @param entreprise_id: Fiche entreprise ProspectLab
        @param job_type: search | scrape_page | messenger_inbox
        @param query: Requete de recherche FB optionnelle
        @param meta: JSON libre (role serv1/serv2, etc.)
        @returns: id du job
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = (
                int(entreprise_id),
                job_type,
                query,
                json.dumps(meta or {}, ensure_ascii=False),
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_jobs
                        (entreprise_id, job_type, status, search_query, meta_json)
                    VALUES (?, ?, 'pending', ?, ?)
                    RETURNING id
                    ''',
                    params,
                )
                row = cursor.fetchone()
                job_id = row.get('id') if isinstance(row, dict) else row[0]
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_jobs
                        (entreprise_id, job_type, status, search_query, meta_json)
                    VALUES (?, ?, 'pending', ?, ?)
                    ''',
                    params,
                )
                job_id = cursor.lastrowid
            conn.commit()
            return int(job_id)
        finally:
            conn.close()

    def update_facebook_prospection_job_status(
        self,
        job_id: int,
        status: str,
        error_message: str | None = None,
        result_json: dict[str, Any] | None = None,
    ) -> None:
        """Met a jour le statut et le resultat d'un job."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            if result_json is None:
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE facebook_prospection_jobs
                    SET status = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (status, error_message, int(job_id)),
                )
            else:
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE facebook_prospection_jobs
                    SET status = ?, error_message = ?, result_json = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (
                        status,
                        error_message,
                        json.dumps(result_json, ensure_ascii=False),
                        int(job_id),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def append_facebook_job_progress(
        self,
        job_id: int,
        step: str,
        detail: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """
        Ajoute une ligne de journal au result_json du job (sans changer le statut).

        @param job_id: Job Facebook
        @param step: Etape courte (search, follow, messenger...)
        @param detail: Texte affiche dans l'UI
        @param extra: Champs libres (url, score, count...)
        """
        from datetime import datetime, timezone

        job = self.get_facebook_prospection_job(int(job_id))
        if not job:
            return
        raw = job.get('result_json')
        result: dict[str, Any] = {}
        if isinstance(raw, dict):
            result = dict(raw)
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    result = parsed
            except json.JSONDecodeError:
                result = {}
        log = list(result.get('progress') or [])
        entry: dict[str, Any] = {
            'ts': datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            'step': str(step)[:80],
            'detail': str(detail)[:400],
        }
        if extra:
            entry.update(extra)
        log.append(entry)
        result['progress'] = log[-50:]
        self.update_facebook_prospection_job_status(
            int(job_id),
            str(job.get('status') or 'running'),
            error_message=job.get('error_message'),
            result_json=result,
        )

    def get_facebook_prospection_job(self, job_id: int) -> dict[str, Any] | None:
        """Retourne un job par id."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'SELECT * FROM facebook_prospection_jobs WHERE id = ?',
                (int(job_id),),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row) if not isinstance(row, dict) else row
        finally:
            conn.close()

    def list_facebook_prospection_jobs(
        self,
        entreprise_id: int,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Liste les jobs recents pour une entreprise."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_jobs
                WHERE entreprise_id = ?
                ORDER BY id DESC
                LIMIT ?
                ''',
                (int(entreprise_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_facebook_prospection_queue_snapshot(self, job_id: int | None = None) -> dict[str, int]:
        """
        Compte les jobs Facebook en file (pending + running).

        @param job_id: Si fourni, calcule la position FIFO du job parmi les pending
        @returns: { pending, running, position, total_active }
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT COUNT(*) AS c FROM facebook_prospection_jobs
                WHERE status = 'pending'
                ''',
                (),
            )
            row_p = cursor.fetchone()
            pending = int((row_p.get('c') if isinstance(row_p, dict) else row_p[0]) or 0)

            self.execute_sql(
                cursor,
                '''
                SELECT COUNT(*) AS c FROM facebook_prospection_jobs
                WHERE status = 'running'
                ''',
                (),
            )
            row_r = cursor.fetchone()
            running = int((row_r.get('c') if isinstance(row_r, dict) else row_r[0]) or 0)

            position = pending
            if job_id is not None:
                self.execute_sql(
                    cursor,
                    '''
                    SELECT COUNT(*) AS c FROM facebook_prospection_jobs
                    WHERE status = 'pending' AND id <= ?
                    ''',
                    (int(job_id),),
                )
                row_pos = cursor.fetchone()
                position = int((row_pos.get('c') if isinstance(row_pos, dict) else row_pos[0]) or 1)
                if position < 1:
                    position = 1

            return {
                'pending': pending,
                'running': running,
                'position': position,
                'total_active': pending + running,
            }
        finally:
            conn.close()

    def _facebook_job_remote_node_from_row(self, row: dict[str, Any]) -> str:
        """Lit serv1 ou alt depuis meta_json (serv2 Debian = messagerie plus tard, pas ici)."""
        job_type = str(row.get('job_type') or '')
        if job_type == 'messenger_inbox':
            return 'serv1'
        raw = row.get('meta_json')
        meta: dict[str, Any] = {}
        if isinstance(raw, dict):
            meta = raw
        elif isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                meta = parsed if isinstance(parsed, dict) else {}
            except json.JSONDecodeError:
                meta = {}
        node = str(meta.get('remote_node') or meta.get('remote_host') or '').strip().lower()
        if node in ('alt', 'secondary', 'serv1_b', 'win2'):
            return 'alt'
        if node in ('serv2', 'messenger', '2', 'serv2.lan'):
            return 'serv1'
        return 'serv1'

    def auto_assign_facebook_remote_node(self, job_type: str) -> str:
        """
        Affecte le noeud Windows Playwright (serv1 ou hote ALT optionnel).

        serv2.lan est Debian (pas Chrome) : jamais choisi ici.

        @param job_type: search | scrape_page | prospect_flow | messenger_inbox
        @returns: 'serv1' ou 'alt'
        """
        from config import FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT

        alt_host = (FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT or '').strip()
        if not alt_host:
            return 'serv1'

        loads = {'serv1': 0, 'alt': 0}
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT job_type, meta_json FROM facebook_prospection_jobs
                WHERE status IN ('pending', 'running')
                ''',
                (),
            )
            for row in cursor.fetchall():
                r = dict(row) if not isinstance(row, dict) else row
                node = self._facebook_job_remote_node_from_row(r)
                if node == 'alt':
                    loads['alt'] += 1
                else:
                    loads['serv1'] += 1
        finally:
            conn.close()
        if loads['serv1'] <= loads['alt']:
            return 'serv1'
        return 'alt'

    def save_facebook_page_candidates(
        self,
        job_id: int,
        entreprise_id: int,
        candidates: list[dict[str, Any]],
    ) -> None:
        """
        Enregistre les candidats pages FB pour un job de recherche.

        @param job_id: Job source
        @param entreprise_id: Entreprise liee
        @param candidates: Liste {name, url, score, raw}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            for item in candidates:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_page_candidates
                        (job_id, entreprise_id, page_name, page_url, match_score, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        int(job_id),
                        int(entreprise_id),
                        str(item.get('name') or '')[:500],
                        str(item.get('url') or '')[:1000],
                        float(item.get('score') or 0),
                        json.dumps(item, ensure_ascii=False),
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    def list_facebook_page_candidates(self, job_id: int) -> list[dict[str, Any]]:
        """Candidats pages pour un job."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_page_candidates
                WHERE job_id = ?
                ORDER BY match_score DESC, id ASC
                ''',
                (int(job_id),),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def pick_facebook_page_from_job_result(
        self,
        job_type: str,
        parsed: dict[str, Any],
        *,
        min_score: float = FACEBOOK_PAGE_MIN_MATCH_SCORE,
    ) -> dict[str, Any] | None:
        """
        Choisit la page FB a enregistrer apres un job search ou prospect_flow.

        @param job_type: search | prospect_flow
        @param parsed: JSON retour Playwright
        @param min_score: Seuil minimal match_score
        @returns: {name, url, score, ...} ou None
        """
        jt = (job_type or '').strip()
        sel = parsed.get('selected') if isinstance(parsed.get('selected'), dict) else {}
        if jt in ('search', 'prospect_flow') and sel:
            url = str(sel.get('url') or '').strip()
            if url and float(sel.get('score') or 1) >= min_score:
                return sel
        if jt == 'search' and parsed.get('ok'):
            cands = list(parsed.get('candidates') or [])
            if not cands:
                return None
            top = cands[0]
            url = str(top.get('url') or '').strip()
            if url and float(top.get('score') or 0) >= min_score:
                return top
        if jt == 'scrape_page':
            prof = parsed.get('profile') if isinstance(parsed.get('profile'), dict) else {}
            url = str(prof.get('page_url') or '').strip()
            if url:
                return {
                    'url': url,
                    'name': prof.get('title'),
                    'score': 1,
                }
        return None

    def get_facebook_prospection_selected_page(self, entreprise_id: int) -> dict[str, Any] | None:
        """
        Page Facebook retenue pour une entreprise (derniere selection).

        @param entreprise_id: ID entreprise
        @returns: Ligne facebook_prospection_pages ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        page: dict[str, Any] | None = None
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_pages
                WHERE entreprise_id = ? AND selected = 1
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                ''',
                (int(entreprise_id),),
            )
            row = cursor.fetchone()
            if row:
                page = dict(row) if not isinstance(row, dict) else row
        finally:
            conn.close()
        if not page:
            return None
        page_id = int(page.get('id') or 0)
        if page_id:
            page['contacts'] = self.list_facebook_page_contacts(page_id)
            page['posts'] = self.list_facebook_page_posts(page_id)
            page['media'] = self.list_facebook_page_media(page_id)
        return page

    def sync_entreprise_facebook_page_url(
        self,
        entreprise_id: int,
        page_url: str | None,
        page_id: int | None = None,
    ) -> None:
        """
        Pointe la fiche entreprise vers la page Facebook (URL + FK).

        @param entreprise_id: Entreprise
        @param page_url: URL canonique ou None
        @param page_id: PK facebook_prospection_pages
        """
        url = str(page_url or '').strip()[:1000] or None
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                UPDATE entreprises
                SET facebook_page_url = ?, facebook_page_id = ?
                WHERE id = ?
                ''',
                (url, int(page_id) if page_id else None, int(entreprise_id)),
            )
            conn.commit()
        finally:
            conn.close()

    def persist_facebook_page_from_job(
        self,
        entreprise_id: int,
        job_id: int,
        job_type: str,
        parsed: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Enregistre le lien FB si une page pertinente a ete trouvee.

        @returns: Page retenue ou None
        """
        if not entreprise_id:
            return None
        picked = self.pick_facebook_page_from_job_result(job_type, parsed)
        scrape = parsed.get('profile') if isinstance(parsed.get('profile'), dict) else None
        if not picked and scrape and scrape.get('page_url'):
            picked = {
                'url': scrape.get('page_url'),
                'name': scrape.get('title'),
                'score': 1,
            }
        if not picked:
            return None
        page_url = str(picked.get('url') or '').strip()
        if not page_url:
            return None
        profile = {
            'source_job_type': job_type,
            'match_score': picked.get('score'),
            'snippet': picked.get('snippet'),
        }
        if scrape:
            profile.update(
                {
                    'scrape': scrape,
                    'title': scrape.get('title'),
                    'about_preview': scrape.get('about_preview'),
                    'category': scrape.get('category'),
                    'likes': scrape.get('likes'),
                    'followers': scrape.get('followers'),
                    'rating': scrape.get('rating'),
                    'phones': scrape.get('phones'),
                    'emails': scrape.get('emails'),
                    'websites': scrape.get('websites'),
                    'address': scrape.get('address'),
                    'hours': scrape.get('hours'),
                    'intro': scrape.get('intro'),
                    'posts': scrape.get('posts'),
                }
            )
        if job_type == 'prospect_flow':
            profile.update(
                {
                    'follow': parsed.get('follow'),
                    'message': parsed.get('message'),
                    'address_hint': parsed.get('address_hint'),
                }
            )
        page_name = (picked.get('name') or (scrape or {}).get('title') or '').strip() or None
        page_id = self.save_facebook_prospection_selected_page(
            int(entreprise_id),
            int(job_id),
            page_url,
            page_name,
            profile,
            scrape=scrape,
            match_score=picked.get('score'),
        )
        self.sync_entreprise_facebook_page_url(int(entreprise_id), page_url, page_id=page_id)
        if scrape:
            self.apply_facebook_scrape_to_entreprise(int(entreprise_id), scrape, page_url=page_url)
        return picked

    def save_facebook_prospection_selected_page(
        self,
        entreprise_id: int,
        job_id: int,
        page_url: str,
        page_name: str | None,
        profile_json: dict[str, Any] | None = None,
        scrape: dict[str, Any] | None = None,
        match_score: Any = None,
    ) -> int:
        """
        Upsert la page Facebook retenue (id stable pour les FK enfants).

        @param entreprise_id: Entreprise liee
        @param job_id: Job source
        @param page_url: URL canonique page FB
        @param page_name: Nom affiche
        @param profile_json: Suivi / message / brut
        @param scrape: Champs extraits Playwright
        @param match_score: Score de matching
        @returns: id facebook_prospection_pages
        """
        url = str(page_url)[:1000]
        name = (page_name or '')[:500] or None
        payload = profile_json or {}
        scrape_data = scrape if isinstance(scrape, dict) else None
        if scrape_data is None and isinstance(payload.get('scrape'), dict):
            scrape_data = payload.get('scrape')
        cols = _page_columns_from_scrape(scrape_data, name, match_score)
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'UPDATE facebook_prospection_pages SET selected = 0 WHERE entreprise_id = ?',
                (int(entreprise_id),),
            )
            self.execute_sql(
                cursor,
                '''
                SELECT id FROM facebook_prospection_pages
                WHERE entreprise_id = ? AND page_url = ?
                LIMIT 1
                ''',
                (int(entreprise_id), url),
            )
            existing = cursor.fetchone()
            existing_id = None
            if existing:
                existing_id = existing.get('id') if isinstance(existing, dict) else existing[0]

            if existing_id:
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE facebook_prospection_pages
                    SET job_id = ?, page_name = ?, profile_json = ?, selected = 1,
                        category = ?, likes_text = ?, likes_count = ?,
                        followers_text = ?, followers_count = ?, rating = ?,
                        intro = ?, about_text = ?, hours_text = ?,
                        address_1 = ?, code_postal = ?, ville = ?,
                        match_score = ?, scraped_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (
                        int(job_id) if job_id else None,
                        cols['page_name'],
                        json.dumps(payload, ensure_ascii=False),
                        cols['category'],
                        cols['likes_text'],
                        cols['likes_count'],
                        cols['followers_text'],
                        cols['followers_count'],
                        cols['rating'],
                        cols['intro'],
                        cols['about_text'],
                        cols['hours_text'],
                        cols['address_1'],
                        cols['code_postal'],
                        cols['ville'],
                        cols['match_score'],
                        int(existing_id),
                    ),
                )
                page_id = int(existing_id)
            elif self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_pages (
                        entreprise_id, job_id, page_url, page_name, profile_json, selected,
                        category, likes_text, likes_count, followers_text, followers_count,
                        rating, intro, about_text, hours_text, address_1, code_postal, ville,
                        match_score, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    RETURNING id
                    ''',
                    (
                        int(entreprise_id),
                        int(job_id) if job_id else None,
                        url,
                        cols['page_name'],
                        json.dumps(payload, ensure_ascii=False),
                        cols['category'],
                        cols['likes_text'],
                        cols['likes_count'],
                        cols['followers_text'],
                        cols['followers_count'],
                        cols['rating'],
                        cols['intro'],
                        cols['about_text'],
                        cols['hours_text'],
                        cols['address_1'],
                        cols['code_postal'],
                        cols['ville'],
                        cols['match_score'],
                    ),
                )
                row = cursor.fetchone()
                page_id = int(row.get('id') if isinstance(row, dict) else row[0])
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_pages (
                        entreprise_id, job_id, page_url, page_name, profile_json, selected,
                        category, likes_text, likes_count, followers_text, followers_count,
                        rating, intro, about_text, hours_text, address_1, code_postal, ville,
                        match_score, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ''',
                    (
                        int(entreprise_id),
                        int(job_id) if job_id else None,
                        url,
                        cols['page_name'],
                        json.dumps(payload, ensure_ascii=False),
                        cols['category'],
                        cols['likes_text'],
                        cols['likes_count'],
                        cols['followers_text'],
                        cols['followers_count'],
                        cols['rating'],
                        cols['intro'],
                        cols['about_text'],
                        cols['hours_text'],
                        cols['address_1'],
                        cols['code_postal'],
                        cols['ville'],
                        cols['match_score'],
                    ),
                )
                page_id = int(cursor.lastrowid)
            conn.commit()
        finally:
            conn.close()
        if scrape_data:
            self.replace_facebook_page_contacts(page_id, scrape_data)
            self.replace_facebook_page_posts(page_id, scrape_data)
            self.replace_facebook_page_media(page_id, scrape_data)
            self.apply_facebook_page_extra_columns(page_id, cols)
        return page_id

    def replace_facebook_page_contacts(self, page_id: int, scrape: dict[str, Any]) -> None:
        """Remplace les contacts normalises (tel / mail / site) d'une page."""
        rows: list[tuple[str, str]] = []
        for kind, key in (
            ('phone', 'phones'),
            ('email', 'emails'),
            ('website', 'websites'),
            ('social', 'socials'),
        ):
            values = scrape.get(key) if isinstance(scrape.get(key), list) else []
            for raw in values:
                val = str(raw or '').strip()[:500]
                if val:
                    rows.append((kind, val))
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'DELETE FROM facebook_prospection_page_contacts WHERE page_id = ?',
                (int(page_id),),
            )
            seen: set[tuple[str, str]] = set()
            for kind, value in rows:
                key = (kind, value.lower())
                if key in seen:
                    continue
                seen.add(key)
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_page_contacts (page_id, kind, value)
                    VALUES (?, ?, ?)
                    ''',
                    (int(page_id), kind, value),
                )
            conn.commit()
        finally:
            conn.close()

    def replace_facebook_page_posts(self, page_id: int, scrape: dict[str, Any]) -> None:
        """Remplace les extraits de posts d'une page."""
        posts = scrape.get('posts') if isinstance(scrape.get('posts'), list) else []
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'DELETE FROM facebook_prospection_page_posts WHERE page_id = ?',
                (int(page_id),),
            )
            for idx, raw in enumerate(posts[:12]):
                body = str(raw or '').strip()[:2000]
                if not body:
                    continue
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_page_posts (page_id, position, body_text)
                    VALUES (?, ?, ?)
                    ''',
                    (int(page_id), idx, body),
                )
            conn.commit()
        finally:
            conn.close()

    def list_facebook_page_contacts(self, page_id: int) -> list[dict[str, Any]]:
        """Contacts d'une page Facebook."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT id, kind, value
                FROM facebook_prospection_page_contacts
                WHERE page_id = ?
                ORDER BY kind, id
                ''',
                (int(page_id),),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def apply_facebook_page_extra_columns(self, page_id: int, cols: dict[str, Any]) -> None:
        """Met a jour username, visuels et extras sur facebook_prospection_pages."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                UPDATE facebook_prospection_pages
                SET username = ?, fb_page_id = ?, cover_url = ?, logo_url = ?,
                    reviews_count = ?, creation_text = ?, price_range = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    cols.get('username'),
                    cols.get('fb_page_id'),
                    cols.get('cover_url'),
                    cols.get('logo_url'),
                    cols.get('reviews_count'),
                    cols.get('creation_text'),
                    cols.get('price_range'),
                    int(page_id),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def replace_facebook_page_media(self, page_id: int, scrape: dict[str, Any]) -> None:
        """Remplace cover / logo / photos d'une page."""
        items: list[tuple[str, str, int]] = []
        cover = str(scrape.get('cover_url') or '').strip()
        logo = str(scrape.get('logo_url') or '').strip()
        if cover:
            items.append(('cover', cover[:1000], 0))
        if logo:
            items.append(('logo', logo[:1000], 0))
        photos = scrape.get('photos') if isinstance(scrape.get('photos'), list) else []
        for idx, raw in enumerate(photos[:16]):
            url = str(raw or '').strip()[:1000]
            if url:
                items.append(('photo', url, idx))
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                'DELETE FROM facebook_prospection_page_media WHERE page_id = ?',
                (int(page_id),),
            )
            seen: set[str] = set()
            for kind, url, pos in items:
                if url in seen:
                    continue
                seen.add(url)
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_page_media (page_id, kind, url, position)
                    VALUES (?, ?, ?, ?)
                    ''',
                    (int(page_id), kind, url, pos),
                )
            conn.commit()
        finally:
            conn.close()

    def list_facebook_page_media(self, page_id: int) -> list[dict[str, Any]]:
        """Medias (cover, logo, photos) d'une page Facebook."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT id, kind, url, position
                FROM facebook_prospection_page_media
                WHERE page_id = ?
                ORDER BY kind, position, id
                ''',
                (int(page_id),),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_facebook_page_posts(self, page_id: int) -> list[dict[str, Any]]:
        """Posts extraits d'une page Facebook."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT id, position, body_text
                FROM facebook_prospection_page_posts
                WHERE page_id = ?
                ORDER BY position ASC, id ASC
                ''',
                (int(page_id),),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def upsert_facebook_prospection_conversation(
        self,
        entreprise_id: int,
        *,
        page_id: int | None,
        thread_key: str,
        fb_page_url: str | None,
        status: str,
        meta: dict[str, Any] | None = None,
    ) -> int:
        """
        Cree ou met a jour un fil Messenger lie a une entreprise.

        @returns: id conversation
        """
        key = str(thread_key or fb_page_url or '')[:500]
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT id FROM facebook_prospection_conversations
                WHERE entreprise_id = ? AND thread_key = ?
                LIMIT 1
                ''',
                (int(entreprise_id), key),
            )
            row = cursor.fetchone()
            meta_json = json.dumps(meta or {}, ensure_ascii=False)
            if row:
                conv_id = row.get('id') if isinstance(row, dict) else row[0]
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE facebook_prospection_conversations
                    SET page_id = ?, fb_page_url = ?, status = ?, meta_json = ?,
                        last_sync_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    ''',
                    (
                        page_id,
                        (fb_page_url or '')[:1000] or None,
                        str(status)[:80],
                        meta_json,
                        int(conv_id),
                    ),
                )
            else:
                if self.is_postgresql():
                    self.execute_sql(
                        cursor,
                        '''
                        INSERT INTO facebook_prospection_conversations
                            (entreprise_id, page_id, thread_key, fb_page_url, status, meta_json, last_sync_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        RETURNING id
                        ''',
                        (
                            int(entreprise_id),
                            page_id,
                            key,
                            (fb_page_url or '')[:1000] or None,
                            str(status)[:80],
                            meta_json,
                        ),
                    )
                    ins = cursor.fetchone()
                    conv_id = ins.get('id') if isinstance(ins, dict) else ins[0]
                else:
                    self.execute_sql(
                        cursor,
                        '''
                        INSERT INTO facebook_prospection_conversations
                            (entreprise_id, page_id, thread_key, fb_page_url, status, meta_json, last_sync_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        ''',
                        (
                            int(entreprise_id),
                            page_id,
                            key,
                            (fb_page_url or '')[:1000] or None,
                            str(status)[:80],
                            meta_json,
                        ),
                    )
                    conv_id = cursor.lastrowid
            conn.commit()
            return int(conv_id)
        finally:
            conn.close()

    def add_facebook_prospection_message(
        self,
        conversation_id: int,
        direction: str,
        body_text: str | None,
        *,
        sent_at: str | None = None,
        raw_json: dict[str, Any] | None = None,
    ) -> int:
        """
        Ajoute un message au fil (sortant prospect ou sync inbox futur).

        @returns: id message
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            params = (
                int(conversation_id),
                str(direction)[:20],
                (body_text or '')[:8000] or None,
                sent_at,
                json.dumps(raw_json or {}, ensure_ascii=False),
            )
            if self.is_postgresql():
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_messages
                        (conversation_id, direction, body_text, sent_at, raw_json)
                    VALUES (?, ?, ?, ?, ?)
                    RETURNING id
                    ''',
                    params,
                )
                row = cursor.fetchone()
                msg_id = row.get('id') if isinstance(row, dict) else row[0]
            else:
                self.execute_sql(
                    cursor,
                    '''
                    INSERT INTO facebook_prospection_messages
                        (conversation_id, direction, body_text, sent_at, raw_json)
                    VALUES (?, ?, ?, ?, ?)
                    ''',
                    params,
                )
                msg_id = cursor.lastrowid
            conn.commit()
            return int(msg_id)
        finally:
            conn.close()

    def list_facebook_prospection_conversations(
        self,
        entreprise_id: int,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Fils Messenger enregistres pour une entreprise."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_conversations
                WHERE entreprise_id = ?
                ORDER BY last_sync_at DESC, id DESC
                LIMIT ?
                ''',
                (int(entreprise_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    def list_facebook_prospection_messages(
        self,
        conversation_id: int,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Messages d'une conversation."""
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT * FROM facebook_prospection_messages
                WHERE conversation_id = ?
                ORDER BY id ASC
                LIMIT ?
                ''',
                (int(conversation_id), int(limit)),
            )
            return [dict(r) if not isinstance(r, dict) else r for r in cursor.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def _conversation_status_from_prospect(message: dict[str, Any]) -> str:
        """Derive le statut conversation depuis le bloc message Playwright."""
        msg = message or {}
        if msg.get('ok') and not msg.get('dry_run'):
            return 'sent'
        if msg.get('ok') and msg.get('dry_run'):
            return 'draft_dry_run'
        step = str(msg.get('step') or '')
        if step == 'no-message-button':
            return 'messenger_no_button'
        if step in ('type', 'send') or step == 'opened':
            return 'compose_failed'
        return 'open'

    def persist_prospect_flow_outreach(
        self,
        entreprise_id: int,
        job_id: int,
        parsed: dict[str, Any],
        *,
        message_text: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Enregistre fil Messenger + message sortant apres prospect_flow.

        @returns: {conversation_id, message_id?, status} ou None si pas de page
        """
        page_row = self.get_facebook_prospection_selected_page(int(entreprise_id))
        if not page_row:
            return None

        selected = parsed.get('selected') or {}
        follow = parsed.get('follow') or {}
        message = parsed.get('message') or {}
        body = (message_text or parsed.get('message_text') or '').strip()
        fb_page_url = str(selected.get('url') or page_row.get('page_url') or '')[:1000]
        messenger_url = str(message.get('messenger_url') or '')[:1000]
        thread_key = messenger_url or fb_page_url

        conv_status = self._conversation_status_from_prospect(message)
        conv_id = self.upsert_facebook_prospection_conversation(
            int(entreprise_id),
            page_id=int(page_row.get('id') or 0) or None,
            thread_key=thread_key,
            fb_page_url=fb_page_url,
            status=conv_status,
            meta={
                'job_id': job_id,
                'follow': follow,
                'message': message,
                'prospect_status': parsed.get('prospect_status'),
                'steps': parsed.get('steps'),
            },
        )

        out: dict[str, Any] = {'conversation_id': conv_id, 'status': conv_status}
        if not body:
            return out

        sent_at_val = None
        if message.get('ok') and not message.get('dry_run'):
            from datetime import datetime, timezone

            sent_at_val = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

        raw_msg = {
            'job_id': job_id,
            'dry_run': message.get('dry_run'),
            'step': message.get('step'),
            'sent': message.get('sent'),
            'typed': message.get('typed'),
        }
        msg_id = self.add_facebook_prospection_message(
            conv_id,
            'outbound',
            body,
            sent_at=sent_at_val,
            raw_json=raw_msg,
        )

        out['message_id'] = msg_id
        return out

    def merge_facebook_page_scrape_profile(
        self,
        entreprise_id: int,
        profile: dict[str, Any],
    ) -> None:
        """
        Fusionne le resultat scrape_page dans profile_json de la page selectionnee.

        @param entreprise_id: Entreprise
        @param profile: JSON profile renvoye par Playwright
        """
        page_row = self.get_facebook_prospection_selected_page(int(entreprise_id))
        if not page_row:
            return
        raw = page_row.get('profile_json')
        existing: dict[str, Any] = {}
        if isinstance(raw, dict):
            existing = raw
        elif isinstance(raw, str) and raw.strip():
            try:
                existing = json.loads(raw)
            except json.JSONDecodeError:
                existing = {}
        merged = {
            **existing,
            'scrape': profile,
            'title': profile.get('title'),
            'about_preview': profile.get('about_preview'),
        }
        cols = _page_columns_from_scrape(profile, page_row.get('page_name'), page_row.get('match_score'))
        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                UPDATE facebook_prospection_pages
                SET profile_json = ?, page_name = COALESCE(?, page_name),
                    category = ?, likes_text = ?, likes_count = ?,
                    followers_text = ?, followers_count = ?, rating = ?,
                    intro = ?, about_text = ?, hours_text = ?,
                    address_1 = ?, code_postal = ?, ville = ?,
                    scraped_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                ''',
                (
                    json.dumps(merged, ensure_ascii=False),
                    cols['page_name'],
                    cols['category'],
                    cols['likes_text'],
                    cols['likes_count'],
                    cols['followers_text'],
                    cols['followers_count'],
                    cols['rating'],
                    cols['intro'],
                    cols['about_text'],
                    cols['hours_text'],
                    cols['address_1'],
                    cols['code_postal'],
                    cols['ville'],
                    int(page_row['id']),
                ),
            )
            conn.commit()
        finally:
            conn.close()
        self.replace_facebook_page_contacts(int(page_row['id']), profile)
        self.replace_facebook_page_posts(int(page_row['id']), profile)
        self.replace_facebook_page_media(int(page_row['id']), profile)
        self.apply_facebook_page_extra_columns(int(page_row['id']), cols)
        self.apply_facebook_scrape_to_entreprise(
            int(entreprise_id),
            profile,
            page_url=page_row.get('page_url'),
        )

    def apply_facebook_scrape_to_entreprise(
        self,
        entreprise_id: int,
        scrape: dict[str, Any],
        *,
        page_url: str | None = None,
    ) -> None:
        """
        Recopie tel / mail / site / adresse Facebook sur la fiche entreprise
        uniquement si les champs sont encore vides.

        @param entreprise_id: Fiche CRM
        @param scrape: JSON renvoye par Playwright
        @param page_url: URL page FB a synchroniser
        """
        if not entreprise_id or not isinstance(scrape, dict):
            return

        phones = scrape.get('phones') if isinstance(scrape.get('phones'), list) else []
        emails = scrape.get('emails') if isinstance(scrape.get('emails'), list) else []
        websites = scrape.get('websites') if isinstance(scrape.get('websites'), list) else []
        phone = str(phones[0] if phones else '').strip()
        email = str(emails[0] if emails else '').strip()
        website = ''
        for item in websites:
            href = str(item or '').strip()
            if href and href.startswith('http') and 'facebook.com' not in href.lower():
                website = href[:500]
                break
        address = str(scrape.get('address') or '').strip()
        street, postal, city = _split_french_address(address)
        fb_url = str(page_url or scrape.get('page_url') or '').strip()[:1000] or None

        conn = self.get_connection()
        cursor = conn.cursor()
        try:
            self.execute_sql(
                cursor,
                '''
                SELECT facebook_page_url, telephone, email_principal, website,
                       address_1, ville, code_postal
                FROM entreprises WHERE id = ?
                ''',
                (int(entreprise_id),),
            )
            row = cursor.fetchone()
            if not row:
                return
            ent = dict(row) if not isinstance(row, dict) else row

            def _empty(val: Any) -> bool:
                return val is None or (isinstance(val, str) and not str(val).strip())

            updates: list[str] = []
            params: list[Any] = []
            if fb_url:
                updates.append('facebook_page_url = ?')
                params.append(fb_url)
            if phone and _empty(ent.get('telephone')):
                updates.append('telephone = ?')
                params.append(phone[:80])
            if email and '@' in email and _empty(ent.get('email_principal')):
                updates.append('email_principal = ?')
                params.append(email[:200])
            if website and _empty(ent.get('website')):
                updates.append('website = ?')
                params.append(website)
            if street and _empty(ent.get('address_1')):
                updates.append('address_1 = ?')
                params.append(street[:500])
            if postal and _empty(ent.get('code_postal')):
                updates.append('code_postal = ?')
                params.append(postal[:16])
            if city and _empty(ent.get('ville')):
                updates.append('ville = ?')
                params.append(city[:120])
            if not updates:
                return
            params.append(int(entreprise_id))
            self.execute_sql(
                cursor,
                f'UPDATE entreprises SET {", ".join(updates)} WHERE id = ?',
                tuple(params),
            )
            conn.commit()
        finally:
            conn.close()


def _parse_fb_count(raw: Any) -> int | None:
    """Parse '1 234', '1,2 k', '864' en entier."""
    text = str(raw or '').strip().lower().replace('\u00a0', ' ')
    if not text:
        return None
    match = re.search(r'([\d]+(?:[.,]\d+)?)\s*([km])?', text.replace(' ', ''))
    if not match:
        digits = re.sub(r'\D', '', text)
        return int(digits) if digits else None
    number = float(match.group(1).replace(',', '.'))
    suffix = match.group(2) or ''
    if suffix == 'k':
        number *= 1000
    elif suffix == 'm':
        number *= 1000000
    return int(number)


def _page_columns_from_scrape(
    scrape: dict[str, Any] | None,
    page_name: str | None,
    match_score: Any,
) -> dict[str, Any]:
    """Mappe un scrape Playwright vers les colonnes facebook_prospection_pages."""
    data = scrape if isinstance(scrape, dict) else {}
    street, postal, city = _split_french_address(str(data.get('address') or ''))
    rating_raw = data.get('rating')
    rating_val = None
    if rating_raw not in (None, ''):
        try:
            rating_val = float(str(rating_raw).replace(',', '.').split()[0])
        except (TypeError, ValueError):
            rating_val = None
    score_val = None
    if match_score not in (None, ''):
        try:
            score_val = float(match_score)
        except (TypeError, ValueError):
            score_val = None
    return {
        'page_name': (data.get('title') or page_name or None),
        'category': (str(data.get('category') or '').strip()[:160] or None),
        'likes_text': (str(data.get('likes') or '').strip()[:80] or None),
        'likes_count': _parse_fb_count(data.get('likes')),
        'followers_text': (str(data.get('followers') or '').strip()[:80] or None),
        'followers_count': _parse_fb_count(data.get('followers')),
        'rating': rating_val,
        'intro': (str(data.get('intro') or '').strip()[:1000] or None),
        'about_text': (str(data.get('about_preview') or '').strip()[:4000] or None),
        'hours_text': (str(data.get('hours') or '').strip()[:200] or None),
        'address_1': street[:500] or None,
        'code_postal': postal or None,
        'ville': city[:120] or None,
        'match_score': score_val,
        'username': (str(data.get('username') or '').strip()[:120] or None),
        'fb_page_id': (str(data.get('fb_page_id') or '').strip()[:40] or None),
        'cover_url': (str(data.get('cover_url') or '').strip()[:1000] or None),
        'logo_url': (str(data.get('logo_url') or '').strip()[:1000] or None),
        'reviews_count': _parse_fb_count(data.get('reviews_count')),
        'creation_text': (str(data.get('creation_text') or '').strip()[:200] or None),
        'price_range': (str(data.get('price_range') or '').strip()[:80] or None),
    }


def _split_french_address(address: str) -> tuple[str, str, str]:
    """Decoupe '12 rue X, 57000 Metz' en rue / CP / ville."""
    text = (address or '').strip()
    if not text:
        return '', '', ''
    match = re.search(r'^(.*?)[,\s]+(\d{5})\s+([A-Za-zÀ-ÿ\'\- ]{2,80})$', text)
    if match:
        return match.group(1).strip(' ,'), match.group(2), match.group(3).strip()
    return text, '', ''
