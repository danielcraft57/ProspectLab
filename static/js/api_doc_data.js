/**
 * Données partagées pour la documentation API (page api_doc.html)
 * Aligné sur docs/guides/API_PUBLIQUE.md
 */
const API_DOC_FAMILIES = [
    {
        id: 'public',
        name: 'API publique',
        description: 'Endpoints sous `/api/public` avec un token API (header `Authorization: Bearer <token>`, à éviter en prod : `?api_token=`). Réponses GET souvent mises en cache serveur ; voir le guide pour les TTL et la désactivation.',
        basePath: '/api/public',
        auth: 'Header: Authorization: Bearer <votre_token> (recommandé). Paramètre ?api_token= possible mais déconseillé (logs, partage d’URL).',
        categories: [
            {
                id: 'token',
                name: 'Token',
                categoryDesc: 'Vérifier un token et les permissions sans toucher aux données métier.',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/token/info',
                        desc: 'Métadonnées du token (nom, aperçu masqué, permissions, dates). La valeur secrète complète n’est jamais renvoyée.',
                        permission: 'Token valide'
                    }
                ]
            },
            {
                id: 'statistiques',
                name: 'Statistiques',
                categoryDesc: 'Indicateurs globaux ; `overview` est adapté aux tableaux de bord et apps mobiles.',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/statistics',
                        desc: 'Statistiques globales détaillées (répartitions, campagnes récentes, etc.).',
                        permission: 'Statistiques'
                    },
                    {
                        method: 'GET',
                        path: '/statistics/overview',
                        desc: 'Vue compacte + série journalière `trend_entreprises` pour les N derniers jours.',
                        permission: 'Statistiques',
                        params: [
                            { name: 'days', type: 'int', desc: 'Nombre de jours (défaut serveur, max 90)' }
                        ]
                    }
                ]
            },
            {
                id: 'reference-filtres',
                name: 'Référence & filtres',
                categoryDesc: 'Listes de valeurs pour construire des filtres et facettes côté client (secteurs, tags, statuts entreprise et campagne).',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/reference/ciblage',
                        desc: 'Valeurs distinctes : secteurs, opportunités, statuts entreprise, tags.',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/reference/ciblage/counts',
                        desc: 'Mêmes dimensions avec effectifs `{ value, count }` pour facettes.',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/reference/carte-villes',
                        desc: 'Villes (presets Grand Est) avec nombre d’entreprises géolocalisées dans un rayon autour du centre-ville.',
                        permission: 'Entreprises',
                        params: [
                            { name: 'rayon_km', type: 'float', desc: 'Rayon de comptage (défaut 25, min 5, max 80)' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/statuses',
                        desc: 'Statuts entreprise supportés (pipeline + délivrabilité).',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/campagnes/statuses',
                        desc: 'Valeurs de statut pour les campagnes : draft, scheduled, running, completed, failed.',
                        permission: 'Campagnes'
                    }
                ]
            },
            {
                id: 'entreprises',
                name: 'Entreprises',
                categoryDesc: 'Liste, détail, proximité GPS, recherches (site, email, téléphone) ; galerie images ; emails et téléphones ; campagnes liées. Suppression : DELETE sur la même URL que le détail — sans cache serveur ; données liées en cascade selon le schéma.',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/entreprises',
                        desc: 'Liste paginée. Pour `statut` : valeurs Gagné / Perdu / Relance incluent les statuts événementiels associés ; sinon filtre exact.',
                        permission: 'Entreprises',
                        params: [
                            { name: 'limit', type: 'int', desc: 'Défaut 100, max 1000' },
                            { name: 'offset', type: 'int', desc: 'Pagination' },
                            { name: 'secteur', type: 'str' },
                            { name: 'statut', type: 'str' },
                            { name: 'search', type: 'str' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/proches',
                        desc: 'Entreprises ProspectLab proches d’un point GPS (pas OSM).',
                        permission: 'Entreprises',
                        params: [
                            { name: 'latitude', type: 'float', desc: 'Requis' },
                            { name: 'longitude', type: 'float', desc: 'Requis' },
                            { name: 'rayon_km', type: 'float', desc: 'Alias radius_km ; défaut 10, max 100' },
                            { name: 'limit', type: 'int', desc: 'Défaut 80, max 250' },
                            { name: 'secteur', type: 'str', desc: 'Optionnel' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>',
                        desc: 'Détail d’une entreprise.',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'DELETE',
                        path: '/entreprises/<id>',
                        desc: 'Supprime définitivement la fiche et les enregistrements associés (CASCADE). Réponse 200 : { success, deleted_id, message } ; 404 si id inconnu. Pas de body. Exige le droit token « suppression entreprises » (can_delete_entreprises) en plus de la lecture entreprises — sinon 403.',
                        permission: 'Entreprises + suppression entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/by-website',
                        desc: 'Recherche par site web (URL ou domaine normalisé).',
                        permission: 'Entreprises',
                        params: [{ name: 'website', type: 'str', desc: 'Requis' }]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/by-email',
                        desc: 'Recherche par email. `include_emails` ajoute la liste complète des emails de la fiche dans la réponse.',
                        permission: 'Entreprises + Emails',
                        params: [
                            { name: 'email', type: 'str', desc: 'Requis' },
                            { name: 'include_emails', type: 'bool', desc: 'Optionnel' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/by-phone',
                        desc: 'Recherche par téléphone (variantes FR et international).',
                        permission: 'Entreprises',
                        params: [
                            { name: 'phone', type: 'str', desc: 'Requis' },
                            { name: 'include_phones', type: 'bool', desc: 'Optionnel' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/emails',
                        desc: 'Emails format court pour l’entreprise.',
                        permission: 'Entreprises + Emails'
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/emails/all',
                        desc: 'Emails enrichis (analyse, personne, etc.).',
                        permission: 'Entreprises + Emails',
                        params: [{ name: 'include_primary', type: 'bool', desc: 'Optionnel (défaut true)' }]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/phones',
                        desc: 'Téléphones scrapés + téléphone principal.',
                        permission: 'Entreprises',
                        params: [{ name: 'include_primary', type: 'bool', desc: 'Optionnel' }]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/gallery',
                        desc: 'Images liées à la fiche (scraping, OpenGraph, logo) pour galerie mobile légère.',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/screenshots',
                        desc: 'Dernier set de screenshots publics (desktop/tablet/mobile) + historique récent (+ champs design_* si analyse déjà faite).',
                        permission: 'Entreprises',
                        params: [{ name: 'limit', type: 'int', desc: 'Optionnel, défaut 20, max 100' }]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/landing-variants',
                        desc: 'Dernier run de landing variants (liens index.html + screenshots + runs récents).',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/landing-variants/runs/<run_id>',
                        desc: 'Détail d’un run précis (liste normalisée des assets: html/css/js/screenshots).',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/campagnes',
                        desc: 'Campagnes liées à l’entreprise.',
                        permission: 'Campagnes',
                        params: [
                            { name: 'limit', type: 'int' },
                            { name: 'offset', type: 'int' },
                            { name: 'statut', type: 'str' }
                        ]
                    }
                ]
            },
            {
                id: 'design-gemini',
                name: 'Design review & rapport Gemini',
                categoryDesc: 'Analyses UX/UI (Gemini Vision) sur screenshots, et rapport d’audit complet Gemini. Les clés Gemini ne sont jamais exposées. POST = tâche Celery (réponse 202 + task_id) ; relire ensuite le GET.',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/design-review',
                        desc: 'Lecture de l’analyse design UX/UI du dernier screenshot (score, positifs/négatifs, pitch).',
                        permission: 'Entreprises'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/design-review',
                        desc: 'Lance l’analyse design (Celery, queue screenshot). 202 + task_id si un screenshot existe ; 409 sinon.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'screenshot_set_id', type: 'int', required: false, desc: 'Set cible (défaut : dernier set disponible)' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/entreprises/<id>/gemini-report',
                        desc: 'Dernier rapport Gemini (score, indicateurs modules, résumé, pitch, points forts/faibles, actions, design) — même contenu que l’onglet site. status=never si aucun rapport.',
                        permission: 'Entreprises',
                        params: [
                            { name: 'include_document', type: 'bool', desc: 'Inclure le Markdown report_document (volumineux)' },
                            { name: 'include_raw', type: 'bool', desc: 'Inclure le dict latest brut (debug)' },
                            { name: 'task_id', type: 'str', desc: 'Suivi Celery après un POST (progress / logs)' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/gemini-report',
                        desc: 'Lance le rapport Gemini complet (202 + task_id + poll_url). Capture screenshots si besoin. Puis poller le GET.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'ensure_screenshots', type: 'bool', required: false, desc: 'Capturer les screenshots manquants (défaut true)' }
                        ]
                    }
                ]
            },
            {
                id: 'statuts-evenements',
                name: 'Statuts & événements',
                categoryDesc: 'Mise à jour du statut pipeline ou raccourcis POST pour la délivrabilité. Statuts autorisés : `GET /entreprises/statuses`. Body optionnel sur les POST : `{ "note": "..." }`.',
                endpoints: [
                    {
                        method: 'PATCH',
                        path: '/entreprises/<id>/statut',
                        desc: 'Mise à jour du statut (+ note optionnelle).',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'statut', type: 'str', required: true, desc: 'Valeur cible (voir GET /entreprises/statuses)' },
                            { name: 'note', type: 'str', required: false, desc: 'Commentaire interne optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/statut',
                        desc: 'Identique à PATCH (alias).',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'statut', type: 'str', required: true, desc: 'Valeur cible (voir GET /entreprises/statuses)' },
                            { name: 'note', type: 'str', required: false, desc: 'Commentaire interne optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/unsubscribe',
                        desc: 'Raccourci : Désabonné.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/negative-reply',
                        desc: 'Raccourci : Réponse négative.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/bounce',
                        desc: 'Raccourci : Bounce.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/positive-reply',
                        desc: 'Raccourci : Réponse positive.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/spam-complaint',
                        desc: 'Raccourci : Plainte spam.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/do-not-contact',
                        desc: 'Raccourci : Ne pas contacter.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/callback',
                        desc: 'Raccourci : À rappeler (auto-réponse).',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'note', type: 'str', required: false, desc: 'Corps entièrement optionnel' }
                        ]
                    }
                ]
            },
            {
                id: 'emails-campagnes',
                name: 'Emails & campagnes (global)',
                categoryDesc: 'Liste globale des emails et gestion des campagnes (hors scoping par entreprise, déjà dans la section Entreprises).',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/emails',
                        desc: 'Liste globale des emails.',
                        permission: 'Emails',
                        params: [
                            { name: 'limit', type: 'int' },
                            { name: 'offset', type: 'int' },
                            { name: 'entreprise_id', type: 'int' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/campagnes',
                        desc: 'Liste des campagnes.',
                        permission: 'Campagnes',
                        params: [
                            { name: 'limit', type: 'int' },
                            { name: 'offset', type: 'int' },
                            { name: 'statut', type: 'str' },
                            { name: 'entreprise_id', type: 'int', desc: 'Filtre par entreprise' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/campagnes/<id>',
                        desc: 'Détail d’une campagne.',
                        permission: 'Campagnes'
                    },
                    {
                        method: 'GET',
                        path: '/campagnes/<id>/emails',
                        desc: 'Emails envoyés pour la campagne.',
                        permission: 'Campagnes',
                        params: [
                            { name: 'limit', type: 'int' },
                            { name: 'offset', type: 'int' },
                            { name: 'statut', type: 'str' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/campagnes/<id>/statistics',
                        desc: 'Métriques de tracking (ouvertures, clics).',
                        permission: 'Campagnes'
                    }
                ]
            },
            {
                id: 'analyse-site',
                name: 'Analyse de site',
                categoryDesc: 'Rapport agrégé SEO / technique / OSINT / pentest. GET : données déjà en base ; POST : lance des tâches asynchrones (réponse typique 202).',
                endpoints: [
                    {
                        method: 'GET',
                        path: '/website-analysis',
                        desc: 'Récupère un rapport existant ; 404 si aucune entreprise associée au site.',
                        permission: 'Entreprises',
                        params: [
                            { name: 'website', type: 'str', desc: 'Requis (URL ou domaine)' },
                            { name: 'full', type: 'bool', desc: 'Inclut le détail scraping (volumineux)' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/website-analysis',
                        desc: 'Déclenche les analyses (Celery). Réponse typique 202 avec task_id par module ; sinon 200 si rapport déjà en base et force=false.',
                        permission: 'Entreprises',
                        bodyParams: [
                            { name: 'website', type: 'str', required: true, desc: 'URL ou domaine à analyser' },
                            { name: 'force', type: 'bool', required: false, desc: 'Relancer même si un rapport existe déjà (défaut false)' },
                            { name: 'full', type: 'bool', required: false, desc: 'Inclure l’historique scraping dans la réponse immédiate si rapport existant' },
                            { name: 'max_depth', type: 'int', required: false, desc: 'Profondeur scraping (défaut 2)' },
                            { name: 'max_workers', type: 'int', required: false, desc: 'Workers scraping (défaut 5)' },
                            { name: 'max_time', type: 'int', required: false, desc: 'Timeout scraping en secondes (défaut 180)' },
                            { name: 'max_pages', type: 'int', required: false, desc: 'Pages max scraping (défaut 30)' },
                            { name: 'enable_nmap', type: 'bool', required: false, desc: 'Active Nmap sur l’analyse technique (défaut false)' },
                            { name: 'use_lighthouse', type: 'bool', required: false, desc: 'Lighthouse SEO (défaut config serveur)' }
                        ]
                    }
                ]
            },
            {
                id: 'audit-report-pdf',
                name: 'Rapport d\'audit PDF (email)',
                categoryDesc: 'Analyse + PDF + envoi email. Auth : Bearer token API ou header X-Website-Audit-Key (PUBLIC_WEBSITE_AUDIT_LEAD_KEY). Ne nécessite pas la permission Entreprises.',
                endpoints: [
                    {
                        method: 'POST',
                        path: '/website-audit-report',
                        desc: 'Scraping → technique → SEO → pentest, puis PDF local + email. Si déjà analysé en base : PDF + email direct (skipped_analysis).',
                        permission: 'Auth audit (Bearer ou X-Website-Audit-Key)',
                        bodyParams: [
                            { name: 'website', type: 'str', required: true, desc: 'URL ou domaine (alias url)' },
                            { name: 'email', type: 'str', required: true, desc: 'Destinataire du PDF (alias recipient_email)' },
                            { name: 'max_depth', type: 'int', required: false, desc: 'Profondeur scraping (défaut 2)' },
                            { name: 'max_workers', type: 'int', required: false, desc: 'Workers scraping (défaut 5)' },
                            { name: 'max_time', type: 'int', required: false, desc: 'Timeout scraping en secondes (défaut 300)' },
                            { name: 'max_pages', type: 'int', required: false, desc: 'Pages max scraping (défaut 40)' },
                            { name: 'enable_nmap', type: 'bool', required: false, desc: 'Nmap sur l’analyse technique (défaut false)' },
                            { name: 'use_lighthouse', type: 'bool', required: false, desc: 'Lighthouse SEO (défaut config serveur)' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/website-audit-report/complete',
                        desc: 'Mode complet : scraping, technique, SEO, screenshots, OSINT, pentest ; PDF serv1 (repli local). Réponse 202.',
                        permission: 'Auth audit (Bearer ou X-Website-Audit-Key)',
                        bodyParams: [
                            { name: 'website', type: 'str', required: true, desc: 'URL ou domaine (alias url)' },
                            { name: 'email', type: 'str', required: true, desc: 'Destinataire du PDF (alias recipient_email)' },
                            { name: 'max_depth', type: 'int', required: false, desc: 'Profondeur scraping (défaut 2)' },
                            { name: 'max_workers', type: 'int', required: false, desc: 'Workers scraping (défaut 5)' },
                            { name: 'max_time', type: 'int', required: false, desc: 'Timeout scraping en secondes (défaut 300)' },
                            { name: 'max_pages', type: 'int', required: false, desc: 'Pages max scraping (défaut 40)' },
                            { name: 'enable_nmap', type: 'bool', required: false, desc: 'Nmap (défaut false)' },
                            { name: 'use_lighthouse', type: 'bool', required: false, desc: 'Lighthouse SEO (défaut config serveur)' },
                            { name: 'extra_instructions', type: 'str', required: false, desc: 'Consignes additionnelles pour l’agent Cursor sur serv1' }
                        ]
                    },
                    {
                        method: 'POST',
                        path: '/website-audit-report/complete/resume',
                        desc: 'Reprise après pause Cursor (quota). GET aussi possible (lien email admin : ?pending_id=…).',
                        permission: 'Auth audit (Bearer ou X-Website-Audit-Key)',
                        bodyParams: [
                            { name: 'pending_id', type: 'str', required: false, desc: 'Identifiant de reprise (recommandé)' },
                            { name: 'website', type: 'str', required: false, desc: 'Alternative si pas de pending_id' },
                            { name: 'email', type: 'str', required: false, desc: 'Avec website si pas de pending_id' },
                            { name: 'extra_instructions', type: 'str', required: false, desc: 'Consignes agent serv1' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/website-audit-report/complete/resume',
                        desc: 'Même reprise via lien (query pending_id, website, email). Réponse HTML courte si pending_id présent.',
                        permission: 'Auth audit (Bearer ou X-Website-Audit-Key / audit_key en query)',
                        params: [
                            { name: 'pending_id', type: 'str', desc: 'Identifiant de reprise' },
                            { name: 'website', type: 'str', desc: 'Optionnel' },
                            { name: 'email', type: 'str', desc: 'Optionnel' }
                        ]
                    },
                    {
                        method: 'GET',
                        path: '/website-audit-report/<task_id>',
                        desc: 'État Celery (PENDING, STARTED, SUCCESS, FAILURE) ; champ result si terminé avec succès.',
                        permission: 'Auth audit (Bearer ou X-Website-Audit-Key)',
                        params: [
                            { name: 'task_id', type: 'str', desc: 'Identifiant Celery renvoyé par le POST (segment d’URL)' }
                        ]
                    }
                ]
            },
            {
                id: 'push-mobile',
                name: 'Push mobile (Expo)',
                categoryDesc: 'Enregistrement / retrait d’un jeton Expo Push lié au token API (notif mobile). Content-Type application/json requis.',
                endpoints: [
                    {
                        method: 'POST',
                        path: '/push/register',
                        desc: 'Enregistre un jeton Expo Push pour ce token API.',
                        permission: 'Token valide',
                        bodyParams: [
                            { name: 'expo_push_token', type: 'str', required: true, desc: 'ExponentPushToken[…]' },
                            { name: 'platform', type: 'str', required: false, desc: 'android | ios (défaut android)' },
                            { name: 'installation_id', type: 'str', required: false, desc: 'Identifiant stable d’installation' }
                        ]
                    },
                    {
                        method: 'DELETE',
                        path: '/push/register',
                        desc: 'Retire un jeton Expo Push enregistré pour ce token API.',
                        permission: 'Token valide',
                        bodyParams: [
                            { name: 'expo_push_token', type: 'str', required: true, desc: 'ExponentPushToken[…] à retirer' }
                        ]
                    }
                ]
            }
        ]
    }
];
