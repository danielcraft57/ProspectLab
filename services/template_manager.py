"""
Gestionnaire de modèles de messages
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional


class TemplateManager:
    def __init__(self, templates_file=None):
        """
        Initialise le gestionnaire de templates
        
        Args:
            templates_file: Chemin vers le fichier JSON de templates (optionnel)
        """
        if templates_file:
            self.templates_file = Path(templates_file)
        else:
            # Utiliser un fichier par défaut dans le dossier de l'app
            app_dir = Path(__file__).parent.parent
            self.templates_file = app_dir / 'templates_data.json'
        
        # Créer le fichier s'il n'existe pas (copie du fichier par défaut complet si présent)
        if not self.templates_file.exists():
            default_file = self.templates_file.parent / 'templates_data.default.json'
            if default_file.exists():
                import shutil
                shutil.copy(default_file, self.templates_file)
            else:
                self._init_templates_file()
        
        self.templates = self._load_templates()
    
    def _init_templates_file(self):
        """Initialise le fichier de templates (vide). Utilisez scripts/generate_html_templates.py --restore pour charger les modèles HTML."""
        default_templates = {'templates': []}
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(default_templates, f, ensure_ascii=False, indent=2)
    
    def _load_templates(self) -> Dict:
        """Charge les templates depuis le fichier JSON"""
        try:
            with open(self.templates_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('templates', [])
        except Exception as e:
            return []
    
    def _save_templates(self):
        """Sauvegarde les templates dans le fichier JSON"""
        data = {'templates': self.templates}
        with open(self.templates_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def list_templates(self, category=None) -> List[Dict]:
        """
        Liste tous les templates.
        Recharge le fichier à chaque appel pour afficher les modèles ajoutés ou modifiés.
        
        Args:
            category: Filtrer par catégorie (optionnel)
        
        Returns:
            Liste de templates
        """
        self.templates = self._load_templates()
        templates = [dict(t) for t in self.templates]
        
        if category:
            templates = [t for t in templates if t.get('category') == category]
        
        for template in templates:
            if 'content' in template:
                content = template['content']
                if template.get('is_html'):
                    template['preview'] = 'Modèle HTML avec variables dynamiques. {{nom}} = nom du contact ou responsable entreprise si inconnu ; {{entreprise}}, {{email}}, {{responsable}}, blocs conditionnels.'
                else:
                    template['preview'] = content[:100] + '...' if len(content) > 100 else content
        
        return templates
    
    def get_template(self, template_id: str) -> Optional[Dict]:
        """
        Récupère un template par son ID
        
        Args:
            template_id: ID du template
        
        Returns:
            Template ou None
        """
        for template in self.templates:
            if template.get('id') == template_id:
                return template.copy()
        return None
    
    def create_template(self, name: str, subject: str, content: str, category: str = 'cold_email') -> Dict:
        """
        Crée un nouveau template
        
        Args:
            name: Nom du template
            subject: Sujet de l'email
            content: Contenu de l'email (peut contenir {nom}, {entreprise})
            category: Catégorie du template
        
        Returns:
            Template créé
        """
        template_id = f"template_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        template = {
            'id': template_id,
            'name': name,
            'category': category,
            'subject': subject,
            'content': content,
            'is_html': category == 'html_email',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.templates.append(template)
        self._save_templates()
        
        return template
    
    def update_template(self, template_id: str, name: str = None, subject: str = None,
                        content: str = None, category: str = None) -> Optional[Dict]:
        """
        Met à jour un template existant.

        Args:
            template_id: ID du template
            name: Nouveau nom (optionnel)
            subject: Nouveau sujet (optionnel)
            content: Nouveau contenu (optionnel)
            category: Nouvelle catégorie (optionnel) ; si 'html_email', is_html est mis à True.

        Returns:
            Template mis à jour ou None
        """
        for template in self.templates:
            if template.get('id') == template_id:
                if name is not None:
                    template['name'] = name
                if subject is not None:
                    template['subject'] = subject
                if content is not None:
                    template['content'] = content
                if category is not None:
                    template['category'] = category
                    template['is_html'] = category == 'html_email'
                template['updated_at'] = datetime.now().isoformat()
                self._save_templates()
                return template.copy()
        return None
    
    def delete_template(self, template_id: str) -> bool:
        """
        Supprime un template
        
        Args:
            template_id: ID du template
        
        Returns:
            True si supprimé, False sinon
        """
        initial_count = len(self.templates)
        self.templates = [t for t in self.templates if t.get('id') != template_id]
        
        if len(self.templates) < initial_count:
            self._save_templates()
            return True
        
        return False
    
    def _get_entreprise_extended_data(self, entreprise_id: int = None) -> dict:
        """
        Récupère les données étendues d'une entreprise depuis la BDD
        
        Args:
            entreprise_id: ID de l'entreprise (optionnel)
        
        Returns:
            Dict avec toutes les données disponibles (technique, OSINT, pentest, scraping)
        """
        if not entreprise_id:
            return {}
        
        try:
            from services.database import Database
            from services.database.technical import TechnicalManager
            from services.database.osint import OSINTManager
            from services.database.pentest import PentestManager
            from services.database.scrapers import ScraperManager
            
            db = Database()
            tech_manager = TechnicalManager()
            osint_manager = OSINTManager()
            pentest_manager = PentestManager()
            scraper_manager = ScraperManager()
            
            data = {}
            
            # Données de base de l'entreprise
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM entreprises WHERE id = ?', (entreprise_id,))
            entreprise_row = cursor.fetchone()
            if entreprise_row:
                entreprise = dict(entreprise_row)
                data.update({
                    'website': entreprise.get('website', ''),
                    'secteur': entreprise.get('secteur', ''),
                    'framework': entreprise.get('framework', ''),
                    'hosting_provider': entreprise.get('hosting_provider', ''),
                    'responsable': entreprise.get('responsable') or '',
                    'email_principal': entreprise.get('email_principal') or '',
                })
            conn.close()
            
            # Analyse technique
            tech_analysis = tech_manager.get_technical_analysis(entreprise_id)
            if tech_analysis:
                data.update({
                    'framework': tech_analysis.get('framework') or data.get('framework', ''),
                    'framework_version': tech_analysis.get('framework_version', ''),
                    'cms': tech_analysis.get('cms', ''),
                    'cms_version': tech_analysis.get('cms_version', ''),
                    'hosting_provider': tech_analysis.get('hosting_provider') or data.get('hosting_provider', ''),
                    'performance_score': tech_analysis.get('performance_score'),
                    'security_score': tech_analysis.get('security_score'),
                    'server': tech_analysis.get('server_software', ''),
                })
                
                # Exposer quelques infos SEO / sécurité / perf utiles pour les emails
                seo_meta = tech_analysis.get('seo_meta') or tech_analysis.get('technical_details', {}).get('seo_meta', {}) or {}
                technical_details = tech_analysis.get('technical_details', {}) or {}
                performance_metrics = tech_analysis.get('performance_metrics', {}) or {}
                pages_summary = tech_analysis.get('pages_summary', {}) or {}
                security_headers = tech_analysis.get('security_headers', {}) or {}

                # Champs SEO bruts
                if seo_meta:
                    data.update({
                        'meta_title': seo_meta.get('meta_title', ''),
                        'meta_title_length': seo_meta.get('meta_title_length'),
                        'meta_description': seo_meta.get('meta_description', ''),
                        'meta_description_length': seo_meta.get('meta_description_length'),
                        'canonical_url': seo_meta.get('canonical_url', ''),
                        'hreflang': seo_meta.get('hreflang', ''),
                    })

                # Champs techniques complémentaires (robots / sitemap / SSL / mixed content...)
                for key in [
                    'robots_txt_exists',
                    'robots_has_rules',
                    'sitemap_exists',
                    'sitemap_url_count',
                    'mixed_content_detected',
                    'scripts_without_sri',
                    'cookies_count',
                    'cookie_types',
                    'mobile_friendly',
                    'viewport_meta',
                    'html_language',
                ]:
                    if key in technical_details:
                        data[key] = technical_details.get(key)

                # Récupérer quelques agrégats de performance s'ils existent
                if isinstance(pages_summary, dict):
                    for key in ['avg_response_time_ms', 'avg_weight_bytes', 'pages_scanned']:
                        if key in pages_summary:
                            data[key] = pages_summary.get(key)

                # Construire une liste de problèmes SEO lisibles
                seo_issues_list = []
                meta_title = data.get('meta_title') or ''
                meta_title_len = data.get('meta_title_length')
                meta_desc = data.get('meta_description') or ''
                meta_desc_len = data.get('meta_description_length')

                if not meta_title:
                    seo_issues_list.append("Balise titre absente ou vide sur la page principale.")
                elif isinstance(meta_title_len, int) and (meta_title_len < 35 or meta_title_len > 65):
                    seo_issues_list.append("Balise titre trop courte ou trop longue pour un affichage optimal dans Google.")

                if not meta_desc:
                    seo_issues_list.append("Aucune meta description claire pour contrôler le texte affiché dans Google.")
                elif isinstance(meta_desc_len, int) and (meta_desc_len < 70 or meta_desc_len > 170):
                    seo_issues_list.append("Meta description peu optimisée (trop courte ou trop longue).")

                if data.get('robots_txt_exists') is False:
                    seo_issues_list.append("Pas de fichier robots.txt pour guider les moteurs de recherche.")

                if data.get('sitemap_exists') is False:
                    seo_issues_list.append("Aucun sitemap.xml détecté pour aider Google à trouver toutes les pages importantes.")
                elif data.get('sitemap_exists') and isinstance(data.get('sitemap_url_count'), int) and data.get('sitemap_url_count') <= 3:
                    seo_issues_list.append("Sitemap.xml avec très peu de pages déclarées, ce qui limite la visibilité globale du site.")

                if not data.get('canonical_url'):
                    seo_issues_list.append("Pas de lien canonique explicite, ce qui peut créer du contenu dupliqué aux yeux de Google.")

                if data.get('html_language') in (None, '', 'Non spécifié'):
                    seo_issues_list.append("Langue de la page non déclarée dans la balise HTML, ce qui complique la compréhension du site par les moteurs.")

                # Construire une liste de problèmes de sécurité lisibles
                security_issues_list = []

                security_score_val = data.get('security_score')
                ssl_valid = data.get('ssl_valid')

                if ssl_valid is False:
                    security_issues_list.append("Le site n'est pas correctement protégé en HTTPS (problème de certificat ou d'activation SSL).")

                mixed_content = data.get('mixed_content_detected')
                if mixed_content and mixed_content is not False:
                    security_issues_list.append("Certaines ressources du site sont encore chargées en HTTP sur une page HTTPS (contenu mixte).")

                scripts_without_sri = data.get('scripts_without_sri')
                if isinstance(scripts_without_sri, int) and scripts_without_sri > 0:
                    security_issues_list.append("Les scripts tiers ne sont pas protégés par une vérification d'intégrité (SRI).")

                cookies_count = data.get('cookies_count')
                cookie_types = (data.get('cookie_types') or '').lower()
                if isinstance(cookies_count, int) and cookies_count > 0 and 'tracking' in cookie_types:
                    security_issues_list.append("Présence de cookies de suivi sans information claire, à vérifier côté conformité (RGPD).")

                # Manques dans les headers de sécurité importants
                if isinstance(security_headers, dict):
                    normalized_header_keys = {k.lower().replace('_', '-') for k in security_headers.keys()}
                    missing_map = {
                        'strict-transport-security': "Header Strict-Transport-Security manquant (protection incomplète contre les attaques sur HTTP).",
                        'content-security-policy': "Aucune Content-Security-Policy définie (protection limitée contre XSS et injections de scripts).",
                        'x-frame-options': "Header X-Frame-Options absent (site potentiellement intégrable dans des iframes malveillants).",
                        'x-content-type-options': "Header X-Content-Type-Options manquant (risque de détection de type MIME incorrect).",
                        'referrer-policy': "Aucune Referrer-Policy définie (fuite possible d'URLs complètes vers des sites externes).",
                    }
                    for header_key, message in missing_map.items():
                        if header_key not in normalized_header_keys:
                            security_issues_list.append(message)

                # Exposer les listes sous forme de <li>...</li> pour les templates HTML
                if seo_issues_list:
                    data['seo_issues'] = "\n".join(f"<li>{issue}</li>" for issue in seo_issues_list)

                if security_issues_list:
                    data['security_issues'] = "\n".join(f"<li>{issue}</li>" for issue in security_issues_list)
            
            # Analyse OSINT
            osint_analysis = osint_manager.get_osint_analysis_by_entreprise(entreprise_id)
            if osint_analysis:
                data.update({
                    'osint_people_count': len(osint_analysis.get('people', {}).get('enriched', [])),
                    'osint_emails_count': len(osint_analysis.get('emails', [])),
                })
            
            # Analyse Pentest
            pentest_analysis = pentest_manager.get_pentest_analysis_by_entreprise(entreprise_id)
            if pentest_analysis:
                # Utiliser risk_score comme security_score pour Pentest
                risk_score = pentest_analysis.get('risk_score')
                if risk_score is not None:
                    # Convertir risk_score (0-100) en security_score (inversé : 100-risk_score)
                    data['security_score'] = max(0, 100 - risk_score) if risk_score else data.get('security_score')
                vulnerabilities = pentest_analysis.get('vulnerabilities', [])
                if vulnerabilities:
                    data['vulnerabilities_count'] = len(vulnerabilities) if isinstance(vulnerabilities, list) else 0
            
            # Données de scraping (prendre le scraper le plus récent)
            scrapers = scraper_manager.get_scrapers_by_entreprise(entreprise_id)
            if scrapers and len(scrapers) > 0:
                scraper = scrapers[0]  # Le premier est le plus récent (trié par date DESC)
                social_list = scraper.get('total_social_profiles', [])
                data.update({
                    'total_emails': scraper.get('total_emails', 0),
                    'total_people': scraper.get('total_people', 0),
                    'total_phones': scraper.get('total_phones', 0),
                    'total_social': social_list,
                    'total_social_count': len(social_list) if isinstance(social_list, list) else 0,
                    'total_technologies': scraper.get('total_technologies', 0),
                })
            
            return data
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Erreur lors de la récupération des données étendues pour entreprise {entreprise_id}: {e}')
            return {}
    
    def render_template(self, template_id: str, nom: str = '', entreprise: str = '', email: str = '', 
                       entreprise_id: int = None):
        """
        Rend un template avec les variables remplacées
        
        Args:
            template_id: ID du template
            nom: Nom du destinataire
            entreprise: Nom de l'entreprise
            email: Email du destinataire
            entreprise_id: ID de l'entreprise pour récupérer les données étendues (optionnel)
        
        Returns:
            Tuple (contenu rendu, is_html)
        """
        template = self.get_template(template_id)
        if not template:
            return '', False
        
        content = template.get('content', '')
        is_html = template.get('is_html', False)
        
        # Récupérer les données étendues si entreprise_id fourni
        extended_data = {}
        if entreprise_id:
            extended_data = self._get_entreprise_extended_data(entreprise_id)
        
        # Formater le nom : contact > responsable entreprise > Monsieur/Madame
        from utils.name_formatter import format_name
        formatted_nom = format_name(nom) if nom else None
        if not formatted_nom or str(formatted_nom).strip() in ('', 'N/A'):
            formatted_nom = (extended_data.get('responsable') or '').strip() or None
        if not formatted_nom:
            formatted_nom = 'Monsieur/Madame'
        
        # Base URL pour les images (hero.webp, etc.) et liens
        try:
            from config import BASE_URL
            base_url = (BASE_URL or '').rstrip('/') or 'http://localhost:5000'
        except Exception:
            base_url = 'http://localhost:5000'
        
        # Préparer toutes les variables (total_social_count pour condition scraping)
        extended_flat = dict(extended_data)
        if 'total_social' in extended_flat and isinstance(extended_flat.get('total_social'), list):
            extended_flat['total_social_count'] = len(extended_flat['total_social'])
        variables = {
            'nom': formatted_nom,
            'entreprise': entreprise or 'votre entreprise',
            'email': email or '',
            'base_url': base_url,
            **extended_flat
        }
        
        # Remplacer les conditions {#if_xxx} ... {#endif}
        import re
        
        # Gérer les conditions {#if_tech_data} ... {#endif}
        if '{#if_tech_data}' in content:
            has_tech = any(variables.get(k) for k in ['framework', 'cms', 'hosting_provider', 'performance_score'])
            if has_tech:
                # Construire les infos techniques
                tech_items = []
                if variables.get('framework'):
                    tech_items.append(f"<li>Framework détecté : <strong>{variables['framework']}</strong></li>")
                if variables.get('cms'):
                    tech_items.append(f"<li>CMS utilisé : <strong>{variables['cms']}</strong></li>")
                if variables.get('hosting_provider'):
                    tech_items.append(f"<li>Hébergeur : <strong>{variables['hosting_provider']}</strong></li>")
                if variables.get('performance_score'):
                    tech_items.append(f"<li>Score de performance : <strong>{variables['performance_score']}/100</strong></li>")
                variables['framework_info'] = tech_items[0] if len(tech_items) > 0 else ''
                variables['cms_info'] = tech_items[1] if len(tech_items) > 1 else ''
                variables['hosting_info'] = tech_items[2] if len(tech_items) > 2 else ''
                variables['performance_info'] = tech_items[3] if len(tech_items) > 3 else ''
            else:
                # Supprimer le bloc conditionnel
                content = re.sub(r'\{#if_tech_data\}.*?\{#endif\}', '', content, flags=re.DOTALL)
        
        # Gérer {#if_performance}
        if '{#if_performance}' in content:
            has_perf = variables.get('performance_score') is not None
            if not has_perf:
                content = re.sub(r'\{#if_performance\}.*?\{#endif\}', '', content, flags=re.DOTALL)
        
        # Gérer {#if_security}
        if '{#if_security}' in content:
            has_sec = variables.get('security_score') is not None
            if not has_sec:
                content = re.sub(r'\{#if_security\}.*?\{#endif\}', '', content, flags=re.DOTALL)
        
        # Gérer {#if_scraping_data}
        if '{#if_scraping_data}' in content:
            has_scraping = any(variables.get(k, 0) > 0 for k in ['total_emails', 'total_people', 'total_social_count'])
            if has_scraping:
                scraping_items = []
                if variables.get('total_emails', 0) > 0:
                    scraping_items.append(f"<li><strong>{variables['total_emails']}</strong> contacts identifiés sur votre site</li>")
                if variables.get('total_social_count', 0) > 0:
                    scraping_items.append(f"<li>Présence sur <strong>{variables['total_social_count']}</strong> réseau(x) social(aux)</li>")
                if variables.get('website'):
                    scraping_items.append(f"<li>Site web : <strong>{variables['website']}</strong></li>")
                variables['scraping_info'] = '\n'.join(scraping_items)
            else:
                content = re.sub(r'\{#if_scraping_data\}.*?\{#endif\}', '', content, flags=re.DOTALL)
        
        # Gérer {#if_all_data}
        if '{#if_all_data}' in content:
            has_all = any(variables.get(k) for k in ['framework', 'cms', 'performance_score', 'security_score', 'total_emails'])
            if has_all:
                summary_rows = []
                if variables.get('framework') or variables.get('cms'):
                    tech_str = f"{variables.get('framework', '')} • {variables.get('cms', '')}".strip(' • ')
                    summary_rows.append(f'<tr><td style="padding: 10px 0; color: #666666; font-size: 15px; border-bottom: 1px solid #E0E0E0;"><strong style="color: #333333;">Technologies :</strong></td><td style="padding: 10px 0; color: #333333; font-size: 15px; border-bottom: 1px solid #E0E0E0; text-align: right;">{tech_str}</td></tr>')
                if variables.get('performance_score'):
                    summary_rows.append(f'<tr><td style="padding: 10px 0; color: #666666; font-size: 15px; border-bottom: 1px solid #E0E0E0;"><strong style="color: #333333;">Performance :</strong></td><td style="padding: 10px 0; color: #333333; font-size: 15px; border-bottom: 1px solid #E0E0E0; text-align: right;">{variables["performance_score"]}/100</td></tr>')
                if variables.get('security_score'):
                    summary_rows.append(f'<tr><td style="padding: 10px 0; color: #666666; font-size: 15px; border-bottom: 1px solid #E0E0E0;"><strong style="color: #333333;">Sécurité :</strong></td><td style="padding: 10px 0; color: #333333; font-size: 15px; border-bottom: 1px solid #E0E0E0; text-align: right;">{variables["security_score"]}/100</td></tr>')
                if variables.get('hosting_provider'):
                    summary_rows.append(f'<tr><td style="padding: 10px 0; color: #666666; font-size: 15px; border-bottom: 1px solid #E0E0E0;"><strong style="color: #333333;">Hébergement :</strong></td><td style="padding: 10px 0; color: #333333; font-size: 15px; border-bottom: 1px solid #E0E0E0; text-align: right;">{variables["hosting_provider"]}</td></tr>')
                variables['analysis_summary'] = '\n'.join(summary_rows)
            else:
                content = re.sub(r'\{#if_all_data\}.*?\{#endif\}', '', content, flags=re.DOTALL)
        
        # Gérer les conditionnels génériques {#if_xxx} ... {#endif} (secteur, website, etc.)
        def replace_generic_if(match):
            var_name = match.group(1)
            block_content = match.group(2)
            return block_content if variables.get(var_name) else ''
        content = re.sub(r'\{#if_(\w+)\}(.*?)\{#endif\}', replace_generic_if, content, flags=re.DOTALL)
        # Nettoyer les marqueurs de condition restants
        content = re.sub(r'\{#if_\w+\}', '', content)
        content = re.sub(r'\{#endif\}', '', content)
        
        # Remplacer toutes les variables avec gestion des valeurs manquantes
        try:
            # Utiliser SafeFormatter pour gérer les clés manquantes
            class SafeFormatter:
                def __init__(self, mapping):
                    self.mapping = mapping
                
                def format(self, template):
                    def replace(match):
                        key = match.group(1)
                        return str(self.mapping.get(key, ''))
                    return re.sub(r'\{([^}]+)\}', replace, template)
            
            formatter = SafeFormatter(variables)
            content = formatter.format(content)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'Erreur lors du remplacement des variables: {e}')
            # Fallback sur format simple
            try:
                content = content.format(**{k: str(v) if v is not None else '' for k, v in variables.items()})
            except:
                pass
        
        return content, is_html

