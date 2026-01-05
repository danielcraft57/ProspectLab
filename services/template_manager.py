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
        
        # Créer le fichier s'il n'existe pas
        if not self.templates_file.exists():
            self._init_templates_file()
        
        self.templates = self._load_templates()
    
    def _init_templates_file(self):
        """Initialise le fichier de templates avec des exemples"""
        default_templates = {
            'templates': [
                {
                    'id': 'cold_email_1',
                    'name': 'Cold Email - Entreprise Locale',
                    'category': 'cold_email',
                    'subject': 'Développeur web freelance à Metz - Partenariat pour vos startups',
                    'content': """Bonjour,

Je suis Loïc DANIEL, développeur web freelance basé à Metz, spécialisé en TypeScript, React et Node.js avec 10 ans d'expérience.

Je vois que {entreprise} accompagne de nombreuses startups et entreprises innovantes. Beaucoup d'entre elles ont besoin de sites web modernes, d'applications web ou d'optimisation de leurs outils numériques.

Je propose mes services aux entreprises que vous accompagnez :
- Sites vitrines modernes et performants (600€)
- Applications web sur mesure
- Audit et optimisation de sites existants (800€)
- Automatisation de processus (900€)

Pourriez-vous me mettre en relation avec des entreprises qui auraient des besoins en développement web ? Je peux également intervenir lors d'événements ou proposer des ateliers techniques.

Disponible pour un échange de 15 minutes cette semaine pour discuter d'un éventuel partenariat ?

Cordialement,
Loïc DANIEL
Développeur web freelance
danielcraft.fr""",
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                },
                {
                    'id': 'cold_email_2',
                    'name': 'Cold Email - PME avec site obsolète',
                    'category': 'cold_email',
                    'subject': 'Modernisation de votre site web - {entreprise}',
                    'content': """Bonjour {nom},

J'ai remarqué que le site web de {entreprise} pourrait bénéficier d'une modernisation pour améliorer l'expérience utilisateur et les performances.

En tant que développeur web freelance spécialisé en TypeScript, React et Node.js, j'ai aidé plusieurs entreprises similaires à moderniser leur présence en ligne, avec des résultats concrets :
- Amélioration de la vitesse de chargement (réduction de 40-60%)
- Meilleure expérience utilisateur mobile
- Optimisation SEO pour plus de visibilité

Je propose un audit gratuit de votre site actuel pour identifier les opportunités d'amélioration.

Seriez-vous disponible pour un échange de 15 minutes cette semaine ?

Cordialement,
Loïc DANIEL
Développeur web freelance
danielcraft.fr""",
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
            ]
        }
        
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
        Liste tous les templates
        
        Args:
            category: Filtrer par catégorie (optionnel)
        
        Returns:
            Liste de templates
        """
        templates = self.templates.copy()
        
        if category:
            templates = [t for t in templates if t.get('category') == category]
        
        # Retirer le contenu complet pour la liste (garder juste un aperçu)
        for template in templates:
            if 'content' in template:
                content = template['content']
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
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        
        self.templates.append(template)
        self._save_templates()
        
        return template
    
    def update_template(self, template_id: str, name: str = None, subject: str = None, 
                        content: str = None) -> Optional[Dict]:
        """
        Met à jour un template existant
        
        Args:
            template_id: ID du template
            name: Nouveau nom (optionnel)
            subject: Nouveau sujet (optionnel)
            content: Nouveau contenu (optionnel)
        
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
    
    def render_template(self, template_id: str, nom: str = '', entreprise: str = '', email: str = '') -> str:
        """
        Rend un template avec les variables remplacées
        
        Args:
            template_id: ID du template
            nom: Nom du destinataire
            entreprise: Nom de l'entreprise
            email: Email du destinataire
        
        Returns:
            Contenu rendu
        """
        template = self.get_template(template_id)
        if not template:
            return ''
        
        content = template.get('content', '')
        
        # Remplacer les variables
        content = content.format(
            nom=nom or 'Monsieur/Madame',
            entreprise=entreprise or 'votre entreprise',
            email=email or ''
        )
        
        return content

