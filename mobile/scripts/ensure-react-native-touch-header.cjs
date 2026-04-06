/**
 * Restaure TouchEventEmitter.h si absent (certains installs npm Windows omettent ce fichier).
 * Source: react-native v0.81.5 sur GitHub (meme contenu que le tag du package).
 */
const fs = require('fs');
const path = require('path');
const https = require('https');

const RN_VERSION = require('../node_modules/react-native/package.json').version;
const target = path.join(
  __dirname,
  '..',
  'node_modules',
  'react-native',
  'ReactCommon',
  'react',
  'renderer',
  'components',
  'view',
  'TouchEventEmitter.h',
);

if (fs.existsSync(target)) {
  process.exit(0);
}

const tag = `v${RN_VERSION}`;
const url = `https://raw.githubusercontent.com/facebook/react-native/${tag}/packages/react-native/ReactCommon/react/renderer/components/view/TouchEventEmitter.h`;

function fetch(urlStr) {
  return new Promise((resolve, reject) => {
    https
      .get(urlStr, (res) => {
        if (res.statusCode === 302 || res.statusCode === 301) {
          fetch(res.headers.location).then(resolve).catch(reject);
          return;
        }
        if (res.statusCode !== 200) {
          reject(new Error(`HTTP ${res.statusCode} for ${urlStr}`));
          return;
        }
        const chunks = [];
        res.on('data', (c) => chunks.push(c));
        res.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
      })
      .on('error', reject);
  });
}

fetch(url)
  .then((body) => {
    if (!body.includes('class TouchEventEmitter')) {
      throw new Error('Contenu TouchEventEmitter.h invalide');
    }
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.writeFileSync(target, body, 'utf8');
    console.log('[postinstall] Restaure TouchEventEmitter.h pour react-native', RN_VERSION);
  })
  .catch((e) => {
    console.warn('[postinstall] Impossible de telecharger TouchEventEmitter.h:', e.message);
    process.exit(0);
  });
