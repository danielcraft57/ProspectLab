import * as FileSystemLegacy from 'expo-file-system/legacy';

const FILE = `${FileSystemLegacy.documentDirectory ?? ''}website_analysis_queue_v1.json`;

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

async function readRaw(): Promise<QueuedWebsiteAnalysis[]> {
  if (!FileSystemLegacy.documentDirectory) return [];
  try {
    const info = await FileSystemLegacy.getInfoAsync(FILE);
    if (!info.exists) return [];
    const raw = await FileSystemLegacy.readAsStringAsync(FILE);
    const parsed = JSON.parse(raw) as QueuedWebsiteAnalysis[];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export async function loadWebsiteQueue(): Promise<QueuedWebsiteAnalysis[]> {
  return readRaw();
}

export async function saveWebsiteQueue(items: QueuedWebsiteAnalysis[]): Promise<void> {
  if (!FileSystemLegacy.documentDirectory) return;
  await FileSystemLegacy.writeAsStringAsync(FILE, JSON.stringify(items, null, 0));
}

export async function enqueueWebsiteAnalysis(item: Omit<QueuedWebsiteAnalysis, 'status'>): Promise<void> {
  const q = await readRaw();
  if (q.some((x) => x.website === item.website && (x.status === 'queued_offline' || x.status === 'syncing'))) {
    return;
  }
  q.unshift({ ...item, status: 'queued_offline' });
  await saveWebsiteQueue(q);
}

export async function updateQueueItem(id: string, patch: Partial<QueuedWebsiteAnalysis>): Promise<void> {
  const q = await readRaw();
  const i = q.findIndex((x) => x.id === id);
  if (i < 0) return;
  q[i] = { ...q[i], ...patch };
  await saveWebsiteQueue(q);
}

export function pendingQueueCount(items: QueuedWebsiteAnalysis[]): number {
  return items.filter((x) => x.status === 'queued_offline' || x.status === 'error').length;
}
