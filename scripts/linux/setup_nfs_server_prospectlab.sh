#!/usr/bin/env bash
# ProspectLab - installation serveur NFS (uploads + exports partagés)
# À exécuter UNE FOIS sur le noeud stockage (ex. node15.lan), avec sudo.
#
# Usage:
#   sudo EXPORT_ROOT=/srv/nfs/prospectlab LAN_CIDR=192.168.1.0/24 \
#     bash scripts/linux/setup_nfs_server_prospectlab.sh
#
# Puis sur chaque client (app + workers), utilisez setup_nfs_client_prospectlab.sh
# ou le déploiement (deploy_production / deploy_cluster) qui le lance si NFS_SERVER est défini.

set -euo pipefail

EXPORT_ROOT="${EXPORT_ROOT:-/srv/nfs/prospectlab}"
LAN_CIDR="${LAN_CIDR:-192.168.1.0/24}"

if [ "${SKIP_APT:-0}" != "1" ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y nfs-kernel-server
fi

mkdir -p "${EXPORT_ROOT}/uploads" "${EXPORT_ROOT}/exports"
chmod 755 "${EXPORT_ROOT}" "${EXPORT_ROOT}/uploads" "${EXPORT_ROOT}/exports"

EXPORTS_LINE="${EXPORT_ROOT} ${LAN_CIDR}(rw,sync,no_subtree_check,no_root_squash)"

if [ -f /etc/exports ]; then
  if grep -qF "${EXPORT_ROOT} " /etc/exports 2>/dev/null; then
    echo "Entrée NFS déjà présente pour ${EXPORT_ROOT} dans /etc/exports (rien à ajouter)."
  else
    echo "${EXPORTS_LINE}" >> /etc/exports
    echo "Ajout dans /etc/exports : ${EXPORTS_LINE}"
  fi
else
  echo "${EXPORTS_LINE}" > /etc/exports
fi

exportfs -ra

if systemctl is-active --quiet nfs-server 2>/dev/null; then
  systemctl restart nfs-server
elif systemctl is-active --quiet nfs-kernel-server 2>/dev/null; then
  systemctl restart nfs-kernel-server
else
  systemctl enable --now nfs-kernel-server 2>/dev/null \
    || systemctl enable --now nfs-server 2>/dev/null \
    || true
fi

echo "NFS serveur OK. Export : ${EXPORT_ROOT} -> ${LAN_CIDR}"
echo "Sous-dossiers : ${EXPORT_ROOT}/uploads , ${EXPORT_ROOT}/exports"
