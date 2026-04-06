"""
Calculateur de score d'opportunité pour les entreprises
Combine les données OSINT, Pentest et Analyse Technique pour calculer un score d'opportunité précis
"""

import json
import logging
from typing import Dict, Optional, Tuple, List

logger = logging.getLogger(__name__)


class OpportunityCalculator:
    """
    Calcule le score d'opportunité d'une entreprise en combinant plusieurs facteurs
    """
    
    def __init__(self, database=None):
        """
        Initialise le calculateur
        
        Args:
            database: Instance de Database (optionnel, pour charger les analyses)
        """
        self.database = database

    def _safe_json_list(self, value) -> List[str]:
        """
        Normalise une valeur de tags en liste de chaînes.
        """
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            txt = value.strip()
            if not txt:
                return []
            try:
                parsed = json.loads(txt)
                if isinstance(parsed, list):
                    return [str(v).strip() for v in parsed if str(v).strip()]
            except Exception:
                pass
            return [p.strip() for p in txt.split(',') if p.strip()]
        return []

    def _status_signal(self, statut: str) -> Tuple[float, List[str]]:
        """
        Score d'ajustement lié au statut CRM.
        """
        s = (statut or '').strip()
        if not s:
            return 0.0, []

        # Statuts fermés (faible opportunité commerciale)
        closed_lost = {'Perdu', 'Réponse négative', 'Bounce', 'Désabonné', 'Ne pas contacter', 'Plainte spam'}
        closed_won = {'Gagné', 'Réponse positive'}
        if s in closed_lost:
            return -14.0, ['Pipeline fermé: perdu']
        if s in closed_won:
            return -10.0, ['Pipeline fermé: gagné']

        # Pipeline actif
        if s in {'Relance', 'À rappeler'}:
            return 8.0, ['Prospect en relance active']
        if s in {'Contacté', 'En cours'}:
            return 6.0, ['Prospect déjà engagé']
        if s in {'À qualifier'}:
            return 4.0, ['Prospect à qualifier']
        if s in {'Nouveau'}:
            return 2.0, ['Prospect nouveau']
        return 1.0, [f'Statut CRM: {s}']

    def _tags_signal(self, tags: List[str]) -> Tuple[float, List[str]]:
        """
        Ajuste le score selon les tags métiers/techniques.
        """
        if not tags:
            return 0.0, []
        normalized = [t.lower() for t in tags]
        score = 0.0
        indicators = []

        positive_keywords = {
            'risque_cyber_eleve': (4.0, 'Risque cyber élevé'),
            'seo_a_ameliorer': (2.5, 'SEO à améliorer'),
            'perf_lente': (2.5, 'Performance lente'),
            'site_sans_https': (3.0, 'Site sans HTTPS'),
            'refonte': (2.5, 'Besoin de refonte'),
            'migration': (2.0, 'Potentiel de migration'),
            'wordpress': (1.5, 'CMS exploitable'),
            'prestashop': (1.5, 'E-commerce exploitable'),
            'shopify': (1.0, 'Stack e-commerce active'),
        }
        negative_keywords = {
            'ne_pas_contacter': (6.0, 'Tag ne_pas_contacter'),
            'spam': (4.0, 'Risque de plainte spam'),
            'client': (3.0, 'Déjà client / hors cible'),
        }

        for key, (pts, label) in positive_keywords.items():
            if any(key in t for t in normalized):
                score += pts
                indicators.append(label)
        for key, (pts, label) in negative_keywords.items():
            if any(key in t for t in normalized):
                score -= pts
                indicators.append(label)

        return max(-12.0, min(12.0, score)), indicators

    def _engagement_signal(self, entreprise_id: int) -> Tuple[float, List[str]]:
        """
        Mesure un signal commercial basé sur les emails envoyés/open/click.
        Retourne un score dans [-8 ; +10].
        """
        if not self.database or not hasattr(self.database, 'get_connection') or entreprise_id is None:
            return 0.0, []
        conn = None
        try:
            conn = self.database.get_connection()
            cursor = conn.cursor()
            # Total d'emails envoyés à cette entreprise
            self.database.execute_sql(
                cursor,
                '''
                SELECT COUNT(*) AS sent_count
                FROM emails_envoyes
                WHERE entreprise_id = ?
                ''',
                (entreprise_id,)
            )
            row = cursor.fetchone()
            sent_count = int((row['sent_count'] if isinstance(row, dict) else row[0]) or 0) if row else 0
            if sent_count <= 0:
                return 0.0, []

            # Uniques ouvrants / cliqueurs
            self.database.execute_sql(
                cursor,
                '''
                SELECT
                    COUNT(DISTINCT CASE WHEN et.event_type = 'open' THEN et.email_id END) AS open_unique,
                    COUNT(DISTINCT CASE WHEN et.event_type = 'click' THEN et.email_id END) AS click_unique
                FROM emails_envoyes e
                LEFT JOIN email_tracking_events et ON et.email_id = e.id
                WHERE e.entreprise_id = ?
                ''',
                (entreprise_id,)
            )
            row2 = cursor.fetchone()
            open_unique = int((row2['open_unique'] if isinstance(row2, dict) else row2[0]) or 0) if row2 else 0
            click_unique = int((row2['click_unique'] if isinstance(row2, dict) else row2[1]) or 0) if row2 else 0

            open_rate = (open_unique / max(sent_count, 1)) * 100.0
            click_rate = (click_unique / max(sent_count, 1)) * 100.0
            # Engagement fort => opportunité commerciale plus élevée
            score = min(10.0, open_rate * 0.08 + click_rate * 0.16)
            # Taux très faibles malgré plusieurs envois => pénalité
            if sent_count >= 5 and open_rate < 5.0 and click_rate < 1.0:
                score -= 8.0
            indicators = [f'Engagement email: {open_rate:.1f}% open / {click_rate:.1f}% click']
            return max(-8.0, min(10.0, score)), indicators
        except Exception:
            return 0.0, []
        finally:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass

    def _score_to_band(self, score: int) -> Dict:
        """
        Echelle fine 1-10 pour le pilotage interne (compatible avec les 5 niveaux existants).
        """
        s = max(0, min(100, int(score)))
        level = min(10, max(1, (s // 10) + 1))
        return {
            'level': level,
            'label': f'Niveau {level}/10'
        }
    
    def calculate_opportunity_score(self, entreprise_id: int, 
                                   site_age_score: Optional[int] = None,
                                   technical_analysis: Optional[Dict] = None,
                                   pentest_analysis: Optional[Dict] = None,
                                   osint_analysis: Optional[Dict] = None,
                                   scraping_data: Optional[Dict] = None,
                                   seo_analysis: Optional[Dict] = None) -> Dict:
        """
        Calcule le score d'opportunité global en combinant tous les facteurs
        
        Args:
            entreprise_id: ID de l'entreprise
            site_age_score: Score d'âge du site (0-10, plus élevé = plus obsolète)
            technical_analysis: Analyse technique (dict avec security_score, performance_score, etc.)
            pentest_analysis: Analyse pentest (dict avec risk_score, vulnerabilities, etc.)
            osint_analysis: Analyse OSINT (dict avec people, emails, etc.)
            scraping_data: Données de scraping (dict avec emails, people, phones, etc.)
        
        Returns:
            dict: {
                'opportunity': str ('Très élevée', 'Élevée', 'Moyenne', 'Faible', 'Très faible'),
                'score': int (0-100),
                'breakdown': dict (détail par catégorie),
                'indicators': list (liste des indicateurs)
            }
        """
        # Charger les analyses si non fournies
        # Le database peut être une instance de Database qui hérite de tous les managers
        if self.database:
            # Utiliser directement les méthodes du database (qui hérite de tous les managers)
            if technical_analysis is None:
                if hasattr(self.database, 'get_technical_analysis'):
                    technical_analysis = self.database.get_technical_analysis(entreprise_id)
            
            if pentest_analysis is None:
                if hasattr(self.database, 'get_pentest_analysis_by_entreprise'):
                    pentest_analysis = self.database.get_pentest_analysis_by_entreprise(entreprise_id)
            
            if osint_analysis is None:
                if hasattr(self.database, 'get_osint_analysis_by_entreprise'):
                    osint_analysis = self.database.get_osint_analysis_by_entreprise(entreprise_id)
            
            if scraping_data is None:
                if hasattr(self.database, 'get_scrapers_by_entreprise'):
                    scrapers = self.database.get_scrapers_by_entreprise(entreprise_id)
                    if scrapers:
                        # Utiliser le scraper le plus récent (trié par date DESC)
                        latest_scraper = scrapers[0]
                        # Les données sont déjà chargées par get_scrapers_by_entreprise
                        scraping_data = {
                            'emails': latest_scraper.get('emails', []),
                            'people': latest_scraper.get('people', []),
                            'phones': latest_scraper.get('phones', [])
                        }

            # Charger l'analyse SEO si disponible
            if seo_analysis is None:
                if hasattr(self.database, 'get_seo_analyses_by_entreprise'):
                    try:
                        seo_list = self.database.get_seo_analyses_by_entreprise(entreprise_id, limit=1)
                        if seo_list:
                            seo_analysis = seo_list[0]
                    except Exception:
                        seo_analysis = None
        
        ent_data = None
        if self.database and hasattr(self.database, 'get_entreprise'):
            try:
                ent_data = self.database.get_entreprise(entreprise_id)
            except Exception:
                ent_data = None

        breakdown = {}
        indicators = []
        total_score = 0
        max_score = 0
        
        # 1. Score d'âge du site (0-25 points)
        # Plus le site est obsolète, plus l'opportunité est élevée
        if site_age_score is not None:
            age_score = min(site_age_score * 2.5, 25)  # Max 25 points
            breakdown['age'] = age_score
            total_score += age_score
            max_score += 25
            if site_age_score >= 4:
                indicators.append('Site très obsolète')
            elif site_age_score >= 2:
                indicators.append('Site obsolète')
        
        # 2. Score de sécurité technique (0-20 points)
        # Plus la sécurité est faible, plus l'opportunité est élevée
        security_score = None
        if technical_analysis:
            security_score = technical_analysis.get('security_score')
        if security_score is None and ent_data:
            security_score = ent_data.get('score_securite')
        if security_score is not None:
            # Inverser : sécurité faible = opportunité élevée
            security_opportunity = max(0, (100 - float(security_score)) / 5)  # Max 20 points
            breakdown['security'] = security_opportunity
            total_score += security_opportunity
            max_score += 20
            if security_score < 40:
                indicators.append('Sécurité faible détectée')
            elif security_score < 60:
                indicators.append('Sécurité moyenne')
        
        # 3. Score de performance technique (0-15 points)
        # Plus les performances sont faibles, plus l'opportunité est élevée
        performance_score = None
        if technical_analysis:
            performance_score = technical_analysis.get('performance_score')
        if performance_score is None and ent_data:
            performance_score = ent_data.get('performance_score')
        if performance_score is not None:
            # Inverser : performance faible = opportunité élevée
            perf_opportunity = max(0, (100 - float(performance_score)) / 6.67)  # Max 15 points
            breakdown['performance'] = perf_opportunity
            total_score += perf_opportunity
            max_score += 15
            if performance_score < 50:
                indicators.append('Performances faibles')
        
        # 4. Score Pentest (0-20 points)
        # Plus le risque est élevé, plus l'opportunité est élevée
        if pentest_analysis:
            risk_score = pentest_analysis.get('risk_score')
            if risk_score is not None:
                # Le risk_score est déjà un indicateur d'opportunité (0-100)
                pentest_opportunity = risk_score / 5  # Max 20 points
                breakdown['pentest'] = pentest_opportunity
                total_score += pentest_opportunity
                max_score += 20
                
                vulnerabilities = pentest_analysis.get('vulnerabilities', [])
                critical_count = len([v for v in vulnerabilities if v.get('severity') == 'Critical'])
                high_count = len([v for v in vulnerabilities if v.get('severity') == 'High'])
                
                if critical_count > 0:
                    indicators.append(f'{critical_count} vulnérabilité(s) critique(s)')
                elif high_count > 0:
                    indicators.append(f'{high_count} vulnérabilité(s) haute(s)')
                elif risk_score >= 70:
                    indicators.append('Risque de sécurité élevé')
        
        # 5. Données OSINT (0-10 points)
        # Plus on trouve de données, plus l'opportunité est élevée (entreprise active)
        if osint_analysis:
            osint_score = 0
            people_count = len(osint_analysis.get('people', {}).get('enriched', []))
            emails_count = len(osint_analysis.get('emails', []))
            
            # Points pour les personnes trouvées (max 5 points)
            if people_count > 0:
                osint_score += min(people_count * 0.5, 5)
                indicators.append(f'{people_count} personne(s) identifiée(s)')
            
            # Points pour les emails trouvés (max 5 points)
            if emails_count > 0:
                osint_score += min(emails_count * 0.5, 5)
            
            breakdown['osint'] = osint_score
            total_score += osint_score
            max_score += 10
        
        # 6. Données de scraping (0-10 points)
        # Plus on trouve de contacts, plus l'opportunité est élevée
        if scraping_data:
            scraping_score = 0
            emails = scraping_data.get('emails', [])
            people = scraping_data.get('people', [])
            phones = scraping_data.get('phones', [])
            
            # Gérer les différents formats (list ou dict avec email/phone)
            if emails:
                if isinstance(emails, list):
                    # Si c'est une liste de dicts, extraire les emails
                    email_list = [e.get('email', e) if isinstance(e, dict) else e for e in emails]
                    email_count = len([e for e in email_list if e])
                else:
                    email_count = 1
                scraping_score += min(email_count * 0.4, 4)
            
            if people:
                if isinstance(people, list):
                    people_count = len(people)
                else:
                    people_count = 1
                scraping_score += min(people_count * 0.3, 3)
            
            if phones:
                if isinstance(phones, list):
                    # Si c'est une liste de dicts, extraire les téléphones
                    phone_list = [p.get('phone', p) if isinstance(p, dict) else p for p in phones]
                    phone_count = len([p for p in phone_list if p])
                else:
                    phone_count = 1
                scraping_score += min(phone_count * 0.3, 3)
            
            breakdown['scraping'] = scraping_score
            total_score += scraping_score
            max_score += 10

        # 7. Score SEO global (0-10 points)
        # Plus le score SEO est faible, plus l'opportunité est élevée
        if seo_analysis:
            seo_score = seo_analysis.get('score')
            if seo_score is not None:
                try:
                    s = max(0, min(100, int(seo_score)))
                    seo_opportunity = max(0, (100 - s) / 10.0)  # Max 10 points
                    breakdown['seo'] = seo_opportunity
                    total_score += seo_opportunity
                    max_score += 10
                    if s < 50:
                        indicators.append('SEO faible détecté')
                    elif s < 70:
                        indicators.append('SEO perfectible')
                except Exception:
                    pass

        # 8. Signal CRM (statut) : -14 à +8 points
        status_pts, status_indicators = self._status_signal((ent_data or {}).get('statut') if ent_data else None)
        breakdown['status'] = status_pts
        total_score += status_pts
        max_score += 14
        indicators.extend(status_indicators)

        # 9. Signal tags : -12 à +12 points
        tags_pts, tags_indicators = self._tags_signal(self._safe_json_list((ent_data or {}).get('tags') if ent_data else None))
        breakdown['tags'] = tags_pts
        total_score += tags_pts
        max_score += 12
        indicators.extend(tags_indicators)

        # 10. Signal engagement email : -8 à +10 points
        engagement_pts, engagement_indicators = self._engagement_signal(entreprise_id)
        breakdown['engagement'] = engagement_pts
        total_score += engagement_pts
        max_score += 10
        indicators.extend(engagement_indicators)
        
        # Calculer le score final (0-100)
        if max_score > 0:
            final_score = int((total_score / max_score) * 100)
        else:
            # Fallback sur le score d'âge uniquement
            if site_age_score is not None:
                final_score = min(site_age_score * 10, 100)
            else:
                final_score = 0
        
        # Déterminer le niveau d'opportunité
        if final_score >= 80:
            opportunity = 'Très élevée'
        elif final_score >= 60:
            opportunity = 'Élevée'
        elif final_score >= 40:
            opportunity = 'Moyenne'
        elif final_score >= 20:
            opportunity = 'Faible'
        else:
            opportunity = 'Très faible'
        
        band = self._score_to_band(final_score)
        return {
            'opportunity': opportunity,
            'score': final_score,
            'breakdown': breakdown,
            'indicators': indicators,
            'max_possible_score': max_score,
            'actual_score': total_score,
            'score_band': band
        }
    
    def calculate_opportunity_from_entreprise(self, entreprise_data: Dict) -> Dict:
        """
        Calcule l'opportunité à partir des données d'une entreprise
        
        Args:
            entreprise_data: Dict avec les données de l'entreprise (doit contenir 'id')
        
        Returns:
            dict: Résultat du calcul d'opportunité
        """
        entreprise_id = entreprise_data.get('id')
        if not entreprise_id:
            logger.warning('Entreprise ID manquant pour le calcul d\'opportunité')
            return {
                'opportunity': 'Faible',
                'score': 0,
                'breakdown': {},
                'indicators': []
            }
        
        # Extraire le score d'âge du site depuis les indicateurs
        site_indicators = entreprise_data.get('site_indicators', '')
        site_age_score = 0
        if site_indicators:
            # Compter les indicateurs d'obsolescence
            indicators_list = site_indicators.split('; ')
            site_age_score = len([i for i in indicators_list if i and i != 'Aucun'])
        
        return self.calculate_opportunity_score(
            entreprise_id=entreprise_id,
            site_age_score=site_age_score,
            technical_analysis=None,  # Sera chargé automatiquement
            pentest_analysis=None,    # Sera chargé automatiquement
            osint_analysis=None,      # Sera chargé automatiquement
            scraping_data=None,       # Sera chargé automatiquement
            seo_analysis=None         # Sera chargé automatiquement
        )
