#!/usr/bin/env bash
# Test local sur serv2 : sync inbox ProspectLab (JSON stdout).

set -euo pipefail

JOB="${1:-sync}"
SCRIPTS="${SOCIALDESK_REPO_ROOT:-/home/pi/Documents/socialdesk}/deploy/scripts"
FB_DIR="${SOCIALDESK_REPO_ROOT:-/home/pi/Documents/socialdesk}/facebook-playwright"

case "$JOB" in
  sync)
    JOB_TYPE="messenger_sync"
    PAYLOAD_JSON='{"max_threads":3,"headless":true}'
    ;;
  cookies)
    JOB_TYPE="cookies_refresh"
    PAYLOAD_JSON='{"headless":true}'
    ;;
  check)
    JOB_TYPE="check_session"
    PAYLOAD_JSON='{}'
    ;;
  *)
    echo "Usage: $0 sync|cookies|check"
    exit 1
    ;;
esac

PAYLOAD_B64=$(python3 - "$JOB_TYPE" "$PAYLOAD_JSON" "$FB_DIR" <<'PY'
import base64, json, sys
job_type, payload_raw, fb_dir = sys.argv[1], sys.argv[2], sys.argv[3]
payload = json.loads(payload_raw)
job = {
    "account": "danielcraft",
    "job_type": job_type,
    "payload": payload,
    "facebook_module_dir": fb_dir,
}
print(base64.b64encode(json.dumps(job, ensure_ascii=False).encode()).decode())
PY
)

export PYTHONUNBUFFERED=1
python3 -u "$SCRIPTS/prospectlab_facebook_remote.py" --payload-b64 "$PAYLOAD_B64"
