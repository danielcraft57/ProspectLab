import type { QueuedWebsiteAnalysis } from './websiteQueueTypes';
import {
  sqliteEnqueueWebsiteAnalysis,
  sqliteLoadWebsiteQueue,
  sqliteSaveWebsiteQueue,
  sqliteUpdateQueueItem,
} from './websiteQueueSqlite';

export type { QueuedWebsiteAnalysis };

export async function loadWebsiteQueue(): Promise<QueuedWebsiteAnalysis[]> {
  return sqliteLoadWebsiteQueue();
}

export async function saveWebsiteQueue(items: QueuedWebsiteAnalysis[]): Promise<void> {
  return sqliteSaveWebsiteQueue(items);
}

export async function enqueueWebsiteAnalysis(item: Omit<QueuedWebsiteAnalysis, 'status'>): Promise<void> {
  return sqliteEnqueueWebsiteAnalysis(item);
}

export async function updateQueueItem(id: string, patch: Partial<QueuedWebsiteAnalysis>): Promise<void> {
  return sqliteUpdateQueueItem(id, patch);
}

export function pendingQueueCount(items: QueuedWebsiteAnalysis[]): number {
  return items.filter((x) => x.status === 'queued_offline' || x.status === 'error').length;
}
