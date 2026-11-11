#!/usr/bin/env python3
"""Liste les tâches Celery actives / réservées."""
from __future__ import annotations

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from celery_app import celery

insp = celery.control.inspect(timeout=5)
for label, getter in (('active', insp.active), ('reserved', insp.reserved), ('scheduled', insp.scheduled)):
    print('===', label)
    data = getter() or {}
    if not data:
        print('(vide)')
        continue
    for host, tasks in data.items():
        print(host, len(tasks))
        for t in tasks or []:
            name = t.get('name', '?')
            tid = (t.get('id') or '')[:14]
            print(' -', name, 'id=', tid, 'args=', str(t.get('args', ''))[:100])
