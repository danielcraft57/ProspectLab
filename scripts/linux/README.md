# Scripts d'installation et de test des outils ProspectLab

## Structure

Les scripts sont organisés par environnement :

- **`bookworm/`** : Scripts pour Debian 12 (Bookworm) / Raspberry Pi OS basé sur Bookworm
- **`trixie/`** : Scripts pour Debian 13 (Trixie)
- **`kali/`** : Scripts pour Kali Linux (WSL / desktop)
- **Racine** : Scripts dispatcher et utilitaires génériques

## Utilisation recommandée

### Installation complète (détection automatique)

```bash
cd /opt/prospectlab
bash scripts/linux/install_all_tools.sh
```

Ce script détecte automatiquement votre version Debian et appelle le bon script d'installation.

### Test complet (détection automatique)

```bash
bash scripts/linux/test_all_tools.sh
```

## Scripts disponibles

### Dispatchers (racine)

- `install_all_tools.sh` : Installation complète (OSINT, Pentest, SEO, Social) avec détection auto
- `test_all_tools.sh` : Test complet de tous les outils avec détection auto
- `upgrade_python_venv.sh` : Mise à jour du venv Python vers une version plus récente

### Par version (bookworm/, trixie/, kali/)

- `install_osint_tools_*.sh` : Installation outils OSINT
- `install_pentest_tools_*.sh` : Installation outils Pentest
- `install_seo_tools_*.sh` : Installation outils SEO
- `install_social_tools_*.sh` : Installation outils OSINT réseaux sociaux
- `install_all_tools_*.sh` : Installation complète (tous les outils)
- `test_*_tools_prod.sh` : Tests individuels
- `test_all_tools_*.sh` : Test complet

## Détection automatique

Les dispatchers lisent `/etc/os-release` et utilisent :
- `VERSION_CODENAME=trixie` → `trixie/`
- `VERSION_CODENAME=bookworm` → `bookworm/`
- Sinon → `bookworm/` par défaut

## Voir aussi

Documentation complète : `docs/INSTALL_OSINT_TOOLS.md`
