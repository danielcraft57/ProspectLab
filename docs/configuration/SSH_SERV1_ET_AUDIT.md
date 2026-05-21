# SSH Pi → serv1 (audit PDF + landing variants)

Le rapport d’audit **complet** et les **landing variants** appellent `scripts/experiments/gen_audit_report/generate_website_audit_cursor_remote.py`, qui utilise **SSH/SCP** depuis le serveur application (ex. Raspberry Pi `node15`) vers **serv1** (Windows + Cursor Agent).

## Fichiers de configuration

| Emplacement | Fichier | Rôle |
|-------------|---------|------|
| PC (modèle) | `.env.prod` | Non versionné — secrets et réglages prod |
| Serveur app | `/opt/prospectlab/.env` | **Lu par Gunicorn et Celery** (`EnvironmentFile` systemd) |
| Déploiement | `deploy_production` | Copie `.env.prod` → `.env` sur le serveur |

Il n’existe **pas** de `.env.lan`. Si un message d’erreur affiche `.env.lan`, c’est en général un artefact d’affichage (CRLF dans `.env` + hostname `serv1.lan`).

## Prérequis sur le Pi (node15)

```bash
sudo apt install -y openssh-client
which ssh scp   # /usr/bin/ssh
```

## Clé SSH (ex. `id_rsa`)

Sur le Pi, utilisateur `pi` :

```bash
# Si la clé n’existe pas encore :
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ""

# Autoriser sur serv1 (Windows OpenSSH) :
ssh-copy-id -i ~/.ssh/id_rsa.pub loicDaniel@serv1.lan

# Test :
ssh -o BatchMode=yes loicDaniel@serv1.lan 'powershell -Command "echo OK"'
```

Dans **`.env`** sur le serveur (copié depuis `.env.prod`) :

```env
LANDING_VARIANTS_REMOTE_HOST=loicDaniel@serv1.lan
LANDING_VARIANTS_SSH_KEY_PATH=/home/pi/.ssh/id_rsa
```

Laisser `LANDING_VARIANTS_SSH_KEY_PATH` vide uniquement si la clé par défaut de `pi` est déjà acceptée sur serv1.

## Copie `.env.prod` depuis Windows

Après `scp` depuis le PC, **convertir les fins de ligne** (sinon `hostname contains invalid characters`) :

```bash
cd /opt/prospectlab
bash scripts/linux/fix_env_crlf.sh
cp -f .env.prod .env    # si pas déjà fait par deploy
chmod 600 .env
sudo systemctl restart prospectlab prospectlab-celery
```

## Script de test

```bash
cd /opt/prospectlab
git pull --ff-only origin main
bash scripts/linux/test_audit_agent_ssh.sh
```

Attendu : Test 1 OK, Test 2 OK, Test 3 OK.

## Script d’audit versionné

Le fichier doit être présent sur le serveur (versionné dans Git depuis `scripts/experiments/gen_audit_report/`) :

```bash
test -f scripts/experiments/gen_audit_report/generate_website_audit_cursor_remote.py && echo OK
```

## Logs utiles

| Fichier | Contenu |
|---------|---------|
| `logs/website_audit_agent.log` | Lancement script, erreur SSH détaillée |
| `logs/website_audit_report.log` | Phases Celery, pause/reprise |
| `logs/website_audit_api.log` | Requêtes API publiques |

## Dépannage rapide

| Symptôme | Cause | Action |
|----------|--------|--------|
| `No such file or directory: 'ssh'` | `openssh-client` absent | `sudo apt install openssh-client` |
| `hostname contains invalid characters` | CRLF dans `.env` | `bash scripts/linux/fix_env_crlf.sh` |
| `No such file or directory` + `-i` | Clé inexistante | Créer `id_rsa` ou corriger `LANDING_VARIANTS_SSH_KEY_PATH` |
| `agent_unavailable` en ~1 s | Script absent ou SSH KO | `git pull`, test SSH, voir `website_audit_agent.log` |
| Pause `agent_unavailable` | Agent Cursor / quota | Email admin + `POST .../complete/resume` |
| `out-file : processus ne peut pas accéder au fichier` | Logs agent verrouillés sur serv1 | Mettre à jour le script audit (git pull), ne pas cliquer 2× sur reprise |

## Variables partagées (audit + landing)

- `LANDING_VARIANTS_REMOTE_HOST`, `LANDING_VARIANTS_SSH_KEY_PATH`, `LANDING_VARIANTS_REMOTE_CURSOR_COMMAND`
- `WEBSITE_AUDIT_AGENT_*` (timeouts, pause, alerte email)
- Script audit : `WEBSITE_AUDIT_AGENT_SCRIPT_PATH` (défaut : `generate_website_audit_cursor_remote.py`)

Voir aussi `env.example` et `docs/configuration/PRODUCTION_POSTGRES_AUDIT.md`.
