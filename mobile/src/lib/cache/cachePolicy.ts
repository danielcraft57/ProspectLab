import { CacheScope, type CacheScopeValue } from './cacheScopes';

/** Après ce délai, une entrée est considérée « périmée » pour déclencher un appel réseau prioritaire (SWR). */
export const STALE_AFTER_MS: Record<CacheScopeValue, number> = {
  [CacheScope.DASHBOARD]: 2 * 60 * 1000,
  [CacheScope.ENTREPRISES_LIST]: 3 * 60 * 1000,
  [CacheScope.ENTREPRISE_DETAIL]: 6 * 60 * 1000,
  [CacheScope.CAMPAGNES_LIST]: 3 * 60 * 1000,
  [CacheScope.CAMPAGNE_DETAIL]: 6 * 60 * 1000,
};

/** Nombre max de fiches détail conservées (LRU par `last_accessed_at`). */
export const DETAIL_LRU_MAX: Partial<Record<CacheScopeValue, number>> = {
  [CacheScope.ENTREPRISE_DETAIL]: 55,
  [CacheScope.CAMPAGNE_DETAIL]: 35,
};

/** Budget doux pour la taille totale des `payload` (octets), hors queue offline. */
export const MAX_CACHE_BYTES_SOFT = 10 * 1024 * 1024;

export function isStale(updatedAtMs: number, scope: CacheScopeValue): boolean {
  return Date.now() - updatedAtMs > STALE_AFTER_MS[scope];
}
