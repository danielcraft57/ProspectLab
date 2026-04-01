/**
 * Installation APK debug sur appareil (souvent en panne en Wi-Fi avec « streamed install »).
 * 1) adb install -r -d --no-streaming (recommandé par adb sur liaisons instables)
 * 2) Sinon push + pm install, avec reprises et verification de taille (EOF trompeur apres push).
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const apkRel = path.join('android', 'app', 'build', 'outputs', 'apk', 'debug', 'app-debug.apk');
const mobileRoot = path.join(__dirname, '..');
const apkPath = path.join(mobileRoot, apkRel);

function adbBin() {
  const sdk =
    process.env.ANDROID_HOME ||
    process.env.ANDROID_SDK_ROOT ||
    path.join(process.env.LOCALAPPDATA || '', 'Android', 'Sdk');
  const adb = path.join(sdk, 'platform-tools', process.platform === 'win32' ? 'adb.exe' : 'adb');
  if (!fs.existsSync(adb)) {
    console.error('[install-debug-apk] adb introuvable. Definis ANDROID_HOME ou installe platform-tools.');
    process.exit(1);
  }
  return adb;
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: 'utf8', stdio: 'pipe', ...opts });
  return { status: r.status, stdout: r.stdout || '', stderr: r.stderr || '' };
}

function localSize(p) {
  try {
    return fs.statSync(p).size;
  } catch {
    return -1;
  }
}

function remoteFileSize(adb, serial, remotePath) {
  const r = run(adb, [...serial, 'shell', 'stat', '-c', '%s', remotePath]);
  if (r.status !== 0) return null;
  const n = parseInt(String(r.stdout).trim(), 10);
  return Number.isFinite(n) && n >= 0 ? n : null;
}

function sleepSync(ms) {
  const end = Date.now() + ms;
  while (Date.now() < end) {}
}

const adb = adbBin();
const serialArg = process.argv[2];
const serial = serialArg && serialArg.includes(':') ? ['-s', serialArg] : [];

if (!fs.existsSync(apkPath)) {
  console.error(`[install-debug-apk] APK introuvable: ${apkPath}`);
  console.error('Lance dabord: npx expo run:android --no-bundler (ou build Gradle debug).');
  process.exit(1);
}

const remote = '/data/local/tmp/pl-app-debug.apk';
const sizeWant = localSize(apkPath);

// 1) Install classique sans streaming (souvent OK la ou le streamed install echoue sans message).
console.error('[install-debug-apk] tentative: adb install -r -d --no-streaming');
let r = run(adb, [...serial, 'install', '-r', '-d', '--no-streaming', apkPath], { cwd: mobileRoot });
process.stdout.write(r.stdout);
process.stderr.write(r.stderr);
if (r.status === 0) {
  console.error('[install-debug-apk] OK');
  process.exit(0);
}

console.error('[install-debug-apk] install --no-streaming a echoue, push + pm install...');

// 2) Nettoyer une ancienne copie partielle puis pousser avec reprises.
run(adb, [...serial, 'shell', 'rm', '-f', remote]);

const maxAttempts = 4;
for (let attempt = 1; attempt <= maxAttempts; attempt++) {
  console.error(`[install-debug-apk] push -> ${remote} (essai ${attempt}/${maxAttempts})`);
  r = run(adb, [...serial, 'push', apkPath, remote], { cwd: mobileRoot });
  const combined = `${r.stderr}\n${r.stdout}`;
  const got = remoteFileSize(adb, serial, remote);
  const sizeOk = got !== null && got === sizeWant;

  if (sizeOk) {
    if (r.status !== 0) {
      console.error('[install-debug-apk] push a renvoye une erreur (EOF?) mais taille OK sur le device, on continue.');
    }
    break;
  }
  if (attempt === maxAttempts) {
    console.error(combined);
    console.error(
      `[install-debug-apk] Echec push (status=${r.status}, taille locale=${sizeWant}, distante=${got}). Reessaie USB ou reseau plus stable.`,
    );
    process.exit(r.status || 1);
  }
  sleepSync(800 * attempt);
}

console.error('[install-debug-apk] pm install -r -d');
r = run(adb, [...serial, 'shell', 'pm', 'install', '-r', '-d', remote], { cwd: mobileRoot });
process.stdout.write(r.stdout);
process.stderr.write(r.stderr);
if (r.status !== 0) process.exit(r.status || 1);

run(adb, [...serial, 'shell', 'rm', '-f', remote]);

console.error('[install-debug-apk] OK');
process.exit(0);
