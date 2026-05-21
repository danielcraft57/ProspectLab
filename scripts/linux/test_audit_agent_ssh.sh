#!/usr/bin/env bash
# Test SSH/SCP Pi → serv1 pour les rapports d'audit (à lancer sur node15).
set -euo pipefail

cd /opt/prospectlab

# Retire les CR Windows (sinon ssh: « hostname contains invalid characters »)
if [ -f .env ] && grep -q $'\r' .env 2>/dev/null; then
  echo "Correction des fins de ligne CRLF dans .env..."
  sed -i 's/\r$//' .env
fi

set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a

strip_var() { printf '%s' "$1" | tr -d '\r\n' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//'; }

HOST="$(strip_var "${LANDING_VARIANTS_REMOTE_HOST:-loicDaniel@serv1.lan}")"
KEY="$(strip_var "${LANDING_VARIANTS_SSH_KEY_PATH:-}")"
SSH_BIN="${SSH_BIN:-$(command -v ssh 2>/dev/null || echo /usr/bin/ssh)}"
SCP_BIN="${SCP_BIN:-$(command -v scp 2>/dev/null || echo /usr/bin/scp)}"
if [ ! -x "$SSH_BIN" ] || [ ! -x "$SCP_BIN" ]; then
  echo "openssh-client manquant. Installez : sudo apt install -y openssh-client"
  exit 1
fi
SSH=("$SSH_BIN" -o ConnectTimeout=15 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
SCP=("$SCP_BIN" -o ConnectTimeout=15 -o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [ -n "$KEY" ]; then
  if [ ! -r "$KEY" ]; then
    echo "Clé SSH introuvable ou illisible: $KEY"
    echo "Créez-la : ssh-keygen -t ed25519 -f $KEY -N \"\""
    echo "Puis : ssh-copy-id -i ${KEY}.pub $HOST"
    exit 1
  fi
  SSH+=(-i "$KEY")
  SCP+=(-i "$KEY")
fi

if printf '%s' "$HOST" | grep -q '[^a-zA-Z0-9.@_:-]'; then
  echo "HOST invalide (caractères parasites — souvent CRLF dans .env):"
  printf '%s' "$HOST" | od -An -tx1 | head -3
  exit 1
fi

echo "=== Test 1: SSH vers $HOST ==="
"${SSH[@]}" "$HOST" 'powershell -NoProfile -Command "echo OK"' || {
  echo "ÉCHEC SSH. Essayez : ${SSH_BIN} -v $HOST"
  echo "Ou : ssh-copy-id -i ${KEY:-$HOME/.ssh/id_rsa}.pub $HOST"
  exit 1
}

echo "=== Test 2: script audit présent ==="
test -f scripts/experiments/gen_audit_report/generate_website_audit_cursor_remote.py && echo OK || exit 1

echo "=== Test 3: dry-run --help ==="
/opt/prospectlab/env/bin/python scripts/experiments/gen_audit_report/generate_website_audit_cursor_remote.py --help | head -3

echo "Tout est prêt côté SSH si les 3 tests passent."
