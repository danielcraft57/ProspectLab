#!/usr/bin/env bash
# Applique un overlay table par table, ignore les tables absentes du schema.
set -euo pipefail
SQL_FILE="${1:?sql file}"
DB_URL_OR_PASS_MODE="${2:-local}"

export PGPASSWORD="${DB_PASSWORD:?DB_PASSWORD required}"
PSQL=(psql -h 127.0.0.1 -U prospectlab -d prospectlab -v ON_ERROR_STOP=1)

# Split loosely on TRUNCATE blocks
python3 - <<'PY' "$SQL_FILE"
import sys
path=sys.argv[1]
text=open(path,encoding='utf-8').read()
# keep SET preamble
pre=[]
blocks=[]
cur=[]
for line in text.splitlines(True):
    if line.startswith('TRUNCATE TABLE') and cur and any(x.startswith('COPY ') for x in cur):
        blocks.append(''.join(cur))
        cur=[line]
    else:
        if not blocks and not cur and (line.startswith('SET ') or line.strip()==''):
            pre.append(line)
            continue
        cur.append(line)
if cur:
    blocks.append(''.join(cur))
open('/tmp/overlay_pre.sql','w',encoding='utf-8').write(''.join(pre))
for i,b in enumerate(blocks):
    open(f'/tmp/overlay_block_{i:03d}.sql','w',encoding='utf-8').write(b)
print(len(blocks))
PY

"${PSQL[@]}" -f /tmp/overlay_pre.sql >/dev/null 2>&1 || true
for f in /tmp/overlay_block_*.sql; do
  echo "[*] $f"
  if ! "${PSQL[@]}" -f "$f" >/tmp/overlay_block_last.log 2>&1; then
    echo "  SKIP/FAIL:"
    tail -n 5 /tmp/overlay_block_last.log || true
  else
    echo "  OK"
  fi
done
echo DONE
