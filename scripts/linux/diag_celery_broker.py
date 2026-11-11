#!/usr/bin/env python3
"""Diagnostic broker Celery + ping depuis l'app."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
os.chdir(ROOT)

import redis
from config import CELERY_BROKER_URL
from utils.celery_health import broker_ping_ok, online_workers_count

print('redis-py', redis.__version__)
print('CELERY_BROKER_URL', CELERY_BROKER_URL)
print('broker_ping_ok', broker_ping_ok(ttl_seconds=0))
print('online_workers', online_workers_count(ttl_seconds=0))

try:
    from celery_app import celery

    insp = celery.control.inspect(timeout=3.0)
    active = insp.active() or {}
    reserved = insp.reserved() or {}
    scheduled = insp.scheduled() or {}
    total_active = sum(len(v or []) for v in active.values())
    total_reserved = sum(len(v or []) for v in reserved.values())
    total_scheduled = sum(len(v or []) for v in scheduled.values())
    print('tasks active', total_active)
    print('tasks reserved', total_reserved)
    print('tasks scheduled', total_scheduled)
except Exception as e:
    print('inspect error', e)
