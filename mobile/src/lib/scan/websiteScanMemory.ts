import * as FileSystemLegacy from 'expo-file-system/legacy';

const FILE = `${FileSystemLegacy.documentDirectory ?? ''}website_scan_discovered_v1.json`;

/** Domaines repérés au scan (URL canonique https://apex, sans www.) — réutilisés entre sessions. */
export async function loadWebsiteScanDiscovered(): Promise<string[]> {
  if (!FileSystemLegacy.documentDirectory) return [];
  try {
    const info = await FileSystemLegacy.getInfoAsync(FILE);
    if (!info.exists) return [];
    const raw = await FileSystemLegacy.readAsStringAsync(FILE);
    const parsed = JSON.parse(raw) as unknown;
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

export async function saveWebsiteScanDiscovered(urls: string[]): Promise<void> {
  if (!FileSystemLegacy.documentDirectory) return;
  const unique = [...new Set(urls)].sort((a, b) => a.localeCompare(b));
  await FileSystemLegacy.writeAsStringAsync(FILE, JSON.stringify(unique, null, 0));
}

/** À la fermeture du scan : plus de persistance jusqu’à la prochaine session sur l’écran. */
export async function clearWebsiteScanDiscovered(): Promise<void> {
  if (!FileSystemLegacy.documentDirectory) return;
  try {
    const info = await FileSystemLegacy.getInfoAsync(FILE);
    if (info.exists) {
      await FileSystemLegacy.deleteAsync(FILE, { idempotent: true });
    }
  } catch {
    try {
      await saveWebsiteScanDiscovered([]);
    } catch {
      /* ignore */
    }
  }
}
