# Scripts prospection Facebook (ProspectLab + SocialDesk sur **serv1 Windows**)

**serv2.lan** = Debian (Celery). Pas de Chrome ni `prospectlab-facebook-job.mjs` aujourd'hui. A terme : couche messagerie Facebook sur serv2 (a brancher plus tard). En attendant, Messenger Playwright reste sur **serv1** comme la recherche.

## Deploiement (serv1 uniquement)

```powershell
cd C:\Users\loicDaniel\Projects\ProspectLab
.\scripts\facebook_prospection\deploy_to_serv.ps1
```

Puis en RDP sur serv1 :

```powershell
cd C:\Users\loicDaniel\Documents\SocialDesk\deploy\scripts
.\install_facebook_prospectlab_host.ps1
.\test_on_host.ps1 search "boulangerie metz"
```

## File d'attente ProspectLab

Les jobs partent en Celery depuis node15. L'affectation **serv1 / alt** est automatique :

- par defaut tout sur **serv1**
- si `FACEBOOK_PROSPECTION_REMOTE_HOST_SEARCH_ALT=utilisateur@autre-windows.lan` dans `.env` node15, repartition selon la charge entre serv1 et ce second poste Windows

Ne pas pointer `FACEBOOK_PROSPECTION_REMOTE_HOST_MESSENGER` vers serv2.lan (Debian).

Doc : `docs/guides/FACEBOOK_PROSPECTION.md`
