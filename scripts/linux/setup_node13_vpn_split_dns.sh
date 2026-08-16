#!/bin/bash
# Configure le split-DNS VPN sur node13 pour ProspectLab.
# A lancer sur node13 (pi@node13.lan).

set -euo pipefail

CONF_SRC="${1:-/tmp/prospectlab-split-dns.conf}"
CONF_DST="/etc/dnsmasq.d/prospectlab-split.conf"
NGINX_LAN_IP="192.168.1.209"
DNS_LISTEN_IP="192.168.1.191"

if [[ ! -f "$CONF_SRC" ]]; then
  echo "Fichier source introuvable: $CONF_SRC" >&2
  exit 1
fi

echo "[1/5] Installation conf dnsmasq"
sudo cp "$CONF_SRC" "$CONF_DST"
sudo chmod 644 "$CONF_DST"

echo "[2/5] Mise a jour DNS pousse par IPsec (xauth-psk)"
sudo cp -a /etc/ipsec.conf "/etc/ipsec.conf.bak.$(date +%Y%m%d%H%M%S)"
sudo sed -i 's|^[[:space:]]*modecfgdns=.*|  modecfgdns="'"$DNS_LISTEN_IP"'"|' /etc/ipsec.conf
if ! grep -q "modecfgdns=\"$DNS_LISTEN_IP\"" /etc/ipsec.conf; then
  echo "Echec: modecfgdns non mis a jour dans /etc/ipsec.conf" >&2
  exit 1
fi

echo "[3/5] Mise a jour DNS pousse par L2TP/PPP"
sudo cp -a /etc/ppp/options.xl2tpd "/etc/ppp/options.xl2tpd.bak.$(date +%Y%m%d%H%M%S)"
sudo sed -i '/^ms-dns /d' /etc/ppp/options.xl2tpd
echo "ms-dns $DNS_LISTEN_IP" | sudo tee -a /etc/ppp/options.xl2tpd >/dev/null

echo "[4/5] Redemarrage dnsmasq + ipsec"
sudo systemctl enable dnsmasq
sudo systemctl restart dnsmasq
sudo systemctl restart ipsec

echo "[5/5] Verification DNS split"
dig +short @"$DNS_LISTEN_IP" campaigns.danielcraft.fr A || true
dig +short @"$DNS_LISTEN_IP" prospectlab.danielcraft.fr A || true

echo "OK. Reconnecte le VPN client, puis teste https://campaigns.danielcraft.fr/"
echo "Attendu: campaigns -> $NGINX_LAN_IP, IP vue par Flask dans 192.168.43.0/24"
