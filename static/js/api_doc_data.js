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
                categoryDesc: 'Liste, détail et recherches (site, email, téléphone) ; emails et téléphones d’une fiche ; campagnes liées. Suppression : DELETE sur la même URL que le détail — sans cache serveur ; données liées en cascade selon le schéma.',
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
                        path: '/entreprises/<id>/screenshots',
                        desc: 'Dernier set de screenshots publics (desktop/tablet/mobile) + historique récent.',
                        permission: 'Entreprises',
                        params: [{ name: 'limit', type: 'int', desc: 'Optionnel, défaut 20, max 100' }]
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
                id: 'statuts-evenements',
                name: 'Statuts & événements',
                categoryDesc: 'Mise à jour du statut pipeline ou raccourcis POST pour la délivrabilité. Statuts autorisés : `GET /entreprises/statuses`. Body optionnel sur les POST : `{ "note": "..." }`.',
                endpoints: [
                    {
                        method: 'PATCH',
                        path: '/entreprises/<id>/statut',
                        desc: 'Mise à jour du statut (+ note optionnelle).',
                        permission: 'Entreprises',
                        body: 'JSON: { "statut": "<string>", "note": "<optionnel>" }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/statut',
                        desc: 'Identique à PATCH (alias).',
                        permission: 'Entreprises',
                        body: 'JSON: { "statut": "<string>", "note": "<optionnel>" }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/unsubscribe',
                        desc: 'Raccourci : Désabonné.',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/negative-reply',
                        desc: 'Raccourci : Réponse négative.',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/bounce',
                        desc: 'Raccourci : Bounce.',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/positive-reply',
                        desc: 'Raccourci : Réponse positive.',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/spam-complaint',
                        desc: 'Raccourci : Plainte spam.',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/do-not-contact',
                        desc: 'Raccourci : Ne pas contacter.',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
                    },
                    {
                        method: 'POST',
                        path: '/entreprises/<id>/callback',
                        desc: 'Raccourci : À rappeler (auto-réponse).',
                        permission: 'Entreprises',
                        body: 'JSON optionnel: { "note": "..." }'
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
                        desc: 'Déclenche les analyses (Celery). Corps : website (requis), force, full, profondeur, workers, Lighthouse, Nmap, etc.',
                        permission: 'Entreprises',
                        body: 'JSON: website (requis), force?, full?, max_depth?, max_workers?, max_time?, max_pages?, enable_nmap?, use_lighthouse?, …'
                    }
                ]
            }
        ]
    }
];
