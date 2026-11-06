#!/usr/bin/env bash
# Installe ou met a jour les dependances Python de ProspectLab (etape deploy [6/9]).
# Compatible Python 3.11+ (prod node15 peut etre en 3.13 : wheels psycopg2-binary>=2.9.10, lxml>=5).

set -u

REMOTE_ROOT="${1:-/opt/prospectlab}"
cd "$REMOTE_ROOT" || exit 1

if [ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/miniconda3/etc/profile.d/conda.sh"
elif [ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]; then
  # shellcheck source=/dev/null
  source "$HOME/anaconda3/etc/profile.d/conda.sh"
fi

if [ ! -d "$REMOTE_ROOT/env" ]; then
  conda create --prefix "$REMOTE_ROOT/env" python=3.11 -y --override-channels -c conda-forge
fi

PY="$REMOTE_ROOT/env/bin/python"
PIP="$REMOTE_ROOT/env/bin/pip"

"$PIP" install --upgrade pip setuptools wheel
"$PIP" install -r requirements.txt
pip_ec=$?

"$PY" -c "import psycopg2, lxml, flask, celery, redis"
import_ec=$?

if [ "$import_ec" -ne 0 ]; then
  echo "Imports critiques manquants (psycopg2, lxml, flask, celery, redis)." >&2
  exit 1
fi

if [ "$pip_ec" -ne 0 ]; then
  echo "WARN: pip install a signale une erreur mais l environnement reste utilisable."
fi

exit 0
