/**
 * Lance `npx expo run:android` avec JAVA_HOME.
 * Priorite : JDK 21 (winget : Eclipse Adoptium, Microsoft, Oracle, etc.) > JAVA_HOME deja defini > JBR Android Studio.
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const javaBin = process.platform === 'win32' ? 'java.exe' : 'java';

function readJdkMajor(javaHome) {
  const releasePath = path.join(javaHome, 'release');
  if (!fs.existsSync(releasePath)) return null;
  try {
    const text = fs.readFileSync(releasePath, 'utf8');
    const m = text.match(/JAVA_VERSION="?(\d+)/);
    return m ? parseInt(m[1], 10) : null;
  } catch {
    return null;
  }
}

/** Cherche un JDK 21 installe (chemins typiques winget). */
function findJdk21Home() {
  if (process.platform !== 'win32') {
    return null;
  }
  const roots = [
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Java'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Eclipse Adoptium'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Microsoft'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Amazon Corretto'),
    path.join(process.env.ProgramFiles || 'C:\\Program Files', 'Zulu'),
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Eclipse Adoptium'),
  ];
  for (const root of roots) {
    if (!root || !fs.existsSync(root)) continue;
    let entries;
    try {
      entries = fs.readdirSync(root, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const ent of entries) {
      if (!ent.isDirectory()) continue;
      const candidate = path.join(root, ent.name);
      const maj = readJdkMajor(candidate);
      if (maj === 21 && fs.existsSync(path.join(candidate, 'bin', javaBin))) {
        return candidate;
      }
    }
  }
  return null;
}

function findJbr() {
  const candidates =
    process.platform === 'darwin'
      ? ['/Applications/Android Studio.app/Contents/jbr']
      : [
          path.join(process.env['ProgramFiles'] || 'C:\\Program Files', 'Android', 'Android Studio', 'jbr'),
          path.join(process.env['ProgramFiles(x86)'] || '', 'Android', 'Android Studio', 'jbr'),
          path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Android', 'Android Studio', 'jbr'),
        ];
  for (const c of candidates) {
    if (c && fs.existsSync(path.join(c, 'bin', javaBin))) {
      return c;
    }
  }
  return null;
}

function resolveJavaHome() {
  const jdk21 = findJdk21Home();
  if (jdk21) {
    console.error(`[run-expo-android] JAVA_HOME -> JDK 21 (${jdk21})`);
    return jdk21;
  }
  if (process.env.JAVA_HOME && fs.existsSync(path.join(process.env.JAVA_HOME, 'bin', javaBin))) {
    const maj = readJdkMajor(process.env.JAVA_HOME);
    console.error(
      `[run-expo-android] JAVA_HOME -> env (${process.env.JAVA_HOME})${maj != null ? ` (Java ${maj})` : ''}`,
    );
    return process.env.JAVA_HOME;
  }
  const jbr = findJbr();
  if (jbr) {
    console.error(`[run-expo-android] JAVA_HOME -> Android Studio JBR (${jbr})`);
    return jbr;
  }
  return null;
}

function resolveAndroidSdkRoot() {
  if (process.env.ANDROID_SDK_ROOT && fs.existsSync(process.env.ANDROID_SDK_ROOT)) {
    return process.env.ANDROID_SDK_ROOT;
  }
  if (process.env.ANDROID_HOME && fs.existsSync(process.env.ANDROID_HOME)) {
    return process.env.ANDROID_HOME;
  }
  if (process.platform === 'win32') {
    const winSdk = path.join(process.env.LOCALAPPDATA || '', 'Android', 'Sdk');
    if (fs.existsSync(winSdk)) return winSdk;
  }
  return null;
}

const home = resolveJavaHome();
if (home) {
  process.env.JAVA_HOME = home;
  const sep = path.delimiter;
  process.env.Path = `${path.join(home, 'bin')}${sep}${process.env.Path || ''}`;
} else {
  console.error('[run-expo-android] Aucun JDK trouve. Installe JDK 21 (winget) ou Android Studio.');
}

const mobileRoot = path.join(__dirname, '..');
const androidRoot = path.join(mobileRoot, 'android');
const sdkRoot = resolveAndroidSdkRoot();
if (sdkRoot) {
  process.env.ANDROID_HOME = sdkRoot;
  process.env.ANDROID_SDK_ROOT = sdkRoot;
  const sep = path.delimiter;
  process.env.Path = `${path.join(sdkRoot, 'platform-tools')}${sep}${path.join(sdkRoot, 'emulator')}${sep}${process.env.Path || ''}`;
  console.error(`[run-expo-android] ANDROID_HOME -> ${sdkRoot}`);

  const localPropertiesPath = path.join(androidRoot, 'local.properties');
  if (!fs.existsSync(localPropertiesPath)) {
    const escaped = sdkRoot.replace(/\\/g, '\\\\');
    fs.writeFileSync(localPropertiesPath, `sdk.dir=${escaped}\n`, 'utf8');
    console.error('[run-expo-android] local.properties cree (sdk.dir).');
  }
} else {
  console.error('[run-expo-android] SDK Android introuvable. Installe Android SDK (platform-tools, build-tools, platforms).');
}

const extra = process.argv.slice(2);
const r = spawnSync('npx', ['expo', 'run:android', ...extra], {
  stdio: 'inherit',
  cwd: mobileRoot,
  env: process.env,
  shell: true,
});
process.exit(r.status !== null && r.status !== undefined ? r.status : 1);
