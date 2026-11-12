#!/bin/bash
set -euo pipefail
cd /opt/prospectlab
set -a
# shellcheck disable=SC1091
source .env
set +a
export PATH="/opt/prospectlab/env/bin:/usr/bin:/bin"
exec xvfb-run -a ./env/bin/python scripts/linux/test_playwright_chromium.py
