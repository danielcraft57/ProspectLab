"""
Persistance des audits complets en attente (limite Cursor / agent distant).
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from config import AUDIT_REPORTS_DIR, CELERY_BROKER_URL

_AUDIT_RESUME_LOCK_TTL_SEC = 7200
_redis_client = None


def _resume_lock_key(pending_id: str) -> str:
    return f'prospectlab:audit:resume:{(pending_id or "").strip()}'


def _audit_redis():
    global _redis_client
    if _redis_client is None:
        import redis

        _redis_client = redis.Redis.from_url(
            CELERY_BROKER_URL,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
    return _redis_client


def claim_audit_resume_enqueue(pending_id: str) -> tuple[bool, Optional[str]]:
    """
    Verrou Redis anti double-clic / double GET sur /complete/resume.
    Retourne (True, None) si cette requête peut enfiler la tâche.
    Sinon (False, task_id_existante).
    """
    pid = (pending_id or '').strip()
    if not pid:
        return False, None
    key = _resume_lock_key(pid)
    try:
        r = _audit_redis()
        if r.set(key, '__enqueue__', nx=True, ex=_AUDIT_RESUME_LOCK_TTL_SEC):
            return True, None
        existing = (r.get(key) or '').strip()
        if existing and existing not in ('__enqueue__',):
            return False, existing
        return False, None
    except Exception:
        return True, None


def bind_audit_resume_task_id(pending_id: str, celery_task_id: str) -> None:
    pid = (pending_id or '').strip()
    tid = (celery_task_id or '').strip()
    if not pid or not tid:
        return
    try:
        _audit_redis().set(_resume_lock_key(pid), tid, ex=_AUDIT_RESUME_LOCK_TTL_SEC)
    except Exception:
        pass


def get_audit_resume_task_id(pending_id: str) -> Optional[str]:
    pid = (pending_id or '').strip()
    if not pid:
        return None
    try:
        val = (_audit_redis().get(_resume_lock_key(pid)) or '').strip()
    except Exception:
        return None
    if not val or val == '__enqueue__':
        return None
    return val


def release_audit_resume_lock(pending_id: str) -> None:
    pid = (pending_id or '').strip()
    if not pid:
        return
    try:
        _audit_redis().delete(_resume_lock_key(pid))
    except Exception:
        pass


def audit_site_slug(website: str) -> str:
    host = urlparse((website or '').strip()).netloc or 'site'
    return re.sub(r'[^\w.\-]', '_', host) or 'site'


def pending_job_path(website: str, *, pending_id: Optional[str] = None) -> Path:
    slug = audit_site_slug(website)
    if pending_id:
        return AUDIT_REPORTS_DIR / slug / f'pending_{pending_id}.json'
    return AUDIT_REPORTS_DIR / slug / 'pending_agent.json'


def _legacy_pending_path(website: str) -> Path:
    return AUDIT_REPORTS_DIR / audit_site_slug(website) / 'pending_serv1.json'


def save_pending_agent_job(payload: Dict[str, Any]) -> str:
    """Enregistre le job en pause ; retourne pending_id."""
    website = (payload.get('website') or '').strip()
    if not website:
        raise ValueError('website requis pour pending job')
    existing_id = (payload.get('pending_id') or '').strip()
    pending_id = existing_id or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    payload = dict(payload)
    payload['pending_id'] = pending_id
    if not (payload.get('resume_token') or '').strip():
        payload['resume_token'] = secrets.token_urlsafe(32)
    payload['saved_at'] = payload.get('saved_at') or datetime.now(timezone.utc).isoformat()
    path = pending_job_path(website, pending_id=pending_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    latest = pending_job_path(website)
    latest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    return pending_id


def refresh_pending_resume_token(
    *,
    pending_id: str,
    website: Optional[str] = None,
) -> Optional[str]:
    """Régénère le jeton de reprise (jobs créés avant l’ajout du resume_token)."""
    pending = load_pending_agent_job(pending_id=pending_id, website=website)
    if not pending:
        return None
    pending['resume_token'] = secrets.token_urlsafe(32)
    save_pending_agent_job(pending)
    return pending['resume_token']


def validate_pending_resume_token(
    *,
    pending_id: str,
    resume_token: str,
    website: Optional[str] = None,
) -> bool:
    """Vérifie le jeton de reprise d'un job en pause (lien email admin)."""
    token = (resume_token or '').strip()
    pid = (pending_id or '').strip()
    if not token or not pid:
        return False
    pending = load_pending_agent_job(pending_id=pid, website=website)
    if not pending:
        return False
    expected = (pending.get('resume_token') or '').strip()
    if not expected:
        return False
    return secrets.compare_digest(token, expected)


def reopen_pending_after_failed_resume(pending: Dict[str, Any]) -> Dict[str, Any]:
    """Réouvre un job bloqué en resume_queued après échec Celery (nouvelle reprise possible)."""
    updated = dict(pending)
    if updated.get('status') == 'resume_queued':
        reason = (updated.get('reason') or '').strip()
        updated['status'] = 'paused_cursor' if reason == 'cursor_usage_limit' else 'paused_agent'
    updated.pop('resume_celery_task_id', None)
    updated.pop('resume_queued_at', None)
    save_pending_agent_job(updated)
    return updated


def mark_pending_resume_queued(
    pending: Dict[str, Any],
    *,
    celery_task_id: str,
) -> Dict[str, Any]:
    """Évite deux reprises Celery simultanées (double clic sur le lien admin)."""
    updated = dict(pending)
    updated['status'] = 'resume_queued'
    updated['resume_celery_task_id'] = (celery_task_id or '').strip()
    updated['resume_queued_at'] = datetime.now(timezone.utc).isoformat()
    save_pending_agent_job(updated)
    return updated


def load_pending_agent_job(
    *,
    pending_id: Optional[str] = None,
    website: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    if website:
        if pending_id:
            path = pending_job_path(website, pending_id=pending_id)
            if path.is_file():
                return json.loads(path.read_text(encoding='utf-8'))
        for candidate in (pending_job_path(website), _legacy_pending_path(website)):
            if candidate.is_file():
                return json.loads(candidate.read_text(encoding='utf-8'))
    if pending_id:
        for path in AUDIT_REPORTS_DIR.glob(f'*/pending_{pending_id}.json'):
            if path.is_file():
                return json.loads(path.read_text(encoding='utf-8'))
    return None


def list_pending_agent_jobs(limit: int = 20) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for path in sorted(AUDIT_REPORTS_DIR.glob('*/pending_*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name in ('pending_agent.json', 'pending_serv1.json'):
            continue
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if data.get('status') in ('paused_agent', 'paused_cursor'):
                out.append(data)
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


# Rétrocompatibilité
save_pending_serv1_job = save_pending_agent_job
load_pending_serv1_job = load_pending_agent_job
list_pending_serv1_jobs = list_pending_agent_jobs
