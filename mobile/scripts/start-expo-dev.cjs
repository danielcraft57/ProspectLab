/**
 * Demarre Metro/Expo avec la bonne URL pour le QR code et le dev client.
 * - EXPO_PACKAGER_PROXY_URL (dans .env) : URL publique derriere un reverse-proxy (prioritaire dans @expo/cli).
 * - EXPO_DEV_SERVER_HOST : hostname/IP fixe pour QR + Metro si pas de proxy.
 * - Sinon : meme detection LAN que run-expo-android.cjs -> REACT_NATIVE_PACKAGER_HOSTNAME.
 *
 * Ne pas forcer l'IP en mode --tunnel ou --localhost.
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const mobileRoot = path.join(__dirname, '..');

function loadDotenvSync(filePath) {
  if (!fs.existsSync(filePath)) return;
  const text = fs.readFileSync(filePath, 'utf8');
  for (const line of text.split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    const eq = t.indexOf('=');
    if (eq <= 0) continue;
    const key = t.slice(0, eq).trim();
    let val = t.slice(eq + 1).trim();
    if (
      (val.startsWith('"') && val.endsWith('"')) ||
      (val.startsWith("'") && val.endsWith("'"))
    ) {
      val = val.slice(1, -1);
    }
    if (process.env[key] === undefined) process.env[key] = val;
  }
}

function getLanIPv4() {
  const nets = os.networkInterfaces();
  const preferred = [];
  const fallback = [];

  for (const name of Object.keys(nets)) {
    for (const net of nets[name] || []) {
      if (net.family !== 'IPv4' && net.family !== 4) continue;
      if (net.internal) continue;
      const a = net.address;
      if (!a || a.startsWith('169.254.')) continue;

      const lname = String(name).toLowerCase();
      const isVirtualIface =
        lname.includes('vethernet') ||
        lname.includes('virtualbox') ||
        lname.includes('vmware') ||
        lname.includes('hyper-v') ||
        lname.includes('loopback');
      if (isVirtualIface) continue;

      if (a.startsWith('192.168.56.')) continue;

      if (
        lname.includes('wi-fi') ||
        lname.includes('wifi') ||
        lname.includes('wireless') ||
        lname.includes('wlan')
      ) {
        preferred.push(a);
      } else {
        fallback.push(a);
      }
    }
  }
  return preferred[0] || fallback[0] || null;
}

function hasExplicitHostMode(argv) {
  return argv.some(
    (a) =>
      a === '--localhost' ||
      a === '--lan' ||
      a === '--tunnel' ||
      a === '--offline' ||
      /^--host(=|$)/.test(a),
  );
}

loadDotenvSync(path.join(mobileRoot, '.env'));

const extra = process.argv.slice(2);
const wantsLocalhost = extra.includes('--localhost');
const wantsTunnel = extra.includes('--tunnel');

if (!wantsLocalhost && !wantsTunnel) {
  const proxy = process.env.EXPO_PACKAGER_PROXY_URL && process.env.EXPO_PACKAGER_PROXY_URL.trim();
  if (proxy) {
    console.error(`[start] EXPO_PACKAGER_PROXY_URL -> ${proxy} (QR + manifest via proxy public)`);
  } else {
    const fixed = process.env.EXPO_DEV_SERVER_HOST && process.env.EXPO_DEV_SERVER_HOST.trim();
    if (fixed) {
      process.env.REACT_NATIVE_PACKAGER_HOSTNAME = fixed;
      console.error(`[start] REACT_NATIVE_PACKAGER_HOSTNAME -> ${fixed} (depuis EXPO_DEV_SERVER_HOST)`);
    } else if (process.env.REACT_NATIVE_PACKAGER_HOSTNAME && process.env.REACT_NATIVE_PACKAGER_HOSTNAME.trim()) {
      console.error(
        `[start] REACT_NATIVE_PACKAGER_HOSTNAME (env) -> ${process.env.REACT_NATIVE_PACKAGER_HOSTNAME.trim()}`,
      );
    } else {
      const lan = getLanIPv4();
      if (lan) {
        process.env.REACT_NATIVE_PACKAGER_HOSTNAME = lan;
        console.error(`[start] REACT_NATIVE_PACKAGER_HOSTNAME -> ${lan} (auto LAN, QR + Metro)`);
      } else {
        console.error('[start] Aucune IP LAN detectee : definis EXPO_DEV_SERVER_HOST ou EXPO_PACKAGER_PROXY_URL dans .env');
      }
    }
  }
}

if (!process.env.EXPO_DEVTOOLS_LISTEN_ADDRESS) {
  process.env.EXPO_DEVTOOLS_LISTEN_ADDRESS = '0.0.0.0';
}

const expoArgs = ['expo', 'start'];
if (!hasExplicitHostMode(extra)) {
  expoArgs.push('--host', 'lan');
}
expoArgs.push(...extra);

const r = spawnSync('npx', expoArgs, {
  stdio: 'inherit',
  cwd: mobileRoot,
  env: process.env,
  shell: true,
});
process.exit(r.status !== null && r.status !== undefined ? r.status : 1);
