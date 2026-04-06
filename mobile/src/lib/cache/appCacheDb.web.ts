import type { SQLiteDatabase } from 'expo-sqlite';

/**
 * Shim mémoire pour le web : évite d'importer expo-sqlite (worker + WASM non résolu par Metro).
 * Couvre uniquement les requêtes émises par `appCacheStore` et `osmTileFileCache`.
 */
type CacheRow = {
  scope: string;
  cache_key: string;
  payload: string;
  updated_at: number;
  last_accessed_at: number;
  byte_length: number;
};

type OsmRow = {
  z: number;
  x: number;
  y: number;
  relative_path: string;
  byte_length: number;
  updated_at: number;
  last_accessed_at: number;
};

const cache = new Map<string, CacheRow>();
const osm = new Map<string, OsmRow>();

function ck(scope: string, cacheKey: string): string {
  return `${scope}\u0000${cacheKey}`;
}

function ok(z: number, x: number, y: number): string {
  return `${z}:${x}:${y}`;
}

function norm(sql: string): string {
  return sql.replace(/\s+/g, ' ').trim();
}

class WebSqliteShim {
  async execAsync(_sql: string): Promise<void> {
    return;
  }

  async getFirstAsync<T>(sql: string, ...params: unknown[]): Promise<T | null> {
    const q = norm(sql);
    const p = params;

    if (q.startsWith('SELECT payload, updated_at, last_accessed_at FROM cache_entry WHERE scope = ? AND cache_key = ?')) {
      const row = cache.get(ck(p[0] as string, p[1] as string));
      if (!row) return null;
      return {
        payload: row.payload,
        updated_at: row.updated_at,
        last_accessed_at: row.last_accessed_at,
      } as T;
    }

    if (q === 'SELECT COALESCE(SUM(byte_length), 0) as s FROM cache_entry') {
      let s = 0;
      for (const r of cache.values()) s += r.byte_length;
      return { s } as T;
    }

    if (q.startsWith('SELECT byte_length FROM cache_entry WHERE scope = ? AND cache_key = ?')) {
      const row = cache.get(ck(p[0] as string, p[1] as string));
      if (!row) return null;
      return { byte_length: row.byte_length } as T;
    }

    if (q === 'SELECT COUNT(*) as c FROM osm_tile_index') {
      return { c: osm.size } as T;
    }

    if (q === 'SELECT COALESCE(SUM(byte_length), 0) as s FROM osm_tile_index') {
      let s = 0;
      for (const r of osm.values()) s += r.byte_length;
      return { s } as T;
    }

    if (q.startsWith('SELECT z, x, y, relative_path FROM osm_tile_index ORDER BY last_accessed_at ASC LIMIT 1')) {
      const sorted = [...osm.values()].sort((a, b) => a.last_accessed_at - b.last_accessed_at);
      const v = sorted[0];
      if (!v) return null;
      return { z: v.z, x: v.x, y: v.y, relative_path: v.relative_path } as T;
    }

    return null;
  }

  async getAllAsync<T>(sql: string, ...params: unknown[]): Promise<T[]> {
    const q = norm(sql);
    const p = params;

    if (q.startsWith('SELECT cache_key FROM cache_entry WHERE scope = ? ORDER BY last_accessed_at DESC')) {
      const scope = p[0] as string;
      return [...cache.values()]
        .filter((r) => r.scope === scope)
        .sort((a, b) => b.last_accessed_at - a.last_accessed_at)
        .map((r) => ({ cache_key: r.cache_key })) as T[];
    }

    if (q.startsWith('SELECT scope, cache_key FROM cache_entry WHERE scope IN (')) {
      const scopes = new Set(p as string[]);
      return [...cache.values()]
        .filter((r) => scopes.has(r.scope))
        .sort((a, b) => a.last_accessed_at - b.last_accessed_at)
        .map((r) => ({ scope: r.scope, cache_key: r.cache_key })) as T[];
    }

    if (q.startsWith('SELECT z, x, y, relative_path FROM osm_tile_index WHERE updated_at < ?')) {
      const cut = p[0] as number;
      return [...osm.values()]
        .filter((r) => r.updated_at < cut)
        .map((r) => ({ z: r.z, x: r.x, y: r.y, relative_path: r.relative_path })) as T[];
    }

    return [];
  }

