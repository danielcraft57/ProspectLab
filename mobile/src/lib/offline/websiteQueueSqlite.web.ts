import type { QueuedWebsiteAnalysis } from './websiteQueueTypes';

/** Web : pas de SQLite (pas de WASM / pas de file queue). La file hors-ligne est ignorée. */
export async function sqliteLoadWebsiteQueue(): Promise<QueuedWebsiteAnalysis[]> {
  return [];
}

export async function sqliteSaveWebsiteQueue(_items: QueuedWebsiteAnalysis[]): Promise<void> {}

export async function sqliteEnqueueWebsiteAnalysis(_item: Omit<QueuedWebsiteAnalysis, 'status'>): Promise<void> {}

export async function sqliteUpdateQueueItem(_id: string, _patch: Partial<QueuedWebsiteAnalysis>): Promise<void> {}
