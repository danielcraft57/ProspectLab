"""
Calculateur de score d'opportunité pour les entreprises
Combine les données OSINT, Pentest et Analyse Technique pour calculer un score d'opportunité précis
"""

import logging
from typing import Dict, Optional

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
    
    def calculate_opportunity_score(self, entreprise_id: int, 
                                   site_age_score: Optional[int] = None,
                                   technical_analysis: Optional[Dict] = None,
                                   pentest_analysis: Optional[Dict] = None,
                                   osint_analysis: Optional[Dict] = None,
                                   scraping_data: Optional[Dict] = None) -> Dict:
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
        if technical_analysis:
            security_score = technical_analysis.get('security_score')
            if security_score is not None:
                # Inverser : sécurité faible = opportunité élevée
                security_opportunity = max(0, (100 - security_score) / 5)  # Max 20 points
                breakdown['security'] = security_opportunity
                total_score += security_opportunity
                max_score += 20
                if security_score < 40:
                    indicators.append('Sécurité faible détectée')
                elif security_score < 60:
                    indicators.append('Sécurité moyenne')
        
        # 3. Score de performance technique (0-15 points)
        # Plus les performances sont faibles, plus l'opportunité est élevée
        if technical_analysis:
            performance_score = technical_analysis.get('performance_score')
            if performance_score is not None:
                # Inverser : performance faible = opportunité élevée
                perf_opportunity = max(0, (100 - performance_score) / 6.67)  # Max 15 points
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
        
        return {
            'opportunity': opportunity,
            'score': final_score,
            'breakdown': breakdown,
            'indicators': indicators,
            'max_possible_score': max_score,
            'actual_score': total_score
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
            scraping_data=None        # Sera chargé automatiquement
        )
