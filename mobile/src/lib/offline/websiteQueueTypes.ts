export type QueuedWebsiteAnalysis = {
  id: string;
  website: string;
  /** Libellé court (host) pour l'UI */
  label: string;
  createdAt: number;
  status: 'queued_offline' | 'syncing' | 'synced' | 'error';
  errorMessage?: string;
  syncedAt?: number;
};
