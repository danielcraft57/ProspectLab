## Outils OSINT / Pentest limités sur Debian Trixie (RPi)

Ce document résume les outils qui posent problème sur **Debian 13 Trixie / aarch64 (Raspberry Pi)**, même après exécution de `scripts/linux/trixie/install_all_tools_trixie.sh`.  
L'idée est de ne pas les oublier, mais aussi de ne pas bloquer le déploiement à cause d'eux.

### 1. Outils OSINT réseau / sous-domaines

- **theHarvester**
  - **État**: non disponible via `apt` ni pipx (pas de package fonctionnel sur Trixie/ARM).
  - **Impact**: ProspectLab ne l'utilise pas directement aujourd'hui.
  - **Piste manuelle**:
    - Cloner le dépôt officiel puis utiliser un venv dédié:
      ```bash
      git clone https://github.com/laramies/theHarvester.git
      cd theHarvester
      python3 -m venv venv
      source venv/bin/activate
      pip install -r requirements.txt
      ```

- **findomain**
  - **État**: installation binaire GitHub tentée dans `install_osint_tools_trixie.sh`, mais le binaire ou l'URL ne sont pas disponibles/fiables pour ARM.
  - **Impact**: pas utilisé par ProspectLab en prod à ce jour.
  - **Piste manuelle**:
    - Surveille les releases officielles:
      - récupérer à la main un binaire `findomain-linux-aarch64` si/quad il existe à nouveau,
      - le placer dans `/usr/local/bin/findomain` (+ `chmod +x`).

- **metagoofil**
  - **État**: pas de paquet `apt` sur Trixie.
  - **Impact**: outil bonus pour métadonnées, non essentiel.
  - **Piste manuelle**:
    - GitHub + venv dédié si tu en as vraiment besoin.

- **recon-ng**
  - **État**: pas de wheel/distribution pip compatible pour Trixie/ARM (pipx échoue).
  - **Impact**: framework OSINT optionnel, non utilisé par ProspectLab.
  - **Piste manuelle**:
    - VM Kali dédiée, ou conteneur Docker spécifique, plutôt que sur RPi.

### 2. Outils Pentest lourds / spécifiques

Certains outils ne sont pas disponibles en paquets `apt` sur Trixie/ARM, ou seulement via dépôts externes:

- **wapiti**, **zaproxy**, **feroxbuster**
  - **État**:
    - `wapiti`: pas de paquet, mais un fallback `wapiti3` est installé via pipx (alias `wapiti` créé si possible).
    - `zaproxy`, `feroxbuster`: introuvables dans les dépôts standards ARM.
  - **Impact**: non utilisés directement par ProspectLab.
  - **Piste manuelle**:
    - VM Kali / conteneur Docker dédié pour ces outils si besoin.

- **wordlists**
  - **État**: pas de paquet générique `wordlists` sur Trixie.
  - **Impact**: uniquement utile pour certains scénarios de bruteforce.
  - **Piste manuelle**:
    - utiliser les wordlists classiques (SecLists, rockyou.txt) via git clone dans un répertoire partagé (ex: `/opt/wordlists`).

- **responder**, **impacket-scripts**, **bloodhound**, **crackmapexec**, **radare2**
  - **État**: paquets indisponibles ou non maintenus pour Debian 13 ARM.
  - **Impact**: outils de post-exploitation / AD / reverse, en dehors du scope ProspectLab.
  - **Piste manuelle**:
    - là encore: VM Kali, conteneur dédié ou machine plus "classique" pour ces usages.

### 3. Modules Python systèmes

- `python3-whois` (paquet `apt`)
  - **État**: indisponible sur Trixie/ARM.
  - **Contournement mis en place**:
    - `python-whois` est installé dans l'environnement Conda de ProspectLab (`/opt/prospectlab/env`), ce qui est suffisant pour le code de l'app.
  - **Remarque**:
    - Les scripts de test OSINT affichent encore `[KO] Module Python whois` pour le Python système, mais ce n'est **pas bloquant** pour ProspectLab.

### 4. Stratégie recommandée

- Sur les **Raspberry Pi (node13, node14)**:
  - considérer que l'on a un **set d'outils OSINT/Pentest/SEO suffisant** pour ce que ProspectLab fait réellement;
  - accepter que certains outils très orientés "offensif lourd" ne soient pas disponibles ou uniquement via install manuelle.

- Pour les besoins Pentest avancés / AD / reverse:
  - utiliser une **VM Kali** ou un **serveur dédié** (x86_64) avec:
    - `bloodhound`, `crackmapexec`, `responder`, `impacket`, `radare2`, etc.
  - éventuellement exposer des scripts ou API internes qui parlent avec cette machine, plutôt que de tout forcer sur les RPi.

### 5. Tests et diagnostics

- Pour voir rapidement l'état des outils sur un noeud:
  - `bash scripts/linux/test_all_tools.sh` (détecte la bonne variante Trixie/Bookworm/Kali).
  - ou via Windows:
    - `.\scripts\test_cluster_worker.ps1 -Server node13.lan -User pi -RemotePath /opt/prospectlab`

Les `[OK]` / `[KO]` s'affichent alors clairement, avec des messages explicites quand un outil est intrinsèquement indisponible sur cette distribution.

