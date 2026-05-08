# AGENT - Exploitation et deploiement ProspectLab

Ce fichier sert de repere rapide pour l'agent et pour les operations de deploiement.

## Topologie de production validee

- Noeud application (prod): `pi@node15.lan`
- Noeud reverse proxy Nginx: `pi@node2.lan`
- Les deux noeuds sont certifies et autorises pour la production.
- Branche cible sur le noeud prod: `main`

## Commande de deploiement recommandee (Windows / PowerShell)

Depuis la racine du projet:

```powershell
.\scripts\deploy_production.ps1 -Server node15.lan -User pi -RemotePath /opt/prospectlab -ProxyServer node2.lan -ProxyUser pi
```

Cette commande:

- deploie l'application sur `node15.lan`
- remet a zero le dossier distant puis clone la branche cible (`main` par defaut)
- redemarre les services applicatifs (`prospectlab`, `prospectlab-celery`, `prospectlab-celerybeat`)
- teste la reponse HTTP locale sur le port `5000`
- valide et recharge Nginx sur `node2.lan`

## Verification rapide post-deploiement

### Sur le noeud application (`pi@node15.lan`)

```bash
sudo systemctl status prospectlab prospectlab-celery prospectlab-celerybeat
curl -I http://127.0.0.1:5000/
```

### Sync automatique `main` par crontab (sur `pi@node15.lan`)

```bash
cd /opt/prospectlab
bash scripts/linux/setup_git_pull_cron.sh
crontab -l
```

### Sur le noeud Nginx (`pi@node2.lan`)

```bash
sudo nginx -t
sudo systemctl status nginx
```

## Rappels importants

- La conf Nginx doit proxyfier vers `http://node15.lan:5000`.
- Les certificats SSL sont geres sur le noeud proxy `node2.lan`.
- Le fichier `.env.prod` local est copie sur le serveur app en `.env` pendant le deploiement si present.
