#!/usr/bin/env bash
# Purge l'etat Celery Beat corrompu avant redemarrage (shelve vide, incomplet ou pid obsolete).
# A lancer depuis la racine du projet ou via scripts/linux/.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR" || exit 1

SCHEDULE_BASE="celerybeat-schedule"
PIDFILE="celery_beat.pid"
should_purge=false

if [ -f "${SCHEDULE_BASE}.dat" ]; then
    dat_size=$(stat -c%s "${SCHEDULE_BASE}.dat" 2>/dev/null || echo 0)
    if [ "$dat_size" -eq 0 ]; then
        echo "[!] ${SCHEDULE_BASE}.dat vide (${dat_size} o) : purge necessaire"
        should_purge=true
    fi
fi

if [ -f "${SCHEDULE_BASE}.dat" ] && [ ! -f "${SCHEDULE_BASE}.dir" ]; then
    echo "[!] ${SCHEDULE_BASE}.dir manquant : purge necessaire"
    should_purge=true
fi

if [ -f "${SCHEDULE_BASE}.dir" ] && [ ! -f "${SCHEDULE_BASE}.dat" ]; then
    echo "[!] ${SCHEDULE_BASE}.dat manquant : purge necessaire"
    should_purge=true
fi

if [ -f "$PIDFILE" ]; then
    pid=$(tr -d '[:space:]' < "$PIDFILE" 2>/dev/null || true)
    if [ -z "$pid" ] || ! kill -0 "$pid" 2>/dev/null; then
        echo "[!] PID obsolete dans ${PIDFILE} (pid=${pid:-vide}) : suppression"
        rm -f "$PIDFILE"
    fi
fi

if [ "$should_purge" = true ]; then
    echo "[*] Suppression de l'etat Celery Beat corrompu..."
    rm -f "${SCHEDULE_BASE}.bak" "${SCHEDULE_BASE}.dat" "${SCHEDULE_BASE}.dir" "$PIDFILE"
    echo "[*] Etat Celery Beat purge."
else
    echo "[*] Etat Celery Beat OK, aucune purge."
fi
