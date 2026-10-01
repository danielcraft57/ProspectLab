#!/usr/bin/env bash
# Convertit .env (CRLF Windows → LF Unix). À lancer sur le serveur après copie depuis Windows.
# Important: ne jamais utiliser sed 's/r$//' (coupe le « r » de .fr dans BASE_URL).
set -euo pipefail

ENV_FILE="${1:-/opt/prospectlab/.env}"
if [ ! -f "$ENV_FILE" ]; then
  echo "Fichier introuvable: $ENV_FILE"
  exit 1
fi

# Conversion via Python: sûr sur les caractères (pas de piège sed \r → r)
python3 - "$ENV_FILE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
raw = path.read_bytes()
if b"\r" not in raw:
    print(f"Déjà au format Unix: {path}")
    raise SystemExit(0)
cleaned = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
path.write_bytes(cleaned)
print(f"CRLF corrigés dans {path}")
PY
