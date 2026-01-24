"""
Module de gestion des analyses OSINT
Contient toutes les méthodes liées aux analyses OSINT
"""

import json
import logging
from urllib.parse import urlparse
from .base import DatabaseBase

logger = logging.getLogger(__name__)


class OSINTManager(DatabaseBase):
    """
    Gère toutes les opérations sur les analyses OSINT
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module OSINT"""
        super().__init__(*args, **kwargs)
    
    def save_osint_analysis(self, entreprise_id, url, osint_data):
        """
        Sauvegarde une analyse OSINT avec normalisation des données
        
        Args:
            entreprise_id: ID de l'entreprise
            url: URL analysée
            osint_data: Dictionnaire avec les données OSINT
        
        Returns:
            int: ID de l'analyse créée
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain_clean = domain.replace('www.', '') if domain else ''
        
        # Sauvegarder l'analyse principale
        if self.is_postgresql():
            self.execute_sql(cursor,'''
                INSERT INTO analyses_osint (
                    entreprise_id, url, domain, whois_data,
                    ssl_info, ip_info, shodan_data, censys_data, osint_details
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                entreprise_id,
                url,
                domain_clean,
                json.dumps(osint_data.get('whois_info', {})) if osint_data.get('whois_info') else None,
                json.dumps(osint_data.get('ssl_info', {})) if osint_data.get('ssl_info') else None,
                json.dumps(osint_data.get('ip_info', {})) if osint_data.get('ip_info') else None,
                json.dumps(osint_data.get('shodan_data', {})) if osint_data.get('shodan_data') else None,
                json.dumps(osint_data.get('censys_data', {})) if osint_data.get('censys_data') else None,
                json.dumps(osint_data) if osint_data else None
            ))
            result = cursor.fetchone()
            analysis_id = result['id'] if result else None
        else:
            self.execute_sql(cursor,'''
                INSERT INTO analyses_osint (
                    entreprise_id, url, domain, whois_data,
                    ssl_info, ip_info, shodan_data, censys_data, osint_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                entreprise_id,
                url,
                domain_clean,
                json.dumps(osint_data.get('whois_info', {})) if osint_data.get('whois_info') else None,
                json.dumps(osint_data.get('ssl_info', {})) if osint_data.get('ssl_info') else None,
                json.dumps(osint_data.get('ip_info', {})) if osint_data.get('ip_info') else None,
                json.dumps(osint_data.get('shodan_data', {})) if osint_data.get('shodan_data') else None,
                json.dumps(osint_data.get('censys_data', {})) if osint_data.get('censys_data') else None,
                json.dumps(osint_data) if osint_data else None
            ))
            analysis_id = cursor.lastrowid
        
        # Sauvegarder les sous-domaines
        subdomains = osint_data.get('subdomains', [])
        if subdomains:
            if isinstance(subdomains, str):
                try:
                    subdomains = json.loads(subdomains)
                except:
                    subdomains = []
            if isinstance(subdomains, list):
                for subdomain in subdomains:
                    subdomain_str = str(subdomain).strip()
                    if subdomain_str:
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_subdomains (analysis_id, subdomain)
                                VALUES (%s, %s)
                                ON CONFLICT (analysis_id, subdomain) DO NOTHING
                            ''', (analysis_id, subdomain_str))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_osint_subdomains (analysis_id, subdomain)
                                VALUES (?, ?)
                            ''', (analysis_id, subdomain_str))
        
        # Sauvegarder les enregistrements DNS
        dns_records = osint_data.get('dns_records', {})
        if dns_records:
            if isinstance(dns_records, str):
                try:
                    dns_records = json.loads(dns_records)
                except:
                    dns_records = {}
            if isinstance(dns_records, dict):
                for record_type, records in dns_records.items():
                    if not isinstance(records, list):
                        records = [records]
                    for record_value in records:
                        record_value_str = str(record_value).strip()
                        if record_value_str:
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_dns_records (analysis_id, record_type, record_value)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, record_type, record_value_str))
        
        # Sauvegarder les emails
        emails = osint_data.get('emails', [])
        if emails:
            if isinstance(emails, str):
                try:
                    emails = json.loads(emails)
                except:
                    emails = []
            if isinstance(emails, list):
                for email in emails:
                    if isinstance(email, dict):
                        email_str = email.get('email') or email.get('value') or str(email)
                        source = email.get('source')
                    else:
                        email_str = str(email).strip()
                        source = None
                    if email_str:
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_emails (analysis_id, email, source)
                                VALUES (%s, %s, %s)
                                ON CONFLICT (analysis_id, email) DO NOTHING
                            ''', (analysis_id, email_str, source))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_osint_emails (analysis_id, email, source)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, email_str, source))
        
        # Sauvegarder les réseaux sociaux
        social_media = osint_data.get('social_media', {})
        if not social_media and osint_data.get('people'):
            people = osint_data.get('people', {})
            if isinstance(people, dict):
                for person_data in people.values():
                    if isinstance(person_data, dict) and person_data.get('social_profiles'):
                        if not social_media:
                            social_media = {}
                        for platform, url_social in person_data.get('social_profiles', {}).items():
                            if platform not in social_media:
                                social_media[platform] = []
                            if url_social not in social_media[platform]:
                                social_media[platform].append(url_social)
        
        if social_media:
            if isinstance(social_media, str):
                try:
                    social_media = json.loads(social_media)
                except:
                    social_media = {}
            if isinstance(social_media, dict):
                for platform, urls in social_media.items():
                    if not isinstance(urls, list):
                        urls = [urls]
                    for url_social in urls:
                        url_social_str = str(url_social).strip()
                        if url_social_str:
                            if self.is_postgresql():
                                self.execute_sql(cursor,'''
                                    INSERT INTO analysis_osint_social_media (analysis_id, platform, url)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (analysis_id, platform, url) DO NOTHING
                                ''', (analysis_id, platform, url_social_str))
                            else:
                                self.execute_sql(cursor,'''
                                    INSERT OR IGNORE INTO analysis_osint_social_media (analysis_id, platform, url)
                                    VALUES (?, ?, ?)
                                ''', (analysis_id, platform, url_social_str))
        
        # Sauvegarder les technologies (filtrer les raw_output et erreurs)
        technologies = osint_data.get('technologies', {})
        if technologies:
            if isinstance(technologies, str):
                try:
                    technologies = json.loads(technologies)
                except:
                    technologies = {}
            if isinstance(technologies, dict):
                # Clés à exclure
                excluded_keys = {'raw_output', 'error', 'non disponible'}
                for category, techs in technologies.items():
                    # Ignorer les catégories d'erreur
                    category_lower = category.lower()
                    if any(excluded in category_lower for excluded in excluded_keys):
                        continue
                    if not isinstance(techs, list):
                        techs = [techs]
                    for tech in techs:
                        tech_name = str(tech).strip()
                        # Filtrer les valeurs d'erreur
                        if tech_name and not any(excluded in tech_name.lower() for excluded in excluded_keys):
                            if self.is_postgresql():
                                self.execute_sql(cursor,'''
                                    INSERT INTO analysis_osint_technologies (analysis_id, category, name)
                                    VALUES (%s, %s, %s)
                                    ON CONFLICT (analysis_id, category, name) DO NOTHING
                                ''', (analysis_id, category, tech_name))
                            else:
                                self.execute_sql(cursor,'''
                                    INSERT OR IGNORE INTO analysis_osint_technologies (analysis_id, category, name)
                                    VALUES (?, ?, ?)
                                ''', (analysis_id, category, tech_name))
        
        # Sauvegarder les métadonnées de documents
        document_metadata = osint_data.get('document_metadata', [])
        if document_metadata:
            if isinstance(document_metadata, str):
                try:
                    document_metadata = json.loads(document_metadata)
                except:
                    document_metadata = []
            if isinstance(document_metadata, list):
                for doc in document_metadata:
                    if isinstance(doc, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_osint_document_metadata (
                                analysis_id, file_url, file_type, author, creator, producer,
                                creation_date, modification_date, software, company, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            doc.get('file_url', ''),
                            doc.get('file_type'),
                            doc.get('author'),
                            doc.get('creator'),
                            doc.get('producer'),
                            doc.get('creation_date'),
                            doc.get('modification_date'),
                            doc.get('software'),
                            doc.get('company'),
                            json.dumps(doc) if doc else None
                        ))
        
        # Sauvegarder les métadonnées d'images
        image_metadata = osint_data.get('image_metadata', [])
        if image_metadata:
            if isinstance(image_metadata, str):
                try:
                    image_metadata = json.loads(image_metadata)
                except:
                    image_metadata = []
            if isinstance(image_metadata, list):
                for img in image_metadata:
                    if isinstance(img, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_osint_image_metadata (
                                analysis_id, image_url, camera_make, camera_model, date_taken,
                                gps_latitude, gps_longitude, gps_altitude, location_description,
                                software, metadata_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            img.get('image_url', ''),
                            img.get('camera_make'),
                            img.get('camera_model'),
                            img.get('date_taken'),
                            img.get('gps_latitude'),
                            img.get('gps_longitude'),
                            img.get('gps_altitude'),
                            img.get('location_description'),
                            img.get('software'),
                            json.dumps(img) if img else None
                        ))
        
        # Sauvegarder les détails SSL/TLS
        ssl_details = osint_data.get('ssl_details', [])
        if ssl_details:
            if isinstance(ssl_details, str):
                try:
                    ssl_details = json.loads(ssl_details)
                except:
                    ssl_details = []
            if isinstance(ssl_details, list):
                for ssl in ssl_details:
                    if isinstance(ssl, dict):
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_ssl_details (
                                analysis_id, host, port, certificate_valid, certificate_issuer,
                                certificate_subject, certificate_expiry, protocol_version,
                                cipher_suites, vulnerabilities, grade, details_json
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (analysis_id, host, port) DO NOTHING
                        ''', (
                            analysis_id,
                            ssl.get('host', ''),
                            ssl.get('port', 443),
                            ssl.get('certificate_valid'),
                            ssl.get('certificate_issuer'),
                            ssl.get('certificate_subject'),
                            ssl.get('certificate_expiry'),
                            ssl.get('protocol_version'),
                            ssl.get('cipher_suites'),
                            ssl.get('vulnerabilities'),
                            ssl.get('grade'),
                            json.dumps(ssl) if ssl else None
                        ))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_osint_ssl_details (
                                analysis_id, host, port, certificate_valid, certificate_issuer,
                                certificate_subject, certificate_expiry, protocol_version,
                                cipher_suites, vulnerabilities, grade, details_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            ssl.get('host', ''),
                            ssl.get('port', 443),
                            ssl.get('certificate_valid'),
                            ssl.get('certificate_issuer'),
                            ssl.get('certificate_subject'),
                            ssl.get('certificate_expiry'),
                            ssl.get('protocol_version'),
                            ssl.get('cipher_suites'),
                            ssl.get('vulnerabilities'),
                            ssl.get('grade'),
                            json.dumps(ssl) if ssl else None
                        ))
        
        # Sauvegarder la détection WAF
        waf_detections = osint_data.get('waf_detections', [])
        if waf_detections:
            if isinstance(waf_detections, str):
                try:
                    waf_detections = json.loads(waf_detections)
                except:
                    waf_detections = []
            if isinstance(waf_detections, list):
                for waf in waf_detections:
                    if isinstance(waf, dict):
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_waf_detection (
                                    analysis_id, url, waf_name, waf_vendor, detected,
                                    detection_method, details_json
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (analysis_id, url) DO NOTHING
                        ''', (
                            analysis_id,
                            waf.get('url', ''),
                            waf.get('waf_name'),
                            waf.get('waf_vendor'),
                            waf.get('detected', False),
                            waf.get('detection_method'),
                            json.dumps(waf) if waf else None
                        ))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_osint_waf_detection (
                                    analysis_id, url, waf_name, waf_vendor, detected,
                                    detection_method, details_json
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            waf.get('url', ''),
                            waf.get('waf_name'),
                            waf.get('waf_vendor'),
                            waf.get('detected', False),
                            waf.get('detection_method'),
                            json.dumps(waf) if waf else None
                        ))
        
        # Sauvegarder les répertoires trouvés
        directories = osint_data.get('directories', [])
        if directories:
            if isinstance(directories, str):
                try:
                    directories = json.loads(directories)
                except:
                    directories = []
            if isinstance(directories, list):
                for dir_item in directories:
                    if isinstance(dir_item, dict):
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_directories (
                                    analysis_id, path, status_code, content_length,
                                    content_type, redirect_url, tool_used
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (analysis_id, path) DO NOTHING
                        ''', (
                            analysis_id,
                            dir_item.get('path', ''),
                            dir_item.get('status_code'),
                            dir_item.get('content_length'),
                            dir_item.get('content_type'),
                            dir_item.get('redirect_url'),
                            dir_item.get('tool_used')
                        ))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_osint_directories (
                                    analysis_id, path, status_code, content_length,
                                    content_type, redirect_url, tool_used
                                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            dir_item.get('path', ''),
                            dir_item.get('status_code'),
                            dir_item.get('content_length'),
                            dir_item.get('content_type'),
                            dir_item.get('redirect_url'),
                            dir_item.get('tool_used')
                        ))
        
        # Sauvegarder les ports ouverts
        open_ports = osint_data.get('open_ports', [])
        if open_ports:
            if isinstance(open_ports, str):
                try:
                    open_ports = json.loads(open_ports)
                except:
                    open_ports = []
            if isinstance(open_ports, list):
                for port_info in open_ports:
                    if isinstance(port_info, dict):
                        if self.is_postgresql():
                            self.execute_sql(cursor,'''
                                INSERT INTO analysis_osint_open_ports (
                                    analysis_id, host, port, protocol, service,
                                    version, banner, source
                                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                                ON CONFLICT (analysis_id, host, port) DO NOTHING
                        ''', (
                            analysis_id,
                            port_info.get('host', ''),
                            port_info.get('port'),
                            port_info.get('protocol', 'tcp'),
                            port_info.get('service'),
                            port_info.get('version'),
                            port_info.get('banner'),
                            port_info.get('source')
                        ))
                        else:
                            self.execute_sql(cursor,'''
                                INSERT OR IGNORE INTO analysis_osint_open_ports (
                                    analysis_id, host, port, protocol, service,
                                    version, banner, source
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            port_info.get('host', ''),
                            port_info.get('port'),
                            port_info.get('protocol', 'tcp'),
                            port_info.get('service'),
                            port_info.get('version'),
                            port_info.get('banner'),
                            port_info.get('source')
                        ))
        
        # Sauvegarder les services détectés
        services = osint_data.get('services', [])
        if services:
            if isinstance(services, str):
                try:
                    services = json.loads(services)
                except:
                    services = []
            if isinstance(services, list):
                for service in services:
                    if isinstance(service, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_osint_services (
                                analysis_id, host, service_name, service_type,
                                port, product, version, details_json, source
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            service.get('host', ''),
                            service.get('service_name', ''),
                            service.get('service_type'),
                            service.get('port'),
                            service.get('product'),
                            service.get('version'),
                            json.dumps(service) if service else None,
                            service.get('source')
                        ))
        
        # Sauvegarder les certificats SSL
        certificates = osint_data.get('certificates', [])
        if certificates:
            if isinstance(certificates, str):
                try:
                    certificates = json.loads(certificates)
                except:
                    certificates = []
            if isinstance(certificates, list):
                for cert in certificates:
                    if isinstance(cert, dict):
                        self.execute_sql(cursor,'''
                            INSERT INTO analysis_osint_certificates (
                                analysis_id, host, port, issuer, subject,
                                serial_number, valid_from, valid_to, fingerprint, details_json
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            analysis_id,
                            cert.get('host', ''),
                            cert.get('port', 443),
                            cert.get('issuer'),
                            cert.get('subject'),
                            cert.get('serial_number'),
                            cert.get('valid_from'),
                            cert.get('valid_to'),
                            cert.get('fingerprint'),
                            json.dumps(cert) if cert else None
                        ))
        
        conn.commit()
        conn.close()
        
        # Logger pour déboguer
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f'[OSINT DB] Analyse sauvegardée: ID={analysis_id}, entreprise_id={entreprise_id}, url={url}')
        logger.info(f'[OSINT DB] Données sauvegardées: subdomains={len(subdomains)}, emails={len(emails)}, ssl_details={len(ssl_details) if ssl_details else 0}, waf={len(waf_detections) if waf_detections else 0}')
        
        return analysis_id
    
    def _load_osint_analysis_normalized_data(self, cursor, analysis_id):
        """
        Charge les données normalisées d'une analyse OSINT
        
        Args:
            cursor: Curseur SQLite
            analysis_id: ID de l'analyse
        
        Returns:
            dict: Dictionnaire avec toutes les données normalisées
        """
        # Charger les sous-domaines
        self.execute_sql(cursor,'SELECT subdomain FROM analysis_osint_subdomains WHERE analysis_id = ?', (analysis_id,))
        subdomains = [row['subdomain'] for row in cursor.fetchall()]
        
        # Charger les enregistrements DNS
        self.execute_sql(cursor,'SELECT record_type, record_value FROM analysis_osint_dns_records WHERE analysis_id = ?', (analysis_id,))
        dns_records = {}
        for row in cursor.fetchall():
            record_type = row['record_type']
            if record_type not in dns_records:
                dns_records[record_type] = []
            dns_records[record_type].append(row['record_value'])
        
        # Charger les emails
        self.execute_sql(cursor,'SELECT email, source FROM analysis_osint_emails WHERE analysis_id = ?', (analysis_id,))
        emails = []
        for row in cursor.fetchall():
            email = {'email': row['email']}
            if row['source']:
                email['source'] = row['source']
            emails.append(email)
        
        # Charger les réseaux sociaux
        self.execute_sql(cursor,'SELECT platform, url FROM analysis_osint_social_media WHERE analysis_id = ?', (analysis_id,))
        social_media = {}
        for row in cursor.fetchall():
            platform = row['platform']
            if platform not in social_media:
                social_media[platform] = []
            social_media[platform].append(row['url'])
        
        # Charger les technologies
        self.execute_sql(cursor,'SELECT category, name FROM analysis_osint_technologies WHERE analysis_id = ?', (analysis_id,))
        technologies = {}
        for row in cursor.fetchall():
            category = row['category']
            if category not in technologies:
                technologies[category] = []
            technologies[category].append(row['name'])
        
        # Charger les métadonnées de documents
        self.execute_sql(cursor,'''
            SELECT file_url, file_type, author, creator, producer, creation_date,
                   modification_date, software, company, metadata_json
            FROM analysis_osint_document_metadata WHERE analysis_id = ?
        ''', (analysis_id,))
        document_metadata = []
        for row in cursor.fetchall():
            doc = dict(row)
            if doc.get('metadata_json'):
                try:
                    doc.update(json.loads(doc['metadata_json']))
                except:
                    pass
            document_metadata.append(doc)
        
        # Charger les métadonnées d'images
        self.execute_sql(cursor,'''
            SELECT image_url, camera_make, camera_model, date_taken, gps_latitude,
                   gps_longitude, gps_altitude, location_description, software, metadata_json
            FROM analysis_osint_image_metadata WHERE analysis_id = ?
        ''', (analysis_id,))
        image_metadata = []
        for row in cursor.fetchall():
            img = dict(row)
            if img.get('metadata_json'):
                try:
                    img.update(json.loads(img['metadata_json']))
                except:
                    pass
            image_metadata.append(img)
        
        # Charger les détails SSL/TLS
        self.execute_sql(cursor,'''
            SELECT host, port, certificate_valid, certificate_issuer, certificate_subject,
                   certificate_expiry, protocol_version, cipher_suites, vulnerabilities, grade, details_json
            FROM analysis_osint_ssl_details WHERE analysis_id = ?
        ''', (analysis_id,))
        ssl_details = []
        for row in cursor.fetchall():
            ssl = dict(row)
            if ssl.get('details_json'):
                try:
                    ssl.update(json.loads(ssl['details_json']))
                except:
                    pass
            ssl_details.append(ssl)
        
        # Charger les détections WAF
        self.execute_sql(cursor,'''
            SELECT url, waf_name, waf_vendor, detected, detection_method, details_json
            FROM analysis_osint_waf_detection WHERE analysis_id = ?
        ''', (analysis_id,))
        waf_detections = []
        for row in cursor.fetchall():
            waf = dict(row)
            if waf.get('details_json'):
                try:
                    waf.update(json.loads(waf['details_json']))
                except:
                    pass
            waf_detections.append(waf)
        
        # Charger les répertoires trouvés
        self.execute_sql(cursor,'''
            SELECT path, status_code, content_length, content_type, redirect_url, tool_used
            FROM analysis_osint_directories WHERE analysis_id = ?
        ''', (analysis_id,))
        directories = [dict(row) for row in cursor.fetchall()]
        
        # Charger les ports ouverts
        self.execute_sql(cursor,'''
            SELECT host, port, protocol, service, version, banner, source
            FROM analysis_osint_open_ports WHERE analysis_id = ?
        ''', (analysis_id,))
        open_ports = [dict(row) for row in cursor.fetchall()]
        
        # Charger les services détectés
        self.execute_sql(cursor,'''
            SELECT host, service_name, service_type, port, product, version, details_json, source
            FROM analysis_osint_services WHERE analysis_id = ?
        ''', (analysis_id,))
        services = []
        for row in cursor.fetchall():
            service = dict(row)
            if service.get('details_json'):
                try:
                    service.update(json.loads(service['details_json']))
                except:
                    pass
            services.append(service)
        
        # Charger les certificats SSL
        self.execute_sql(cursor,'''
            SELECT host, port, issuer, subject, serial_number, valid_from, valid_to, fingerprint, details_json
            FROM analysis_osint_certificates WHERE analysis_id = ?
        ''', (analysis_id,))
        certificates = []
        for row in cursor.fetchall():
            cert = dict(row)
            if cert.get('details_json'):
                try:
                    cert.update(json.loads(cert['details_json']))
                except:
                    pass
            certificates.append(cert)
        
        return {
            'subdomains': subdomains,
            'dns_records': dns_records,
            'emails': emails,
            'emails_found': emails,  # Compatibilité
            'social_media': social_media,
            'technologies_detected': technologies,
            'technologies': technologies,  # Compatibilité
            'document_metadata': document_metadata,
            'image_metadata': image_metadata,
            'ssl_details': ssl_details,
            'waf_detections': waf_detections,
            'directories': directories,
            'open_ports': open_ports,
            'services': services,
            'certificates': certificates
        }
    
    def get_osint_analysis_by_entreprise(self, entreprise_id):
        """
        Récupère l'analyse OSINT d'une entreprise avec données normalisées
        
        Args:
            entreprise_id: ID de l'entreprise
        
        Returns:
            dict: Analyse OSINT ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT * FROM analyses_osint
            WHERE entreprise_id = ?
            ORDER BY date_analyse DESC
            LIMIT 1
        ''', (entreprise_id,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_osint_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            json_fields = ['whois_data', 'ssl_info', 'ip_info', 'shodan_data', 'censys_data', 'osint_details']
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            # Normaliser les noms de champs pour le frontend
            if 'whois_data' in analysis:
                analysis['whois_info'] = analysis['whois_data']
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def update_osint_analysis(self, analysis_id, osint_data):
        """
        Met à jour une analyse OSINT existante avec normalisation
        
        Args:
            analysis_id: ID de l'analyse
            osint_data: Nouvelles données OSINT
        
        Returns:
            int: ID de l'analyse (nouvelle ou existante)
        """
        # Supprimer les anciennes données normalisées
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor,'DELETE FROM analysis_osint_subdomains WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_dns_records WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_emails WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_social_media WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_technologies WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_document_metadata WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_image_metadata WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_ssl_details WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_waf_detection WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_directories WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_open_ports WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_services WHERE analysis_id = ?', (analysis_id,))
        self.execute_sql(cursor,'DELETE FROM analysis_osint_certificates WHERE analysis_id = ?', (analysis_id,))
        conn.commit()
        conn.close()
        
        # Réutiliser save_osint_analysis qui gère déjà la normalisation
        conn = self.get_connection()
        cursor = conn.cursor()
        self.execute_sql(cursor,'SELECT entreprise_id, url FROM analyses_osint WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            entreprise_id = row['entreprise_id']
            url = row['url'] or osint_data.get('url', '')
            # Supprimer l'ancienne analyse et en créer une nouvelle
            conn = self.get_connection()
            cursor = conn.cursor()
            self.execute_sql(cursor,'DELETE FROM analyses_osint WHERE id = ?', (analysis_id,))
            conn.commit()
            conn.close()
            # Sauvegarder avec la nouvelle méthode normalisée
            return self.save_osint_analysis(entreprise_id, url, osint_data)
        
        return analysis_id
    
    def get_osint_analysis_by_url(self, url):
        """
        Récupère une analyse OSINT par son URL avec données normalisées
        
        Args:
            url: URL analysée
        
        Returns:
            dict: Analyse OSINT ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT ao.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_osint ao
            LEFT JOIN entreprises e ON ao.entreprise_id = e.id
            WHERE ao.url = ?
            ORDER BY ao.date_analyse DESC
            LIMIT 1
        ''', (url,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_osint_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            json_fields = ['whois_data', 'ssl_info', 'ip_info', 'shodan_data', 'censys_data', 'osint_details']
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            # Normaliser les noms de champs pour le frontend
            if 'whois_data' in analysis:
                analysis['whois_info'] = analysis['whois_data']
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_osint_analysis(self, analysis_id):
        """
        Récupère une analyse OSINT par ID avec données normalisées
        
        Args:
            analysis_id: ID de l'analyse
        
        Returns:
            dict: Analyse OSINT ou None
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT ao.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_osint ao
            LEFT JOIN entreprises e ON ao.entreprise_id = e.id
            WHERE ao.id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            
            # Charger les données normalisées
            normalized = self._load_osint_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Parser les autres champs JSON
            json_fields = ['whois_data', 'ssl_info', 'ip_info', 'shodan_data', 'censys_data', 'osint_details']
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            # Normaliser les noms de champs pour le frontend
            if 'whois_data' in analysis:
                analysis['whois_info'] = analysis['whois_data']
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_all_osint_analyses(self):
        """
        Récupère toutes les analyses OSINT avec données normalisées
        
        Returns:
            list: Liste des analyses OSINT
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'''
            SELECT ao.*, e.nom as entreprise_nom
            FROM analyses_osint ao
            LEFT JOIN entreprises e ON ao.entreprise_id = e.id
            ORDER BY ao.date_analyse DESC
        ''')
        
        rows = cursor.fetchall()
        
        analyses = []
        for row in rows:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_osint_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Ajouter les compteurs pour compatibilité
            analysis['subdomains_count'] = len(analysis.get('subdomains', []))
            analysis['emails_count'] = len(analysis.get('emails', []))
            
            analyses.append(analysis)
        
        conn.close()
        return analyses
    
    def delete_osint_analysis(self, analysis_id):
        """
        Supprime une analyse OSINT
        
        Args:
            analysis_id: ID de l'analyse à supprimer
        
        Returns:
            bool: True si supprimée, False sinon
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        self.execute_sql(cursor,'DELETE FROM analyses_osint WHERE id = ?', (analysis_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        
        return deleted
