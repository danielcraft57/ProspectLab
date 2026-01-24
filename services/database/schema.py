"""
Module de schéma de base de données
Contient la création de toutes les tables et migrations
"""

from .base import DatabaseBase


class DatabaseSchema(DatabaseBase):
    """
    Gère la création du schéma de base de données
    Toutes les tables et migrations sont définies ici
    """
    
    def __init__(self, *args, **kwargs):
        """Initialise le module de schéma"""
        super().__init__(*args, **kwargs)
    
    def init_database(self):
        """
        Initialise les tables de la base de données
        Crée toutes les tables nécessaires avec leurs contraintes et index
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Pour PostgreSQL, activer le mode autocommit pour éviter les problèmes de transaction
        if self.is_postgresql():
            conn.autocommit = True
        
        # Table des analyses
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                output_filename TEXT,
                total_entreprises INTEGER,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                parametres TEXT,
                statut TEXT,
                duree_secondes REAL
            )
        ''')
        
        # Table des entreprises analysées
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS entreprises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analyse_id INTEGER,
                nom TEXT NOT NULL,
                website TEXT,
                secteur TEXT,
                statut TEXT,
                opportunite TEXT,
                email_principal TEXT,
                responsable TEXT,
                taille_estimee TEXT,
                hosting_provider TEXT,
                framework TEXT,
                score_securite INTEGER,
                tags TEXT,
                notes TEXT,
                favori INTEGER DEFAULT 0,
                telephone TEXT,
                pays TEXT,
                address_1 TEXT,
                address_2 TEXT,
                longitude REAL,
                latitude REAL,
                note_google REAL,
                nb_avis_google INTEGER,
                date_analyse TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analyse_id) REFERENCES analyses(id) ON DELETE CASCADE
            )
        ''')
        
        # Commit pour PostgreSQL après création de la table
        if self.is_postgresql():
            conn.commit()
        
        # Ajouter les nouvelles colonnes si elles n'existent pas (migration)
        new_columns = [
            ('telephone', 'TEXT'),
            ('pays', 'TEXT'),
            ('address_1', 'TEXT'),
            ('address_2', 'TEXT'),
            ('longitude', 'REAL'),
            ('latitude', 'REAL'),
            ('note_google', 'REAL'),
            ('nb_avis_google', 'INTEGER')
        ]
        
        for col_name, col_type in new_columns:
            self.safe_execute_sql(cursor, f'ALTER TABLE entreprises ADD COLUMN {col_name} {col_type}')
        
        # Ajouter la colonne resume si elle n'existe pas
        self.safe_execute_sql(cursor, 'ALTER TABLE entreprises ADD COLUMN resume TEXT')
        
        # Ajouter les colonnes pour les images et icônes
        icon_columns = [
            ('og_image', 'TEXT'),
            ('favicon', 'TEXT'),
            ('logo', 'TEXT')
        ]
        for col_name, col_type in icon_columns:
            self.safe_execute_sql(cursor, f'ALTER TABLE entreprises ADD COLUMN {col_name} {col_type}')
        
        # Table des données OpenGraph (normalisée selon ogp.me)
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS entreprise_og_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                page_url TEXT,
                og_title TEXT,
                og_type TEXT,
                og_url TEXT,
                og_description TEXT,
                og_determiner TEXT,
                og_locale TEXT,
                og_site_name TEXT,
                og_audio TEXT,
                og_video TEXT,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Migration : ajouter la colonne page_url si elle n'existe pas
        self.safe_execute_sql(cursor, 'ALTER TABLE entreprise_og_data ADD COLUMN page_url TEXT')
        
        # Table des images OpenGraph
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS entreprise_og_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                og_data_id INTEGER,
                image_url TEXT NOT NULL,
                secure_url TEXT,
                image_type TEXT,
                width INTEGER,
                height INTEGER,
                alt_text TEXT,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (og_data_id) REFERENCES entreprise_og_data(id) ON DELETE CASCADE
            )
        ''')
        
        # Table des vidéos OpenGraph
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS entreprise_og_videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                og_data_id INTEGER,
                video_url TEXT NOT NULL,
                secure_url TEXT,
                video_type TEXT,
                width INTEGER,
                height INTEGER,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (og_data_id) REFERENCES entreprise_og_data(id) ON DELETE CASCADE
            )
        ''')
        
        # Table des audios OpenGraph
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS entreprise_og_audios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                og_data_id INTEGER,
                audio_url TEXT NOT NULL,
                secure_url TEXT,
                audio_type TEXT,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (og_data_id) REFERENCES entreprise_og_data(id) ON DELETE CASCADE
            )
        ''')
        
        # Table des locales alternatives OpenGraph
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS entreprise_og_locales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                og_data_id INTEGER,
                locale TEXT NOT NULL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (og_data_id) REFERENCES entreprise_og_data(id) ON DELETE CASCADE,
                UNIQUE(og_data_id, locale)
            )
        ''')
        
        # Index pour les recherches
        self.execute_sql(cursor, 'CREATE INDEX IF NOT EXISTS idx_og_data_entreprise_id ON entreprise_og_data(entreprise_id)')
        self.execute_sql(cursor, 'CREATE INDEX IF NOT EXISTS idx_og_images_entreprise_id ON entreprise_og_images(entreprise_id)')
        self.execute_sql(cursor, 'CREATE INDEX IF NOT EXISTS idx_og_videos_entreprise_id ON entreprise_og_videos(entreprise_id)')
        self.execute_sql(cursor, 'CREATE INDEX IF NOT EXISTS idx_og_audios_entreprise_id ON entreprise_og_audios(entreprise_id)')
        self.execute_sql(cursor, 'CREATE INDEX IF NOT EXISTS idx_og_locales_entreprise_id ON entreprise_og_locales(entreprise_id)')
        
        # Table des campagnes email
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS campagnes_email (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                template_id TEXT,
                sujet TEXT,
                total_destinataires INTEGER,
                total_envoyes INTEGER,
                total_reussis INTEGER,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                statut TEXT
            )
        ''')
        
        # Table des emails envoyés
        self.execute_sql(cursor, '''
            CREATE TABLE IF NOT EXISTS emails_envoyes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                campagne_id INTEGER,
                entreprise_id INTEGER,
                email TEXT NOT NULL,
                nom_destinataire TEXT,
                entreprise TEXT,
                sujet TEXT,
                date_envoi TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                statut TEXT,
                erreur TEXT,
                tracking_token TEXT,
                FOREIGN KEY (campagne_id) REFERENCES campagnes_email(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Migration : ajouter la colonne tracking_token si elle n'existe pas
        self.safe_execute_sql(cursor, 'ALTER TABLE emails_envoyes ADD COLUMN tracking_token TEXT')
        
        # Table des utilisateurs (authentification)
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                is_admin INTEGER DEFAULT 0,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                derniere_connexion TIMESTAMP
            )
        ''')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
        
        # Table des tokens API
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS api_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                app_url TEXT,
                user_id INTEGER,
                is_active INTEGER DEFAULT 1,
                can_read_entreprises INTEGER DEFAULT 1,
                can_read_emails INTEGER DEFAULT 1,
                can_read_statistics INTEGER DEFAULT 1,
                can_read_campagnes INTEGER DEFAULT 1,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
            )
        ''')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_api_tokens_token ON api_tokens(token)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_api_tokens_user_id ON api_tokens(user_id)')
        
        # Migration : ajouter les nouvelles colonnes si elles n'existent pas
        self.safe_execute_sql(cursor, 'ALTER TABLE api_tokens ADD COLUMN app_url TEXT')
        self.safe_execute_sql(cursor, 'ALTER TABLE api_tokens ADD COLUMN can_read_entreprises INTEGER DEFAULT 1')
        self.safe_execute_sql(cursor, 'ALTER TABLE api_tokens ADD COLUMN can_read_emails INTEGER DEFAULT 1')
        self.safe_execute_sql(cursor, 'ALTER TABLE api_tokens ADD COLUMN can_read_statistics INTEGER DEFAULT 1')
        self.safe_execute_sql(cursor, 'ALTER TABLE api_tokens ADD COLUMN can_read_campagnes INTEGER DEFAULT 1')
        
        # Table des événements de tracking email
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS email_tracking_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER NOT NULL,
                tracking_token TEXT NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT,
                ip_address TEXT,
                user_agent TEXT,
                date_event TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (email_id) REFERENCES emails_envoyes(id) ON DELETE CASCADE
            )
        ''')
        
        # Index pour le tracking
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tracking_email_id ON email_tracking_events(email_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tracking_token ON email_tracking_events(tracking_token)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tracking_event_type ON email_tracking_events(event_type)')
        
        # Table des analyses techniques
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analyses_techniques (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER,
                url TEXT NOT NULL,
                domain TEXT,
                ip_address TEXT,
                server_software TEXT,
                framework TEXT,
                framework_version TEXT,
                cms TEXT,
                cms_version TEXT,
                cms_plugins TEXT,
                hosting_provider TEXT,
                domain_creation_date TEXT,
                domain_updated_date TEXT,
                domain_registrar TEXT,
                ssl_valid BOOLEAN,
                ssl_expiry_date TEXT,
                security_headers TEXT,
                waf TEXT,
                cdn TEXT,
                analytics TEXT,
                seo_meta TEXT,
                performance_metrics TEXT,
                nmap_scan TEXT,
                technical_details TEXT,
                date_analyse TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Ajouter la colonne cms_version si elle n'existe pas (migration)
        self.safe_execute_sql(cursor, 'ALTER TABLE analyses_techniques ADD COLUMN cms_version TEXT')
        
        # Tables normalisées pour les analyses techniques
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_technique_cms_plugins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                plugin_name TEXT NOT NULL,
                version TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_techniques(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, plugin_name)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_technique_security_headers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                header_name TEXT NOT NULL,
                header_value TEXT,
                status TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_techniques(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, header_name)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_technique_analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                tool_name TEXT NOT NULL,
                tool_id TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_techniques(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, tool_name)
            )
        ''')
        
        # Index pour les analyses techniques
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_cms_plugins_analysis_id ON analysis_technique_cms_plugins(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_security_headers_analysis_id ON analysis_technique_security_headers(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_analytics_analysis_id ON analysis_technique_analytics(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_url ON analyses_techniques(url)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_domain ON analyses_techniques(domain)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_entreprise_date ON analyses_techniques(entreprise_id, date_analyse)')

        # Colonnes complémentaires pour les analyses techniques
        for col_name, col_type in [
            ('pages_count', 'INTEGER'),
            ('security_score', 'INTEGER'),
            ('performance_score', 'INTEGER'),
            ('trackers_count', 'INTEGER'),
            ('pages_summary', 'TEXT')
        ]:
            self.safe_execute_sql(cursor, f'ALTER TABLE analyses_techniques ADD COLUMN {col_name} {col_type}')

        # Table des pages analysées
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_technique_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                page_url TEXT NOT NULL,
                status_code INTEGER,
                final_url TEXT,
                content_type TEXT,
                title TEXT,
                response_time_ms INTEGER,
                content_length INTEGER,
                security_score INTEGER,
                performance_score INTEGER,
                trackers_count INTEGER,
                security_headers TEXT,
                analytics TEXT,
                details TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_techniques(id) ON DELETE CASCADE
            )
        ''')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_pages_analysis_id ON analysis_technique_pages(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_pages_url ON analysis_technique_pages(page_url)')
        
        # Table des analyses OSINT
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analyses_osint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER,
                url TEXT NOT NULL,
                domain TEXT,
                subdomains TEXT,
                dns_records TEXT,
                whois_data TEXT,
                emails_found TEXT,
                social_media TEXT,
                technologies_detected TEXT,
                ssl_info TEXT,
                ip_info TEXT,
                shodan_data TEXT,
                censys_data TEXT,
                osint_details TEXT,
                date_analyse TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Tables normalisées pour les analyses OSINT
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_subdomains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                subdomain TEXT NOT NULL,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, subdomain)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_dns_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                record_type TEXT NOT NULL,
                record_value TEXT NOT NULL,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, email)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_social_media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, platform, url)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_technologies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, category, name)
            )
        ''')
        
        # Tables pour les nouveaux outils OSINT
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_document_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                file_url TEXT NOT NULL,
                file_type TEXT,
                author TEXT,
                creator TEXT,
                producer TEXT,
                creation_date TEXT,
                modification_date TEXT,
                software TEXT,
                company TEXT,
                metadata_json TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_image_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                image_url TEXT NOT NULL,
                camera_make TEXT,
                camera_model TEXT,
                date_taken TEXT,
                gps_latitude REAL,
                gps_longitude REAL,
                gps_altitude REAL,
                location_description TEXT,
                software TEXT,
                metadata_json TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_ssl_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                host TEXT NOT NULL,
                port INTEGER DEFAULT 443,
                certificate_valid BOOLEAN,
                certificate_issuer TEXT,
                certificate_subject TEXT,
                certificate_expiry TEXT,
                protocol_version TEXT,
                cipher_suites TEXT,
                vulnerabilities TEXT,
                grade TEXT,
                details_json TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, host, port)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_waf_detection (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                waf_name TEXT,
                waf_vendor TEXT,
                detected BOOLEAN DEFAULT 0,
                detection_method TEXT,
                details_json TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, url)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_directories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                path TEXT NOT NULL,
                status_code INTEGER,
                content_length INTEGER,
                content_type TEXT,
                redirect_url TEXT,
                tool_used TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, path)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_open_ports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                host TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT DEFAULT 'tcp',
                service TEXT,
                version TEXT,
                banner TEXT,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, host, port, protocol)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                host TEXT NOT NULL,
                service_name TEXT NOT NULL,
                service_type TEXT,
                port INTEGER,
                product TEXT,
                version TEXT,
                details_json TEXT,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_osint_certificates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                host TEXT NOT NULL,
                port INTEGER DEFAULT 443,
                issuer TEXT,
                subject TEXT,
                serial_number TEXT,
                valid_from TEXT,
                valid_to TEXT,
                fingerprint TEXT,
                details_json TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE
            )
        ''')
        
        # Index pour les analyses OSINT
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_subdomains_analysis_id ON analysis_osint_subdomains(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_dns_analysis_id ON analysis_osint_dns_records(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_emails_analysis_id ON analysis_osint_emails(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_social_analysis_id ON analysis_osint_social_media(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_tech_analysis_id ON analysis_osint_technologies(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_doc_metadata_analysis_id ON analysis_osint_document_metadata(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_image_metadata_analysis_id ON analysis_osint_image_metadata(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_ssl_details_analysis_id ON analysis_osint_ssl_details(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_waf_analysis_id ON analysis_osint_waf_detection(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_directories_analysis_id ON analysis_osint_directories(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_open_ports_analysis_id ON analysis_osint_open_ports(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_services_analysis_id ON analysis_osint_services(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_certificates_analysis_id ON analysis_osint_certificates(analysis_id)')
        
        # Table des analyses Pentest
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analyses_pentest (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER,
                url TEXT NOT NULL,
                domain TEXT,
                vulnerabilities TEXT,
                sql_injection TEXT,
                xss_vulnerabilities TEXT,
                csrf_vulnerabilities TEXT,
                authentication_issues TEXT,
                authorization_issues TEXT,
                sensitive_data_exposure TEXT,
                security_headers_analysis TEXT,
                ssl_tls_analysis TEXT,
                waf_detection TEXT,
                cms_vulnerabilities TEXT,
                api_security TEXT,
                network_scan TEXT,
                pentest_details TEXT,
                risk_score INTEGER,
                date_analyse TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Tables normalisées pour les analyses Pentest
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_pentest_vulnerabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                severity TEXT,
                description TEXT,
                recommendation TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_pentest(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_pentest_security_headers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                header_name TEXT NOT NULL,
                status TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_pentest(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, header_name)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_pentest_cms_vulnerabilities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                severity TEXT,
                description TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_pentest(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS analysis_pentest_open_ports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                port INTEGER NOT NULL,
                service TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_pentest(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, port)
            )
        ''')
        
        # Index pour les analyses Pentest
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_pentest_vuln_analysis_id ON analysis_pentest_vulnerabilities(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_pentest_security_headers_analysis_id ON analysis_pentest_security_headers(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_pentest_cms_vuln_analysis_id ON analysis_pentest_cms_vulnerabilities(analysis_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_pentest_ports_analysis_id ON analysis_pentest_open_ports(analysis_id)')
        
        # Table des scrapers
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scrapers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER,
                url TEXT NOT NULL,
                scraper_type TEXT NOT NULL,
                emails TEXT,
                people TEXT,
                phones TEXT,
                social_profiles TEXT,
                technologies TEXT,
                metadata TEXT,
                visited_urls INTEGER,
                total_emails INTEGER,
                total_people INTEGER,
                total_phones INTEGER,
                total_social_profiles INTEGER,
                total_technologies INTEGER,
                total_metadata INTEGER,
                total_images INTEGER DEFAULT 0,
                total_forms INTEGER DEFAULT 0,
                duration REAL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(entreprise_id, url, scraper_type)
            )
        ''')
        
        # Table des images
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER,
                scraper_id INTEGER,
                url TEXT NOT NULL,
                alt_text TEXT,
                page_url TEXT,
                width INTEGER,
                height INTEGER,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE
            )
        ''')
        
        # Migrations pour les colonnes manquantes
        for col_name, col_type in [
            ('entreprise_id', 'INTEGER'),
            ('scraper_id', 'INTEGER'),
            ('total_forms', 'INTEGER DEFAULT 0')
        ]:
                if col_name == 'total_forms':
                    self.safe_execute_sql(cursor, f'ALTER TABLE scrapers ADD COLUMN {col_name} {col_type}')
                else:
                    self.safe_execute_sql(cursor, f'ALTER TABLE images ADD COLUMN {col_name} {col_type}')
        
        # Index pour les images
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_images_entreprise_id ON images(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_images_scraper_id ON images(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_images_url ON images(url)')
        
        # Commit final pour PostgreSQL
        if self.is_postgresql():
            conn.commit()
        self.execute_sql(cursor,'CREATE UNIQUE INDEX IF NOT EXISTS idx_images_entreprise_url ON images(entreprise_id, url)')
        
        # Tables normalisées pour les scrapers
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scraper_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                page_url TEXT,
                provider TEXT,
                type TEXT,
                format_valid INTEGER,
                mx_valid INTEGER,
                risk_score INTEGER,
                domain TEXT,
                name_info TEXT,
                is_person INTEGER DEFAULT 0,
                analyzed_at TIMESTAMP,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(scraper_id, email)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scraper_phones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                phone TEXT NOT NULL,
                page_url TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(scraper_id, phone)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scraper_social_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                platform TEXT NOT NULL,
                url TEXT NOT NULL,
                page_url TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(scraper_id, platform, url)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scraper_technologies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                name TEXT NOT NULL,
                page_url TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(scraper_id, category, name)
            )
        ''')
        
        # Note: scraper_people sera créée APRÈS personnes (voir plus bas)
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scraper_forms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                page_url TEXT NOT NULL,
                action_url TEXT,
                method TEXT DEFAULT 'GET',
                enctype TEXT,
                has_csrf INTEGER DEFAULT 0,
                has_file_upload INTEGER DEFAULT 0,
                fields_count INTEGER DEFAULT 0,
                fields_data TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Index pour les scrapers
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_emails_scraper_id ON scraper_emails(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_emails_entreprise_id ON scraper_emails(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_phones_scraper_id ON scraper_phones(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_phones_entreprise_id ON scraper_phones(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_social_scraper_id ON scraper_social_profiles(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_social_entreprise_id ON scraper_social_profiles(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_tech_scraper_id ON scraper_technologies(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_tech_entreprise_id ON scraper_technologies(entreprise_id)')
        # Note: Les index pour scraper_people seront créés après la création de la table (voir plus bas)
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_forms_scraper_id ON scraper_forms(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_forms_entreprise_id ON scraper_forms(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_forms_page_url ON scraper_forms(page_url)')
        
        # Commit pour PostgreSQL avant de créer scraper_people
        if self.is_postgresql():
            conn.commit()
        
        # Table des personnes (doit être créée AVANT scraper_people qui la référence)
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entreprise_id INTEGER NOT NULL,
                nom TEXT NOT NULL,
                prenom TEXT,
                titre TEXT,
                role TEXT,
                email TEXT,
                telephone TEXT,
                linkedin_url TEXT,
                linkedin_profile_data TEXT,
                social_profiles TEXT,
                osint_data TEXT,
                niveau_hierarchique INTEGER,
                manager_id INTEGER,
                source TEXT,
                bio TEXT,
                languages TEXT,
                skills TEXT,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_mise_a_jour TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (manager_id) REFERENCES personnes(id) ON DELETE SET NULL
            )
        ''')
        
        # Commit pour PostgreSQL après création de personnes
        if self.is_postgresql():
            conn.commit()
        
        # Créer scraper_people APRÈS personnes (car elle référence personnes)
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS scraper_people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                person_id INTEGER,
                name TEXT,
                title TEXT,
                email TEXT,
                linkedin_url TEXT,
                page_url TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (person_id) REFERENCES personnes(id) ON DELETE SET NULL
            )
        ''')
        
        # Créer les index pour scraper_people maintenant que la table existe
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_people_scraper_id ON scraper_people(scraper_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_people_entreprise_id ON scraper_people(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_people_person_id ON scraper_people(person_id)')
        
        # Tables pour les données OSINT enrichies sur les personnes
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_osint_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                location TEXT,
                location_city TEXT,
                location_country TEXT,
                location_address TEXT,
                location_latitude REAL,
                location_longitude REAL,
                age_range TEXT,
                birth_date TEXT,
                hobbies TEXT,
                interests TEXT,
                education TEXT,
                professional_history TEXT,
                family_members TEXT,
                data_breaches TEXT,
                photos_urls TEXT,
                bio TEXT,
                languages TEXT,
                skills TEXT,
                certifications TEXT,
                date_collected TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE,
                UNIQUE(personne_id)
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                photo_url TEXT NOT NULL,
                source TEXT,
                thumbnail_url TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                location_type TEXT,
                address TEXT,
                city TEXT,
                country TEXT,
                latitude REAL,
                longitude REAL,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_hobbies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                hobby_name TEXT NOT NULL,
                category TEXT,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_professional_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                company_name TEXT,
                position TEXT,
                start_date TEXT,
                end_date TEXT,
                description TEXT,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_family (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                family_member_name TEXT NOT NULL,
                relationship TEXT,
                age TEXT,
                location TEXT,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE
            )
        ''')
        
        self.execute_sql(cursor,'''
            CREATE TABLE IF NOT EXISTS personnes_data_breaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                personne_id INTEGER NOT NULL,
                breach_name TEXT NOT NULL,
                breach_date TEXT,
                data_leaked TEXT,
                source TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (personne_id) REFERENCES personnes(id) ON DELETE CASCADE
            )
        ''')
        
        # Index pour les personnes
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_osint_personne ON personnes_osint_details(personne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_photos_personne ON personnes_photos(personne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_locations_personne ON personnes_locations(personne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_hobbies_personne ON personnes_hobbies(personne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_professional_personne ON personnes_professional_history(personne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_family_personne ON personnes_family(personne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_breaches_personne ON personnes_data_breaches(personne_id)')
        
        # Index généraux pour performance
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_entreprises_analyse ON entreprises(analyse_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_entreprises_nom ON entreprises(nom)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_entreprises_secteur ON entreprises(secteur)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_entreprises_geo ON entreprises(longitude, latitude)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_emails_campagne ON emails_envoyes(campagne_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_tech_entreprise ON analyses_techniques(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_osint_entreprise ON analyses_osint(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_pentest_entreprise ON analyses_pentest(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scrapers_entreprise ON scrapers(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scrapers_url ON scrapers(url)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_entreprise ON personnes(entreprise_id)')
        self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_personnes_manager ON personnes(manager_id)')
        
        # Migration : ajouter la colonne is_person si elle n'existe pas
        try:
            self.execute_sql(cursor,'ALTER TABLE scraper_emails ADD COLUMN is_person INTEGER DEFAULT 0')
            conn.commit()
        except Exception:
            # La colonne existe déjà, ignorer l'erreur
            conn.rollback()
        
        # Créer l'index pour is_person après la migration
        try:
            self.execute_sql(cursor,'CREATE INDEX IF NOT EXISTS idx_scraper_emails_is_person ON scraper_emails(is_person)')
            if not self.is_postgresql():
                conn.commit()
        except Exception:
            if not self.is_postgresql():
                conn.rollback()
        
        # Désactiver autocommit pour PostgreSQL avant de fermer
        if self.is_postgresql():
            conn.autocommit = False
        
        conn.close()
        
        # Migration : recréer les contraintes avec ON DELETE CASCADE si nécessaire
        self.migrate_foreign_keys_cascade()
    
    def migrate_foreign_keys_cascade(self):
        """
        Active les clés étrangères pour SQLite
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Activer les clés étrangères
            self.execute_sql(cursor,'PRAGMA foreign_keys = ON')
            conn.commit()
        except Exception as e:
            # Si l'activation échoue, on continue quand même
            conn.rollback()
        finally:
            conn.close()

