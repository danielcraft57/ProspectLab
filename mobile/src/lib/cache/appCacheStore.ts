import { MAX_CACHE_BYTES_SOFT, SCOPE_LRU_MAX } from './cachePolicy';
import { CacheScope, type CacheScopeValue } from './cacheScopes';
import { getAppCacheDb } from './appCacheDb';

export type CacheRowMeta = {
  payload: string;
  updatedAt: number;
  lastAccessedAt: number;
};

const DETAIL_SCOPES: CacheScopeValue[] = [CacheScope.ENTREPRISE_DETAIL, CacheScope.CAMPAGNE_DETAIL];

const MAP_NEARBY_PRUNE_MS = 5 * 24 * 60 * 60 * 1000;

export async function readCacheEntry(scope: CacheScopeValue, cacheKey: string): Promise<CacheRowMeta | null> {
  const db = await getAppCacheDb();
  const now = Date.now();
  const row = await db.getFirstAsync<{
    payload: string;
    updated_at: number;
    last_accessed_at: number;
  }>(
    `SELECT payload, updated_at, last_accessed_at FROM cache_entry WHERE scope = ? AND cache_key = ?`,
    [scope, cacheKey],
  );
  if (!row) return null;
  await db.runAsync(`UPDATE cache_entry SET last_accessed_at = ? WHERE scope = ? AND cache_key = ?`, [
    now,
    scope,
    cacheKey,
  ]);
  return {
    payload: row.payload,
    updatedAt: row.updated_at,
    lastAccessedAt: now,
  };
}

export async function writeCacheEntry(scope: CacheScopeValue, cacheKey: string, payload: string): Promise<void> {
  const db = await getAppCacheDb();
  const now = Date.now();
  const byteLength = payload.length * 2;
  await db.runAsync(
    `INSERT OR REPLACE INTO cache_entry (scope, cache_key, payload, updated_at, last_accessed_at, byte_length)
     VALUES (?, ?, ?, ?, ?, ?)`,
    [scope, cacheKey, payload, now, now, byteLength],
  );
  const lruCap = SCOPE_LRU_MAX[scope];
  if (typeof lruCap === 'number') {
    await trimScopeLru(scope, lruCap);
  }
  await trimSoftBudget();
}

export async function deleteCacheEntry(scope: CacheScopeValue, cacheKey: string): Promise<void> {
  const db = await getAppCacheDb();
  await db.runAsync(`DELETE FROM cache_entry WHERE scope = ? AND cache_key = ?`, [scope, cacheKey]);
}

async function trimScopeLru(scope: CacheScopeValue, maxKeep: number): Promise<void> {
  const db = await getAppCacheDb();
  const rows = await db.getAllAsync<{ cache_key: string }>(
    `SELECT cache_key FROM cache_entry WHERE scope = ? ORDER BY last_accessed_at DESC`,
    [scope],
  );
  if (rows.length <= maxKeep) return;
  const drop = rows.slice(maxKeep);
  for (const r of drop) {
    await db.runAsync(`DELETE FROM cache_entry WHERE scope = ? AND cache_key = ?`, [scope, r.cache_key]);
  }
}

async function totalPayloadBytes(): Promise<number> {
  const db = await getAppCacheDb();
  const row = await db.getFirstAsync<{ s: number }>(`SELECT COALESCE(SUM(byte_length), 0) as s FROM cache_entry`);
  return row?.s ?? 0;
}

/** Supprime des entrées les moins récemment consultées jusqu'à repasser sous le budget doux. */
export async function trimSoftBudget(): Promise<void> {
  let total = await totalPayloadBytes();
  if (total <= MAX_CACHE_BYTES_SOFT) return;
  const db = await getAppCacheDb();
  const victims = await db.getAllAsync<{ scope: string; cache_key: string }>(
    `SELECT scope, cache_key FROM cache_entry
     WHERE scope IN (${DETAIL_SCOPES.map(() => '?').join(',')})
     ORDER BY last_accessed_at ASC`,
    [...DETAIL_SCOPES],
  );
  for (const v of victims) {
    if (total <= MAX_CACHE_BYTES_SOFT) break;
    const m = await db.getFirstAsync<{ byte_length: number }>(
      `SELECT byte_length FROM cache_entry WHERE scope = ? AND cache_key = ?`,
      [v.scope, v.cache_key],
    );
    await db.runAsync(`DELETE FROM cache_entry WHERE scope = ? AND cache_key = ?`, [v.scope, v.cache_key]);
    total -= m?.byte_length ?? 0;
  }
}

/** Nettoyage opportuniste au démarrage : listes / dashboard > 7 jours. */
export async function pruneExpiredLooseEntries(ttlMs: number): Promise<void> {
  const db = await getAppCacheDb();
  const cutoff = Date.now() - ttlMs;
  await db.runAsync(
    `DELETE FROM cache_entry WHERE scope IN (?, ?, ?) AND updated_at < ?`,
    [CacheScope.DASHBOARD, CacheScope.ENTREPRISES_LIST, CacheScope.CAMPAGNES_LIST, cutoff],
  );
}

export async function pruneExpiredMapNearbyEntries(): Promise<void> {
  const db = await getAppCacheDb();
  const cutoff = Date.now() - MAP_NEARBY_PRUNE_MS;
  await db.runAsync(`DELETE FROM cache_entry WHERE scope = ? AND updated_at < ?`, [CacheScope.MAP_NEARBY, cutoff]);
}

export async function runAppCacheMaintenance(): Promise<void> {
  await pruneExpiredLooseEntries(7 * 24 * 60 * 60 * 1000);
  await pruneExpiredMapNearbyEntries();
  const { runOsmTileCacheMaintenance } = await import('../map/osmTileFileCache');
  await runOsmTileCacheMaintenance();
  await trimSoftBudget();
}
