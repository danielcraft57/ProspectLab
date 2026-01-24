#!/usr/bin/env bash
# Script pour corriger le service Celery

sudo tee /etc/systemd/system/prospectlab-celery.service > /dev/null << 'SERVICE_EOF'
[Unit]
Description=ProspectLab Celery Worker
After=network.target postgresql.service redis-server.service

[Service]
Type=forking
User=pi
Group=pi
WorkingDirectory=/opt/prospectlab
Environment="PATH=/opt/prospectlab/venv/bin"
EnvironmentFile=/opt/prospectlab/.env
ExecStart=/opt/prospectlab/scripts/linux/start_celery_worker.sh
ExecStop=/bin/sh -c "kill -s TERM \$(cat /opt/prospectlab/celery_worker.pid 2>/dev/null) || true"
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
SERVICE_EOF

sudo systemctl daemon-reload
sudo systemctl restart prospectlab-celery
sleep 2
sudo systemctl status prospectlab-celery --no-pager | head -15

