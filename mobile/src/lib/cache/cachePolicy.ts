import { CacheScope, type CacheScopeValue } from './cacheScopes';

/** Après ce délai, une entrée est considérée « périmée » pour déclencher un appel réseau prioritaire (SWR). */
export const STALE_AFTER_MS: Record<CacheScopeValue, number> = {
  [CacheScope.DASHBOARD]: 2 * 60 * 1000,
  [CacheScope.ENTREPRISES_LIST]: 3 * 60 * 1000,
  [CacheScope.ENTREPRISE_DETAIL]: 6 * 60 * 1000,
  [CacheScope.CAMPAGNES_LIST]: 3 * 60 * 1000,
  [CacheScope.CAMPAGNE_DETAIL]: 6 * 60 * 1000,
  [CacheScope.MAP_NEARBY]: 2 * 60 * 1000,
};

/**
 * LRU par scope (last_accessed_at) : limite le nombre de clés conservées.
 * MAP_NEARBY : plusieurs cellules de carte / filtres sans explosion SQLite.
 */
export const SCOPE_LRU_MAX: Partial<Record<CacheScopeValue, number>> = {
  [CacheScope.ENTREPRISE_DETAIL]: 55,
  [CacheScope.CAMPAGNE_DETAIL]: 35,
  [CacheScope.MAP_NEARBY]: 48,
};

/** @deprecated Utiliser SCOPE_LRU_MAX */
export const DETAIL_LRU_MAX: Partial<Record<CacheScopeValue, number>> = SCOPE_LRU_MAX;

/** Budget doux pour la taille totale des `payload` (octets), hors queue offline. */
export const MAX_CACHE_BYTES_SOFT = 10 * 1024 * 1024;

export function isStale(updatedAtMs: number, scope: CacheScopeValue): boolean {
  return Date.now() - updatedAtMs > STALE_AFTER_MS[scope];
}
