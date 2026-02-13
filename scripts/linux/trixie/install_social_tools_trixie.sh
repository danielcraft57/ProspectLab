#!/usr/bin/env bash

# Installation d'outils OSINT orientés réseaux sociaux sur Debian Trixie / RPi
# Exécution : bash scripts/linux/trixie/install_social_tools_trixie.sh

set -e

echo "[*] Mise à jour APT..."
sudo apt-get update

install_pkg() {
  local pkg="$1"
  if sudo apt-get install -y "$pkg"; then
    echo "[✓] $pkg installé"
  else
    echo "[!] $pkg indisponible sur cette distro, à installer manuellement si besoin"
  fi
}

echo "[*] Pré-requis..."
install_pkg python3-pip
install_pkg python3-venv
install_pkg python3-dev
install_pkg git

echo "[*] Installation de pipx (recommandé)..."
install_pkg pipx || true
pipx ensurepath || true

echo "[*] Outils CLI principaux (via pipx)..."
pipx install sherlock-project || true
pipx install maigret || true

echo "[*] Social Analyzer (module Python)..."
# Détecter si on est dans un venv
if [ -n "$VIRTUAL_ENV" ]; then
  echo "[*] Environnement virtuel détecté, installation dans le venv..."
  pip3 install --upgrade social-analyzer || true
else
  echo "[*] Installation globale (--user)..."
  pip3 install --user --upgrade social-analyzer || true
fi

echo "[*] Tinfoleak n'est généralement pas dans les dépôts Debian. Installation manuelle recommandée si besoin (git clone + venv)."

echo "[*] Vérifications rapides..."
for tool in sherlock maigret; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "[OK] $tool détecté"
  else
    echo "[KO] $tool manquant"
  fi
done

python3 - << 'EOF' || true
import importlib
import sys

print("[*] Vérification du module social-analyzer...")
print("[*] Python utilisé: {}".format(sys.executable))
print("[*] Venv: {}".format(sys.prefix))

# Essayer différents noms d'import possibles
module_names = ["social_analyzer", "socialanalyzer", "socialanalyzer.socialanalyzer"]

found = False
for name in module_names:
    try:
        importlib.import_module(name)
        print("[OK] Module Python {} importable".format(name))
        found = True
        break
    except ImportError:
        continue
    except Exception as e:
        print("[!] Erreur lors de l'import de {}: {}".format(name, e))

if not found:
    print("[KO] Aucun module social-analyzer trouvé")
    print("[*] Vérification si le package est installé...")
    try:
        import pkg_resources
        dist = pkg_resources.get_distribution("social-analyzer")
        print("[!] Package social-analyzer installé (version {}), mais import impossible".format(dist.version))
        print("[!] Le module peut nécessiter une configuration ou un chemin spécifique")
    except:
        print("[KO] Package social-analyzer non trouvé dans les distributions installées")
EOF

echo "[*] Installation outils social OSINT (Trixie) terminée."
