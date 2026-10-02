# Maquettes sequence PAS (semaine)

6 mails DanielCraft - methode PAS, vouvoiement.

Playbook : `docs/guides/SEQUENCE_EMAIL_PAS_SEMAINE.md`

Sources de verite (HTML campagnes) : `template_studio/html_sources/html_dc_pas_*.html`

Ces maquettes sont des copies pour preview design. Apres edit des sources :

```powershell
Copy-Item -Force template_studio/html_sources/html_dc_pas_echantillon.html design/mockups/emails-pas/01-pas-echantillon.html
Copy-Item -Force template_studio/html_sources/html_dc_pas_style_custom.html design/mockups/emails-pas/02-pas-style-custom.html
Copy-Item -Force template_studio/html_sources/html_dc_pas_constat_site.html design/mockups/emails-pas/03-pas-constat-site.html
Copy-Item -Force template_studio/html_sources/html_dc_pas_projection.html design/mockups/emails-pas/04-pas-projection.html
Copy-Item -Force template_studio/html_sources/html_dc_pas_midi.html design/mockups/emails-pas/05-pas-midi.html
Copy-Item -Force template_studio/html_sources/html_dc_pas_breakup.html design/mockups/emails-pas/06-pas-breakup.html
```

Sync BDD (prod / local avec DATABASE_URL) :

```powershell
python scripts/sync_pas_templates_to_db.py --purge
```
