"""
Module de gestion des analyses UX (corpus @clea_ux).
"""

from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

from .base import DatabaseBase

logger = logging.getLogger(__name__)


class UXManager(DatabaseBase):
    """
    Persistance des analyses UX (scores, findings, résultats d'outils).
    """

    def __init__(self, *args, **kwargs):
        """Initialise le module UX."""
        super().__init__(*args, **kwargs)

    def save_ux_analysis(self, entreprise_id, url, ux_data):
        """
        Sauvegarde une analyse UX.

        @param entreprise_id: ID entreprise (optionnel).
        @param url: URL analysée.
        @param ux_data: Dict résultat UXAnalyzer.analyze_ux.
        @returns: ID de l'analyse créée.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain_clean = domain.replace('www.', '') if domain else ''

        findings = ux_data.get('findings') or ux_data.get('issues') or []
        summary = ux_data.get('summary') or {}
        tools_results = ux_data.get('tools_results') or {}
        corpus = ux_data.get('corpus') or {}
        score = ux_data.get('score', 0)

        if self.is_postgresql():
            self.execute_sql(cursor, '''
                INSERT INTO analyses_ux (
                    entreprise_id, url, domain, score,
                    findings_json, tools_json, corpus_json,
                    summary_json, ux_details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                entreprise_id,
                url,
                domain_clean,
                score,
                json.dumps(findings, ensure_ascii=False),
                json.dumps(tools_results, ensure_ascii=False),
                json.dumps(corpus, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False),
                json.dumps(ux_data, ensure_ascii=False, default=str),
            ))
            result = cursor.fetchone()
            analysis_id = result['id'] if result else None
        else:
            self.execute_sql(cursor, '''
                INSERT INTO analyses_ux (
                    entreprise_id, url, domain, score,
                    findings_json, tools_json, corpus_json,
                    summary_json, ux_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entreprise_id,
                url,
                domain_clean,
                score,
                json.dumps(findings, ensure_ascii=False),
                json.dumps(tools_results, ensure_ascii=False),
                json.dumps(corpus, ensure_ascii=False),
                json.dumps(summary, ensure_ascii=False),
                json.dumps(ux_data, ensure_ascii=False, default=str),
            ))
            analysis_id = cursor.lastrowid

        for finding in findings:
            if not isinstance(finding, dict):
                continue
            self.execute_sql(cursor, '''
                INSERT INTO analysis_ux_findings (
                    analysis_id, tool_name, chapter, severity,
                    title, message, recommendation, score_delta, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                analysis_id,
                finding.get('tool'),
                finding.get('chapter'),
                finding.get('severity'),
                finding.get('title'),
                finding.get('message'),
                finding.get('recommendation'),
                finding.get('score_delta'),
                json.dumps(finding.get('evidence') or {}, ensure_ascii=False),
            ))

        if entreprise_id and analysis_id:
            try:
                self.record_metric_snapshot(
                    cursor,
                    entreprise_id,
                    'ux',
                    analysis_id,
                    {
                        'ux_score': score,
                        'domain': domain_clean,
                        'findings_count': len(findings),
                    },
                )
            except Exception as e:
                logger.warning('Snapshot métriques (analyse UX): %s', e)

        conn.commit()
        conn.close()
        logger.info('Analyse UX sauvegardée: id=%s, url=%s', analysis_id, url)
        return analysis_id

    def update_ux_analysis(self, analysis_id, ux_data):
        """
        Met à jour une analyse UX existante.

        @param analysis_id: ID existant.
        @param ux_data: Nouvelles données.
        @returns: analysis_id.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        findings = ux_data.get('findings') or ux_data.get('issues') or []
        summary = ux_data.get('summary') or {}
        tools_results = ux_data.get('tools_results') or {}
        corpus = ux_data.get('corpus') or {}
        score = ux_data.get('score', 0)

        self.execute_sql(cursor, '''
            UPDATE analyses_ux SET
                score = ?,
                findings_json = ?,
                tools_json = ?,
                corpus_json = ?,
                summary_json = ?,
                ux_details = ?,
                date_analyse = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            score,
            json.dumps(findings, ensure_ascii=False),
            json.dumps(tools_results, ensure_ascii=False),
            json.dumps(corpus, ensure_ascii=False),
            json.dumps(summary, ensure_ascii=False),
            json.dumps(ux_data, ensure_ascii=False, default=str),
            analysis_id,
        ))

        self.execute_sql(cursor, 'DELETE FROM analysis_ux_findings WHERE analysis_id = ?', (analysis_id,))
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            self.execute_sql(cursor, '''
                INSERT INTO analysis_ux_findings (
                    analysis_id, tool_name, chapter, severity,
                    title, message, recommendation, score_delta, evidence_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                analysis_id,
                finding.get('tool'),
                finding.get('chapter'),
                finding.get('severity'),
                finding.get('title'),
                finding.get('message'),
                finding.get('recommendation'),
                finding.get('score_delta'),
                json.dumps(finding.get('evidence') or {}, ensure_ascii=False),
            ))

        self.execute_sql(cursor, 'SELECT entreprise_id, domain FROM analyses_ux WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        if row:
            re = dict(row)
            if re.get('entreprise_id'):
                try:
                    self.record_metric_snapshot(
                        cursor,
                        re['entreprise_id'],
                        'ux',
                        analysis_id,
                        {
                            'ux_score': score,
                            'domain': re.get('domain'),
                            'findings_count': len(findings),
                        },
                    )
                except Exception as e:
                    logger.warning('Snapshot métriques (update UX): %s', e)

        conn.commit()
        conn.close()
        return analysis_id

    def get_ux_analysis_by_url(self, url):
        """
        Dernière analyse UX pour une URL.

        @param url: URL recherchée.
        @returns: Dict ou None.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, '''
            SELECT * FROM analyses_ux WHERE url = ? ORDER BY date_analyse DESC LIMIT 1
        ''', (url,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_ux(row) if row else None

    def get_ux_analysis_by_entreprise(self, entreprise_id):
        """
        Dernière analyse UX pour une entreprise.

        @param entreprise_id: ID entreprise.
        @returns: Dict ou None.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, '''
            SELECT * FROM analyses_ux
            WHERE entreprise_id = ?
            ORDER BY date_analyse DESC LIMIT 1
        ''', (entreprise_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_ux(row) if row else None

    def get_ux_analyses_by_entreprise(self, entreprise_id, limit=10):
        """
        Liste des analyses UX d'une entreprise.

        @param entreprise_id: ID entreprise.
        @param limit: Nombre max.
        @returns: Liste de dicts.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, '''
            SELECT * FROM analyses_ux
            WHERE entreprise_id = ?
            ORDER BY date_analyse DESC
            LIMIT ?
        ''', (entreprise_id, limit))
        rows = cursor.fetchall() or []
        conn.close()
        return [self._row_to_ux(r) for r in rows]

    def get_ux_analysis_by_id(self, analysis_id):
        """
        Récupère une analyse UX par ID.

        @param analysis_id: ID de l'analyse.
        @returns: Dict ou None.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, 'SELECT * FROM analyses_ux WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        conn.close()
        return self._row_to_ux(row) if row else None

    def get_all_ux_analyses(self, limit=50):
        """
        Liste toutes les analyses UX récentes.

        @param limit: Nombre maximum.
        @returns: Liste de dicts.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, '''
            SELECT * FROM analyses_ux
            ORDER BY date_analyse DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall() or []
        conn.close()
        return [self._row_to_ux(r) for r in rows]

    def delete_ux_analysis(self, analysis_id):
        """
        Supprime une analyse UX (CASCADE findings).

        @param analysis_id: ID à supprimer.
        @returns: True si ok.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor, 'DELETE FROM analyses_ux WHERE id = ?', (analysis_id,))
        conn.commit()
        conn.close()
        return True

    def _row_to_ux(self, row):
        """
        Normalise une ligne SQL en dict UX.

        @param row: Ligne sqlite/psycopg.
        @returns: Dict avec findings/summary/tools parsés.
        """
        if not row:
            return None
        data = dict(row)

        def _loads(raw):
            if raw is None:
                return None
            if isinstance(raw, (dict, list)):
                return raw
            if isinstance(raw, str) and raw:
                try:
                    return json.loads(raw)
                except json.JSONDecodeError:
                    return None
            return None

        findings = _loads(data.get('findings_json'))
        tools = _loads(data.get('tools_json'))
        corpus = _loads(data.get('corpus_json'))
        summary = _loads(data.get('summary_json'))
        details = _loads(data.get('ux_details'))
        data['findings'] = findings if isinstance(findings, list) else []
        data['tools_results'] = tools if isinstance(tools, dict) else {}
        data['corpus'] = corpus if isinstance(corpus, dict) else {}
        data['summary'] = summary if isinstance(summary, dict) else {}
        if isinstance(details, dict):
            data['ux_details'] = details
        return data
