#!/usr/bin/env bash
# Met à jour les services systemd ProspectLab pour utiliser l'environnement Conda (prefix env)
# À exécuter sur le serveur de production après passage de venv à conda, ou pour réappliquer la config.
# Usage: sudo bash scripts/linux/update_services_to_conda.sh [--restart]

set -e

PROJECT_DIR="${PROJECT_DIR:-/opt/prospectlab}"
RESTART="${1:-}"

echo "[*] Mise à jour des services systemd vers Conda (prefix=$PROJECT_DIR/env)"

# ProspectLab (Gunicorn)
sudo tee /etc/systemd/system/prospectlab.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Flask Application
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/env/bin"
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/env/bin/gunicorn -k eventlet -w 1 -b 0.0.0.0:5000 --timeout 120 --access-logfile /opt/prospectlab/logs/gunicorn_access.log --error-logfile /opt/prospectlab/logs/gunicorn_error.log app:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Celery Worker
sudo tee /etc/systemd/system/prospectlab-celery.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/env/bin"
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/scripts/linux/start_celery_worker.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

# Celery Beat
sudo tee /etc/systemd/system/prospectlab-celerybeat.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Celery Beat Scheduler
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/env/bin"
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/env/bin/celery -A celery_app beat --loglevel=info --logfile=/opt/prospectlab/logs/celery_beat.log --pidfile=/opt/prospectlab/celery_beat.pid
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
echo "[✓] Unités systemd mises à jour et daemon-reload effectué"

if [ "$RESTART" = "--restart" ]; then
    echo "[*] Redémarrage des services..."
    sudo systemctl restart prospectlab prospectlab-celery prospectlab-celerybeat
    echo "[✓] Services redémarrés"
else
    echo "[*] Pour appliquer: sudo systemctl restart prospectlab prospectlab-celery prospectlab-celerybeat"
fi
