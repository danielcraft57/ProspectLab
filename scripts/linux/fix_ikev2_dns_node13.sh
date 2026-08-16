#!/bin/bash
set -euo pipefail

echo "[1] Backup + patch ikev2.conf"
sudo cp -a /etc/ipsec.d/ikev2.conf "/etc/ipsec.d/ikev2.conf.bak.$(date +%Y%m%d%H%M%S)"
sudo sed -i 's/modecfgdns="8.8.8.8 8.8.4.4"/modecfgdns="192.168.1.191"/' /etc/ipsec.d/ikev2.conf
grep modecfgdns /etc/ipsec.d/ikev2.conf

echo "[2] Replace ikev2-cp (via jump, OK si clients drop)"
sudo ipsec auto --replace ikev2-cp

echo "[3] DNAT DNS VPN -> dnsmasq local"
add_rule() {
  local proto="$1"
  local src="$2"
  if ! sudo iptables -t nat -C PREROUTING -s "$src" -p "$proto" --dport 53 -j DNAT --to-destination 192.168.1.191:53 2>/dev/null; then
    sudo iptables -t nat -A PREROUTING -s "$src" -p "$proto" --dport 53 -j DNAT --to-destination 192.168.1.191:53
    echo "added $proto $src"
  else
    echo "exists $proto $src"
  fi
}
add_rule udp 192.168.43.0/24
add_rule tcp 192.168.43.0/24
add_rule udp 192.168.42.0/24
add_rule tcp 192.168.42.0/24

echo "[4] Persist iptables if netfilter-persistent exists"
if command -v netfilter-persistent >/dev/null 2>&1; then
  sudo netfilter-persistent save || true
elif [[ -d /etc/iptables ]]; then
  sudo sh -c 'iptables-save > /etc/iptables/rules.v4' || true
fi

echo "[5] Verify"
dig +short @192.168.1.191 prospectlab.danielcraft.fr A || true
sudo ipsec status | sed -n '/ikev2-cp": /,/modecfg info/p' | head -20
echo DONE
