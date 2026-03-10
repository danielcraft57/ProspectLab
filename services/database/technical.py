"""
Module de gestion des analyses techniques
Contient toutes les méthodes liées aux analyses techniques
"""

import json
import logging
import re
from datetime import datetime
from .base import DatabaseBase

logger = logging.getLogger(__name__)


class TechnicalManager(DatabaseBase):
    """
    Gère toutes les opérations sur les analyses techniques
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module technical"""
        super().__init__(*args, **kwargs)

    def _compute_obsolescence_indicators(self, tech_data, url):
        """
        Détermine les signaux d'obsolescence de la stack à partir des données techniques.
        
        Returns:
            tuple[list[str], bool]: (liste d'indicateurs, fort_potentiel_refonte)
        """
        indicators = []
        data = tech_data or {}

        def _parse_version(value):
            if not value:
                return None
            try:
                match = re.search(r'(\d+(?:\.\d+)*)', str(value))
                if not match:
                    return None
                parts = match.group(1).split('.')
                major = int(parts[0]) if parts else 0
                minor = int(parts[1]) if len(parts) > 1 else 0
                patch = int(parts[2]) if len(parts) > 2 else 0
                return major, minor, patch
            except Exception:
                return None

        # 1) CMS très ancien (focus WordPress)
        cms = data.get('cms')
        cms_version = data.get('cms_version')
        if isinstance(cms, str) and cms.lower() == 'wordpress':
            v = _parse_version(cms_version)
            if v:
                major, minor, _ = v
                # WordPress 4.x ou moins considéré comme très ancien
                if major <= 4:
                    indicators.append('wordpress_ancien')
                elif major == 5 and minor < 5:
                    indicators.append('wordpress_a_mettre_a_jour')

        # 2) Bootstrap 3 et jQuery anciens
        css_framework = data.get('css_framework') or ''
        js_library = data.get('js_library') or ''

        if isinstance(css_framework, str) and 'bootstrap' in css_framework.lower():
            v = _parse_version(css_framework)
            if v:
                major, _, _ = v
                if major <= 3:
                    indicators.append('bootstrap_ancien')

        if isinstance(js_library, str) and 'jquery' in js_library.lower():
            v = _parse_version(js_library)
            if v:
                major, minor, _ = v
                if major < 3 or (major == 3 and minor < 5):
                    indicators.append('jquery_lourd')

        # 3) HTTP uniquement / HTTPS mal configuré
        ssl_valid = data.get('ssl_valid')
        mixed_content = data.get('mixed_content_detected')

        if isinstance(url, str) and url.startswith('http://'):
            indicators.append('http_sans_https')
        if ssl_valid is False and 'http_sans_https' not in indicators:
            indicators.append('http_sans_https')
        if mixed_content:
            indicators.append('https_mixed_content')

        # 4) Domaine très ancien et peu mis à jour
        creation = data.get('domain_creation_date')
        updated = data.get('domain_updated_date')

        def _parse_date(value):
            if not value or not isinstance(value, str):
                return None
            candidates = [
                '%Y-%m-%d',
                '%Y-%m-%d %H:%M:%S',
                '%d-%m-%Y',
                '%Y/%m/%d',
            ]
            for fmt in candidates:
                try:
                    return datetime.strptime(value[:19], fmt)
                except Exception:
                    continue
            return None

        creation_dt = _parse_date(creation)
        updated_dt = _parse_date(updated)
        if creation_dt:
            try:
                if creation_dt.year <= 2014:
                    if not updated_dt or updated_dt.year <= 2018:
                        indicators.append('domaine_tres_ancien')
            except Exception:
                pass

        # 5) Scores globaux faibles (sécurité / performance)
        security_score = data.get('security_score')
        performance_score = data.get('performance_score')
        if isinstance(security_score, (int, float)) and security_score < 40:
            indicators.append('securite_faible')
        if isinstance(performance_score, (int, float)) and performance_score < 40:
            indicators.append('performance_faible')

        strong_signals = {
            'wordpress_ancien',
            'bootstrap_ancien',
            'jquery_lourd',
            'http_sans_https',
            'https_mixed_content',
            'domaine_tres_ancien',
        }
        has_strong = any(sig in indicators for sig in strong_signals)

        low_scores = 0
        if isinstance(security_score, (int, float)) and security_score < 50:
            low_scores += 1
        if isinstance(performance_score, (int, float)) and performance_score < 50:
            low_scores += 1
        has_refonte_potential = has_strong or (low_scores >= 2)

        # Enrichir les données brutes pour exploitation ultérieure
        if tech_data is not None:
            tech_data.setdefault('obsolescence', {})
            tech_data['obsolescence']['indicators'] = indicators
            tech_data['obsolescence']['fort_potentiel_refonte'] = has_refonte_potential

        return indicators, has_refonte_potential

    def _update_entreprise_obsolescence_tags(self, cursor, entreprise_id, indicators, has_refonte_potential):
        """
        Met à jour les tags d'une entreprise en fonction des signaux d'obsolescence.
        Ajoute / retire le tag fort_potentiel_refonte de manière idempotente.
        """
        if not entreprise_id:
            return
        try:
            self.execute_sql(cursor, 'SELECT tags FROM entreprises WHERE id = ?', (entreprise_id,))
            row = cursor.fetchone()
            raw_tags = None
            if row is not None:
                if isinstance(row, dict):
                    raw_tags = row.get('tags')
                else:
                    raw_tags = row[0]
            tags = []
            if raw_tags:
                try:
                    tags = json.loads(raw_tags) if isinstance(raw_tags, str) else list(raw_tags)
                except Exception:
                    tags = []
            if not isinstance(tags, list):
                tags = []

            tag_refonte = 'fort_potentiel_refonte'
            if has_refonte_potential:
                if tag_refonte not in tags:
                    tags.append(tag_refonte)
            else:
                tags = [t for t in tags if t != tag_refonte]

            # Dé-doublonnage tout en conservant l'ordre
            seen = set()
            deduped = []
            for t in tags:
                if t not in seen:
                    seen.add(t)
                    deduped.append(t)
            tags = deduped

            self.execute_sql(
                cursor,
                'UPDATE entreprises SET tags = ? WHERE id = ?',
                (json.dumps(tags) if tags else None, entreprise_id)
            )
        except Exception as e:
            logger.warning(f"Erreur lors de la mise à jour des tags d'obsolescence pour entreprise {entreprise_id}: {e}")
    
    def save_technical_analysis(self, entreprise_id, url, tech_data):
        """
        Sauvegarde une analyse technique avec normalisation des données
        
        Args:
            entreprise_id: ID de l'entreprise
            url: URL analysée
            tech_data: Dictionnaire avec les données techniques
        
        Returns:
            int: ID de l'analyse créée
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Extraire le domaine de l'URL
        domain = url.replace('http://', '').replace('https://', '').split('/')[0].replace('www.', '')
        
        pages_summary = tech_data.get('pages_summary') or {}
        pages = tech_data.get('pages') or []
        security_score = tech_data.get('security_score')
        performance_score = tech_data.get('performance_score')
        trackers_count = tech_data.get('trackers_count')
        pages_count = tech_data.get('pages_count') or (len(pages) if pages else None)

        # Calculer les signaux d'obsolescence et enrichir les données avant sauvegarde
        indicators, has_refonte_potential = self._compute_obsolescence_indicators(tech_data, url)
        
        # Sauvegarder l'analyse principale
        if self.is_postgresql():
            self.execute_sql(cursor,'''
                INSERT INTO analyses_techniques (
                    entreprise_id, url, domain, ip_address, server_software,
                    framework, framework_version, cms, cms_version, cms_plugins, hosting_provider,
                    domain_creation_date, domain_updated_date, domain_registrar,
                    ssl_valid, ssl_expiry_date, security_headers, waf, cdn, analytics,
                    seo_meta, performance_metrics, nmap_scan, technical_details,
                    pages_count, security_score, performance_score, trackers_count, pages_summary
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                entreprise_id,
                url,
                domain,
                tech_data.get('ip_address'),
                tech_data.get('server_software'),
                tech_data.get('framework'),
                tech_data.get('framework_version'),
                tech_data.get('cms'),
                tech_data.get('cms_version'),
                json.dumps(tech_data.get('cms_plugins', [])) if tech_data.get('cms_plugins') else None,
                tech_data.get('hosting_provider'),
                tech_data.get('domain_creation_date'),
                tech_data.get('domain_updated_date'),
                tech_data.get('domain_registrar'),
                tech_data.get('ssl_valid'),
                tech_data.get('ssl_expiry_date'),
                json.dumps(tech_data.get('security_headers', {})) if tech_data.get('security_headers') else None,
                tech_data.get('waf'),
                tech_data.get('cdn'),
                json.dumps(tech_data.get('analytics', {})) if tech_data.get('analytics') else None,
                json.dumps(tech_data.get('seo_meta', {})) if tech_data.get('seo_meta') else None,
                json.dumps(tech_data.get('performance_metrics', {})) if tech_data.get('performance_metrics') else None,
                json.dumps(tech_data.get('nmap_scan', {})) if tech_data.get('nmap_scan') else None,
                json.dumps(tech_data) if tech_data else None,
                pages_count,
                security_score,
                performance_score,
                trackers_count,
                json.dumps(pages_summary) if pages_summary else None
            ))
            result = cursor.fetchone()
            analysis_id = result['id'] if result else None
        else:
            self.execute_sql(cursor,'''
                INSERT INTO analyses_techniques (
                    entreprise_id, url, domain, ip_address, server_software,
                    framework, framework_version, cms, cms_version, cms_plugins, hosting_provider,
                    domain_creation_date, domain_updated_date, domain_registrar,
                    ssl_valid, ssl_expiry_date, security_headers, waf, cdn, analytics,
                    seo_meta, performance_metrics, nmap_scan, technical_details,
                    pages_count, security_score, performance_score, trackers_count, pages_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entreprise_id,
                url,
                domain,
                tech_data.get('ip_address'),
                tech_data.get('server_software'),
                tech_data.get('framework'),
                tech_data.get('framework_version'),
                tech_data.get('cms'),
                tech_data.get('cms_version'),
                json.dumps(tech_data.get('cms_plugins', [])) if tech_data.get('cms_plugins') else None,
                tech_data.get('hosting_provider'),
                tech_data.get('domain_creation_date'),
                tech_data.get('domain_updated_date'),
                tech_data.get('domain_registrar'),
                tech_data.get('ssl_valid'),
                tech_data.get('ssl_expiry_date'),
                json.dumps(tech_data.get('security_headers', {})) if tech_data.get('security_headers') else None,
                tech_data.get('waf'),
                tech_data.get('cdn'),
                json.dumps(tech_data.get('analytics', {})) if tech_data.get('analytics') else None,
                json.dumps(tech_data.get('seo_meta', {})) if tech_data.get('seo_meta') else None,
                json.dumps(tech_data.get('performance_metrics', {})) if tech_data.get('performance_metrics') else None,
                json.dumps(tech_data.get('nmap_scan', {})) if tech_data.get('nmap_scan') else None,
                json.dumps(tech_data) if tech_data else None,
                pages_count,
                security_score,
                performance_score,
                trackers_count,
                json.dumps(pages_summary) if pages_summary else None
            ))
            analysis_id = cursor.lastrowid
        
        # Mettre à jour le résumé de l'entreprise pour la segmentation (si entreprise connue)
        if entreprise_id:
            try:
                cms_value = tech_data.get('cms')
                framework_value = tech_data.get('framework')
                perf_value = performance_score

                # Détection simple des comportements / contenu à partir du résumé de pages
                has_blog = False
                has_form = False
                has_checkout = False

                # Utiliser pages_summary si disponible
                if isinstance(pages_summary, dict):
                    pages_meta = pages_summary.get('pages') or pages_summary
                else:
                    pages_meta = {}

                def safe_lower(s):
                    return str(s or '').lower()

                # Parcourir quelques URLs/titres pour inférer blog / formulaire / tunnel
                candidates = []
                if isinstance(pages, list):
                    candidates = pages[:20]
                if isinstance(pages_meta, dict):
                    # pages_summary peut contenir un dict {url: {...}}
                    for k, v in list(pages_meta.items())[:20]:
                        candidates.append({'url': k, **(v if isinstance(v, dict) else {})})

                for p in candidates:
                    url_p = safe_lower(p.get('page_url') or p.get('url'))
                    title_p = safe_lower(p.get('title') or '')
                    # Blog
                    if any(x in url_p for x in ['/blog', '/actualites', '/actus']) or 'blog' in title_p:
                        has_blog = True
                    # Formulaire de contact
                    if any(x in url_p for x in ['/contact', '/contactez-nous']) or 'contact' in title_p:
                        has_form = True
                    # Tunnel e‑commerce (cart/checkout)
                    if any(x in url_p for x in ['/panier', '/cart', '/checkout', '/commande']):
                        has_checkout = True

                # Mettre à jour les colonnes de résumé de l'entreprise
                self.execute_sql(
                    cursor,
                    '''
                    UPDATE entreprises
                    SET cms = COALESCE(?, cms),
                        framework = COALESCE(?, framework),
                        has_blog = COALESCE(?, has_blog),
                        has_contact_form = COALESCE(?, has_contact_form),
                        has_checkout = COALESCE(?, has_checkout),
                        performance_score = COALESCE(?, performance_score)
                    WHERE id = ?
                    ''',
                    (
                        cms_value,
                        framework_value,
                        int(has_blog) if has_blog else None,
                        int(has_form) if has_form else None,
                        int(has_checkout) if has_checkout else None,
                        int(perf_value) if isinstance(perf_value, (int, float)) else None,
                        entreprise_id,
                    ),
                )
            except Exception as e:
                logger.warning(f"Erreur lors de la mise à jour du résumé technique pour entreprise {entreprise_id}: {e}")

        # Sauvegarder les plugins CMS dans la table normalisée
        cms_plugins = tech_data.get('cms_plugins', [])
        if cms_plugins:
            if isinstance(cms_plugins, str):
                try:
                    cms_plugins = json.loads(cms_plugins)
                except:
                    cms_plugins = []
            if isinstance(cms_plugins, list):
                for plugin in cms_plugins:
                    if isinstance(plugin, dict):
                        plugin_name = plugin.get('name') or plugin.get('plugin') or str(plugin)
                        plugin_version = plugin.get('version')
                    else:
                        plugin_name = str(plugin)
                        plugin_version = None
                    if plugin_name:
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_technique_cms_plugins (analysis_id, plugin_name, version)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (analysis_id, plugin_name) DO NOTHING
                            ''', (analysis_id, plugin_name, plugin_version))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_technique_cms_plugins (analysis_id, plugin_name, version)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, plugin_name, plugin_version))
        
        # Sauvegarder les headers de sécurité dans la table normalisée
        # L'analyse technique met les security_headers dans chaque page, pas à la racine : les agréger si besoin
        security_headers = tech_data.get('security_headers') or {}
        if not security_headers and pages:
            for p in pages:
                ph = p.get('security_headers') if isinstance(p, dict) else None
                if ph and isinstance(ph, dict):
                    security_headers.update(ph)
                    break
        if security_headers:
            if isinstance(security_headers, str):
                try:
                    security_headers = json.loads(security_headers)
                except:
                    security_headers = {}
            if isinstance(security_headers, dict):
                for header_name, header_data in security_headers.items():
                    if isinstance(header_data, dict):
                        header_value = header_data.get('value') or header_data.get('header')
                        status = header_data.get('status') or header_data.get('present')
                    else:
                        header_value = str(header_data) if header_data else None
                        status = 'present' if header_data else None
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (analysis_id, header_name) DO UPDATE SET
                                header_value = EXCLUDED.header_value,
                                status = EXCLUDED.status
                        ''', (analysis_id, header_name, header_value, status))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT OR REPLACE INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (?, ?, ?, ?)
                        ''', (analysis_id, header_name, header_value, status))
                else:
                    # Cas de secours : utiliser la syntaxe compatible
                    try:
                        # Essayer d'abord INSERT ... ON CONFLICT (PostgreSQL)
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (analysis_id, header_name) DO UPDATE SET
                                header_value = EXCLUDED.header_value,
                                status = EXCLUDED.status
                        ''', (analysis_id, header_name, header_value, status))
                    except:
                        # Fallback vers INSERT OR REPLACE (SQLite)
                        self.execute_sql(cursor,'''
                            INSERT OR REPLACE INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (?, ?, ?, ?)
                        ''', (analysis_id, header_name, header_value, status))
        
        # Sauvegarder les outils d'analytics dans la table normalisée
        analytics = tech_data.get('analytics', [])
        if analytics:
            if isinstance(analytics, str):
                try:
                    analytics = json.loads(analytics)
                except:
                    analytics = []
            if isinstance(analytics, list):
                for tool in analytics:
                    if isinstance(tool, dict):
                        tool_name = tool.get('name') or tool.get('tool') or str(tool)
                        tool_id = tool.get('id') or tool.get('tracking_id')
                    else:
                        tool_name = str(tool)
                        tool_id = None
                    if tool_name:
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_technique_analytics (analysis_id, tool_name, tool_id)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (analysis_id, tool_name) DO NOTHING
                            ''', (analysis_id, tool_name, tool_id))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_technique_analytics (analysis_id, tool_name, tool_id)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, tool_name, tool_id))
        
        # Sauvegarder les pages analysées (multi-pages)
        if pages:
            logger.info(f'Sauvegarde de {len(pages)} page(s) pour l\'analyse technique {analysis_id}')
            for page in pages:
                try:
                    page_url = page.get('url') or page.get('page_url')
                    if not page_url:
                        logger.warning(f'Page sans URL ignorée: {page}')
                        continue
                    self.execute_sql(cursor,'''
                        INSERT INTO analysis_technique_pages (
                            analysis_id, page_url, status_code, final_url, content_type,
                            title, response_time_ms, content_length, security_score,
                            performance_score, trackers_count, security_headers, analytics, details
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        analysis_id,
                        page_url,
                        page.get('status_code'),
                        page.get('final_url'),
                        page.get('content_type'),
                        page.get('title'),
                        page.get('response_time_ms'),
                        page.get('content_length'),
                        page.get('security_score'),
                        page.get('performance_score'),
                        page.get('trackers_count'),
                        json.dumps(page.get('security_headers')) if page.get('security_headers') else None,
                        json.dumps(page.get('analytics')) if page.get('analytics') else None,
                        json.dumps(page) if page else None
                    ))
                except Exception as e:
                    logger.error(f'Erreur lors de la sauvegarde d\'une page pour l\'analyse {analysis_id}: {e}', exc_info=True)
        else:
            logger.warning(f'Aucune page à sauvegarder pour l\'analyse technique {analysis_id} (pages={pages})')
        
        # Mettre à jour la fiche entreprise avec le score de sécurité global si présent
        if entreprise_id and security_score is not None:
            try:
                self.execute_sql(cursor,
                    'UPDATE entreprises SET score_securite = ? WHERE id = ?',
                    (security_score, entreprise_id)
                )
            except Exception:
                pass

        # Mettre à jour les tags d'obsolescence liés à la refonte potentielle
        if entreprise_id:
            self._update_entreprise_obsolescence_tags(cursor, entreprise_id, indicators, has_refonte_potential)
        
        conn.commit()
        conn.close()
        
        return analysis_id
    
    def _load_technical_analysis_normalized_data(self, cursor, analysis_id):
        """
        Charge les données normalisées d'une analyse technique
        
        Args:
            cursor: Curseur SQLite
            analysis_id: ID de l'analyse
        
        Returns:
            dict: Dictionnaire avec toutes les données normalisées
        """
        # Charger les plugins CMS
        self.execute_sql(cursor,'''
            SELECT plugin_name, version FROM analysis_technique_cms_plugins
            WHERE analysis_id = ?
        ''', (analysis_id,))
        plugins = []
        for plugin_row in cursor.fetchall():
            plugin = {'name': plugin_row['plugin_name']}
            if plugin_row['version']:
                plugin['version'] = plugin_row['version']
            plugins.append(plugin)
        
        # Charger les headers de sécurité
        self.execute_sql(cursor,'''
            SELECT header_name, header_value, status FROM analysis_technique_security_headers
            WHERE analysis_id = ?
        ''', (analysis_id,))
        headers = {}
        for header_row in cursor.fetchall():
            headers[header_row['header_name']] = {
                'value': header_row['header_value'],
                'status': header_row['status']
            }
        
        # Charger les outils d'analytics
        self.execute_sql(cursor,'''
            SELECT tool_name, tool_id FROM analysis_technique_analytics
            WHERE analysis_id = ?
        ''', (analysis_id,))
        analytics = []
        for analytics_row in cursor.fetchall():
            tool = {'name': analytics_row['tool_name']}
            if analytics_row['tool_id']:
                tool['id'] = analytics_row['tool_id']
            analytics.append(tool)
        
        # Charger les pages analysées (multi-pages)
        self.execute_sql(cursor,'''
            SELECT * FROM analysis_technique_pages
            WHERE analysis_id = ?
            ORDER BY id ASC
        ''', (analysis_id,))
        pages = []
        for page_row in cursor.fetchall():
            page_data = dict(page_row)
            for json_field in ['security_headers', 'analytics', 'details']:
                if page_data.get(json_field):
                    try:
                        page_data[json_field] = json.loads(page_data[json_field])
                    except Exception:
                        pass
            pages.append(page_data)
        
        return {
            'cms_plugins': plugins,
            'security_headers': headers,
            'analytics': analytics,
            'pages': pages
        }
    
    def get_technical_analysis(self, entreprise_id):
        """
        Récupère l'analyse technique d'une entreprise avec données normalisées
        
        Args:
            entreprise_id: ID de l'entreprise
        
        Returns:
            dict: Analyse technique ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT * FROM analyses_techniques
            WHERE entreprise_id = ?
            ORDER BY date_analyse DESC
            LIMIT 1
        ''', (entreprise_id,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_technical_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details', 'pages_summary']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_technical_analysis_by_id(self, analysis_id):
        """
        Récupère une analyse technique par son ID avec données normalisées
        
        Args:
            analysis_id: ID de l'analyse
        
        Returns:
            dict: Analyse technique ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT at.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_techniques at
            LEFT JOIN entreprises e ON at.entreprise_id = e.id
            WHERE at.id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_technical_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details', 'pages_summary']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_technical_analysis_by_url(self, url):
        """
        Récupère une analyse technique par son URL avec données normalisées
        
        Args:
            url: URL analysée
        
        Returns:
            dict: Analyse technique ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT at.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_techniques at
            LEFT JOIN entreprises e ON at.entreprise_id = e.id
            WHERE at.url = ?
            ORDER BY at.date_analyse DESC
            LIMIT 1
        ''', (url,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_technical_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details', 'pages_summary']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def update_technical_analysis(self, analysis_id, tech_data):
        """
        Met à jour une analyse technique avec normalisation
        
        Args:
            analysis_id: ID de l'analyse
            tech_data: Nouvelles données techniques
        
        Returns:
            int: ID de l'analyse
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        pages_summary = tech_data.get('pages_summary') or {}
        pages = tech_data.get('pages') or []
        security_score = tech_data.get('security_score')
        performance_score = tech_data.get('performance_score')
        trackers_count = tech_data.get('trackers_count')
        pages_count = tech_data.get('pages_count') or (len(pages) if pages else None)
        
        # Récupérer entreprise_id + url existants
        self.execute_sql(cursor,'SELECT entreprise_id, url FROM analyses_techniques WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            return analysis_id
        
        entreprise_id = row['entreprise_id']
        url = row['url'] or tech_data.get('url', '')
        
        # Mettre à jour la ligne principale
        domain = url.replace('http://', '').replace('https://', '').split('/')[0].replace('www.', '')
        self.execute_sql(cursor,'''
            UPDATE analyses_techniques
            SET url = ?,
                domain = ?,
                ip_address = ?,
                server_software = ?,
                framework = ?,
                framework_version = ?,
                cms = ?,
                cms_version = ?,
                hosting_provider = ?,
                domain_creation_date = ?,
                domain_updated_date = ?,
                domain_registrar = ?,
                ssl_valid = ?,
                ssl_expiry_date = ?,
                waf = ?,
                cdn = ?,
                seo_meta = ?,
                performance_metrics = ?,
                nmap_scan = ?,
                technical_details = ?,
                pages_count = ?,
                security_score = ?,
                performance_score = ?,
                trackers_count = ?,
                pages_summary = ?,
                date_analyse = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            url,
            domain,
            tech_data.get('ip_address'),
            tech_data.get('server_software'),
            tech_data.get('framework'),
            tech_data.get('framework_version'),
            tech_data.get('cms'),
            tech_data.get('cms_version'),
            tech_data.get('hosting_provider'),
            tech_data.get('domain_creation_date'),
            tech_data.get('domain_updated_date'),
            tech_data.get('domain_registrar'),
            tech_data.get('ssl_valid'),
            tech_data.get('ssl_expiry_date'),
            tech_data.get('waf'),
            tech_data.get('cdn'),
            json.dumps(tech_data.get('seo_meta', {})) if tech_data.get('seo_meta') else None,
            json.dumps(tech_data.get('performance_metrics', {})) if tech_data.get('performance_metrics') else None,
            json.dumps(tech_data.get('nmap_scan', {})) if tech_data.get('nmap_scan') else None,
            json.dumps(tech_data) if tech_data else None,
            pages_count,
            security_score,
            performance_score,
            trackers_count,
            json.dumps(pages_summary) if pages_summary else None,
            analysis_id
        ))
        
        # Supprimer puis réinsérer les données normalisées
        self.execute_sql(cursor,'DELETE FROM analysis_technique_cms_plugins WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_technique_security_headers WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_technique_analytics WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_technique_pages WHERE analysis_id = ?', (analysis_id,))
        
        # Plugins CMS
        cms_plugins = tech_data.get('cms_plugins', [])
        if cms_plugins:
            if isinstance(cms_plugins, str):
                try:
                    cms_plugins = json.loads(cms_plugins)
                except:
                    cms_plugins = []
            if isinstance(cms_plugins, list):
                for plugin in cms_plugins:
                    if isinstance(plugin, dict):
                        plugin_name = plugin.get('name') or plugin.get('plugin') or str(plugin)
                        plugin_version = plugin.get('version')
                    else:
                        plugin_name = str(plugin)
                        plugin_version = None
                    if plugin_name:
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_technique_cms_plugins (analysis_id, plugin_name, version)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (analysis_id, plugin_name) DO NOTHING
                            ''', (analysis_id, plugin_name, plugin_version))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_technique_cms_plugins (analysis_id, plugin_name, version)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, plugin_name, plugin_version))
        
        # Headers de sécurité
        security_headers = tech_data.get('security_headers', {})
        if security_headers:
            if isinstance(security_headers, str):
                try:
                    security_headers = json.loads(security_headers)
                except:
                    security_headers = {}
            if isinstance(security_headers, dict):
                for header_name, header_data in security_headers.items():
                    if isinstance(header_data, dict):
                        header_value = header_data.get('value') or header_data.get('header')
                        status = header_data.get('status') or header_data.get('present')
                    else:
                        header_value = str(header_data) if header_data else None
                        status = 'present' if header_data else None
                    if self.is_postgresql():
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (analysis_id, header_name) DO UPDATE SET
                                header_value = EXCLUDED.header_value,
                                status = EXCLUDED.status
                        ''', (analysis_id, header_name, header_value, status))
                    else:
                        self.execute_sql(cursor,'''
                            INSERT OR REPLACE INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (?, ?, ?, ?)
                        ''', (analysis_id, header_name, header_value, status))
                else:
                    # Cas de secours : utiliser la syntaxe compatible
                    try:
                        # Essayer d'abord INSERT ... ON CONFLICT (PostgreSQL)
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (analysis_id, header_name) DO UPDATE SET
                                header_value = EXCLUDED.header_value,
                                status = EXCLUDED.status
                        ''', (analysis_id, header_name, header_value, status))
                    except:
                        # Fallback vers INSERT OR REPLACE (SQLite)
                        self.execute_sql(cursor,'''
                            INSERT OR REPLACE INTO analysis_technique_security_headers (analysis_id, header_name, header_value, status)
                            VALUES (?, ?, ?, ?)
                        ''', (analysis_id, header_name, header_value, status))
        
        # Analytics
        analytics = tech_data.get('analytics', [])
        if analytics:
            if isinstance(analytics, str):
                try:
                    analytics = json.loads(analytics)
                except:
                    analytics = []
            if isinstance(analytics, list):
                for tool in analytics:
                    if isinstance(tool, dict):
                        tool_name = tool.get('name') or tool.get('tool') or str(tool)
                        tool_id = tool.get('id') or tool.get('tracking_id')
                    else:
                        tool_name = str(tool)
                        tool_id = None
                    if tool_name:
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_technique_analytics (analysis_id, tool_name, tool_id)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (analysis_id, tool_name) DO NOTHING
                            ''', (analysis_id, tool_name, tool_id))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_technique_analytics (analysis_id, tool_name, tool_id)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, tool_name, tool_id))
        
        # Pages multi-analysées
        if pages:
            for page in pages:
                self.execute_sql(cursor,'''
                    INSERT INTO analysis_technique_pages (
                        analysis_id, page_url, status_code, final_url, content_type,
                        title, response_time_ms, content_length, security_score,
                        performance_score, trackers_count, security_headers, analytics, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis_id,
                    page.get('url') or page.get('page_url'),
                    page.get('status_code'),
                    page.get('final_url'),
                    page.get('content_type'),
                    page.get('title'),
                    page.get('response_time_ms'),
                    page.get('content_length'),
                    page.get('security_score'),
                    page.get('performance_score'),
                    page.get('trackers_count'),
                    json.dumps(page.get('security_headers')) if page.get('security_headers') else None,
                    json.dumps(page.get('analytics')) if page.get('analytics') else None,
                    json.dumps(page) if page else None
                ))
        
        # Mettre à jour la fiche entreprise avec le score global
        if security_score is not None and entreprise_id:
            try:
                self.execute_sql(cursor,
                    'UPDATE entreprises SET score_securite = ? WHERE id = ?',
                    (security_score, entreprise_id)
                )
            except Exception:
                pass

        # Recalculer les signaux d'obsolescence et les tags associés
        if entreprise_id:
            indicators, has_refonte_potential = self._compute_obsolescence_indicators(tech_data, url)
            self._update_entreprise_obsolescence_tags(cursor, entreprise_id, indicators, has_refonte_potential)
        
        conn.commit()
        conn.close()
        
        # Recalculer l'opportunité après l'analyse technique
        if entreprise_id:
            try:
                from services.database.entreprises import EntrepriseManager
                entreprise_manager = EntrepriseManager()
                entreprise_manager.update_opportunity_score(entreprise_id)
            except Exception as e:
                logger.warning(f'Erreur lors du recalcul de l\'opportunité après analyse technique: {e}')
        
        return analysis_id
    
    def get_all_technical_analyses(self, limit=100):
        """
        Récupère toutes les analyses techniques avec données normalisées
        
        Args:
            limit: Nombre maximum d'analyses à retourner
        
        Returns:
            list: Liste des analyses techniques
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT at.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_techniques at
            LEFT JOIN entreprises e ON at.entreprise_id = e.id
            ORDER BY at.date_analyse DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        
        analyses = []
        for row in rows:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_technical_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details', 'pages_summary']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            analyses.append(analysis)
        
        conn.close()
        return analyses
    
    def delete_technical_analysis(self, analysis_id):
        """
        Supprime une analyse technique
        
        Args:
            analysis_id: ID de l'analyse à supprimer
        
        Returns:
            bool: True si supprimée, False sinon
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'DELETE FROM analyses_techniques WHERE id = ?', (analysis_id,))
        
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted
