import type { QueuedWebsiteAnalysis } from './websiteQueueTypes';

export declare function sqliteLoadWebsiteQueue(): Promise<QueuedWebsiteAnalysis[]>;
export declare function sqliteSaveWebsiteQueue(items: QueuedWebsiteAnalysis[]): Promise<void>;
export declare function sqliteEnqueueWebsiteAnalysis(
  item: Omit<QueuedWebsiteAnalysis, 'status'>,
): Promise<void>;
export declare function sqliteUpdateQueueItem(id: string, patch: Partial<QueuedWebsiteAnalysis>): Promise<void>;
