# AGENT - Exploitation et deploiement ProspectLab

Ce fichier sert de repere rapide pour l'agent et pour les operations de deploiement.

## Topologie de production validee

- Noeud application (prod): `pi@node15.lan` (`192.168.1.198`)
- Noeud reverse proxy Nginx: `pi@node12.lan` (`192.168.1.209`, IP publique `89.159.124.25`)
- Noeud VPN (IPsec/XAuth + L2TP): `pi@node13.lan` (`192.168.1.191`, leftid `89.159.124.25`)
- Jump host public (si VPN coupe / ipsec restart): `pi@danielcraft.fr`
- Branche cible sur le noeud prod: `main`

### Acces SSH quand le VPN est instable

Preferer un saut explicite depuis Windows / PowerShell:

```powershell
ssh -J pi@danielcraft.fr pi@node13.lan
ssh -J pi@danielcraft.fr pi@node15.lan
ssh -J pi@danielcraft.fr pi@node12.lan
```

Ne pas redemarrer `ipsec` sur `node13` via une session qui depend uniquement du VPN: la session saute. Passer par `pi@danielcraft.fr`.

## Commande de deploiement recommandee (Windows / PowerShell)

Depuis la racine du projet:

```powershell
.\scripts\deploy_production.ps1 -Server node15.lan -User pi -RemotePath /opt/prospectlab -ProxyServer node12.lan -ProxyUser pi
```

Cette commande:

- deploie l'application sur `node15.lan`
- remet a zero le dossier distant puis clone la branche cible (`main` par defaut)
- redemarre les services applicatifs (`prospectlab`, `prospectlab-celery`, `prospectlab-celerybeat`)
- teste la reponse HTTP locale sur le port `5000`
- valide et recharge Nginx sur `node12.lan`

## VPN et acces restreint ProspectLab

`RESTRICT_TO_LOCAL_NETWORK=true` n'accepte que des IP privees. Or `campaigns.danielcraft.fr` resolvait vers la meme IP publique que le VPN (`89.159.124.25`), donc Windows sortait du tunnel et Flask voyait l'IP box.

Correctif en place sur `node13`:

- dnsmasq split-DNS: `/etc/dnsmasq.d/prospectlab-split.conf`
- `campaigns.danielcraft.fr` / `prospectlab.danielcraft.fr` -> `192.168.1.209` (Nginx)
- DNS pousse aux clients VPN: `192.168.1.191` (`modecfgdns` IPsec + `ms-dns` L2TP)
- Script: `scripts/linux/setup_node13_vpn_split_dns.sh`

Apres un changement DNS VPN, le client doit **se reconnecter au VPN** puis:

```powershell
ipconfig /flushdns
Resolve-DnsName campaigns.danielcraft.fr
```

Attendu: `192.168.1.209` (pas `89.159.124.25`).

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

Log de sync:

```bash
tail -n 100 /opt/prospectlab/logs/prospectlab_git_sync.log
```

### Sur le noeud Nginx (`pi@node12.lan`)

```bash
sudo nginx -t
sudo systemctl status nginx
```

### Sur le noeud VPN (`pi@node13.lan`)

```bash
sudo systemctl status ipsec xl2tpd dnsmasq
dig +short @192.168.1.191 campaigns.danielcraft.fr A
```

## Rappels importants

- La conf Nginx doit proxyfier vers `http://node15.lan:5000`.
- Les certificats SSL sont geres sur le noeud proxy `node12.lan` (vhost `prospectlab.danielcraft.fr`).
- Le fichier `.env.prod` local est copie sur le serveur app en `.env` pendant le deploiement si present.
- Attention aux assets screenshots:
  - ne pas supprimer `static/screenshots/` ni `static/generated/landing_variants/` en prod;
  - conserver une sync non destructive (pas de `git reset --hard`, pas de `git clean -fdx`).
