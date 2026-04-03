import type { StatisticsOverviewData } from '../../features/prospectlab/prospectLabApi';
import { isStale } from './cachePolicy';
import { CacheScope } from './cacheScopes';
import type {
  CampagneDetailCachePayload,
  CampagnesListCachePayload,
  DashboardCachePayload,
  EntrepriseDetailCachePayload,
  EntreprisesListCachePayload,
} from './cacheTypes';
import { readCacheEntry, writeCacheEntry } from './appCacheStore';

const DASHBOARD_KEY = 'overview_days_7';
const CAMPAGNES_LIST_KEY = 'list_default_v1';

export function buildEntreprisesListCacheKey(
  search: string,
  filters: { secteur?: string; statut?: string; opportunite?: string },
): string {
  return JSON.stringify({
    v: 1,
    q: search,
    secteur: filters.secteur ?? '',
    statut: filters.statut ?? '',
    opportunite: filters.opportunite ?? '',
    off: 0,
  });
}

export function buildEntrepriseDetailCacheKey(kind: string, value: string): string {
  const safe = value.length > 200 ? `${value.slice(0, 198)}…` : value;
  return `${kind}:${safe}`;
}

/** Dashboard */
export async function readDashboardOverviewCache(): Promise<{ stats: StatisticsOverviewData | null; updatedAt: number } | null> {
  const row = await readCacheEntry(CacheScope.DASHBOARD, DASHBOARD_KEY);
  if (!row) return null;
  try {
    const body = JSON.parse(row.payload) as DashboardCachePayload;
    if (body?.v !== 1) return null;
    return { stats: body.stats ?? null, updatedAt: row.updatedAt };
  } catch {
    return null;
  }
}

export async function writeDashboardOverviewCache(stats: StatisticsOverviewData | null): Promise<void> {
  const body: DashboardCachePayload = { v: 1, stats };
  await writeCacheEntry(CacheScope.DASHBOARD, DASHBOARD_KEY, JSON.stringify(body));
}

export function dashboardCacheIsStale(updatedAt: number): boolean {
  return isStale(updatedAt, CacheScope.DASHBOARD);
}

/** Entreprises (liste, première page) */
export async function readEntreprisesListCache(
  cacheKey: string,
): Promise<{ items: unknown[]; total: number | null; updatedAt: number } | null> {
  const row = await readCacheEntry(CacheScope.ENTREPRISES_LIST, cacheKey);
  if (!row) return null;
  try {
    const body = JSON.parse(row.payload) as EntreprisesListCachePayload;
    if (body?.v !== 1) return null;
    return { items: body.items ?? [], total: body.total ?? null, updatedAt: row.updatedAt };
  } catch {
    return null;
  }
}

export async function writeEntreprisesListCache(
  cacheKey: string,
  items: unknown[],
  total: number | null,
): Promise<void> {
  const body: EntreprisesListCachePayload = { v: 1, items, total };
  await writeCacheEntry(CacheScope.ENTREPRISES_LIST, cacheKey, JSON.stringify(body));
}

export function entreprisesListCacheIsStale(updatedAt: number): boolean {
  return isStale(updatedAt, CacheScope.ENTREPRISES_LIST);
}

/** Entreprise (fiche) */
export async function readEntrepriseDetailCache(cacheKey: string): Promise<EntrepriseDetailCachePayload & { updatedAt: number } | null> {
  const row = await readCacheEntry(CacheScope.ENTREPRISE_DETAIL, cacheKey);
  if (!row) return null;
  try {
    const body = JSON.parse(row.payload) as EntrepriseDetailCachePayload;
    if (body?.v !== 1) return null;
    return { ...body, updatedAt: row.updatedAt };
  } catch {
    return null;
  }
}

export async function writeEntrepriseDetailCache(cacheKey: string, body: EntrepriseDetailCachePayload): Promise<void> {
  await writeCacheEntry(CacheScope.ENTREPRISE_DETAIL, cacheKey, JSON.stringify(body));
}

export function entrepriseDetailCacheIsStale(updatedAt: number): boolean {
  return isStale(updatedAt, CacheScope.ENTREPRISE_DETAIL);
}

/** Campagnes (liste) */
export async function readCampagnesListCache(): Promise<{ items: unknown[]; updatedAt: number } | null> {
  const row = await readCacheEntry(CacheScope.CAMPAGNES_LIST, CAMPAGNES_LIST_KEY);
  if (!row) return null;
  try {
    const body = JSON.parse(row.payload) as CampagnesListCachePayload;
    if (body?.v !== 1) return null;
    return { items: body.items ?? [], updatedAt: row.updatedAt };
  } catch {
    return null;
  }
}

export async function writeCampagnesListCache(items: unknown[]): Promise<void> {
  const body: CampagnesListCachePayload = { v: 1, items };
  await writeCacheEntry(CacheScope.CAMPAGNES_LIST, CAMPAGNES_LIST_KEY, JSON.stringify(body));
}

export function campagnesListCacheIsStale(updatedAt: number): boolean {
  return isStale(updatedAt, CacheScope.CAMPAGNES_LIST);
}

/** Campagne (détail) */
export async function readCampagneDetailCache(
  id: number,
): Promise<{ campagne: Record<string, unknown> | null; stats: Record<string, unknown> | null; updatedAt: number } | null> {
  const row = await readCacheEntry(CacheScope.CAMPAGNE_DETAIL, String(id));
  if (!row) return null;
  try {
    const body = JSON.parse(row.payload) as CampagneDetailCachePayload;
    if (body?.v !== 1) return null;
    return { campagne: body.campagne, stats: body.stats, updatedAt: row.updatedAt };
  } catch {
    return null;
  }
}

export async function writeCampagneDetailCache(
  id: number,
  campagne: Record<string, unknown> | null,
  stats: Record<string, unknown> | null,
): Promise<void> {
  const body: CampagneDetailCachePayload = { v: 1, campagne, stats };
  await writeCacheEntry(CacheScope.CAMPAGNE_DETAIL, String(id), JSON.stringify(body));
}

export function campagneDetailCacheIsStale(updatedAt: number): boolean {
  return isStale(updatedAt, CacheScope.CAMPAGNE_DETAIL);
}
