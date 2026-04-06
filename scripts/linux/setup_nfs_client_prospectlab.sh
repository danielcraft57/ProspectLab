#!/usr/bin/env bash
# ProspectLab - montage NFS client sur UPLOAD_FOLDER + EXPORT_FOLDER
# Usage:
#   sudo REMOTE_PATH=/opt/prospectlab NFS_SERVER=node15.lan NFS_EXPORT_ROOT=/srv/nfs/prospectlab \
#     bash scripts/linux/setup_nfs_client_prospectlab.sh
#
# Variables :
#   REMOTE_PATH       - racine app (défaut /opt/prospectlab)
#   NFS_SERVER        - hostname ou IP du serveur NFS (obligatoire)
#   NFS_EXPORT_ROOT   - export côté serveur (défaut /srv/nfs/prospectlab)
#   SKIP_APT=1        - ne pas apt install nfs-common
#   NFS_ALLOW_NONEMPTY=1 - autoriser uploads/exports non vides avant montage (déconseillé : masque les fichiers)
#   NFS_AUTO_STASH=1  - si uploads/exports contiennent déjà des fichiers : les déplacer dans
#                       REMOTE_PATH/.nfs_local_backup_<horodatage>/ puis monter le NFS et copier sur le partage

set -euo pipefail

REMOTE_PATH="${REMOTE_PATH:-/opt/prospectlab}"
NFS_SERVER="${NFS_SERVER:-}"
NFS_EXPORT_ROOT="${NFS_EXPORT_ROOT:-/srv/nfs/prospectlab}"
NFS_STASH_ROOT=""

REMOTE_PATH="${REMOTE_PATH%/}"
NFS_EXPORT_ROOT="${NFS_EXPORT_ROOT%/}"

if [ -z "${NFS_SERVER}" ]; then
  o="Usage: NFS_SERVER=node15.lan [REMOTE_PATH=/opt/prospectlab] [NFS_EXPORT_ROOT=/srv/nfs/prospectlab]"
  echo "${o} $0" >&2
  exit 1
fi

_restore_stash_after_mount_failure() {
  if [ -z "${NFS_STASH_ROOT:-}" ]; then
    return 0
  fi
  echo "" >&2
  echo ">>> Échec du montage NFS. Restauration des dossiers locaux depuis ${NFS_STASH_ROOT}..." >&2
  for sub in uploads exports; do
    local d="${REMOTE_PATH}/${sub}"
    if mountpoint -q "${d}" 2>/dev/null; then
      umount "${d}" 2>/dev/null || true
    fi
    if [ -d "${NFS_STASH_ROOT}/${sub}" ]; then
      rm -rf "${d}" 2>/dev/null || true
      mv "${NFS_STASH_ROOT}/${sub}" "${d}"
    else
      mkdir -p "${d}"
    fi
  done
  rmdir "${NFS_STASH_ROOT}" 2>/dev/null || true
  echo ">>> Conseils : démarre le serveur NFS sur ${NFS_SERVER} (scripts/linux/setup_nfs_server_prospectlab.sh)," >&2
  echo ">>> ouvre le port 2049/tcp, ou si l'app est sur la même machine que les fichiers : mets" >&2
  echo ">>> UPLOAD_FOLDER=${NFS_EXPORT_ROOT}/uploads et NFS_SKIP_CLIENT_MOUNT=true dans .env.prod." >&2
}

if [ "${SKIP_APT:-0}" != "1" ]; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq
  apt-get install -y nfs-common
fi

mkdir -p "${REMOTE_PATH}/uploads" "${REMOTE_PATH}/exports"

_stash_nonempty_subdir_if_needed() {
  local name="$1"
  local d="${REMOTE_PATH}/${name}"
  if mountpoint -q "${d}" 2>/dev/null; then
    return 0
  fi
  if [ ! -d "${d}" ]; then
    mkdir -p "${d}"
    return 0
  fi
  if [ -z "$(ls -A "${d}" 2>/dev/null)" ]; then
    return 0
  fi
  if [ -z "${NFS_STASH_ROOT}" ]; then
    NFS_STASH_ROOT="${REMOTE_PATH}/.nfs_local_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "${NFS_STASH_ROOT}"
    echo ">>> Ancien contenu déplacé vers ${NFS_STASH_ROOT} (sera recopié sur le NFS après montage)." >&2
  fi
  mv "${d}" "${NFS_STASH_ROOT}/${name}"
  mkdir -p "${d}"
}

if [ "${NFS_AUTO_STASH:-0}" = "1" ]; then
  _stash_nonempty_subdir_if_needed uploads
  _stash_nonempty_subdir_if_needed exports
fi

_check_dir_empty_or_mount() {
  local dir="$1"
  if mountpoint -q "${dir}" 2>/dev/null; then
    return 0
  fi
  if [ "${NFS_ALLOW_NONEMPTY:-0}" = "1" ]; then
    return 0
  fi
  if [ -n "$(ls -A "${dir}" 2>/dev/null)" ]; then
    echo "Erreur: ${dir} n'est pas vide et n'est pas un point de montage." >&2
    echo "Videz-le ou déplacez les fichiers, ou lancez avec NFS_ALLOW_NONEMPTY=1 (risque de masquage)." >&2
    exit 1
  fi
}

_check_dir_empty_or_mount "${REMOTE_PATH}/uploads"
_check_dir_empty_or_mount "${REMOTE_PATH}/exports"

_mount_line() {
  local target_sub="$1"
  echo "${NFS_SERVER}:${NFS_EXPORT_ROOT}/${target_sub} ${REMOTE_PATH}/${target_sub} nfs defaults,_netdev 0 0"
}

_append_fstab_if_missing() {
  local line="$1"
  if grep -qF "${line}" /etc/fstab 2>/dev/null; then
    return 0
  fi
  echo "${line}" >> /etc/fstab
}

_trial_mount_subdir() {
  local sub="$1"
  local dir="${REMOTE_PATH}/${sub}"
  local spec="${NFS_SERVER}:${NFS_EXPORT_ROOT}/${sub}"
  if mountpoint -q "${dir}" 2>/dev/null; then
    echo "Déjà monté: ${dir}"
    return 0
  fi
  if ! mount -t nfs -o defaults,_netdev "${spec}" "${dir}"; then
    echo "mount.nfs: impossible de monter ${spec} sur ${dir}" >&2
    echo "Cause fréquente : aucun serveur NFS sur ${NFS_SERVER} (port 2049), pare-feu, ou export inexistant." >&2
    _restore_stash_after_mount_failure
    exit 1
  fi
}

_trial_mount_subdir uploads
_trial_mount_subdir exports

line_up="$(_mount_line uploads)"
line_ex="$(_mount_line exports)"
_append_fstab_if_missing "${line_up}"
_append_fstab_if_missing "${line_ex}"

if [ -n "${NFS_STASH_ROOT}" ]; then
  for sub in uploads exports; do
    if [ -d "${NFS_STASH_ROOT}/${sub}" ]; then
      echo ">>> Copie de ${sub} vers le partage NFS..." >&2
      cp -a "${NFS_STASH_ROOT}/${sub}/." "${REMOTE_PATH}/${sub}/"
    fi
  done
  echo ">>> Migration terminée. Supprime la sauvegarde locale quand tu as vérifié : sudo rm -rf ${NFS_STASH_ROOT}" >&2
fi

echo "Montage NFS OK :"
echo "  ${line_up}"
echo "  ${line_ex}"
