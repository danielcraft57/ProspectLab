import { openDatabaseAsync, type SQLiteDatabase } from 'expo-sqlite';
import * as FileSystemLegacy from 'expo-file-system/legacy';
import type { QueuedWebsiteAnalysis } from './websiteQueueTypes';

const DB_NAME = 'prospectlab_offline.db';
const LEGACY_JSON = `${FileSystemLegacy.documentDirectory ?? ''}website_analysis_queue_v1.json`;

let dbPromise: Promise<SQLiteDatabase> | null = null;

async function migrateFromJsonIfNeeded(db: SQLiteDatabase): Promise<void> {
  if (!FileSystemLegacy.documentDirectory) return;
  try {
    const info = await FileSystemLegacy.getInfoAsync(LEGACY_JSON);
    if (!info.exists) return;
    const raw = await FileSystemLegacy.readAsStringAsync(LEGACY_JSON);
    const parsed = JSON.parse(raw) as QueuedWebsiteAnalysis[];
    if (!Array.isArray(parsed) || parsed.length === 0) {
      await FileSystemLegacy.deleteAsync(LEGACY_JSON, { idempotent: true });
      return;
    }
    await db.withTransactionAsync(async () => {
      for (const row of parsed) {
        await db.runAsync(
          `INSERT OR IGNORE INTO website_analysis_queue (id, website, label, created_at, status, error_message, synced_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)`,
          [
            row.id,
            row.website,
            row.label,
            row.createdAt,
            row.status,
            row.errorMessage ?? null,
            row.syncedAt ?? null,
          ],
        );
      }
    });
    await FileSystemLegacy.deleteAsync(LEGACY_JSON, { idempotent: true });
  } catch {
    /* migration best-effort */
  }
}

export async function getWebsiteQueueDb(): Promise<SQLiteDatabase> {
  if (!dbPromise) {
    dbPromise = (async () => {
      const db = await openDatabaseAsync(DB_NAME);
      await db.execAsync(`
        PRAGMA journal_mode = WAL;
        CREATE TABLE IF NOT EXISTS website_analysis_queue (
          id TEXT PRIMARY KEY NOT NULL,
          website TEXT NOT NULL,
          label TEXT NOT NULL,
          created_at INTEGER NOT NULL,
          status TEXT NOT NULL,
          error_message TEXT,
          synced_at INTEGER
        );
      `);
      await migrateFromJsonIfNeeded(db);
      return db;
    })();
  }
  return dbPromise;
}

function rowToItem(r: {
  id: string;
  website: string;
  label: string;
  created_at: number;
  status: string;
  error_message: string | null;
  synced_at: number | null;
}): QueuedWebsiteAnalysis {
  return {
    id: r.id,
    website: r.website,
    label: r.label,
    createdAt: r.created_at,
    status: r.status as QueuedWebsiteAnalysis['status'],
    errorMessage: r.error_message ?? undefined,
    syncedAt: r.synced_at ?? undefined,
  };
}

export async function sqliteLoadWebsiteQueue(): Promise<QueuedWebsiteAnalysis[]> {
  const db = await getWebsiteQueueDb();
  const rows = await db.getAllAsync<{
    id: string;
    website: string;
    label: string;
    created_at: number;
    status: string;
    error_message: string | null;
    synced_at: number | null;
  }>(
    `SELECT id, website, label, created_at, status, error_message, synced_at
     FROM website_analysis_queue
     ORDER BY created_at DESC`,
  );
  return rows.map(rowToItem);
}

export async function sqliteSaveWebsiteQueue(items: QueuedWebsiteAnalysis[]): Promise<void> {
  const db = await getWebsiteQueueDb();
  await db.withTransactionAsync(async () => {
    await db.execAsync('DELETE FROM website_analysis_queue');
    for (const row of items) {
      await db.runAsync(
        `INSERT INTO website_analysis_queue (id, website, label, created_at, status, error_message, synced_at)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        [
          row.id,
          row.website,
          row.label,
          row.createdAt,
          row.status,
          row.errorMessage ?? null,
          row.syncedAt ?? null,
        ],
      );
    }
  });
}

export async function sqliteEnqueueWebsiteAnalysis(item: Omit<QueuedWebsiteAnalysis, 'status'>): Promise<void> {
  const db = await getWebsiteQueueDb();
  const dup = await db.getFirstAsync<{ c: number }>(
    `SELECT COUNT(*) as c FROM website_analysis_queue
     WHERE website = ? AND status IN ('queued_offline', 'syncing')`,
    [item.website],
  );
  if (dup && dup.c > 0) return;
  await db.runAsync(
    `INSERT INTO website_analysis_queue (id, website, label, created_at, status, error_message, synced_at)
     VALUES (?, ?, ?, ?, 'queued_offline', NULL, NULL)`,
    [item.id, item.website, item.label, item.createdAt],
  );
}

export async function sqliteUpdateQueueItem(id: string, patch: Partial<QueuedWebsiteAnalysis>): Promise<void> {
  const db = await getWebsiteQueueDb();
  const cur = await db.getFirstAsync<{
    id: string;
    website: string;
    label: string;
    created_at: number;
    status: string;
    error_message: string | null;
    synced_at: number | null;
  }>(`SELECT * FROM website_analysis_queue WHERE id = ?`, [id]);
  if (!cur) return;
  const merged = rowToItem(cur);
  const next: QueuedWebsiteAnalysis = { ...merged, ...patch };
  await db.runAsync(
    `UPDATE website_analysis_queue SET
       website = ?, label = ?, created_at = ?, status = ?, error_message = ?, synced_at = ?
     WHERE id = ?`,
    [
      next.website,
      next.label,
      next.createdAt,
      next.status,
      next.errorMessage ?? null,
      next.syncedAt ?? null,
      id,
    ],
  );
}
