"""
Tâches Celery pour la génération de landing variants via agent distant (serv1).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from celery_app import celery
from config import (
    CELERY_BROKER_URL,
    LANDING_VARIANTS_AGENT_TIMEOUT,
    LANDING_VARIANTS_ENABLED,
    LANDING_VARIANTS_MODEL,
    LANDING_VARIANTS_REMOTE_CURSOR_COMMAND,
    LANDING_VARIANTS_REMOTE_HOST,
    LANDING_VARIANTS_REMOTE_OUTPUT_ROOT,
    LANDING_VARIANTS_REMOTE_TEMP_ROOT,
    LANDING_VARIANTS_REMOTE_WORKSPACE,
    LANDING_VARIANTS_SCRIPT_PATH,
    LANDING_VARIANTS_SERV1_MAX_CONCURRENT,
    LANDING_VARIANTS_SERV1_SEMAPHORE_KEY,
    LANDING_VARIANTS_SERV1_SEMAPHORE_TTL_SEC,
    LANDING_VARIANTS_SERV1_WAIT_MAX_SEC,
    LANDING_VARIANTS_SERV1_WAIT_RETRY_SEC,
    LANDING_VARIANTS_SSH_KEY_PATH,
    LANDING_VARIANTS_STATIC_OUTPUT_DIR,
    LANDING_VARIANTS_USAGE_LIMIT_RETRIES,
    LANDING_VARIANTS_USAGE_LIMIT_RETRY_DELAY_SEC,
    LANDING_VARIANTS_PUBLIC_BASE_URL,
)
from services.database import Database
from services.logging_config import setup_logger
from utils.celery_socketio_emit import emit_from_celery_worker

logger = setup_logger(__name__, "landing_variant_tasks.log")

USAGE_LIMIT_MARKERS = (
    "usage limit",
    "hit your usage limit",
    "get cursor pro",
    "free plan",
    "quota",
)

_redis_client = None
_AUTOHEAL_CHECK_EVERY_ATTEMPTS = 2


def _website_slug_from_url(url: str) -> str:
    from urllib.parse import urlparse

    host = urlparse(str(url or "").strip()).netloc or "site"
    return re.sub(r"[^\w.\-]", "_", host) or "site"


def _mime_type_from_name(name: str) -> str:
    low = (name or "").lower()
    if low.endswith(".html"):
        return "text/html"
    if low.endswith(".css"):
        return "text/css"
    if low.endswith(".js"):
        return "application/javascript"
    if low.endswith(".webp"):
        return "image/webp"
    return "application/octet-stream"


def _resolve_entreprise_from_url(db: Database, url: str) -> tuple[int | None, dict | None]:
    try:
        eid = db.find_duplicate_entreprise(nom="", website=url)
    except Exception:
        eid = None
    if not eid:
        return None, None
    try:
        entreprise = db.get_entreprise(int(eid))
    except Exception:
        entreprise = None
    return (int(eid), entreprise) if eid else (None, None)


def _collect_generated_assets(site_output_dir: Path, public_root_url: str) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for variant_dir in sorted(site_output_dir.glob("variant_*")):
        if not variant_dir.is_dir():
            continue
        vname = variant_dir.name
        m = re.search(r"(\d+)$", vname)
        vindex = int(m.group(1)) if m else None
        for fname, kind in (("index.html", "html"), ("style.css", "css"), ("script.js", "js")):
            fp = variant_dir / fname
            if not fp.is_file():
                continue
            rel = fp.relative_to(site_output_dir).as_posix()
            assets.append(
                {
                    "variant_name": vname,
                    "variant_index": vindex,
                    "asset_kind": kind,
                    "device_type": None,
                    "relative_path": rel,
                    "file_path": str(fp),
                    "public_url": f"{public_root_url.rstrip('/')}/{rel}",
                    "mime_type": _mime_type_from_name(fname),
                    "size_bytes": int(fp.stat().st_size),
                }
            )
        screenshot_patterns = [
            (f"{vname}.webp", "desktop"),
            (f"{vname}.desktop.webp", "desktop"),
            (f"{vname}.tablet.webp", "tablet"),
            (f"{vname}.mobile.webp", "mobile"),
        ]
        for filename, device in screenshot_patterns:
            fp = site_output_dir / filename
            if not fp.is_file():
                continue
            rel = fp.relative_to(site_output_dir).as_posix()
            assets.append(
                {
                    "variant_name": vname,
                    "variant_index": vindex,
                    "asset_kind": "screenshot",
                    "device_type": device,
                    "relative_path": rel,
                    "file_path": str(fp),
                    "public_url": f"{public_root_url.rstrip('/')}/{rel}",
                    "mime_type": "image/webp",
                    "size_bytes": int(fp.stat().st_size),
                }
            )
    return assets


def _redis():
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


def _semaphore_release() -> str:
    return """
