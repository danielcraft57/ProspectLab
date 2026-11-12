# -*- coding: utf-8 -*-
"""
Payload Socket.IO pour les événements de fin de scraping (Flask + worker Celery).
"""


def flatten_scrape_socket_payload(results, entreprise_id=None):
    """
    Aplatit le dict « results » du scraper pour l'UI (totaux + listes).

    @param results: Bloc résultats du scraper
    @param entreprise_id: ID entreprise optionnel
    @returns: Dict émissible en ``scraping_complete``
    """
    if not isinstance(results, dict):
        results = {}
    r = results
    emails_raw = r.get('emails') or []
    emails_list = []
    for e in emails_raw:
        if isinstance(e, dict) and e.get('email'):
            emails_list.append(e['email'])
        elif isinstance(e, str):
            emails_list.append(e)
    return {
        'success': True,
        'entreprise_id': entreprise_id,
        'total_emails': r.get('total_emails', len(emails_raw)),
        'total_people': r.get('total_people', 0),
        'total_phones': r.get('total_phones', 0),
        'emails': emails_list,
        'people': r.get('people') or [],
        'phones': r.get('phones') or [],
        'social_links': r.get('social_links') or {},
        'technologies': r.get('technologies') or {},
        'metadata': r.get('metadata') or {},
        'images': r.get('images') or [],
        'scraped_location': r.get('scraped_location'),
        'results': r,
    }


def emit_scraping_outcome_from_worker(task_result):
    """
    Émet ``scraping_complete`` ou ``scraping_error`` via Redis (tous les clients).

    Filet de sécurité si le monitor WebSocket a été remplacé par un autre lancement sur le même onglet.

    @param task_result: Dict retour de ``run_scrape_emails_inline`` / ``scrape_emails_task``
    """
    if not isinstance(task_result, dict):
        return
    from utils.celery_socketio_emit import emit_from_celery_worker

    eid = task_result.get('entreprise_id')
    if task_result.get('success') is False:
        err = task_result.get('error') or 'Échec scraping'
        emit_from_celery_worker(
            'scraping_error',
            {'error': str(err), 'entreprise_id': eid},
        )
        return
    res_block = (task_result or {}).get('results') or {}
    payload = flatten_scrape_socket_payload(res_block, eid)
    emit_from_celery_worker('scraping_complete', payload)
