"""
Gestionnaire d'export multi-formats
Export CSV, JSON, PDF avec options personnalisables
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class ExportManager:
    def __init__(self, export_dir=None):
        if export_dir is None:
            app_dir = Path(__file__).parent.parent
            export_dir = app_dir / 'exports'
        
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(exist_ok=True)
    
    def export_to_csv(self, df, filename=None, selected_columns=None):
        """Export vers CSV"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'export_{timestamp}.csv'
        
        filepath = self.export_dir / filename
        
        # Filtrer les colonnes si demandé
        if selected_columns:
            df = df[selected_columns]
        
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        return filepath
    
    def export_to_json(self, df, filename=None, selected_columns=None):
        """Export vers JSON"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'export_{timestamp}.json'
        
        filepath = self.export_dir / filename
        
        # Filtrer les colonnes si demandé
        if selected_columns:
            df = df[selected_columns]
        
        # Convertir en format JSON
        records = df.to_dict('records')
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        
        return filepath
    
    def export_to_pdf_report(self, df, filename=None, title="Rapport d'analyse"):
        """Export vers PDF avec rapport formaté"""
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib import colors
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER
            
            if filename is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f'report_{timestamp}.pdf'
            
            filepath = self.export_dir / filename
            
            doc = SimpleDocTemplate(str(filepath), pagesize=A4)
            elements = []
            styles = getSampleStyleSheet()
            
            # Titre
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                textColor=colors.HexColor('#2c3e50'),
                spaceAfter=30,
                alignment=TA_CENTER
            )
            elements.append(Paragraph(title, title_style))
            elements.append(Spacer(1, 0.2*inch))
            
            # Date
            date_text = f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
            elements.append(Paragraph(date_text, styles['Normal']))
            elements.append(Spacer(1, 0.3*inch))
            
            # Statistiques
            stats_text = f"Total d'entreprises analysées : {len(df)}"
            elements.append(Paragraph(stats_text, styles['Heading2']))
            elements.append(Spacer(1, 0.2*inch))
            
            # Tableau (limité aux colonnes principales pour lisibilité)
            main_columns = ['name', 'secteur', 'statut', 'site_opportunity', 'email_principal', 'responsable']
            available_columns = [col for col in main_columns if col in df.columns]
            
            if available_columns:
                # Limiter à 50 lignes pour le PDF
                df_limited = df[available_columns].head(50)
                
                # Préparer les données
                data = [available_columns]  # En-têtes
                for _, row in df_limited.iterrows():
                    data.append([str(row[col])[:50] if pd.notna(row[col]) else '' for col in available_columns])
                
                # Créer le tableau
                table = Table(data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                ]))
                
                elements.append(table)
            
            # Construire le PDF
            doc.build(elements)
            
            return filepath
        
        except ImportError:
            # Si reportlab n'est pas installé, retourner None
            return None
    
    def export_filtered(self, df, filters, format='xlsx'):
        """Export avec filtres appliqués"""
        filtered_df = df.copy()
        
        # Appliquer les filtres
        if filters.get('secteur'):
            filtered_df = filtered_df[filtered_df['secteur'] == filters['secteur']]
        
        if filters.get('statut'):
            filtered_df = filtered_df[filtered_df['statut'] == filters['statut']]
        
        if filters.get('opportunite'):
            filtered_df = filtered_df[filtered_df['site_opportunity'] == filters['opportunite']]
        
        if filters.get('search'):
            search_term = filters['search'].lower()
            mask = filtered_df.astype(str).apply(
                lambda x: x.str.lower().str.contains(search_term, na=False)
            ).any(axis=1)
            filtered_df = filtered_df[mask]
        
        # Export selon le format
        if format == 'csv':
            return self.export_to_csv(filtered_df)
        elif format == 'json':
            return self.export_to_json(filtered_df)
        elif format == 'pdf':
            return self.export_to_pdf_report(filtered_df)
        else:  # xlsx par défaut
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'export_filtered_{timestamp}.xlsx'
            filepath = self.export_dir / filename
            filtered_df.to_excel(filepath, index=False)
            return filepath