local key = KEYS[1]
local value = tonumber(redis.call('get', key) or '0')
if value <= 0 then
  redis.call('set', key, 0, 'EX', tonumber(ARGV[2]))
  return 0
end
local next = value - 1
if next <= 0 then
  redis.call('set', key, 0, 'EX', tonumber(ARGV[2]))
  return 0
end
redis.call('set', key, next, 'EX', tonumber(ARGV[2]))
return next
"""


def _try_acquire_slot() -> bool:
    script = """
local key = KEYS[1]
local maxv = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local value = tonumber(redis.call('get', key) or '0')
if value >= maxv then
  return 0
end
local next = value + 1
redis.call('set', key, next, 'EX', ttl)
return 1
"""
    return bool(
        _redis().eval(
            script,
            1,
            LANDING_VARIANTS_SERV1_SEMAPHORE_KEY,
            LANDING_VARIANTS_SERV1_MAX_CONCURRENT,
            LANDING_VARIANTS_SERV1_SEMAPHORE_TTL_SEC,
        )
    )


def _release_slot() -> None:
    try:
        _redis().eval(
            _semaphore_release(),
            1,
            LANDING_VARIANTS_SERV1_SEMAPHORE_KEY,
            0,
            LANDING_VARIANTS_SERV1_SEMAPHORE_TTL_SEC,
        )
    except Exception:
        logger.warning("Release semaphore serv1 impossible", exc_info=True)


def _count_active_landing_variant_tasks() -> int | None:
    """
    Retourne le nombre de tâches landing variants actives vues par Celery inspect.
    None en cas d'impossibilité de lecture.
    """
    try:
        insp = celery.control.inspect(timeout=2.0)
        active = insp.active() or {}
        total = 0
        for tasks in active.values():
            for item in tasks or []:
                name = str((item or {}).get("name") or "")
                if name == "tasks.landing_variant_tasks.generate_landing_variants_remote_task":
                    total += 1
        return total
    except Exception:
        logger.warning("Impossible de lire les tâches Celery actives pour auto-heal", exc_info=True)
        return None


def _autoheal_stale_slot_if_needed() -> bool:
    """
    Si le sémaphore est occupé sans tâche landing active, le réinitialise.
    Retourne True si un auto-heal a été appliqué.
    """
    try:
        r = _redis()
        raw_value = r.get(LANDING_VARIANTS_SERV1_SEMAPHORE_KEY)
        current = int(raw_value or 0)
        ttl = int(r.ttl(LANDING_VARIANTS_SERV1_SEMAPHORE_KEY) or -1)
    except Exception:
        logger.warning("Lecture sémaphore serv1 impossible pour auto-heal", exc_info=True)
        return False

    if current < LANDING_VARIANTS_SERV1_MAX_CONCURRENT:
        return False

    active_count = _count_active_landing_variant_tasks()
    if active_count is None:
        return False
    if active_count > 0:
        logger.info(
            "Auto-heal ignoré: slot occupé légitime (active_landing_tasks=%s value=%s ttl=%s)",
            active_count,
            current,
            ttl,
        )
        return False

    try:
        r.set(LANDING_VARIANTS_SERV1_SEMAPHORE_KEY, 0, ex=LANDING_VARIANTS_SERV1_SEMAPHORE_TTL_SEC)
        logger.warning(
            "Auto-heal appliqué: sémaphore serv1 réinitialisé à 0 (value=%s ttl=%s, active_landing_tasks=0)",
            current,
            ttl,
        )
        return True
    except Exception:
        logger.warning("Auto-heal impossible: reset sémaphore serv1 échoué", exc_info=True)
        return False


def _wait_for_slot(task) -> bool:
    logger.info(
        "Attente slot serv1: key=%s max_concurrent=%s wait_max_sec=%s retry_sec=%s",
        LANDING_VARIANTS_SERV1_SEMAPHORE_KEY,
        LANDING_VARIANTS_SERV1_MAX_CONCURRENT,
        LANDING_VARIANTS_SERV1_WAIT_MAX_SEC,
        LANDING_VARIANTS_SERV1_WAIT_RETRY_SEC,
    )
    deadline = time.monotonic() + float(LANDING_VARIANTS_SERV1_WAIT_MAX_SEC)
    attempts = 0
    while time.monotonic() < deadline:
        attempts += 1
        if _try_acquire_slot():
            logger.info("Slot serv1 acquis")
            return True
        if attempts % _AUTOHEAL_CHECK_EVERY_ATTEMPTS == 0:
            healed = _autoheal_stale_slot_if_needed()
            if healed:
                # Réessayer immédiatement après auto-heal.
                if _try_acquire_slot():
                    logger.info("Slot serv1 acquis après auto-heal")
                    return True
        msg = "En attente d'un slot serv1 (limitation de concurrence active)..."
        try:
            task.update_state(state="PROGRESS", meta={"step": "queue", "message": msg})
        except Exception:
            pass
        emit_from_celery_worker("landing_variants_progress", {"step": "queue", "message": msg})
        time.sleep(float(LANDING_VARIANTS_SERV1_WAIT_RETRY_SEC))
    logger.warning("Timeout attente slot serv1")
    return False


def _contains_usage_limit(text: str) -> bool:
    low = (text or "").lower()
    return any(marker in low for marker in USAGE_LIMIT_MARKERS)


def _build_command(
    *,
    url: str,
    variants: int,
    free_mode: bool,
    output_dir: str | None,
    extra_instructions: str | None,
    screenshot_desktop_only: bool,
    skip_screenshots: bool,
) -> list[str]:
    cmd = [
        sys.executable,
        str(Path(LANDING_VARIANTS_SCRIPT_PATH)),
        "--url",
        url,
        "--remote-host",
        LANDING_VARIANTS_REMOTE_HOST,
        "--remote-cursor-command",
        LANDING_VARIANTS_REMOTE_CURSOR_COMMAND,
        "--model",
        LANDING_VARIANTS_MODEL,
        "--agent-timeout",
        str(LANDING_VARIANTS_AGENT_TIMEOUT),
        "--remote-temp-root",
        LANDING_VARIANTS_REMOTE_TEMP_ROOT,
        "--remote-output-root",
        LANDING_VARIANTS_REMOTE_OUTPUT_ROOT,
        "--variants",
        str(variants),
        "--log-level",
        "INFO",
    ]
    if LANDING_VARIANTS_REMOTE_WORKSPACE.strip():
        cmd.extend(["--remote-workspace", LANDING_VARIANTS_REMOTE_WORKSPACE.strip()])
    if LANDING_VARIANTS_SSH_KEY_PATH.strip():
        cmd.extend(["--ssh-key-path", LANDING_VARIANTS_SSH_KEY_PATH.strip()])
    if free_mode:
        cmd.append("--free-mode")
    if output_dir:
        cmd.extend(["--output-dir", str(output_dir)])
    if extra_instructions:
        cmd.extend(["--extra-instructions", str(extra_instructions)])
    if screenshot_desktop_only:
        cmd.append("--screenshot-desktop-only")
    if skip_screenshots:
        cmd.append("--skip-screenshots")
    return cmd


def _sanitize_cmd_for_log(cmd: list[str]) -> str:
    """
    Évite de logger des secrets potentiels dans la ligne de commande.
    """
    safe: list[str] = []
    hide_next = False
    secret_flags = {"--ssh-key-path", "--extra-instructions"}
    for part in cmd:
        if hide_next:
            safe.append("***")
            hide_next = False
            continue
        if part in secret_flags:
            safe.append(part)
            hide_next = True
            continue
        safe.append(str(part))
    return " ".join(safe)


@celery.task(bind=True, name="tasks.landing_variant_tasks.generate_landing_variants_remote_task")
def generate_landing_variants_remote_task(
    self,
    *,
    url: str,
    entreprise_id: int | None = None,
    launch_lock_key: str | None = None,
    variants: int = 4,
    free_mode: bool = True,
    output_dir: str | None = None,
    extra_instructions: str | None = None,
    screenshot_desktop_only: bool = False,
    skip_screenshots: bool = False,
) -> dict[str, Any]:
    task_id = str(getattr(self.request, "id", "") or "")
    if not LANDING_VARIANTS_ENABLED:
        logger.warning("Task %s refusée: feature landing variants désactivée", task_id)
        return {"success": False, "error": "landing_variants_disabled"}

    if not url or not str(url).strip():
        logger.warning("Task %s refusée: url manquante", task_id)
        return {"success": False, "error": "url_required"}

    db = Database()
    website_url = str(url).strip()
    ent = None
    if entreprise_id:
        try:
            ent = db.get_entreprise(int(entreprise_id))
        except Exception:
            ent = None
    if ent is None:
        resolved_id, ent = _resolve_entreprise_from_url(db, website_url)
        if resolved_id:
            entreprise_id = resolved_id
            logger.info("Task %s: entreprise résolue depuis URL -> entreprise_id=%s", task_id, resolved_id)

    if not _wait_for_slot(self):
        msg = "Timeout d'attente du slot serv1"
        logger.warning("Task %s: %s", task_id, msg)
        emit_from_celery_worker("landing_variants_error", {"error": msg})
        return {"success": False, "error": "serv1_wait_timeout", "message": msg}

    cmd = _build_command(
        url=website_url,
        variants=max(1, min(int(variants), 4)),
        free_mode=bool(free_mode),
        output_dir=(
            output_dir
            or LANDING_VARIANTS_STATIC_OUTPUT_DIR
        ),
        extra_instructions=extra_instructions,
        screenshot_desktop_only=bool(screenshot_desktop_only),
        skip_screenshots=bool(skip_screenshots),
    )
    logger.info(
        "Task %s start: url=%s entreprise_id=%s variants=%s free_mode=%s desktop_only=%s skip_screenshots=%s output_dir=%s lock_key=%s",
        task_id,
        website_url,
        int(entreprise_id) if entreprise_id else None,
        variants,
        bool(free_mode),
        bool(screenshot_desktop_only),
        bool(skip_screenshots),
        output_dir or LANDING_VARIANTS_STATIC_OUTPUT_DIR,
        launch_lock_key or "",
    )
    logger.info("Task %s command: %s", task_id, _sanitize_cmd_for_log(cmd))
    emit_from_celery_worker(
        "landing_variants_progress",
        {
            "step": "start",
            "message": "Génération des variantes lancée",
            "url": website_url,
            "entreprise_id": int(entreprise_id) if entreprise_id else None,
        },
    )

    try:
        proc = subprocess.run(
            cmd,
            text=True,
            capture_output=True,
            check=False,
            timeout=max(60, LANDING_VARIANTS_AGENT_TIMEOUT + 300),
        )
        out = proc.stdout or ""
        err = proc.stderr or ""
        merged = f"{out}\n{err}".strip()
        logger.info(
            "Task %s subprocess terminé: returncode=%s stdout_len=%s stderr_len=%s",
            task_id,
            proc.returncode,
            len(out),
            len(err),
        )

        if proc.returncode != 0 and _contains_usage_limit(merged):
            retries = int(getattr(self.request, "retries", 0))
            logger.warning(
                "Task %s usage_limit détecté: retries=%s/%s",
                task_id,
                retries,
                LANDING_VARIANTS_USAGE_LIMIT_RETRIES,
            )
            if retries < LANDING_VARIANTS_USAGE_LIMIT_RETRIES:
                emit_from_celery_worker(
                    "landing_variants_usage_limit",
                    {
                        "step": "retry",
                        "retry_in_sec": LANDING_VARIANTS_USAGE_LIMIT_RETRY_DELAY_SEC,
                        "attempt": retries + 1,
                        "max_attempts": LANDING_VARIANTS_USAGE_LIMIT_RETRIES,
                    },
                )
                raise self.retry(
                    countdown=LANDING_VARIANTS_USAGE_LIMIT_RETRY_DELAY_SEC,
                    exc=RuntimeError("usage_limit_retry"),
                )
            logger.error("Task %s arrêtée: usage_limit persistant après retries", task_id)
            emit_from_celery_worker(
                "landing_variants_usage_limit",
                {"step": "failed", "message": "Usage limit atteint sur le compte Cursor."},
            )
            return {
                "success": False,
                "error": "usage_limit",
                "message": "Usage limit atteint sur le compte Cursor",
                "stdout_tail": out[-4000:],
                "stderr_tail": err[-4000:],
            }

        if proc.returncode != 0:
            logger.error(
                "Task %s generation_failed: returncode=%s stdout_tail=%s stderr_tail=%s",
                task_id,
                proc.returncode,
                out[-500:] if out else "",
                err[-500:] if err else "",
            )
            emit_from_celery_worker(
                "landing_variants_error",
                {
                    "error": "generation_failed",
                    "returncode": proc.returncode,
                    "entreprise_id": int(entreprise_id) if entreprise_id else None,
                },
            )
            return {
                "success": False,
                "error": "generation_failed",
                "returncode": proc.returncode,
                "stdout_tail": out[-4000:],
                "stderr_tail": err[-4000:],
            }

        variants_req = max(1, min(int(variants), 4))
        site_slug = _website_slug_from_url(website_url)
        output_root = Path(output_dir or LANDING_VARIANTS_STATIC_OUTPUT_DIR)
        site_output_dir = output_root / site_slug
        public_root_url = f"{LANDING_VARIANTS_PUBLIC_BASE_URL.rstrip('/')}/{site_slug}"
        assets = _collect_generated_assets(site_output_dir, public_root_url)
        logger.info(
            "Task %s assets collectés: site_slug=%s output=%s assets_count=%s",
            task_id,
            site_slug,
            str(site_output_dir),
            len(assets),
        )
        run_id = None
        if entreprise_id:
            try:
                run_id = db.create_landing_variant_run(
                    entreprise_id=int(entreprise_id),
                    website_url=website_url,
                    website_slug=site_slug,
                    source_task_id=str(getattr(self.request, "id", "") or ""),
                    status="completed",
                    variants_requested=variants_req,
                    variants_generated=len(
                        {str(a.get("variant_name")) for a in assets if a.get("variant_name")}
                    ),
                    output_dir=str(site_output_dir),
                    output_base_url=public_root_url,
                )
                if run_id:
                    db.replace_landing_variant_assets(int(run_id), int(entreprise_id), assets)
                logger.info(
                    "Task %s persistance BDD OK: run_id=%s entreprise_id=%s variants_generated=%s",
                    task_id,
                    int(run_id) if run_id else None,
                    int(entreprise_id),
                    len({str(a.get('variant_name')) for a in assets if a.get('variant_name')}),
                )
            except Exception:
                logger.warning("Enregistrement landing variants en BDD impossible", exc_info=True)

        emit_from_celery_worker(
            "landing_variants_complete",
            {
                "success": True,
                "url": website_url,
                "variants": variants_req,
                "entreprise_id": int(entreprise_id) if entreprise_id else None,
                "run_id": int(run_id) if run_id else None,
            },
        )
        logger.info(
            "Task %s complete: success=True run_id=%s assets_count=%s",
            task_id,
            int(run_id) if run_id else None,
            len(assets),
        )
        return {
            "success": True,
            "url": website_url,
            "entreprise_id": int(entreprise_id) if entreprise_id else None,
            "run_id": int(run_id) if run_id else None,
            "variants_requested": variants_req,
            "free_mode": bool(free_mode),
            "output_dir": str(site_output_dir),
            "assets_count": len(assets),
            "stdout_tail": out[-4000:],
        }
    except subprocess.TimeoutExpired:
        logger.error("Task %s timeout subprocess", task_id, exc_info=True)
        emit_from_celery_worker("landing_variants_error", {"error": "timeout"})
        return {"success": False, "error": "timeout"}
    finally:
        _release_slot()
        logger.info("Task %s release slot serv1", task_id)
        if launch_lock_key:
            try:
                _redis().delete(str(launch_lock_key))
                logger.info("Task %s release lock key=%s", task_id, launch_lock_key)
            except Exception:
                logger.warning("Release lock landing variants impossible", exc_info=True)
