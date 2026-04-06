import * as FileSystem from 'expo-file-system/legacy';
import { getAppCacheDb } from '../cache/appCacheDb';

/** Conforme aux bonnes pratiques OSM : UA identifiable (à ajuster avec URL contact prod). */
export const OSM_TILE_USER_AGENT = 'ProspectLabMobile/1.3 (contact: app support)';

const OSM_TILE_URL = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

const TILE_REL_PREFIX = 'osm_tiles/v1';
const MAX_TILE_COUNT = 900;
const MAX_TOTAL_BYTES = 45 * 1024 * 1024;
const TILE_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;

function absoluteBaseDir(): string {
  const base = FileSystem.cacheDirectory ?? '';
  return base.endsWith('/') ? base : `${base}/`;
}

function relativePath(z: number, x: number, y: number): string {
  return `${TILE_REL_PREFIX}/${z}/${x}_${y}.png`;
}

function absolutePath(rel: string): string {
  return `${absoluteBaseDir()}${rel}`;
}

export function osmTileUrlTemplate(): string {
  return OSM_TILE_URL;
}

function lon2tile(lon: number, zoom: number): number {
  return Math.floor(((lon + 180) / 360) * 2 ** zoom);
}

function lat2tile(lat: number, zoom: number): number {
  const rad = (lat * Math.PI) / 180;
  return Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * 2 ** zoom,
  );
}

/**
 * Tuiles couvrant un viewport (Web Mercator), bornées pour ne pas saturer le réseau / SQLite.
 */
export function tilesCoveringRegion(
  latitude: number,
  longitude: number,
  latitudeDelta: number,
  longitudeDelta: number,
  zoom: number,
  maxTiles = 18,
): Array<{ z: number; x: number; y: number }> {
  const latN = latitude + latitudeDelta / 2;
  const latS = latitude - latitudeDelta / 2;
  const lngE = longitude + longitudeDelta / 2;
  const lngW = longitude - longitudeDelta / 2;
  const xMin = lon2tile(lngW, zoom);
  const xMax = lon2tile(lngE, zoom);
  const yN = lat2tile(latN, zoom);
  const yS = lat2tile(latS, zoom);
  const xStart = Math.min(xMin, xMax);
  const xEnd = Math.max(xMin, xMax);
  const yStart = Math.min(yN, yS);
  const yEnd = Math.max(yN, yS);
  const out: Array<{ z: number; x: number; y: number }> = [];
  for (let x = xStart; x <= xEnd; x++) {
    for (let y = yStart; y <= yEnd; y++) {
      out.push({ z: zoom, x, y });
      if (out.length >= maxTiles) return out;
    }
  }
  return out;
}

export function zoomLevelFromLatitudeDelta(latitudeDelta: number): number {
  const d = Math.max(latitudeDelta, 0.0005);
  const z = Math.round(Math.log2(360 / d));
  return Math.min(19, Math.max(6, z));
}

async function ensureParentDirs(rel: string): Promise<void> {
  const parts = rel.split('/').filter(Boolean);
  if (parts.length <= 1) return;
  let acc = '';
  for (let i = 0; i < parts.length - 1; i++) {
    acc = acc ? `${acc}/${parts[i]}` : parts[i]!;
    const dir = absolutePath(acc);
    const info = await FileSystem.getInfoAsync(dir);
    if (!info.exists) {
      await FileSystem.makeDirectoryAsync(dir, { intermediates: true });
    }
  }
}

/** Télécharge et indexe une tuile (idempotent si déjà présente). */
export async function prefetchOsmTile(z: number, x: number, y: number): Promise<void> {
  if (!FileSystem.cacheDirectory) return;
  const rel = relativePath(z, x, y);
  const dest = absolutePath(rel);
  const info = await FileSystem.getInfoAsync(dest);
  const db = await getAppCacheDb();
  const now = Date.now();
  if (info.exists && info.size && info.size > 0) {
    await db.runAsync(
      `UPDATE osm_tile_index SET last_accessed_at = ? WHERE z = ? AND x = ? AND y = ?`,
      [now, z, x, y],
    );
    return;
  }
  const url = OSM_TILE_URL.replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y));
  await ensureParentDirs(rel);
  const res = await FileSystem.downloadAsync(url, dest, {
    headers: { 'User-Agent': OSM_TILE_USER_AGENT },
  });
  if (res.status !== 200) {
    try {
      await FileSystem.deleteAsync(dest, { idempotent: true });
    } catch {
      /* ignore */
    }
    return;
  }
  const finfo = await FileSystem.getInfoAsync(dest);
  const byteLength = finfo.exists && 'size' in finfo && typeof finfo.size === 'number' ? finfo.size : 0;
  await db.runAsync(
    `INSERT OR REPLACE INTO osm_tile_index (z, x, y, relative_path, byte_length, updated_at, last_accessed_at)
     VALUES (?, ?, ?, ?, ?, ?, ?)`,
    [z, x, y, rel, byteLength, now, now],
  );
}

export async function prefetchOsmTilesForMapRegion(region: {
  latitude: number;
  longitude: number;
  latitudeDelta: number;
  longitudeDelta: number;
}): Promise<void> {
  const z = zoomLevelFromLatitudeDelta(region.latitudeDelta);
  const tiles = tilesCoveringRegion(
    region.latitude,
    region.longitude,
    region.latitudeDelta,
    region.longitudeDelta,
    z,
    16,
  );
  for (const t of tiles) {
    await prefetchOsmTile(t.z, t.x, t.y);
  }
  await trimOsmTileSurplus();
}

async function trimOsmTileSurplus(): Promise<void> {
  const db = await getAppCacheDb();
  const base = absoluteBaseDir();
  if (!base) return;
  const staleCut = Date.now() - TILE_MAX_AGE_MS;

  const staleRows = await db.getAllAsync<{ z: number; x: number; y: number; relative_path: string }>(
    `SELECT z, x, y, relative_path FROM osm_tile_index WHERE updated_at < ?`,
    [staleCut],
  );
  for (const r of staleRows) {
    await db.runAsync(`DELETE FROM osm_tile_index WHERE z = ? AND x = ? AND y = ?`, [r.z, r.x, r.y]);
    try {
      await FileSystem.deleteAsync(`${base}${r.relative_path}`, { idempotent: true });
    } catch {
      /* ignore */
    }
  }

  let guard = 0;
  while (guard < 400) {
    guard += 1;
    const cnt = await db.getFirstAsync<{ c: number }>(`SELECT COUNT(*) as c FROM osm_tile_index`);
    const sum = await db.getFirstAsync<{ s: number }>(`SELECT COALESCE(SUM(byte_length), 0) as s FROM osm_tile_index`);
    if ((cnt?.c ?? 0) <= MAX_TILE_COUNT && (sum?.s ?? 0) <= MAX_TOTAL_BYTES) break;

    const victim = await db.getFirstAsync<{ z: number; x: number; y: number; relative_path: string }>(
      `SELECT z, x, y, relative_path FROM osm_tile_index ORDER BY last_accessed_at ASC LIMIT 1`,
    );
    if (!victim) break;
    await db.runAsync(`DELETE FROM osm_tile_index WHERE z = ? AND x = ? AND y = ?`, [victim.z, victim.x, victim.y]);
    try {
      await FileSystem.deleteAsync(`${base}${victim.relative_path}`, { idempotent: true });
    } catch {
      /* ignore */
    }
  }
}

export async function runOsmTileCacheMaintenance(): Promise<void> {
  await trimOsmTileSurplus();
}
