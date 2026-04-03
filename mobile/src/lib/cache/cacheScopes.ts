/** Domaines logiques de cache (évite les collisions de clés). */
export const CacheScope = {
  DASHBOARD: 'dashboard',
  ENTREPRISES_LIST: 'entreprises_list',
  ENTREPRISE_DETAIL: 'entreprise_detail',
  CAMPAGNES_LIST: 'campagnes_list',
  CAMPAGNE_DETAIL: 'campagne_detail',
} as const;

export type CacheScopeValue = (typeof CacheScope)[keyof typeof CacheScope];
