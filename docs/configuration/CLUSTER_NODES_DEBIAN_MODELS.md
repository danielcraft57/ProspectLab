# Cluster - versions Debian et modèles RPi (node5 à node15)

Date: 2026-03-27

## Méthode (tests refaits)

Sur chaque noeud joignable en SSH (`pi@nodeX.lan`), on a lu:

- Debian: `cat /etc/debian_version`
- Arch: `uname -m`
- Python systeme: `python3 -V`
- Modele Raspberry Pi: `cat /proc/device-tree/model` (nettoyage des octets NUL)

## Résultats (refaits en SSH)

| Noeud | Debian | Arch | Python systeme | Modele detecte | Remarques |
|---|---:|---|---|---|---|
| `node5.lan` | 12.12 | armv7l | 3.11.2 | Raspberry Pi 2 Model B Rev 1.1 | ARM 32-bit. Eviter Conda (installeurs obsoletes). |
| `node6.lan` | 12.12 | armv7l | 3.11.2 | Raspberry Pi 2 Model B Rev 1.1 | ARM 32-bit. Eviter Conda (installeurs obsoletes). |
| `node7.lan` | 12.12 | armv7l | 3.11.2 | Raspberry Pi 2 Model B Rev 1.1 | ARM 32-bit. Eviter Conda (installeurs obsoletes). |
| `node8.lan` | 12.12 | armv7l | 3.11.2 | Raspberry Pi 2 Model B Rev 1.1 | ARM 32-bit. Eviter Conda (installeurs obsoletes). |
| `node9.lan` | 12.12 | armv7l | 3.11.2 | Raspberry Pi 2 Model B Rev 1.1 | ARM 32-bit. Eviter Conda (installeurs obsoletes). |
| `node10.lan` | 13.4 | aarch64 | 3.13.5 | Raspberry Pi 3 Model B Rev 1.2 | Recommande: env Python 3.11 (Conda) pour `pandas==2.1.3`. |
| `node11.lan` | 13.4 | aarch64 | 3.13.5 | Raspberry Pi 3 Model B Rev 1.2 | Recommande: env Python 3.11 (Conda) pour `pandas==2.1.3`. |
| `node12.lan` | 13.4 | aarch64 | 3.13.5 | Raspberry Pi 3 Model B Rev 1.2 | Test refait: Debian 13.4 (plus Debian 12). |
| `node13.lan` | 13.4 | aarch64 | 3.13.5 | Raspberry Pi 3 Model B Rev 1.2 | Node de reference: env Python 3.11 a deja bien fonctionne. |
| `node14.lan` | 13.4 | aarch64 | 3.13.5 | Raspberry Pi 3 Model B Rev 1.2 | Recommande: env Python 3.11 (Conda). |
| `node15.lan` | 13.4 | aarch64 | 3.13.5 | Raspberry Pi 5 Model B Rev 1.1 | Noeud le plus puissant (master Redis/Postgres). |

## RPi 3B+ ?

D'après la détection du modèle (`/proc/device-tree/model`), je ne vois pas de `Raspberry Pi 3 Model B Plus` dans la plage `node5` à `node15`.

Les noeuds `node10`, `node11`, `node12`, `node13` et `node14` sont des **RPi 3 Model B (pas “Plus”)**.

