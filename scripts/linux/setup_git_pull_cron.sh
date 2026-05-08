#!/usr/bin/env bash
set -euo pipefail

# Configure un cron de synchronisation git (git fetch + git pull) pour ProspectLab.
# Usage:
#   bash scripts/linux/setup_git_pull_cron.sh
# Variables optionnelles:
#   PROSPECTLAB_PATH=/opt/prospectlab
#   GIT_BRANCH=main
#   CRON_SCHEDULE="*/5 * * * *"
#   LOG_FILE=/var/log/prospectlab_git_sync.log

PROSPECTLAB_PATH="${PROSPECTLAB_PATH:-/opt/prospectlab}"
GIT_BRANCH="${GIT_BRANCH:-main}"
CRON_SCHEDULE="${CRON_SCHEDULE:-*/5 * * * *}"
LOG_FILE="${LOG_FILE:-/var/log/prospectlab_git_sync.log}"

if [ ! -d "$PROSPECTLAB_PATH/.git" ]; then
  echo "Repository git introuvable: $PROSPECTLAB_PATH"
  exit 1
fi

CRON_CMD="cd $PROSPECTLAB_PATH && git fetch --all --prune && git checkout $GIT_BRANCH && git pull origin $GIT_BRANCH >> $LOG_FILE 2>&1"
CRON_LINE="$CRON_SCHEDULE $CRON_CMD"

TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null | grep -v "git pull origin $GIT_BRANCH" > "$TMP_CRON" || true
printf "%s\n" "$CRON_LINE" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "Cron git pull configuré."
echo "Path: $PROSPECTLAB_PATH"
echo "Branch: $GIT_BRANCH"
echo "Schedule: $CRON_SCHEDULE"
echo "Log: $LOG_FILE"