  async runAsync(sql: string, ...params: unknown[]): Promise<{ changes: number; lastInsertRowId: number }> {
    const q = norm(sql);
    const p = params;

    if (q.startsWith('UPDATE cache_entry SET last_accessed_at = ? WHERE scope = ? AND cache_key = ?')) {
      const [la, scope, key] = p as [number, string, string];
      const row = cache.get(ck(scope, key));
      if (row) row.last_accessed_at = la;
      return { changes: row ? 1 : 0, lastInsertRowId: 0 };
    }

    if (q.startsWith('INSERT OR REPLACE INTO cache_entry')) {
      const [scope, cacheKey, payload, updatedAt, lastAccessedAt, byteLength] = p as [
        string,
        string,
        string,
        number,
        number,
        number,
      ];
      cache.set(ck(scope, cacheKey), {
        scope,
        cache_key: cacheKey,
        payload,
        updated_at: updatedAt,
        last_accessed_at: lastAccessedAt,
        byte_length: byteLength,
      });
      return { changes: 1, lastInsertRowId: 0 };
    }

    if (q.startsWith('DELETE FROM cache_entry WHERE scope = ? AND cache_key = ?')) {
      const [scope, key] = p as [string, string];
      return { changes: cache.delete(ck(scope, key)) ? 1 : 0, lastInsertRowId: 0 };
    }

    if (q.startsWith('DELETE FROM cache_entry WHERE scope IN (') && q.includes('AND updated_at <')) {
      const cutoff = p[p.length - 1] as number;
      const scopes = p.slice(0, -1) as string[];
      let n = 0;
      for (const [k, row] of [...cache.entries()]) {
        if (scopes.includes(row.scope) && row.updated_at < cutoff) {
          cache.delete(k);
          n += 1;
        }
      }
      return { changes: n, lastInsertRowId: 0 };
    }

    if (q.startsWith('DELETE FROM cache_entry WHERE scope = ? AND updated_at < ?')) {
      const [scope, cutoff] = p as [string, number];
      let n = 0;
      for (const [k, row] of [...cache.entries()]) {
        if (row.scope === scope && row.updated_at < cutoff) {
          cache.delete(k);
          n += 1;
        }
      }
      return { changes: n, lastInsertRowId: 0 };
    }

    if (q.startsWith('UPDATE osm_tile_index SET last_accessed_at = ? WHERE z = ? AND x = ? AND y = ?')) {
      const [la, z, x, y] = p as [number, number, number, number];
      const row = osm.get(ok(z, x, y));
      if (row) row.last_accessed_at = la;
      return { changes: row ? 1 : 0, lastInsertRowId: 0 };
    }

    if (q.startsWith('INSERT OR REPLACE INTO osm_tile_index')) {
      const [z, x, y, rel, bl, ua, laa] = p as [number, number, number, string, number, number, number];
      osm.set(ok(z, x, y), {
        z,
        x,
        y,
        relative_path: rel,
        byte_length: bl,
        updated_at: ua,
        last_accessed_at: laa,
      });
      return { changes: 1, lastInsertRowId: 0 };
    }

    if (q.startsWith('DELETE FROM osm_tile_index WHERE z = ? AND x = ? AND y = ?')) {
      const [z, x, y] = p as [number, number, number];
      return { changes: osm.delete(ok(z, x, y)) ? 1 : 0, lastInsertRowId: 0 };
    }

    return { changes: 0, lastInsertRowId: 0 };
  }
}

let singleton: WebSqliteShim | null = null;

export async function getAppCacheDb(): Promise<SQLiteDatabase> {
  if (!singleton) singleton = new WebSqliteShim();
  return singleton as unknown as SQLiteDatabase;
}
