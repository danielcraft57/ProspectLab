import { openDatabaseAsync, type SQLiteDatabase } from 'expo-sqlite';

const DB_NAME = 'prospectlab_app_cache.db';

let dbPromise: Promise<SQLiteDatabase> | null = null;

export async function getAppCacheDb(): Promise<SQLiteDatabase> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const db = await openDatabaseAsync(DB_NAME);
      await db.execAsync(`
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS cache_entry (
          scope TEXT NOT NULL,
          cache_key TEXT NOT NULL,
          payload TEXT NOT NULL,
          updated_at INTEGER NOT NULL,
          last_accessed_at INTEGER NOT NULL,
          byte_length INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (scope, cache_key)
        );
        CREATE INDEX IF NOT EXISTS idx_cache_scope_access ON cache_entry(scope, last_accessed_at);
        CREATE INDEX IF NOT EXISTS idx_cache_updated ON cache_entry(updated_at);
      `);
      return db;
    })();
  }
  return dbPromise;
}
