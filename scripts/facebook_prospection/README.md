# Scripts prospection Facebook (ProspectLab + SocialDesk)

| Hote | Role | Deploy |
|------|------|--------|
| **serv1** Windows | Recherche, scrape, prospect (Chrome visible) | `deploy_to_serv.ps1` |
| **serv2** Debian | Inbox Messenger (sync, reply, headless — comme SocialDesk `facebook-messenger-danielcraft`) | `deploy_to_serv2.ps1` |

## serv1 (Windows)

```powershell
cd C:\Users\loicDaniel\Projects\ProspectLab
.\scripts\facebook_prospection\deploy_to_serv.ps1
```

RDP serv1 :

```powershell
cd C:\Users\loicDaniel\Documents\SocialDesk\deploy\scripts
.\install_facebook_prospectlab_host.ps1
.\test_on_host.ps1 search "boulangerie metz"
```

## serv2 (messagerie)

```powershell
.\scripts\facebook_prospection\deploy_to_serv2.ps1
```

SSH serv2 :

```bash
cd ~/Documents/socialdesk/deploy/scripts
chmod +x install_facebook_messenger_serv2.sh test_on_serv2.sh
./install_facebook_messenger_serv2.sh
./test_on_serv2.sh sync
```

ProspectLab (node15 `.env`) :

- `FACEBOOK_PROSPECTION_REMOTE_HOST_MESSENGER=pi@serv2.lan`
- chemins Linux `FACEBOOK_PROSPECTION_REMOTE_MESSENGER_*` (defauts dans `config.py`)

Le scheduler SocialDesk `socialdesk-messenger.service` sur serv2 peut continuer a tourner en parallele ; ProspectLab declenche ses propres jobs via SSH + `prospectlab-facebook-job.mjs`.

**Cookies serv2** : meme `sync-chrome-session.mjs` que serv1 (profil Chrome **local** sur serv2, pas de copie depuis serv1). Cron SocialDesk `cookies-refresh-danielcraft-serv2` + Celery `facebook_prospection.refresh_cookies`.

KB Q/R : Qdrant `intents_outbound_commercial` sur node15 + page `/tchatche-kb` (doc `docs/guides/TCHATCHE_KB.md`).

Doc : `docs/guides/FACEBOOK_PROSPECTION.md`
