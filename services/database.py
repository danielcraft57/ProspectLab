"""
Service de base de données pour ProspectLab
Stockage des analyses, résultats, et historique
"""

import sqlite3
from pathlib import Path
from datetime import datetime
import json
from typing import List, Dict, Optional


class Database:
    def __init__(self, db_path=None):
        """Initialise la connexion à la base de données"""
        if db_path is None:
            # Vérifier si un chemin est défini dans les variables d'environnement
            import os
            env_db_path = os.environ.get('DATABASE_PATH')
            if env_db_path:
                db_path = env_db_path
            else:
                app_dir = Path(__file__).parent.parent
                db_path = app_dir / 'prospectlab.db'
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True)
        self.init_database()
    
    def get_connection(self):
        """Obtient une connexion à la base de données"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_database(self):
        """Initialise les tables de la base de données"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Table des analyses
        cursor.execute('''
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
        cursor.execute('''
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
        
        # Migration : si adresse_complete existe, la supprimer après migration
        try:
            cursor.execute('SELECT adresse_complete FROM entreprises LIMIT 1')
            # Si la colonne existe, migrer les données vers address_1 et address_2
            cursor.execute('''
                UPDATE entreprises 
                SET address_1 = adresse_complete 
                WHERE adresse_complete IS NOT NULL AND address_1 IS NULL
            ''')
            # Supprimer l'ancienne colonne (SQLite ne supporte pas DROP COLUMN directement)
            # On la laisse pour l'instant, elle sera ignorée
        except sqlite3.OperationalError:
            pass  # La colonne n'existe pas
        
        for col_name, col_type in new_columns:
            try:
                cursor.execute(f'ALTER TABLE entreprises ADD COLUMN {col_name} {col_type}')
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
        
        # Ajouter la colonne resume si elle n'existe pas
        try:
            cursor.execute('ALTER TABLE entreprises ADD COLUMN resume TEXT')
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
        
        # Ajouter les colonnes pour les images et icônes
        icon_columns = [
            ('og_image', 'TEXT'),
            ('favicon', 'TEXT'),
            ('logo', 'TEXT'),
            ('og_data', 'TEXT')  # Stocker toutes les données OpenGraph en JSON
        ]
        for col_name, col_type in icon_columns:
            try:
                cursor.execute(f'ALTER TABLE entreprises ADD COLUMN {col_name} {col_type}')
            except sqlite3.OperationalError:
                pass  # La colonne existe déjà
        
        # Table des campagnes email
        cursor.execute('''
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
        cursor.execute('''
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
                FOREIGN KEY (campagne_id) REFERENCES campagnes_email(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE
            )
        ''')
        
        # Table des analyses techniques
        cursor.execute('''
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
        try:
            cursor.execute('ALTER TABLE analyses_techniques ADD COLUMN cms_version TEXT')
        except sqlite3.OperationalError:
            pass  # La colonne existe déjà
        
        # Tables normalisées pour les analyses techniques
        
        # Table des plugins CMS détectés
        cursor.execute('''
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
        
        # Table des headers de sécurité analysés
        cursor.execute('''
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
        
        # Table des outils d'analytics détectés
        cursor.execute('''
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tech_cms_plugins_analysis_id ON analysis_technique_cms_plugins(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tech_security_headers_analysis_id ON analysis_technique_security_headers(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tech_analytics_analysis_id ON analysis_technique_analytics(analysis_id)')
        
        # Table des analyses OSINT
        cursor.execute('''
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
        
        # Table des sous-domaines trouvés
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_osint_subdomains (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                subdomain TEXT NOT NULL,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE,
                UNIQUE(analysis_id, subdomain)
            )
        ''')
        
        # Table des enregistrements DNS
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_osint_dns_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_id INTEGER NOT NULL,
                record_type TEXT NOT NULL,
                record_value TEXT NOT NULL,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES analyses_osint(id) ON DELETE CASCADE
            )
        ''')
        
        # Table des emails trouvés (OSINT)
        cursor.execute('''
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
        
        # Table des réseaux sociaux trouvés (OSINT)
        cursor.execute('''
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
        
        # Table des technologies détectées (OSINT)
        cursor.execute('''
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
        
        # Index pour les analyses OSINT
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_osint_subdomains_analysis_id ON analysis_osint_subdomains(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_osint_dns_analysis_id ON analysis_osint_dns_records(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_osint_emails_analysis_id ON analysis_osint_emails(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_osint_social_analysis_id ON analysis_osint_social_media(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_osint_tech_analysis_id ON analysis_osint_technologies(analysis_id)')
        
        # Table des analyses Pentest
        cursor.execute('''
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
        
        # Table des vulnérabilités détectées
        cursor.execute('''
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
        
        # Table des headers de sécurité analysés
        cursor.execute('''
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
        
        # Table des vulnérabilités CMS
        cursor.execute('''
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
        
        # Table des ports ouverts (scan réseau)
        cursor.execute('''
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
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pentest_vuln_analysis_id ON analysis_pentest_vulnerabilities(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pentest_security_headers_analysis_id ON analysis_pentest_security_headers(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pentest_cms_vuln_analysis_id ON analysis_pentest_cms_vulnerabilities(analysis_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pentest_ports_analysis_id ON analysis_pentest_open_ports(analysis_id)')
        
        # Table des scrapers
        cursor.execute('''
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
                duration REAL,
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(entreprise_id, url, scraper_type)
            )
        ''')
        
        # Table des images (optimisation BDD avec relation vers l'entreprise)
        cursor.execute('''
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
        
        # Migration: ajouter les colonnes manquantes si la table existe déjà
        try:
            cursor.execute('ALTER TABLE images ADD COLUMN entreprise_id INTEGER')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE images ADD COLUMN scraper_id INTEGER')
        except:
            pass
        
        # Index pour améliorer les performances et éviter les doublons
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_entreprise_id ON images(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_scraper_id ON images(scraper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_images_url ON images(url)')
        cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_images_entreprise_url ON images(entreprise_id, url)')
        
        # Tables normalisées pour les données des scrapers (remplace les colonnes JSON)
        
        # Table des emails scrapés
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scraper_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scraper_id INTEGER NOT NULL,
                entreprise_id INTEGER NOT NULL,
                email TEXT NOT NULL,
                page_url TEXT,
                date_found TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (scraper_id) REFERENCES scrapers(id) ON DELETE CASCADE,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                UNIQUE(scraper_id, email)
            )
        ''')
        
        # Table des téléphones scrapés
        cursor.execute('''
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
        
        # Table des profils sociaux scrapés
        cursor.execute('''
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
        
        # Table des technologies détectées
        cursor.execute('''
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
        
        # Table de liaison scraper-personnes (les personnes sont déjà dans la table personnes)
        cursor.execute('''
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
        
        # Index pour améliorer les performances
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_emails_scraper_id ON scraper_emails(scraper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_emails_entreprise_id ON scraper_emails(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_phones_scraper_id ON scraper_phones(scraper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_phones_entreprise_id ON scraper_phones(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_social_scraper_id ON scraper_social_profiles(scraper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_social_entreprise_id ON scraper_social_profiles(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_tech_scraper_id ON scraper_technologies(scraper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_tech_entreprise_id ON scraper_technologies(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_people_scraper_id ON scraper_people(scraper_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scraper_people_entreprise_id ON scraper_people(entreprise_id)')
        
        # Migration: migrer les données JSON existantes vers les tables normalisées
        try:
            # Migrer les emails
            cursor.execute('''
                INSERT OR IGNORE INTO scraper_emails (scraper_id, entreprise_id, email)
                SELECT id, entreprise_id, value
                FROM scrapers, json_each(emails)
                WHERE emails IS NOT NULL AND json_valid(emails) AND json_type(emails) = 'array'
            ''')
            
            # Migrer les téléphones
            cursor.execute('''
                INSERT OR IGNORE INTO scraper_phones (scraper_id, entreprise_id, phone)
                SELECT id, entreprise_id, 
                    CASE 
                        WHEN json_extract(value, '$.phone') IS NOT NULL THEN json_extract(value, '$.phone')
                        ELSE value
                    END
                FROM scrapers, json_each(phones)
                WHERE phones IS NOT NULL AND json_valid(phones) AND json_type(phones) = 'array'
            ''')
            
            # Migrer les profils sociaux
            cursor.execute('''
                INSERT OR IGNORE INTO scraper_social_profiles (scraper_id, entreprise_id, platform, url)
                SELECT id, entreprise_id, key, 
                    CASE 
                        WHEN json_extract(value, '$.url') IS NOT NULL THEN json_extract(value, '$.url')
                        ELSE value
                    END
                FROM scrapers, json_each(social_profiles), json_each(json_each.value)
                WHERE social_profiles IS NOT NULL AND json_valid(social_profiles) AND json_type(social_profiles) = 'object'
            ''')
            
            # Migrer les technologies
            cursor.execute('''
                INSERT OR IGNORE INTO scraper_technologies (scraper_id, entreprise_id, category, name)
                SELECT id, entreprise_id, key, value
                FROM scrapers, json_each(technologies), json_each(json_each.value)
                WHERE technologies IS NOT NULL AND json_valid(technologies) AND json_type(technologies) = 'object'
            ''')
            
            # Migrer les personnes
            cursor.execute('''
                INSERT OR IGNORE INTO scraper_people (scraper_id, entreprise_id, name, title, email, linkedin_url)
                SELECT id, entreprise_id,
                    json_extract(value, '$.name'),
                    json_extract(value, '$.title'),
                    json_extract(value, '$.email'),
                    json_extract(value, '$.linkedin_url')
                FROM scrapers, json_each(people)
                WHERE people IS NOT NULL AND json_valid(people) AND json_type(people) = 'array'
            ''')
        except Exception as e:
            # Si la migration échoue, on continue (peut-être que les tables n'existent pas encore ou données invalides)
            pass
        
        # Ajouter les nouvelles colonnes si elles n'existent pas (migration)
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN phones TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN social_profiles TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN technologies TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN metadata TEXT')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN total_phones INTEGER DEFAULT 0')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN total_social_profiles INTEGER DEFAULT 0')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN total_technologies INTEGER DEFAULT 0')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN total_metadata INTEGER DEFAULT 0')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN total_images INTEGER DEFAULT 0')
        except:
            pass
        
        # Migration: ajouter date_creation et date_modification si elles n'existent pas
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        except:
            pass
        try:
            cursor.execute('ALTER TABLE scrapers ADD COLUMN date_modification TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        except:
            pass
        
        # Migration: si date_scraping existe mais pas date_modification, copier la valeur
        try:
            cursor.execute('''
                UPDATE scrapers 
                SET date_modification = date_scraping 
                WHERE date_modification IS NULL AND date_scraping IS NOT NULL
            ''')
            cursor.execute('''
                UPDATE scrapers 
                SET date_creation = date_scraping 
                WHERE date_creation IS NULL AND date_scraping IS NOT NULL
            ''')
        except:
            pass
        
        # Nettoyer les doublons avant de créer l'index unique
        # Garder seulement le scraper le plus récent pour chaque (entreprise_id, url, scraper_type)
        try:
            # Supprimer les doublons en gardant le plus récent (par date_modification ou date_scraping ou date_creation)
            cursor.execute('''
                DELETE FROM scrapers
                WHERE id NOT IN (
                    SELECT id FROM (
                        SELECT id, ROW_NUMBER() OVER (
                            PARTITION BY entreprise_id, url, scraper_type 
                            ORDER BY COALESCE(date_modification, date_scraping, date_creation) DESC
                        ) as rn
                        FROM scrapers
                    ) WHERE rn = 1
                )
            ''')
        except:
            # Fallback: si ROW_NUMBER n'est pas supporté, garder le plus récent par ID (moins précis mais fonctionne)
            try:
                cursor.execute('''
                    DELETE FROM scrapers
                    WHERE id NOT IN (
                        SELECT MAX(id)
                        FROM scrapers
                        GROUP BY entreprise_id, url, scraper_type
                    )
                ''')
            except:
                pass
        
        # Créer un index unique sur (entreprise_id, url, scraper_type) pour éviter les doublons
        try:
            cursor.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_scrapers_unique ON scrapers(entreprise_id, url, scraper_type)')
        except:
            pass
        
        # Table des personnes (liées aux entreprises)
        cursor.execute('''
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
                date_creation TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                date_mise_a_jour TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (entreprise_id) REFERENCES entreprises(id) ON DELETE CASCADE,
                FOREIGN KEY (manager_id) REFERENCES personnes(id) ON DELETE SET NULL
            )
        ''')
        
        # Index pour performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entreprises_analyse ON entreprises(analyse_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entreprises_nom ON entreprises(nom)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entreprises_secteur ON entreprises(secteur)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_entreprises_geo ON entreprises(longitude, latitude)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_emails_campagne ON emails_envoyes(campagne_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_tech_entreprise ON analyses_techniques(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_osint_entreprise ON analyses_osint(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_pentest_entreprise ON analyses_pentest(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrapers_entreprise ON scrapers(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scrapers_url ON scrapers(url)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_personnes_entreprise ON personnes(entreprise_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_personnes_manager ON personnes(manager_id)')
        
        conn.commit()
        conn.close()
        
        # Migration : recréer les contraintes avec ON DELETE CASCADE si nécessaire
        self.migrate_foreign_keys_cascade()
    
    def migrate_foreign_keys_cascade(self):
        """
        Migre les contraintes de clés étrangères pour ajouter ON DELETE CASCADE.
        Cette méthode recrée les tables si nécessaire pour les bases existantes.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Vérifier si la migration a déjà été effectuée
            cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='_migrations'
            ''')
            if not cursor.fetchone():
                cursor.execute('CREATE TABLE _migrations (name TEXT PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
            
            cursor.execute('SELECT name FROM _migrations WHERE name = ?', ('foreign_keys_cascade',))
            if cursor.fetchone():
                # Migration déjà effectuée
                conn.close()
                return
            
            # Activer les clés étrangères
            cursor.execute('PRAGMA foreign_keys = ON')
            
            # Pour SQLite, on ne peut pas modifier une contrainte existante.
            # Les nouvelles installations auront les bonnes contraintes grâce aux CREATE TABLE modifiés.
            # Pour les bases existantes, on marque simplement la migration comme effectuée
            # car les contraintes seront appliquées lors de la prochaine recréation de la base.
            # En pratique, clear_all_data() supprime dans le bon ordre pour gérer les bases existantes.
            
            cursor.execute('INSERT INTO _migrations (name) VALUES (?)', ('foreign_keys_cascade',))
            conn.commit()
            
        except Exception as e:
            # Si la migration échoue, on continue quand même
            # Les nouvelles installations auront les bonnes contraintes
            conn.rollback()
        finally:
            conn.close()
    
    def save_analysis(self, filename, output_filename, total, parametres, duree=None):
        """Sauvegarde une analyse dans la base"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO analyses (filename, output_filename, total_entreprises, parametres, statut, duree_secondes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (filename, output_filename, total, json.dumps(parametres), 'Terminé', duree))
        
        analysis_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return analysis_id
    
    def find_duplicate_entreprise(self, nom, website=None, address_1=None, address_2=None):
        """
        Recherche si une entreprise similaire existe déjà dans la base
        
        Critères de détection de doublon (par ordre de priorité) :
        1. Nom + website identiques (le plus fiable)
        2. Nom + address_1 + address_2 identiques (si pas de website)
        3. Website seul (si nom manquant mais website présent)
        
        Args:
            nom (str): Nom de l'entreprise
            website (str, optional): Site web
            address_1 (str, optional): Adresse ligne 1
            address_2 (str, optional): Adresse ligne 2
        
        Returns:
            int or None: ID de l'entreprise existante si doublon trouvé, None sinon
        """
        if not nom:
            return None
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Normaliser les valeurs pour la comparaison (minuscules, espaces supprimés)
        def normalize(value):
            if not value:
                return None
            return str(value).lower().strip()
        
        nom_norm = normalize(nom)
        website_norm = normalize(website)
        address_1_norm = normalize(address_1)
        address_2_norm = normalize(address_2)
        
        # Critère 1: Nom + website identiques
        if nom_norm and website_norm:
            cursor.execute('''
                SELECT id FROM entreprises 
                WHERE LOWER(TRIM(nom)) = ? 
                AND LOWER(TRIM(website)) = ?
                LIMIT 1
            ''', (nom_norm, website_norm))
            row = cursor.fetchone()
            if row:
                conn.close()
                return row['id']
        
        # Critère 2: Nom + address_1 + address_2 identiques (si pas de website ou website différent)
        if nom_norm and address_1_norm and address_2_norm:
            cursor.execute('''
                SELECT id FROM entreprises 
                WHERE LOWER(TRIM(nom)) = ? 
                AND LOWER(TRIM(address_1)) = ?
                AND LOWER(TRIM(address_2)) = ?
                LIMIT 1
            ''', (nom_norm, address_1_norm, address_2_norm))
            row = cursor.fetchone()
            if row:
                conn.close()
                return row['id']
        
        # Critère 3: Website seul (si nom manquant ou très différent mais même site)
        # On évite ce critère car plusieurs entreprises peuvent partager un site
        # Mais on le garde comme dernier recours si vraiment pas d'autres infos
        
        conn.close()
        return None
    
    def save_entreprise(self, analyse_id, entreprise_data, skip_duplicates=True):
        """
        Sauvegarde une entreprise analysée
        
        Args:
            analyse_id (int): ID de l'analyse associée
            entreprise_data (dict): Données de l'entreprise
            skip_duplicates (bool): Si True, ne pas insérer si doublon trouvé (retourne l'ID existant)
        
        Returns:
            int or None: ID de l'entreprise (nouvelle ou existante), None si doublon et skip_duplicates=True
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Mapper les champs Excel vers les champs de la base de données
        # Supporte les noms de colonnes Excel standards
        nom = entreprise_data.get('name') or entreprise_data.get('nom')
        website = entreprise_data.get('website')
        secteur = entreprise_data.get('secteur') or entreprise_data.get('category_translate') or entreprise_data.get('category')
        telephone = entreprise_data.get('phone_number') or entreprise_data.get('telephone')
        pays = entreprise_data.get('country') or entreprise_data.get('pays')
        address_1 = entreprise_data.get('address_1')
        address_2 = entreprise_data.get('address_2')
        
        # Si address_full existe mais pas address_1/address_2, utiliser address_full pour address_1
        if not address_1 and not address_2:
            address_full = entreprise_data.get('address_full')
            if address_full:
                # Mettre address_full dans address_1 si on n'a pas les champs séparés
                address_1 = address_full
        
        # Vérifier les doublons si activé
        if skip_duplicates and nom:
            duplicate_id = self.find_duplicate_entreprise(nom, website, address_1, address_2)
            if duplicate_id:
                conn.close()
                return duplicate_id  # Retourner l'ID de l'entreprise existante
        
        # Gérer longitude et latitude (peuvent être des strings ou des floats)
        longitude = entreprise_data.get('longitude')
        if longitude is not None:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = None
        
        latitude = entreprise_data.get('latitude')
        if latitude is not None:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = None
        
        # Gérer rating et reviews_count
        note_google = entreprise_data.get('rating')
        if note_google is not None:
            try:
                note_google = float(note_google)
            except (ValueError, TypeError):
                note_google = None
        
        nb_avis_google = entreprise_data.get('reviews_count')
        if nb_avis_google is not None:
            try:
                nb_avis_google = int(nb_avis_google)
            except (ValueError, TypeError):
                nb_avis_google = None
        
        # Gérer longitude et latitude (peuvent être des strings ou des floats)
        longitude = entreprise_data.get('longitude')
        if longitude is not None:
            try:
                longitude = float(longitude)
            except (ValueError, TypeError):
                longitude = None
        
        latitude = entreprise_data.get('latitude')
        if latitude is not None:
            try:
                latitude = float(latitude)
            except (ValueError, TypeError):
                latitude = None
        
        # Gérer rating et reviews_count
        note_google = entreprise_data.get('rating')
        if note_google is not None:
            try:
                note_google = float(note_google)
            except (ValueError, TypeError):
                note_google = None
        
        nb_avis_google = entreprise_data.get('reviews_count')
        if nb_avis_google is not None:
            try:
                nb_avis_google = int(nb_avis_google)
            except (ValueError, TypeError):
                nb_avis_google = None
        
        # Récupérer le résumé (peut venir sous plusieurs formes: str, NaN, None)
        resume = entreprise_data.get('resume')
        # Normaliser le résumé: NaN ou chaîne vide -> None
        try:
            import math
            if resume is not None:
                # Gérer le cas pandas.NaT / NaN
                if isinstance(resume, float) and math.isnan(resume):
                    resume = None
                elif isinstance(resume, str) and resume.strip() == '':
                    resume = None
        except Exception:
            if isinstance(resume, str) and resume.strip() == '':
                resume = None
        
        # Récupérer les images et icônes depuis les métadonnées
        metadata = entreprise_data.get('metadata', {})
        # Si les métadonnées sont sérialisées en JSON (string), les désérialiser
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        
        icons = metadata.get('icons', {}) if isinstance(metadata, dict) else {}
        og_tags = metadata.get('open_graph', {}) if isinstance(metadata, dict) else {}
        
        # Extraire les URLs d'images (convertir en URLs absolues si nécessaire)
        og_image = icons.get('og_image') or None
        favicon = icons.get('favicon') or None
        logo = icons.get('logo') or None
        
        # Si les URLs sont relatives, les convertir en absolues avec le website
        if website:
            from urllib.parse import urljoin
            if og_image and not og_image.startswith(('http://', 'https://')):
                og_image = urljoin(website, og_image)
            if favicon and not favicon.startswith(('http://', 'https://')):
                favicon = urljoin(website, favicon)
            if logo and not logo.startswith(('http://', 'https://')):
                logo = urljoin(website, logo)
        
        # Stocker toutes les données OpenGraph en JSON
        og_data_json = None
        if og_tags:
            try:
                og_data_json = json.dumps(og_tags, ensure_ascii=False)
            except Exception:
                og_data_json = None
        
        cursor.execute('''
            INSERT INTO entreprises (
                analyse_id, nom, website, secteur, statut, opportunite,
                email_principal, responsable, taille_estimee, hosting_provider,
                framework, score_securite, telephone, pays, address_1, address_2,
                longitude, latitude, note_google, nb_avis_google, resume, og_image, favicon, logo, og_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analyse_id,
            nom,
            website,
            secteur,
            entreprise_data.get('statut'),
            entreprise_data.get('site_opportunity'),
            entreprise_data.get('email_principal'),
            entreprise_data.get('responsable'),
            entreprise_data.get('taille_estimee'),
            entreprise_data.get('hosting_provider'),
            entreprise_data.get('framework'),
            entreprise_data.get('security_score'),
            telephone,
            pays,
            entreprise_data.get('address_1'),
            entreprise_data.get('address_2'),
            longitude,
            latitude,
            note_google,
            nb_avis_google,
            resume,
            og_image,
            favicon,
            logo,
            og_data_json
        ))
        
        entreprise_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return entreprise_id
    
    def get_analyses(self, limit=50):
        """Récupère les analyses récentes"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM analyses
            ORDER BY date_creation DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_entreprises(self, analyse_id=None, filters=None):
        """Récupère les entreprises avec filtres optionnels"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM entreprises WHERE 1=1'
        params = []
        
        if analyse_id:
            query += ' AND analyse_id = ?'
            params.append(analyse_id)
        
        if filters:
            if filters.get('secteur'):
                query += ' AND secteur = ?'
                params.append(filters['secteur'])
            if filters.get('statut'):
                query += ' AND statut = ?'
                params.append(filters['statut'])
            if filters.get('opportunite'):
                query += ' AND opportunite = ?'
                params.append(filters['opportunite'])
            if filters.get('favori'):
                query += ' AND favori = 1'
            if filters.get('search'):
                search_term = f"%{filters['search']}%"
                query += ' AND (nom LIKE ? OR secteur LIKE ? OR email_principal LIKE ? OR responsable LIKE ?)'
                params.extend([search_term, search_term, search_term, search_term])
        
        query += ' ORDER BY favori DESC, date_analyse DESC'
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        # Parser les tags et données OpenGraph pour chaque entreprise
        entreprises = []
        for row in rows:
            entreprise = dict(row)
            if entreprise.get('tags'):
                try:
                    entreprise['tags'] = json.loads(entreprise['tags']) if isinstance(entreprise['tags'], str) else entreprise['tags']
                except:
                    entreprise['tags'] = []
            else:
                entreprise['tags'] = []
            
            # Parser les données OpenGraph si présentes
            if entreprise.get('og_data'):
                try:
                    entreprise['og_data'] = json.loads(entreprise['og_data']) if isinstance(entreprise['og_data'], str) else entreprise['og_data']
                except:
                    entreprise['og_data'] = None
            
            entreprises.append(entreprise)
        
        return entreprises
    
    def update_entreprise_tags(self, entreprise_id, tags):
        """Met à jour les tags d'une entreprise"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE entreprises SET tags = ? WHERE id = ?
        ''', (json.dumps(tags) if isinstance(tags, list) else tags, entreprise_id))
        
        conn.commit()
        conn.close()
    
    def update_entreprise_notes(self, entreprise_id, notes):
        """Met à jour les notes d'une entreprise"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE entreprises SET notes = ? WHERE id = ?
        ''', (notes, entreprise_id))
        
        conn.commit()
        conn.close()
    
    def toggle_favori(self, entreprise_id):
        """Bascule le statut favori d'une entreprise"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT favori FROM entreprises WHERE id = ?', (entreprise_id,))
        current = cursor.fetchone()[0]
        new_value = 0 if current else 1
        
        cursor.execute('UPDATE entreprises SET favori = ? WHERE id = ?', (new_value, entreprise_id))
        conn.commit()
        conn.close()
        
        return new_value == 1
    
    def get_statistics(self):
        """Récupère les statistiques globales"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total analyses
        cursor.execute('SELECT COUNT(*) FROM analyses')
        stats['total_analyses'] = cursor.fetchone()[0]
        
        # Total entreprises
        cursor.execute('SELECT COUNT(*) FROM entreprises')
        stats['total_entreprises'] = cursor.fetchone()[0]
        
        # Par secteur
        cursor.execute('''
            SELECT secteur, COUNT(*) as count
            FROM entreprises
            WHERE secteur IS NOT NULL
            GROUP BY secteur
            ORDER BY count DESC
            LIMIT 10
        ''')
        stats['par_secteur'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Par opportunité
        cursor.execute('''
            SELECT opportunite, COUNT(*) as count
            FROM entreprises
            WHERE opportunite IS NOT NULL
            GROUP BY opportunite
        ''')
        stats['par_opportunite'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Par statut
        cursor.execute('''
            SELECT statut, COUNT(*) as count
            FROM entreprises
            WHERE statut IS NOT NULL
            GROUP BY statut
        ''')
        stats['par_statut'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Favoris
        cursor.execute('SELECT COUNT(*) FROM entreprises WHERE favori = 1')
        stats['favoris'] = cursor.fetchone()[0]
        
        conn.close()
        
        return stats
    
    def save_technical_analysis(self, entreprise_id, url, tech_data):
        """Sauvegarde une analyse technique avec normalisation des données"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Extraire le domaine de l'URL
        domain = url.replace('http://', '').replace('https://', '').split('/')[0].replace('www.', '')
        
        # Sauvegarder l'analyse principale (sans les données JSON normalisées)
        cursor.execute('''
            INSERT INTO analyses_techniques (
                entreprise_id, url, domain, ip_address, server_software,
                framework, framework_version, cms, cms_version, hosting_provider,
                domain_creation_date, domain_updated_date, domain_registrar,
                ssl_valid, ssl_expiry_date, waf, cdn,
                seo_meta, performance_metrics, nmap_scan, technical_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            json.dumps(tech_data) if tech_data else None
        ))
        
        analysis_id = cursor.lastrowid
        
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
                        cursor.execute('''
                            INSERT OR IGNORE INTO analysis_technique_cms_plugins (analysis_id, plugin_name, version)
                            VALUES (?, ?, ?)
                        ''', (analysis_id, plugin_name, plugin_version))
        
        # Sauvegarder les headers de sécurité dans la table normalisée
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
                    cursor.execute('''
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
                        cursor.execute('''
                            INSERT OR IGNORE INTO analysis_technique_analytics (analysis_id, tool_name, tool_id)
                            VALUES (?, ?, ?)
                        ''', (analysis_id, tool_name, tool_id))
        
        conn.commit()
        conn.close()
        
        return analysis_id
    
    def _load_technical_analysis_normalized_data(self, cursor, analysis_id):
        """Charge les données normalisées d'une analyse technique"""
        # Charger les plugins CMS
        cursor.execute('''
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
        cursor.execute('''
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
        cursor.execute('''
            SELECT tool_name, tool_id FROM analysis_technique_analytics
            WHERE analysis_id = ?
        ''', (analysis_id,))
        analytics = []
        for analytics_row in cursor.fetchall():
            tool = {'name': analytics_row['tool_name']}
            if analytics_row['tool_id']:
                tool['id'] = analytics_row['tool_id']
            analytics.append(tool)
        
        return {
            'cms_plugins': plugins,
            'security_headers': headers,
            'analytics': analytics
        }
    
    def get_technical_analysis(self, entreprise_id):
        """Récupère l'analyse technique d'une entreprise avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def _load_osint_analysis_normalized_data(self, cursor, analysis_id):
        """Charge les données normalisées d'une analyse OSINT"""
        # Charger les sous-domaines
        cursor.execute('SELECT subdomain FROM analysis_osint_subdomains WHERE analysis_id = ?', (analysis_id,))
        subdomains = [row['subdomain'] for row in cursor.fetchall()]
        
        # Charger les enregistrements DNS
        cursor.execute('SELECT record_type, record_value FROM analysis_osint_dns_records WHERE analysis_id = ?', (analysis_id,))
        dns_records = {}
        for row in cursor.fetchall():
            record_type = row['record_type']
            if record_type not in dns_records:
                dns_records[record_type] = []
            dns_records[record_type].append(row['record_value'])
        
        # Charger les emails
        cursor.execute('SELECT email, source FROM analysis_osint_emails WHERE analysis_id = ?', (analysis_id,))
        emails = []
        for row in cursor.fetchall():
            email = {'email': row['email']}
            if row['source']:
                email['source'] = row['source']
            emails.append(email)
        
        # Charger les réseaux sociaux
        cursor.execute('SELECT platform, url FROM analysis_osint_social_media WHERE analysis_id = ?', (analysis_id,))
        social_media = {}
        for row in cursor.fetchall():
            platform = row['platform']
            if platform not in social_media:
                social_media[platform] = []
            social_media[platform].append(row['url'])
        
        # Charger les technologies
        cursor.execute('SELECT category, name FROM analysis_osint_technologies WHERE analysis_id = ?', (analysis_id,))
        technologies = {}
        for row in cursor.fetchall():
            category = row['category']
            if category not in technologies:
                technologies[category] = []
            technologies[category].append(row['name'])
        
        return {
            'subdomains': subdomains,
            'dns_records': dns_records,
            'emails': emails,
            'emails_found': emails,  # Compatibilité
            'social_media': social_media,
            'technologies_detected': technologies,
            'technologies': technologies  # Compatibilité
        }
    
    def get_osint_analysis_by_entreprise(self, entreprise_id):
        """Récupère l'analyse OSINT d'une entreprise avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
    
    def _load_pentest_analysis_normalized_data(self, cursor, analysis_id):
        """Charge les données normalisées d'une analyse Pentest"""
        # Charger les vulnérabilités
        cursor.execute('''
            SELECT name, severity, description, recommendation 
            FROM analysis_pentest_vulnerabilities 
            WHERE analysis_id = ?
        ''', (analysis_id,))
        vulnerabilities = []
        for row in cursor.fetchall():
            vuln = {'name': row['name']}
            if row['severity']:
                vuln['severity'] = row['severity']
            if row['description']:
                vuln['description'] = row['description']
            if row['recommendation']:
                vuln['recommendation'] = row['recommendation']
            vulnerabilities.append(vuln)
        
        # Charger les headers de sécurité
        cursor.execute('SELECT header_name, status FROM analysis_pentest_security_headers WHERE analysis_id = ?', (analysis_id,))
        security_headers = {}
        for row in cursor.fetchall():
            security_headers[row['header_name']] = {'status': row['status']}
        
        # Charger les vulnérabilités CMS
        cursor.execute('''
            SELECT name, severity, description 
            FROM analysis_pentest_cms_vulnerabilities 
            WHERE analysis_id = ?
        ''', (analysis_id,))
        cms_vulnerabilities = {}
        for row in cursor.fetchall():
            cms_vulnerabilities[row['name']] = {
                'severity': row['severity'],
                'description': row['description']
            }
        
        # Charger les ports ouverts
        cursor.execute('SELECT port, service FROM analysis_pentest_open_ports WHERE analysis_id = ?', (analysis_id,))
        open_ports = []
        for row in cursor.fetchall():
            port_data = {'port': row['port']}
            if row['service']:
                port_data['service'] = row['service']
            open_ports.append(port_data)
        
        return {
            'vulnerabilities': vulnerabilities,
            'security_headers': security_headers,
            'security_headers_analysis': security_headers,  # Compatibilité
            'cms_vulnerabilities': cms_vulnerabilities,
            'open_ports': open_ports
        }
    
    def get_pentest_analysis_by_entreprise(self, entreprise_id):
        """Récupère l'analyse Pentest d'une entreprise avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM analyses_pentest
            WHERE entreprise_id = ?
            ORDER BY date_analyse DESC
            LIMIT 1
        ''', (entreprise_id,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_pentest_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Ajouter les ports ouverts au network_scan si présent
            if 'network_scan' in analysis and analysis['network_scan']:
                try:
                    network_scan = json.loads(analysis['network_scan']) if isinstance(analysis['network_scan'], str) else analysis['network_scan']
                    if isinstance(network_scan, dict):
                        network_scan['open_ports'] = normalized['open_ports']
                        analysis['network_scan'] = network_scan
                except:
                    pass
            
            # Parser les autres champs JSON
            json_fields = ['sql_injection', 'xss_vulnerabilities', 'csrf_vulnerabilities',
                          'authentication_issues', 'authorization_issues', 'sensitive_data_exposure',
                          'ssl_tls_analysis', 'waf_detection', 'api_security', 'pentest_details']
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_all_technical_analyses(self, limit=100):
        """Récupère toutes les analyses techniques avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details']:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            analyses.append(analysis)
        
        conn.close()
        return analyses
    
    def get_technical_analysis_by_id(self, analysis_id):
        """Récupère une analyse technique par son ID avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details']:
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
        """Récupère une analyse technique par son URL avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
            for field in ['seo_meta', 'performance_metrics', 'nmap_scan', 'technical_details']:
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
        """Met à jour une analyse technique avec normalisation"""
        # Supprimer les anciennes données normalisées
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM analysis_technique_cms_plugins WHERE analysis_id = ?', (analysis_id,))
        cursor.execute('DELETE FROM analysis_technique_security_headers WHERE analysis_id = ?', (analysis_id,))
        cursor.execute('DELETE FROM analysis_technique_analytics WHERE analysis_id = ?', (analysis_id,))
        conn.commit()
        conn.close()
        
        # Réutiliser save_technical_analysis qui gère déjà la normalisation
        # Mais d'abord récupérer l'entreprise_id et l'url
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT entreprise_id, url FROM analyses_techniques WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            entreprise_id = row['entreprise_id']
            url = row['url'] or tech_data.get('url', '')
            # Supprimer l'ancienne analyse et en créer une nouvelle
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM analyses_techniques WHERE id = ?', (analysis_id,))
            conn.commit()
            conn.close()
            # Sauvegarder avec la nouvelle méthode normalisée
            return self.save_technical_analysis(entreprise_id, url, tech_data)
        
        return analysis_id
    
    def delete_osint_analysis(self, analysis_id):
        """Supprime une analyse OSINT"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM analyses_osint WHERE id = ?', (analysis_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return deleted
    
    def save_scraper(self, entreprise_id, url, scraper_type, emails=None, people=None, phones=None, 
                     social_profiles=None, technologies=None, metadata=None, images=None,
                     visited_urls=0, total_emails=0, total_people=0, total_phones=0,
                     total_social_profiles=0, total_technologies=0, total_metadata=0, total_images=0, duration=0):
        """
        Sauvegarde ou met à jour un scraper dans la base de données.
        Si un scraper existe déjà pour cette entreprise/URL/type, il est mis à jour.
        Sinon, un nouveau scraper est créé.
        
        Args:
            entreprise_id: ID de l'entreprise
            url: URL scrapée
            scraper_type: Type de scraper ('emails', 'people', 'phones', 'social', 'technologies', 'metadata', 'unified', 'global')
            emails: Liste des emails trouvés (JSON string ou list)
            people: Liste des personnes trouvées (JSON string ou list)
            phones: Liste des téléphones trouvés (JSON string ou list)
            social_profiles: Dictionnaire des réseaux sociaux (JSON string ou dict)
            technologies: Dictionnaire des technologies (JSON string ou dict)
            metadata: Dictionnaire des métadonnées (JSON string ou dict)
            images: Liste des images trouvées (list de dicts {url, alt, page_url, width, height})
            visited_urls: Nombre d'URLs visitées
            total_emails: Nombre total d'emails
            total_people: Nombre total de personnes
            total_phones: Nombre total de téléphones
            total_social_profiles: Nombre total de réseaux sociaux
            total_technologies: Nombre total de technologies
            total_metadata: Nombre total de métadonnées
            total_images: Nombre total d'images
            duration: Durée du scraping en secondes
        
        Returns:
            int: ID du scraper créé ou mis à jour
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Convertir en JSON si nécessaire
        emails_json = json.dumps(emails) if emails and not isinstance(emails, str) else (emails or None)
        people_json = json.dumps(people) if people and not isinstance(people, str) else (people or None)
        phones_json = json.dumps(phones) if phones and not isinstance(phones, str) else (phones or None)
        social_json = json.dumps(social_profiles) if social_profiles and not isinstance(social_profiles, str) else (social_profiles or None)
        tech_json = json.dumps(technologies) if technologies and not isinstance(technologies, str) else (technologies or None)
        metadata_json = json.dumps(metadata) if metadata and not isinstance(metadata, str) else (metadata or None)
        
        # Vérifier si un scraper existe déjà pour cette entreprise/URL/type
        cursor.execute('''
            SELECT id FROM scrapers 
            WHERE entreprise_id = ? AND url = ? AND scraper_type = ?
        ''', (entreprise_id, url, scraper_type))
        
        existing = cursor.fetchone()
        
        if existing:
            # UPDATE: mettre à jour le scraper existant
            scraper_id = existing['id']
            cursor.execute('''
                UPDATE scrapers SET
                    emails = ?,
                    people = ?,
                    phones = ?,
                    social_profiles = ?,
                    technologies = ?,
                    metadata = ?,
                    visited_urls = ?,
                    total_emails = ?,
                    total_people = ?,
                    total_phones = ?,
                    total_social_profiles = ?,
                    total_technologies = ?,
                    total_metadata = ?,
                    total_images = ?,
                    duration = ?,
                    date_modification = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                emails_json, people_json, phones_json, social_json, tech_json, metadata_json,
                visited_urls, total_emails, total_people, total_phones,
                total_social_profiles, total_technologies, total_metadata, total_images, duration,
                scraper_id
            ))
        else:
            # INSERT: créer un nouveau scraper
            cursor.execute('''
                INSERT INTO scrapers (
                    entreprise_id, url, scraper_type, emails, people, phones, social_profiles, 
                    technologies, metadata, visited_urls, total_emails, total_people, total_phones,
                    total_social_profiles, total_technologies, total_metadata, total_images, duration,
                    date_creation, date_modification
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ''', (
                entreprise_id, url, scraper_type, emails_json, people_json, phones_json, 
                social_json, tech_json, metadata_json, visited_urls, total_emails, total_people,
                total_phones, total_social_profiles, total_technologies, total_metadata, total_images, duration
            ))
            scraper_id = cursor.lastrowid
        
        # Sauvegarder les données normalisées dans les tables séparées (au lieu de JSON)
        # Utiliser la même connexion pour éviter les verrouillages
        if emails:
            self._save_scraper_emails_in_transaction(cursor, scraper_id, entreprise_id, emails)
        if phones:
            self._save_scraper_phones_in_transaction(cursor, scraper_id, entreprise_id, phones)
        if social_profiles:
            self._save_scraper_social_profiles_in_transaction(cursor, scraper_id, entreprise_id, social_profiles)
        if technologies:
            self._save_scraper_technologies_in_transaction(cursor, scraper_id, entreprise_id, technologies)
        if people:
            self._save_scraper_people_in_transaction(cursor, scraper_id, entreprise_id, people)
        
        # Sauvegarder les images dans la table séparée (optimisation BDD, liées à l'entreprise)
        if images and isinstance(images, list) and len(images) > 0:
            self._save_images_in_transaction(cursor, entreprise_id, scraper_id, images)
        
        conn.commit()
        conn.close()
        
        return scraper_id
    
    def _save_scraper_emails_in_transaction(self, cursor, scraper_id, entreprise_id, emails):
        """Sauvegarde les emails dans la transaction en cours"""
        if not emails:
            return
        
        # Supprimer les anciens emails de ce scraper
        cursor.execute('DELETE FROM scraper_emails WHERE scraper_id = ?', (scraper_id,))
        
        # Désérialiser si nécessaire
        if isinstance(emails, str):
            try:
                emails = json.loads(emails)
            except:
                return
        
        if not isinstance(emails, list):
            return
        
        # Insérer les nouveaux emails
        for email in emails:
            if isinstance(email, dict):
                email_str = email.get('email') or email.get('value') or str(email)
                page_url = email.get('page_url')
            else:
                email_str = str(email)
                page_url = None
            
            if email_str:
                cursor.execute('''
                    INSERT OR IGNORE INTO scraper_emails (scraper_id, entreprise_id, email, page_url)
                    VALUES (?, ?, ?, ?)
                ''', (scraper_id, entreprise_id, email_str, page_url))
    
    def save_scraper_emails(self, scraper_id, entreprise_id, emails):
        """
        Sauvegarde les emails dans la table scraper_emails (normalisation BDD)
        
        Args:
            scraper_id: ID du scraper
            entreprise_id: ID de l'entreprise
            emails: Liste d'emails (string ou list)
        """
        if not emails:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_emails_in_transaction(cursor, scraper_id, entreprise_id, emails)
        conn.commit()
        conn.close()
    
    def _save_scraper_phones_in_transaction(self, cursor, scraper_id, entreprise_id, phones):
        """Sauvegarde les téléphones dans la transaction en cours"""
        if not phones:
            return
        
        cursor.execute('DELETE FROM scraper_phones WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(phones, str):
            try:
                phones = json.loads(phones)
            except:
                return
        
        if not isinstance(phones, list):
            return
        
        for phone in phones:
            if isinstance(phone, dict):
                phone_str = phone.get('phone') or phone.get('value') or str(phone)
                page_url = phone.get('page_url')
            else:
                phone_str = str(phone)
                page_url = None
            
            if phone_str:
                cursor.execute('''
                    INSERT OR IGNORE INTO scraper_phones (scraper_id, entreprise_id, phone, page_url)
                    VALUES (?, ?, ?, ?)
                ''', (scraper_id, entreprise_id, phone_str, page_url))
    
    def save_scraper_phones(self, scraper_id, entreprise_id, phones):
        """Sauvegarde les téléphones dans la table scraper_phones (normalisation BDD)"""
        if not phones:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_phones_in_transaction(cursor, scraper_id, entreprise_id, phones)
        conn.commit()
        conn.close()
    
    def _save_scraper_social_profiles_in_transaction(self, cursor, scraper_id, entreprise_id, social_profiles):
        """Sauvegarde les profils sociaux dans la transaction en cours"""
        if not social_profiles:
            return
        
        cursor.execute('DELETE FROM scraper_social_profiles WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(social_profiles, str):
            try:
                social_profiles = json.loads(social_profiles)
            except:
                return
        
        if not isinstance(social_profiles, dict):
            return
        
        for platform, urls in social_profiles.items():
            if not urls:
                continue
            
            if not isinstance(urls, list):
                urls = [urls]
            
            for url_data in urls:
                if isinstance(url_data, dict):
                    url_str = url_data.get('url') or str(url_data)
                    page_url = url_data.get('page_url')
                else:
                    url_str = str(url_data)
                    page_url = None
                
                if url_str:
                    cursor.execute('''
                        INSERT OR IGNORE INTO scraper_social_profiles (scraper_id, entreprise_id, platform, url, page_url)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (scraper_id, entreprise_id, platform, url_str, page_url))
    
    def save_scraper_social_profiles(self, scraper_id, entreprise_id, social_profiles):
        """Sauvegarde les profils sociaux dans la table scraper_social_profiles (normalisation BDD)"""
        if not social_profiles:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_social_profiles_in_transaction(cursor, scraper_id, entreprise_id, social_profiles)
        conn.commit()
        conn.close()
    
    def _save_scraper_technologies_in_transaction(self, cursor, scraper_id, entreprise_id, technologies):
        """Sauvegarde les technologies dans la transaction en cours"""
        if not technologies:
            return
        
        cursor.execute('DELETE FROM scraper_technologies WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(technologies, str):
            try:
                technologies = json.loads(technologies)
            except:
                return
        
        if not isinstance(technologies, dict):
            return
        
        for category, techs in technologies.items():
            if not techs:
                continue
            
            if not isinstance(techs, list):
                techs = [techs]
            
            for tech in techs:
                tech_name = str(tech)
                if tech_name:
                    cursor.execute('''
                        INSERT OR IGNORE INTO scraper_technologies (scraper_id, entreprise_id, category, name)
                        VALUES (?, ?, ?, ?)
                    ''', (scraper_id, entreprise_id, category, tech_name))
    
    def save_scraper_technologies(self, scraper_id, entreprise_id, technologies):
        """Sauvegarde les technologies dans la table scraper_technologies (normalisation BDD)"""
        if not technologies:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_technologies_in_transaction(cursor, scraper_id, entreprise_id, technologies)
        conn.commit()
        conn.close()
    
    def _save_scraper_people_in_transaction(self, cursor, scraper_id, entreprise_id, people):
        """Sauvegarde les personnes dans la transaction en cours"""
        if not people:
            return
        
        cursor.execute('DELETE FROM scraper_people WHERE scraper_id = ?', (scraper_id,))
        
        if isinstance(people, str):
            try:
                people = json.loads(people)
            except:
                return
        
        if not isinstance(people, list):
            return
        
        for person in people:
            if not isinstance(person, dict):
                continue
            
            name = person.get('name')
            title = person.get('title')
            email = person.get('email')
            linkedin_url = person.get('linkedin_url')
            page_url = person.get('page_url')
            person_id = person.get('person_id')
            
            if name or email:
                cursor.execute('''
                    INSERT INTO scraper_people (scraper_id, entreprise_id, person_id, name, title, email, linkedin_url, page_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (scraper_id, entreprise_id, person_id, name, title, email, linkedin_url, page_url))
    
    def save_scraper_people(self, scraper_id, entreprise_id, people):
        """Sauvegarde les personnes dans la table scraper_people (normalisation BDD)"""
        if not people:
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_scraper_people_in_transaction(cursor, scraper_id, entreprise_id, people)
        conn.commit()
        conn.close()
    
    def _save_images_in_transaction(self, cursor, entreprise_id, scraper_id, images):
        """Sauvegarde les images dans la transaction en cours"""
        if not images or not isinstance(images, list):
            return
        
        for img in images:
            url = img.get('url')
            if not url:
                continue
            
            cursor.execute('''
                INSERT OR IGNORE INTO images (entreprise_id, scraper_id, url, alt_text, page_url, width, height)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                entreprise_id,
                scraper_id,
                url,
                img.get('alt') or None,
                img.get('page_url') or None,
                img.get('width'),
                img.get('height')
            ))
    
    def save_images(self, entreprise_id, scraper_id, images):
        """
        Sauvegarde les images dans la table images (optimisation BDD)
        
        Args:
            entreprise_id: ID de l'entreprise
            scraper_id: ID du scraper (optionnel, pour la traçabilité)
            images: Liste d'objets {url, alt, page_url, width, height}
        """
        if not images or not isinstance(images, list):
            return
        
        conn = self.get_connection()
        cursor = conn.cursor()
        self._save_images_in_transaction(cursor, entreprise_id, scraper_id, images)
        conn.commit()
        conn.close()
    
    def get_images_by_scraper(self, scraper_id):
        """
        Récupère toutes les images d'un scraper
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des images
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, entreprise_id, scraper_id, url, alt_text, page_url, width, height, date_found
            FROM images
            WHERE scraper_id = ?
            ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_scraper_emails(self, scraper_id):
        """
        Récupère les emails d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des emails (strings)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT email FROM scraper_emails WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [row['email'] for row in rows]
    
    def get_scraper_phones(self, scraper_id):
        """
        Récupère les téléphones d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des téléphones (dicts avec phone et page_url)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT phone, page_url FROM scraper_phones WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{'phone': row['phone'], 'page_url': row['page_url']} for row in rows]
    
    def get_scraper_social_profiles(self, scraper_id):
        """
        Récupère les profils sociaux d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            dict: Dictionnaire {platform: [urls]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT platform, url FROM scraper_social_profiles WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        social_profiles = {}
        for row in rows:
            platform = row['platform']
            url = row['url']
            if platform not in social_profiles:
                social_profiles[platform] = []
            social_profiles[platform].append({'url': url})
        
        return social_profiles
    
    def get_scraper_technologies(self, scraper_id):
        """
        Récupère les technologies d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            dict: Dictionnaire {category: [names]}
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT category, name FROM scraper_technologies WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        technologies = {}
        for row in rows:
            category = row['category']
            name = row['name']
            if category not in technologies:
                technologies[category] = []
            technologies[category].append(name)
        
        return technologies
    
    def get_scraper_people(self, scraper_id):
        """
        Récupère les personnes d'un scraper depuis la table normalisée
        
        Args:
            scraper_id: ID du scraper
        
        Returns:
            list: Liste des personnes (dicts)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT person_id, name, title, email, linkedin_url, page_url 
            FROM scraper_people WHERE scraper_id = ? ORDER BY date_found DESC
        ''', (scraper_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_images_by_entreprise(self, entreprise_id):
        """
        Récupère toutes les images d'une entreprise (depuis le scraper le plus récent)
        
        Args:
            entreprise_id: ID de l'entreprise
        
        Returns:
            list: Liste des images
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, entreprise_id, scraper_id, url, alt_text, page_url, width, height, date_found
            FROM images
            WHERE entreprise_id = ?
            ORDER BY date_found DESC
        ''', (entreprise_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_scrapers_by_entreprise(self, entreprise_id):
        """
        Récupère tous les scrapers d'une entreprise avec leurs données normalisées
        
        Args:
            entreprise_id: ID de l'entreprise
        
        Returns:
            list: Liste des scrapers avec leurs données chargées depuis les tables normalisées
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM scrapers WHERE entreprise_id = ? 
            ORDER BY COALESCE(date_modification, date_creation) DESC
        ''', (entreprise_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        scrapers = []
        for row in rows:
            scraper = dict(row)
            scraper_id = scraper['id']
            
            # Charger depuis les tables normalisées
            scraper['emails'] = self.get_scraper_emails(scraper_id)
            scraper['phones'] = self.get_scraper_phones(scraper_id)
            scraper['social_profiles'] = self.get_scraper_social_profiles(scraper_id)
            scraper['technologies'] = self.get_scraper_technologies(scraper_id)
            scraper['people'] = self.get_scraper_people(scraper_id)
            
            # Metadata reste en JSON pour l'instant (structure complexe)
            if scraper.get('metadata'):
                try:
                    scraper['metadata'] = json.loads(scraper['metadata'])
                except:
                    pass
            
            scrapers.append(scraper)
        
        return scrapers
    
    def get_scraper_by_url(self, url, scraper_type):
        """
        Récupère un scraper par URL et type avec ses données normalisées
        
        Args:
            url: URL scrapée
            scraper_type: Type de scraper
        
        Returns:
            dict: Scraper ou None avec ses données chargées depuis les tables normalisées
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM scrapers WHERE url = ? AND scraper_type = ? 
            ORDER BY COALESCE(date_modification, date_scraping, date_creation) DESC LIMIT 1
        ''', (url, scraper_type))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            scraper = dict(row)
            scraper_id = scraper['id']
            
            # Charger depuis les tables normalisées
            scraper['emails'] = self.get_scraper_emails(scraper_id)
            scraper['phones'] = self.get_scraper_phones(scraper_id)
            scraper['social_profiles'] = self.get_scraper_social_profiles(scraper_id)
            scraper['technologies'] = self.get_scraper_technologies(scraper_id)
            scraper['people'] = self.get_scraper_people(scraper_id)
            
            # Metadata reste en JSON pour l'instant (structure complexe)
            if scraper.get('metadata'):
                try:
                    scraper['metadata'] = json.loads(scraper['metadata'])
                except:
                    pass
            
            return scraper
        
        return None
    
    def update_scraper(self, scraper_id, emails=None, people=None, visited_urls=None, total_emails=None, total_people=None, duration=None):
        """
        Met à jour un scraper existant
        
        Args:
            scraper_id: ID du scraper
            emails: Liste des emails (optionnel)
            people: Liste des personnes (optionnel)
            visited_urls: Nombre d'URLs visitées (optionnel)
            total_emails: Nombre total d'emails (optionnel)
            total_people: Nombre total de personnes (optionnel)
            duration: Durée du scraping (optionnel)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        if emails is not None:
            updates.append('emails = ?')
            values.append(json.dumps(emails))
        
        if people is not None:
            updates.append('people = ?')
            values.append(json.dumps(people))
        
        if visited_urls is not None:
            updates.append('visited_urls = ?')
            values.append(visited_urls)
        
        if total_emails is not None:
            updates.append('total_emails = ?')
            values.append(total_emails)
        
        if total_people is not None:
            updates.append('total_people = ?')
            values.append(total_people)
        
        if duration is not None:
            updates.append('duration = ?')
            values.append(duration)
        
        if updates:
            values.append(scraper_id)
            cursor.execute(f'''
                UPDATE scrapers SET {', '.join(updates)} WHERE id = ?
            ''', values)
            
            conn.commit()
        
        conn.close()
    
    def delete_scraper(self, scraper_id):
        """
        Supprime un scraper
        
        Args:
            scraper_id: ID du scraper à supprimer
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM scrapers WHERE id = ?', (scraper_id,))
        
        conn.commit()
        conn.close()

    def delete_pentest_analysis(self, analysis_id):
        """Supprime une analyse Pentest"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM analyses_pentest WHERE id = ?', (analysis_id,))
        deleted = cursor.rowcount > 0
        
        conn.commit()
        conn.close()
        return deleted
    
    def delete_technical_analysis(self, analysis_id):
        """Supprime une analyse technique"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM analyses_techniques WHERE id = ?', (analysis_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def save_osint_analysis(self, entreprise_id, url, osint_data):
        """Sauvegarde une analyse OSINT avec normalisation des données"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain_clean = domain.replace('www.', '') if domain else ''
        
        # Sauvegarder l'analyse principale (sans les données JSON normalisées)
        cursor.execute('''
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
        
        # Sauvegarder les sous-domaines dans la table normalisée
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
                        cursor.execute('''
                            INSERT OR IGNORE INTO analysis_osint_subdomains (analysis_id, subdomain)
                            VALUES (?, ?)
                        ''', (analysis_id, subdomain_str))
        
        # Sauvegarder les enregistrements DNS dans la table normalisée
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
                            cursor.execute('''
                                INSERT INTO analysis_osint_dns_records (analysis_id, record_type, record_value)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, record_type, record_value_str))
        
        # Sauvegarder les emails dans la table normalisée
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
                        cursor.execute('''
                            INSERT OR IGNORE INTO analysis_osint_emails (analysis_id, email, source)
                            VALUES (?, ?, ?)
                        ''', (analysis_id, email_str, source))
        
        # Sauvegarder les réseaux sociaux dans la table normalisée
        social_media = osint_data.get('social_media', {})
        if not social_media and osint_data.get('people'):
            # Si les personnes sont dans 'people', extraire leurs réseaux sociaux
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
                            cursor.execute('''
                                INSERT OR IGNORE INTO analysis_osint_social_media (analysis_id, platform, url)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, platform, url_social_str))
        
        # Sauvegarder les technologies dans la table normalisée
        technologies = osint_data.get('technologies', {})
        if technologies:
            if isinstance(technologies, str):
                try:
                    technologies = json.loads(technologies)
                except:
                    technologies = {}
            if isinstance(technologies, dict):
                for category, techs in technologies.items():
                    if not isinstance(techs, list):
                        techs = [techs]
                    for tech in techs:
                        tech_name = str(tech).strip()
                        if tech_name:
                            cursor.execute('''
                                INSERT OR IGNORE INTO analysis_osint_technologies (analysis_id, category, name)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, category, tech_name))
        
        conn.commit()
        conn.close()
        
        return analysis_id
    
    def update_osint_analysis(self, analysis_id, osint_data):
        """Met à jour une analyse OSINT existante avec normalisation"""
        # Supprimer les anciennes données normalisées
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM analysis_osint_subdomains WHERE analysis_id = ?', (analysis_id,))
        cursor.execute('DELETE FROM analysis_osint_dns_records WHERE analysis_id = ?', (analysis_id,))
        cursor.execute('DELETE FROM analysis_osint_emails WHERE analysis_id = ?', (analysis_id,))
        cursor.execute('DELETE FROM analysis_osint_social_media WHERE analysis_id = ?', (analysis_id,))
        cursor.execute('DELETE FROM analysis_osint_technologies WHERE analysis_id = ?', (analysis_id,))
        conn.commit()
        conn.close()
        
        # Réutiliser save_osint_analysis qui gère déjà la normalisation
        # Mais d'abord récupérer l'entreprise_id et l'url
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT entreprise_id, url FROM analyses_osint WHERE id = ?', (analysis_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            entreprise_id = row['entreprise_id']
            url = row['url'] or osint_data.get('url', '')
            # Supprimer l'ancienne analyse et en créer une nouvelle
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM analyses_osint WHERE id = ?', (analysis_id,))
            conn.commit()
            conn.close()
            # Sauvegarder avec la nouvelle méthode normalisée
            return self.save_osint_analysis(entreprise_id, url, osint_data)
        
        return analysis_id
    
    def get_osint_analysis_by_url(self, url):
        """Récupère une analyse OSINT par son URL avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
        """Récupère une analyse OSINT par ID avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
        """Récupère toutes les analyses OSINT avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
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
    
    def save_pentest_analysis(self, entreprise_id, url, pentest_data):
        """Sauvegarde une analyse Pentest avec normalisation des données"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path.split('/')[0]
        domain_clean = domain.replace('www.', '') if domain else ''
        
        # Sauvegarder l'analyse principale (sans les données JSON normalisées)
        cursor.execute('''
            INSERT INTO analyses_pentest (
                entreprise_id, url, domain, sql_injection, xss_vulnerabilities,
                csrf_vulnerabilities, authentication_issues, authorization_issues,
                sensitive_data_exposure, ssl_tls_analysis,
                waf_detection, api_security, network_scan,
                pentest_details, risk_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            entreprise_id,
            url,
            domain_clean,
            json.dumps(pentest_data.get('sql_injection', {})) if pentest_data.get('sql_injection') else None,
            json.dumps(pentest_data.get('xss_vulnerabilities', [])) if pentest_data.get('xss_vulnerabilities') else None,
            json.dumps(pentest_data.get('csrf_vulnerabilities', [])) if pentest_data.get('csrf_vulnerabilities') else None,
            json.dumps(pentest_data.get('authentication_issues', [])) if pentest_data.get('authentication_issues') else None,
            json.dumps(pentest_data.get('authorization_issues', [])) if pentest_data.get('authorization_issues') else None,
            json.dumps(pentest_data.get('sensitive_data_exposure', [])) if pentest_data.get('sensitive_data_exposure') else None,
            json.dumps(pentest_data.get('ssl_tls', {})) if pentest_data.get('ssl_tls') else None,
            json.dumps(pentest_data.get('waf_detection', {})) if pentest_data.get('waf_detection') else None,
            json.dumps(pentest_data.get('api_security', {})) if pentest_data.get('api_security') else None,
            json.dumps(pentest_data.get('network_scan', {})) if pentest_data.get('network_scan') else None,
            json.dumps(pentest_data) if pentest_data else None,
            pentest_data.get('risk_score', 0)
        ))
        
        analysis_id = cursor.lastrowid
        
        # Sauvegarder les vulnérabilités dans la table normalisée
        vulnerabilities = pentest_data.get('vulnerabilities', [])
        if vulnerabilities:
            if isinstance(vulnerabilities, str):
                try:
                    vulnerabilities = json.loads(vulnerabilities)
                except:
                    vulnerabilities = []
            if isinstance(vulnerabilities, list):
                for vuln in vulnerabilities:
                    if isinstance(vuln, dict):
                        name = vuln.get('name') or vuln.get('title') or str(vuln)
                        severity = vuln.get('severity') or vuln.get('level')
                        description = vuln.get('description')
                        recommendation = vuln.get('recommendation') or vuln.get('fix')
                    else:
                        name = str(vuln)
                        severity = None
                        description = None
                        recommendation = None
                    if name:
                        cursor.execute('''
                            INSERT INTO analysis_pentest_vulnerabilities (analysis_id, name, severity, description, recommendation)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (analysis_id, name, severity, description, recommendation))
        
        # Sauvegarder les headers de sécurité dans la table normalisée
        security_headers = pentest_data.get('security_headers', {})
        if security_headers:
            if isinstance(security_headers, str):
                try:
                    security_headers = json.loads(security_headers)
                except:
                    security_headers = {}
            if isinstance(security_headers, dict):
                for header_name, header_data in security_headers.items():
                    if isinstance(header_data, dict):
                        status = header_data.get('status') or header_data.get('present')
                    else:
                        status = 'present' if header_data else 'missing'
                    cursor.execute('''
                        INSERT OR REPLACE INTO analysis_pentest_security_headers (analysis_id, header_name, status)
                        VALUES (?, ?, ?)
                    ''', (analysis_id, header_name, status))
        
        # Sauvegarder les vulnérabilités CMS dans la table normalisée
        cms_vulnerabilities = pentest_data.get('cms_vulnerabilities', {})
        if cms_vulnerabilities:
            if isinstance(cms_vulnerabilities, str):
                try:
                    cms_vulnerabilities = json.loads(cms_vulnerabilities)
                except:
                    cms_vulnerabilities = {}
            if isinstance(cms_vulnerabilities, dict):
                for vuln_name, vuln_data in cms_vulnerabilities.items():
                    if isinstance(vuln_data, dict):
                        severity = vuln_data.get('severity') or vuln_data.get('level')
                        description = vuln_data.get('description')
                    else:
                        severity = None
                        description = str(vuln_data) if vuln_data else None
                    cursor.execute('''
                        INSERT INTO analysis_pentest_cms_vulnerabilities (analysis_id, name, severity, description)
                        VALUES (?, ?, ?, ?)
                    ''', (analysis_id, vuln_name, severity, description))
        
        # Sauvegarder les ports ouverts dans la table normalisée
        network_scan = pentest_data.get('network_scan', {})
        if network_scan:
            if isinstance(network_scan, str):
                try:
                    network_scan = json.loads(network_scan)
                except:
                    network_scan = {}
            if isinstance(network_scan, dict):
                open_ports = network_scan.get('open_ports', [])
                if not open_ports and network_scan.get('ports'):
                    open_ports = network_scan.get('ports', [])
                if isinstance(open_ports, list):
                    for port_data in open_ports:
                        if isinstance(port_data, dict):
                            port = port_data.get('port') or port_data.get('number')
                            service = port_data.get('service') or port_data.get('name')
                        else:
                            port = int(port_data) if isinstance(port_data, (int, str)) and str(port_data).isdigit() else None
                            service = None
                        if port:
                            cursor.execute('''
                                INSERT OR IGNORE INTO analysis_pentest_open_ports (analysis_id, port, service)
                                VALUES (?, ?, ?)
                            ''', (analysis_id, port, service))
        
        conn.commit()
        conn.close()
        
        return analysis_id
    
    def get_pentest_analysis_by_url(self, url):
        """Récupère une analyse Pentest par son URL avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ap.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_pentest ap
            LEFT JOIN entreprises e ON ap.entreprise_id = e.id
            WHERE ap.url = ?
            ORDER BY ap.date_analyse DESC
            LIMIT 1
        ''', (url,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_pentest_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Ajouter les ports ouverts au network_scan si présent
            if 'network_scan' in analysis and analysis['network_scan']:
                try:
                    network_scan = json.loads(analysis['network_scan']) if isinstance(analysis['network_scan'], str) else analysis['network_scan']
                    if isinstance(network_scan, dict):
                        network_scan['open_ports'] = normalized['open_ports']
                        analysis['network_scan'] = network_scan
                except:
                    pass
            
            # Parser les autres champs JSON
            json_fields = ['sql_injection', 'xss_vulnerabilities', 'csrf_vulnerabilities',
                         'authentication_issues', 'authorization_issues', 'sensitive_data_exposure',
                          'ssl_tls_analysis', 'waf_detection', 'api_security', 'pentest_details']
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_pentest_analysis(self, analysis_id):
        """Récupère une analyse Pentest par ID avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ap.*, e.nom as entreprise_nom, e.id as entreprise_id
            FROM analyses_pentest ap
            LEFT JOIN entreprises e ON ap.entreprise_id = e.id
            WHERE ap.id = ?
        ''', (analysis_id,))
        
        row = cursor.fetchone()
        
        if row:
            analysis = dict(row)
            
            # Charger les données normalisées
            normalized = self._load_pentest_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Ajouter les ports ouverts au network_scan si présent
            if 'network_scan' in analysis and analysis['network_scan']:
                try:
                    network_scan = json.loads(analysis['network_scan']) if isinstance(analysis['network_scan'], str) else analysis['network_scan']
                    if isinstance(network_scan, dict):
                        network_scan['open_ports'] = normalized['open_ports']
                        analysis['network_scan'] = network_scan
                except:
                    pass
            
            # Parser les autres champs JSON
            json_fields = ['sql_injection', 'xss_vulnerabilities', 'csrf_vulnerabilities',
                          'authentication_issues', 'authorization_issues', 'sensitive_data_exposure',
                          'ssl_tls_analysis', 'waf_detection', 'api_security', 'pentest_details']
            for field in json_fields:
                if analysis.get(field):
                    try:
                        analysis[field] = json.loads(analysis[field])
                    except:
                        pass
            
            conn.close()
            return analysis
        
        conn.close()
        return None
    
    def get_all_pentest_analyses(self):
        """Récupère toutes les analyses Pentest avec données normalisées"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT ap.*, e.nom as entreprise_nom
            FROM analyses_pentest ap
            LEFT JOIN entreprises e ON ap.entreprise_id = e.id
            ORDER BY ap.date_analyse DESC
        ''')
        
        rows = cursor.fetchall()
        
        analyses = []
        for row in rows:
            analysis = dict(row)
            analysis_id = analysis['id']
            
            # Charger les données normalisées
            normalized = self._load_pentest_analysis_normalized_data(cursor, analysis_id)
            analysis.update(normalized)
            
            # Ajouter le compteur pour compatibilité
            analysis['vulnerabilities_count'] = len(analysis.get('vulnerabilities', []))
            
            analyses.append(analysis)
        
        conn.close()
        return analyses
    
    def clear_all_data(self):
        """
        Vide toutes les données de la base de données.
        Les contraintes ON DELETE CASCADE s'occupent automatiquement de supprimer
        les données liées dans les tables normalisées.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        try:
            # Activer les contraintes de clés étrangères pour que les CASCADE fonctionnent
            cursor.execute('PRAGMA foreign_keys = ON')
            
            # Supprimer les tables principales dans l'ordre inverse des dépendances
            # Les ON DELETE CASCADE s'occuperont automatiquement des tables liées
            
            # 1. Supprimer les campagnes email (déclenche la suppression des emails_envoyes par CASCADE)
            cursor.execute('DELETE FROM campagnes_email')
            
            # 2. Supprimer les analyses (déclenche la suppression des entreprises avec analyse_id par CASCADE)
            cursor.execute('DELETE FROM analyses')
            
            # 3. Supprimer les scrapers (y compris ceux sans entreprise_id)
            # Cela déclenchera la suppression en cascade des tables liées :
            # - scraper_emails, scraper_phones, scraper_social_profiles, scraper_technologies, scraper_people
            # - images (via scraper_id)
            cursor.execute('DELETE FROM scrapers')
            
            # 4. Supprimer les entreprises restantes (celles sans analyse_id ou pour les bases sans CASCADE)
            # Cela déclenchera la suppression en cascade de toutes les données liées :
            # - analyses_techniques, analyses_osint, analyses_pentest
            # - scrapers (ceux avec entreprise_id, mais déjà supprimés ci-dessus)
            # - personnes
            # - emails_envoyes
            # - images (via entreprise_id)
            # - scraper_emails, scraper_phones, scraper_social_profiles, scraper_technologies, scraper_people
            cursor.execute('DELETE FROM entreprises')
            
            # Réinitialiser les séquences AUTOINCREMENT
            cursor.execute('DELETE FROM sqlite_sequence')
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_nearby_entreprises(self, latitude, longitude, radius_km=10, secteur=None, limit=50):
        """
        Trouve les entreprises proches d'un point géographique
        
        Utilise la formule de Haversine pour calculer la distance en kilomètres
        entre deux points sur la surface de la Terre.
        
        Args:
            latitude (float): Latitude du point de référence
            longitude (float): Longitude du point de référence
            radius_km (float): Rayon de recherche en kilomètres (défaut: 10 km)
            secteur (str, optional): Filtrer par secteur d'activité
            limit (int): Nombre maximum de résultats (défaut: 50)
        
        Returns:
            list: Liste de dictionnaires contenant les entreprises avec leur distance
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Formule de Haversine pour calculer la distance en km
        # R = rayon de la Terre en km (6371 km)
        haversine_query = '''
            SELECT 
                id, nom, website, secteur, statut, opportunite,
                email_principal, telephone, address_1, address_2, pays,
                longitude, latitude, note_google, nb_avis_google,
                (
                    6371 * acos(
                        cos(radians(?)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians(?)) +
                        sin(radians(?)) * sin(radians(latitude))
                    )
                ) AS distance_km
            FROM entreprises
            WHERE longitude IS NOT NULL 
                AND latitude IS NOT NULL
                AND (
                    6371 * acos(
                        cos(radians(?)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians(?)) +
                        sin(radians(?)) * sin(radians(latitude))
                    )
                ) <= ?
        '''
        
        params = [latitude, longitude, latitude, latitude, longitude, latitude, radius_km]
        
        if secteur:
            haversine_query += ' AND secteur = ?'
            params.append(secteur)
        
        haversine_query += ' ORDER BY distance_km ASC LIMIT ?'
        params.append(limit)
        
        cursor.execute(haversine_query, params)
        
        rows = cursor.fetchall()
        conn.close()
        
        entreprises = []
        for row in rows:
            entreprise = dict(row)
            # Arrondir la distance à 2 décimales
            entreprise['distance_km'] = round(entreprise['distance_km'], 2)
            entreprises.append(entreprise)
        
        return entreprises
    
    def get_entreprises_by_secteur_nearby(self, secteur, latitude, longitude, radius_km=10, limit=50):
        """
        Trouve les entreprises d'un secteur spécifique proches d'un point
        
        Utile pour analyser la concurrence locale dans un secteur donné.
        
        Args:
            secteur (str): Secteur d'activité
            latitude (float): Latitude du point de référence
            longitude (float): Longitude du point de référence
            radius_km (float): Rayon de recherche en kilomètres (défaut: 10 km)
            limit (int): Nombre maximum de résultats (défaut: 50)
        
        Returns:
            list: Liste de dictionnaires contenant les entreprises avec leur distance
        """
        return self.get_nearby_entreprises(latitude, longitude, radius_km, secteur, limit)
    
    def get_competition_analysis(self, entreprise_id, radius_km=10):
        """
        Analyse la concurrence locale pour une entreprise donnée
        
        Trouve les entreprises du même secteur dans un rayon donné.
        
        Args:
            entreprise_id (int): ID de l'entreprise de référence
            radius_km (float): Rayon de recherche en kilomètres (défaut: 10 km)
        
        Returns:
            dict: Analyse de la concurrence avec statistiques
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Récupérer l'entreprise de référence
        cursor.execute('''
            SELECT secteur, longitude, latitude FROM entreprises WHERE id = ?
        ''', (entreprise_id,))
        
        entreprise_ref = cursor.fetchone()
        if not entreprise_ref or not entreprise_ref['longitude'] or not entreprise_ref['latitude']:
            conn.close()
            return {'error': 'Entreprise introuvable ou sans coordonnées géographiques'}
        
        secteur = entreprise_ref['secteur']
        latitude = entreprise_ref['latitude']
        longitude = entreprise_ref['longitude']
        
        conn.close()
        
        # Trouver les concurrents
        concurrents = self.get_entreprises_by_secteur_nearby(
            secteur, latitude, longitude, radius_km, limit=100
        )
        
        # Filtrer l'entreprise de référence
        concurrents = [c for c in concurrents if c['id'] != entreprise_id]
        
        # Calculer les statistiques
        stats = {
            'entreprise_id': entreprise_id,
            'secteur': secteur,
            'rayon_km': radius_km,
            'total_concurrents': len(concurrents),
            'concurrents': concurrents[:20],  # Limiter à 20 pour l'affichage
            'distance_moyenne': round(sum(c['distance_km'] for c in concurrents) / len(concurrents), 2) if concurrents else 0,
            'distance_min': round(min(c['distance_km'] for c in concurrents), 2) if concurrents else 0,
            'distance_max': round(max(c['distance_km'] for c in concurrents), 2) if concurrents else 0,
            'note_moyenne': round(sum(c.get('note_google', 0) or 0 for c in concurrents) / len([c for c in concurrents if c.get('note_google')]), 2) if concurrents else 0,
            'nb_avis_total': sum(c.get('nb_avis_google', 0) or 0 for c in concurrents)
        }
        
        return stats

