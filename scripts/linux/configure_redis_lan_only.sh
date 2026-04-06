#!/usr/bin/env bash
#
# Restreint Redis à l’écoute sur loopback + IP LAN, et au pare-feu : port 6379
# uniquement depuis un sous-réseau (ex. 192.168.1.0/24).
#
# Usage sur le serveur Redis (ex. pi@node15.lan) :
#   sudo REDIS_LAN_CIDR=192.168.1.0/24 bash scripts/linux/configure_redis_lan_only.sh
#
# Variables optionnelles :
#   REDIS_LAN_CIDR   — défaut 192.168.1.0/24
#   REDIS_BIND_IP    — IP IPv4 LAN à écouter (sinon détection automatique sur ce sous-réseau)
#   REDIS_CONF       — défaut /etc/redis/redis.conf
#   SKIP_FIREWALL=1  — ne modifie pas iptables (si vous gérez nftables/ufw vous-même)
#   UFW_MODE=1       — utilise ufw au lieu d’iptables (règles simples)
#
set -euo pipefail

REDIS_LAN_CIDR="${REDIS_LAN_CIDR:-192.168.1.0/24}"
REDIS_CONF="${REDIS_CONF:-/etc/redis/redis.conf}"

if [[ "${SKIP_FIREWALL:-0}" != "1" ]] && [[ "${UFW_MODE:-0}" != "1" ]]; then
  if ! command -v iptables >/dev/null 2>&1; then
    echo "[!] iptables introuvable. Installez iptables ou définissez UFW_MODE=1 / SKIP_FIREWALL=1."
    exit 1
  fi
fi

if [[ $EUID -ne 0 ]]; then
  echo "[!] Exécutez en root : sudo $0"
  exit 1
fi

detect_bind_ip() {
  if [[ -n "${REDIS_BIND_IP:-}" ]]; then
    echo "$REDIS_BIND_IP"
    return
  fi
  local base="${REDIS_LAN_CIDR%%/*}"
  local prefix="${base%.*}"
  local a ip=""
  for a in $(hostname -I 2>/dev/null); do
    if [[ "$a" == "${prefix}."* ]]; then
      ip="$a"
      break
    fi
  done
  if [[ -z "$ip" ]]; then
    while read -r a; do
      [[ "$a" == "${prefix}."* ]] && ip="$a" && break
    done < <(ip -4 -o addr show scope global 2>/dev/null | awk '{print $4}' | cut -d/ -f1)
  fi
  if [[ -z "$ip" ]]; then
    echo "[!] Impossible de détecter l’IP LAN (${prefix}.x). Exportez REDIS_BIND_IP=…" >&2
    exit 1
  fi
  echo "$ip"
}

BIND_IP="$(detect_bind_ip)"
echo "[*] IP LAN pour bind Redis : $BIND_IP (CIDR autorisé : $REDIS_LAN_CIDR)"

if [[ ! -f "$REDIS_CONF" ]]; then
  echo "[!] Fichier introuvable : $REDIS_CONF"
  exit 1
fi

cp -a "$REDIS_CONF" "${REDIS_CONF}.bak.$(date +%Y%m%d%H%M%S)"

# Une seule directive bind (loopback + IP LAN)
sed -i '/^[[:space:]]*bind[[:space:]]/d' "$REDIS_CONF"
printf '\nbind 127.0.0.1 %s\n' "$BIND_IP" >> "$REDIS_CONF"

# Sans mot de passe, Redis refuse les clients non-loopback si protected-mode yes.
# Le pare-feu limite le port au LAN.
if grep -qE '^protected-mode' "$REDIS_CONF"; then
  sed -i 's/^protected-mode.*/protected-mode no/' "$REDIS_CONF"
else
  echo 'protected-mode no' >> "$REDIS_CONF"
fi
echo "# Pare-feu : TCP 6379 limité à ${REDIS_LAN_CIDR} (configure_redis_lan_only.sh)" >> "$REDIS_CONF"

echo "[*] Pare-feu (port 6379, source $REDIS_LAN_CIDR uniquement — loopback déjà géré par la politique INPUT habituelle)"

if [[ "${SKIP_FIREWALL:-0}" == "1" ]]; then
  echo "[*] SKIP_FIREWALL=1 — aucune règle iptables/ufw ajoutée."
elif [[ "${UFW_MODE:-0}" == "1" ]]; then
  if command -v ufw >/dev/null 2>&1; then
    ufw allow from "$REDIS_LAN_CIDR" to any port 6379 proto tcp comment 'Redis ProspectLab LAN'
    echo "[✓] ufw : autorisation $REDIS_LAN_CIDR -> :6379"
    echo "    Vérifiez que le port 6379 n’est pas ouvert publiquement (ufw status)."
  else
    echo "[!] ufw absent. Installez ufw ou utilisez le mode iptables par défaut."
    exit 1
  fi
else
  # Ordre : deux ACCEPT en tête (127.0.0.1 puis LAN), puis DROP en fin de chaîne INPUT
  if ! iptables -C INPUT -p tcp -m tcp -s 127.0.0.1 --dport 6379 -j ACCEPT 2>/dev/null; then
    iptables -I INPUT -p tcp -m tcp -s 127.0.0.1 --dport 6379 -j ACCEPT
    echo "[✓] iptables : ACCEPT 127.0.0.1 -> :6379"
  fi
  if ! iptables -C INPUT -p tcp -m tcp --dport 6379 -s "$REDIS_LAN_CIDR" -j ACCEPT 2>/dev/null; then
    iptables -I INPUT -p tcp -m tcp --dport 6379 -s "$REDIS_LAN_CIDR" -j ACCEPT
    echo "[✓] iptables : ACCEPT $REDIS_LAN_CIDR -> :6379"
  else
    echo "[*] Règle iptables ACCEPT LAN déjà présente"
  fi
  if ! iptables -C INPUT -p tcp -m tcp --dport 6379 -j DROP 2>/dev/null; then
    iptables -A INPUT -p tcp -m tcp --dport 6379 -j DROP
    echo "[✓] iptables : DROP le reste sur :6379"
  else
    echo "[*] Règle iptables DROP :6379 déjà présente"
  fi
  if command -v netfilter-persistent >/dev/null 2>&1; then
    netfilter-persistent save 2>/dev/null || true
  elif command -v iptables-save >/dev/null 2>&1; then
    echo "[*] Pour rendre les règles persistantes : apt install iptables-persistent && netfilter-persistent save"
  fi
fi

systemctl restart redis-server
if redis-cli -h 127.0.0.1 ping 2>/dev/null | grep -q PONG; then
  echo "[✓] Redis répond sur 127.0.0.1"
else
  echo "[!] Redis ne répond pas sur 127.0.0.1 — vérifiez $REDIS_CONF"
  exit 1
fi

echo ""
echo "Clients distants (workers sur le LAN) : CELERY_BROKER_URL=redis://${BIND_IP}:6379/1"
echo "ou redis://node15.lan:6379/1 si le DNS pointe vers $BIND_IP"
echo "Terminé."
