#!/usr/bin/env bash

# Teste qu'un noeud worker Celery de cluster est correctement installé et fonctionnel.
# - Vérifie l'env Python local (/opt/prospectlab/env)
# - Vérifie la connexion Redis / broker
# - Vérifie que les workers répondent
# - Envoie une petite tâche de test et attend le résultat
#
# Usage (sur le RPi: node13.lan, node14.lan, etc.) :
#   cd /opt/prospectlab
#   bash scripts/linux/test_cluster_worker.sh

set -e

PROJECT_DIR="/opt/prospectlab"
ENV_DIR="$PROJECT_DIR/env"

echo "=========================================="
echo "Test du worker Celery ProspectLab (noeud cluster)"
echo "Répertoire projet : $PROJECT_DIR"
echo "Environnement     : $ENV_DIR"
echo "=========================================="
echo

if [ ! -d "$PROJECT_DIR" ]; then
  echo "[✗] $PROJECT_DIR n'existe pas"
  exit 1
fi

cd "$PROJECT_DIR"

if [ ! -d "$ENV_DIR" ]; then
  echo "[✗] Environnement Python introuvable dans $ENV_DIR"
  exit 1
fi

PYTHON_BIN="$ENV_DIR/bin/python"
CELERY_BIN="$ENV_DIR/bin/celery"

if [ ! -x "$PYTHON_BIN" ]; then
  echo "[✗] Python introuvable dans $PYTHON_BIN"
  exit 1
fi

if [ ! -x "$CELERY_BIN" ]; then
  echo "[✗] Celery introuvable dans $CELERY_BIN"
  exit 1
fi

if [ ! -f "$PROJECT_DIR/.env" ]; then
  echo "[✗] Fichier .env introuvable dans $PROJECT_DIR"
  echo "    Copie-le depuis le master puis configure CELERY_BROKER_URL / DATABASE_URL"
  exit 1
fi

echo "[1/4] Test import Celery + configuration..."
$PYTHON_BIN - << 'EOF'
import os
from pathlib import Path

from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent
load_dotenv(base_dir / ".env")

from celery_app import celery  # noqa: E402

print("  - CELERY_BROKER_URL :", os.environ.get("CELERY_BROKER_URL"))
print("  - CELERY_RESULT_BACKEND :", os.environ.get("CELERY_RESULT_BACKEND"))

tasks = [name for name in celery.tasks.keys() if not name.startswith("celery.")]
if not tasks:
    raise SystemExit("Aucune tâche Celery enregistrée (vérifie celery_app.py)")

print(f"  - {len(tasks)} tâches enregistrées")
if "debug.ping" not in celery.tasks:
    raise SystemExit("La tâche debug.ping n'est pas enregistrée. Vérifie que tasks/debug_tasks.py est bien présent et importé, puis redémarre le worker Celery.")
EOF
echo "[✓] Import Celery OK"
echo

echo "[2/4] Vérification du statut des workers..."
$CELERY_BIN -A celery_app status || {
  echo "[✗] Aucun worker ne répond à 'celery -A celery_app status'"
  echo "    Vérifie que le service systemd prospectlab-celery est démarré."
  exit 1
}
echo "[✓] Workers Celery répondent"
echo

echo "[3/4] Test d'une tâche Celery simple..."
$PYTHON_BIN - << 'EOF'
import time
from pathlib import Path

from dotenv import load_dotenv

base_dir = Path(__file__).resolve().parent
load_dotenv(base_dir / ".env")

from celery_app import celery  # noqa: E402

result = celery.send_task("debug.ping", args=(2, 3))
print("  - Tâche debug.ping envoyée, id =", result.id)

for _ in range(30):
    if result.ready():
        break
    time.sleep(1)

if not result.ready():
    raise SystemExit("La tâche debug.ping n'a pas terminé dans le délai imparti")

if result.failed():
    raise SystemExit(f"Échec de la tâche debug.ping : {result.traceback}")

value = result.get()
print("  - Résultat =", value)
if value != 5:
    raise SystemExit("Résultat inattendu pour debug.ping (attendu 5)")
EOF
echo "[✓] Tâche Celery de test exécutée avec succès"
echo

echo "[4/4] Vérification rapide des outils OSINT principaux..."
TOOLS=("nmap" "masscan" "dnsrecon" "whatweb" "sslscan")
for tool in "${TOOLS[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "[OK] $tool détecté"
  else
    echo "[KO] $tool manquant (optionnel selon ton usage)"
  fi
done

echo
echo "[+] Vérification complète des outils (scripts/linux/test_all_tools.sh) ..."
if [ -f "$PROJECT_DIR/scripts/linux/test_all_tools.sh" ]; then
  chmod +x "$PROJECT_DIR/scripts/linux/test_all_tools.sh" 2>/dev/null || true
  bash "$PROJECT_DIR/scripts/linux/test_all_tools.sh" || {
    echo
    echo "[!] Certains tests outils ont échoué. Regarde les lignes [KO] au-dessus."
    exit 1
  }
else
  echo "[!] scripts/linux/test_all_tools.sh introuvable, test complet ignoré"
fi

echo
echo "=========================================="
echo "Le worker Celery semble fonctionner correctement sur ce noeud."
echo "Pour voir les logs :"
echo "  sudo journalctl -u prospectlab-celery -f"
echo "=========================================="

