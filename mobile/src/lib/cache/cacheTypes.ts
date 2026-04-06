import type { StatisticsOverviewData } from '../../features/prospectlab/prospectLabApi';

export type CachedEntry<T> = {
  data: T;
  updatedAt: number;
};

/** Payload figé pour la fiche entreprise (ce que l'écran affiche après chargement). */
export type EntrepriseDetailCachePayload = {
  v: 1;
  raw: unknown;
  report: unknown | null;
  emails: unknown[] | null;
  phones: unknown[] | null;
  phonesApi: unknown[] | null;
  campagnes: unknown[] | null;
};

export type CampagneDetailCachePayload = {
  v: 1;
  campagne: Record<string, unknown> | null;
  stats: Record<string, unknown> | null;
};

export type EntreprisesListCachePayload = {
  v: 1;
  items: unknown[];
  total: number | null;
};

export type CampagnesListCachePayload = {
  v: 1;
  items: unknown[];
};

export type DashboardCachePayload = {
  v: 1;
  stats: StatisticsOverviewData | null;
};

/** Cache SWR des entreprises « proches » (API /entreprises/proches). */
export type MapNearbyCachePayload = {
  v: 2;
  items: unknown[];
  /** Centre utilisé pour l’appel (après quantification de clé). */
  queryCenter?: { lat: number; lng: number };
  radiusKm?: number;
};
