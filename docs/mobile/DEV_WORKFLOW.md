# Workflow dev (mobile)

## Pre-requis

- Node.js LTS
- npm (ou pnpm)
- Expo Go sur telephone (optionnel) ou emulateur Android

## Installation

Aller dans `mobile/` puis installer:
- `npm install`

## Variables d'environnement

On utilise des variables Expo (prefixe `EXPO_PUBLIC_`).

Exemples (remplacer l’hôte par le tien en prod ou sur le LAN)

- `EXPO_PUBLIC_PROSPECTLAB_BASE_URL=http://localhost:5000`
- `EXPO_PUBLIC_PROSPECTLAB_API_PUBLIC_PREFIX=/api/public`
- `EXPO_PUBLIC_EAS_PROJECT_ID=...` si tu utilises les notifications push Expo

Le token API n'est pas une variable d'env : il est saisi dans l'app puis stocke de facon securisee.

Fichiers sensibles locaux (non commites, voir `mobile/.gitignore`) : `google-services.json` Firebase **client** Android, cles `.p8` / keystores.

## Lancer

- `npm run start`

## Build natif / EAS

Pour un APK avec FCM, prevvoir un build dev client ou EAS selon la doc Expo (`google-services.json`, `android.googleServicesFile` dans la config).

## Depannage : `BUILD SUCCESSFUL` puis echec `adb install`

Le Gradle a reussi ; l’erreur vient de **l’installation sur l’appareil** (souvent message tronque dans le terminal Expo).

1. **Voir la vraie cause** (PowerShell) :
   ```text
   & "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" -s <SERIAL> install -r -d android\app\build\outputs\apk\debug\app-debug.apk
   ```
   Le serial s’affiche avec `adb devices` (ex. `192.168.x.x:5555` en Wi‑Fi, ou `R58…` en USB).

2. **Signature incompatible** (`INSTALL_FAILED_UPDATE_INCOMPATIBLE`) : une ancienne appli (autre build, autre keystore, Expo Go vs dev client) occupe deja le meme **applicationId**. Desinstaller puis relancer `npm run android` :
   ```text
   adb uninstall com.danielcraft.prospectlab
   ```
   (Verifie le `package` dans `app.json` si tu l’as change.)

3. **ADB Wi‑Fi instable** : brancher en **USB**, activer le debogage USB, verifier `adb devices`. Pour forcer un appareil : `set ANDROID_SERIAL=R58xxxx` (cmd) ou `$env:ANDROID_SERIAL="..."` (PowerShell) avant `npm run android`.

4. **Espace disque** sur le telephone, ou **versionCode** en baisse : messages du type `INSTALL_FAILED_*` dans la sortie `adb install` complete.

