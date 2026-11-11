#!/usr/bin/env python3
"""Révoque les tâches actives (déblocage worker après screenshots bloqués)."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from celery_app import celery

insp = celery.control.inspect(timeout=5)
active = insp.active() or {}
revoked = 0
for _host, tasks in active.items():
    for t in tasks or []:
        tid = t.get('id')
        if not tid:
            continue
        celery.control.revoke(tid, terminate=True)
        print('revoked', tid, t.get('name'))
        revoked += 1
print('total', revoked)
