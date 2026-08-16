#!/bin/bash
# Force le DNS VPN pour les domaines ProspectLab (NRPT Windows equivalent cote serveur:
# deja fait via dnsmasq). Ce script redeploie app.py durci (login PAS public).
set -euo pipefail
echo "Deploy app.py restriction IP only"
sudo cp /tmp/app.py /opt/prospectlab/app.py
sudo chown pi:pi /opt/prospectlab/app.py
# Garder config si deja present
if [[ -f /tmp/config.py ]]; then
  sudo cp /tmp/config.py /opt/prospectlab/config.py
  sudo chown pi:pi /opt/prospectlab/config.py
fi
sudo systemctl restart prospectlab
sleep 5
systemctl is-active prospectlab
curl -sS -o /dev/null -w "root:%{http_code}\n" http://127.0.0.1:5000/
echo DONE
