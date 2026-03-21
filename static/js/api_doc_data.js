/**
 * Données partagées pour la documentation API (page et modale)
 */
const API_DOC_FAMILIES = [
    {
        id: 'public',
        name: 'API publique',
        description: 'Endpoints accessibles uniquement sous `/api/public` avec un token API (header `Authorization: Bearer <token>` ou paramètre `?api_token=<token>`).',
        basePath: '/api/public',
        auth: 'Header: Authorization: Bearer <votre_token> ou paramètre ?api_token=<token>.',
        categories: [
            {
                id: 'entreprises',
                name: 'Entreprises',
                endpoints: [
                    { method: 'GET', path: '/entreprises', desc: 'Liste des entreprises (filtre statut avec niveaux : Gagné/Perdu/Relance).', params: [{ name: 'limit', type: 'int', desc: 'Max résultats (défaut 100, max 1000)' }, { name: 'offset', type: 'int', desc: 'Pagination' }, { name: 'secteur', type: 'str' }, { name: 'statut', type: 'str', desc: 'Valeur exacte ou niveau (Gagné/Perdu/Relance) qui inclut des statuts événementiels associés.' }, { name: 'search', type: 'str' }] },
                    { method: 'GET', path: '/entreprises/<id>', desc: 'Détails d\'une entreprise.' },
                    { method: 'GET', path: '/entreprises/by-email', desc: 'Récupère une entreprise à partir d\'un email (scraping ou email_principal).', params: [{ name: 'email', type: 'str', desc: 'Requis' }, { name: 'include_emails', type: 'bool', desc: 'Optionnel (inclut tous les emails connus)' }] },
                    { method: 'GET', path: '/entreprises/by-website', desc: 'Récupère l\'entreprise ProspectLab à partir d\'un website (URL ou domaine).', params: [{ name: 'website', type: 'str', desc: 'Requis (URL ou domaine)' }] },
                    { method: 'GET', path: '/entreprises/<id>/emails', desc: 'Emails scrapés d\'une entreprise.' }
                ]
            },
            {
                id: 'statuts-entreprise',
                name: 'Statuts entreprise',
                endpoints: [
                    { method: 'GET', path: '/entreprises/statuses', desc: 'Liste des statuts d’entreprise supportés (pipeline + désabonnement/bounce/réponses).' },
                    { method: 'PATCH', path: '/entreprises/<id>/statut', desc: 'Met à jour le statut d’une entreprise (générique).', body: 'JSON: { "statut": <string>, "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/unsubscribe', desc: 'Raccourci: marque l’entreprise comme Désabonné.', body: 'JSON: { "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/negative-reply', desc: 'Raccourci: marque l’entreprise comme Réponse négative.', body: 'JSON: { "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/bounce', desc: 'Raccourci: marque l’entreprise comme Bounce.', body: 'JSON: { "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/positive-reply', desc: 'Raccourci: marque l’entreprise comme Réponse positive.', body: 'JSON: { "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/spam-complaint', desc: 'Raccourci: marque l’entreprise comme Plainte spam.', body: 'JSON: { "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/do-not-contact', desc: 'Raccourci: marque l’entreprise comme Ne pas contacter.', body: 'JSON: { "note": <string optionnel> }' },
                    { method: 'POST', path: '/entreprises/<id>/callback', desc: 'Raccourci: marque l’entreprise comme À rappeler.', body: 'JSON: { "note": <string optionnel> }' }
                ]
            },
            {
                id: 'emails-campagnes',
                name: 'Emails & campagnes',
                endpoints: [
                    { method: 'GET', path: '/emails', desc: 'Liste de tous les emails.', params: [{ name: 'limit', type: 'int' }, { name: 'offset', type: 'int' }, { name: 'entreprise_id', type: 'int' }] },
                    { method: 'GET', path: '/entreprises/<id>/emails/all', desc: 'Tous les emails d\'une entreprise (email_principal + scrapers) avec infos personne/analyse.', params: [{ name: 'include_primary', type: 'bool', desc: 'Optionnel (défaut true)' }] },
                    { method: 'GET', path: '/statistics', desc: 'Statistiques globales.' },
                    { method: 'GET', path: '/campagnes', desc: 'Liste des campagnes email.', params: [{ name: 'limit', type: 'int' }, { name: 'offset', type: 'int' }, { name: 'statut', type: 'str' }] },
                    { method: 'GET', path: '/campagnes/<id>', desc: 'Détails d\'une campagne.' },
                    { method: 'GET', path: '/campagnes/<id>/emails', desc: 'Emails envoyés d\'une campagne.', params: [{ name: 'limit', type: 'int' }, { name: 'offset', type: 'int' }, { name: 'statut', type: 'str' }] },
                    { method: 'GET', path: '/campagnes/<id>/statistics', desc: 'Statistiques de tracking (ouvertures, clics).' }
                ]
            },
            {
                id: 'website-analysis',
                name: 'Website analysis',
                endpoints: [
                    { method: 'POST', path: '/website-analysis', desc: 'Lance une analyse complète d’un site (scraping + technique + SEO + OSINT + pentest) ou retourne le rapport existant.', body: 'JSON: website (requis), force?, full?, max_depth?, max_workers?, max_time?, max_pages?, enable_nmap?, use_lighthouse?' },
                    { method: 'GET', path: '/website-analysis', desc: 'Récupère un rapport d’analyse existant pour un site.', params: [{ name: 'website', type: 'str', desc: 'Requis (URL ou domaine)' }, { name: 'full', type: 'bool', desc: 'Optionnel (inclut items de scraping, volumineux)' }] }
                ]
            }
        ]
    }
];
