import { Config } from '../../core/config';
import type { CacheRequestOptions } from '../../lib/http/apiMemoryCache';
import { fetchJsonCached, prospectLabCacheKey } from '../../lib/http/apiMemoryCache';
import { fetchJson, HttpError } from '../../lib/http/httpClient';

export type ProspectLabStatisticsResponse = {
  success?: boolean;
  data?: unknown;
  error?: string;
};

export type ProspectLabEntreprisesResponse = {
  success: boolean;
  count: number;
  /** Nombre de lignes correspondant aux filtres (présent surtout lorsque offset = 0). */
  total?: number;
  limit: number;
  offset: number;
  data: Array<Record<string, unknown>>;
  error?: string;
};

export type ProspectLabCampagnesResponse = {
  success: boolean;
  count: number;
  limit: number;
  offset: number;
  data: Array<Record<string, unknown>>;
  error?: string;
};

export type { CacheRequestOptions };

const TTL = {
  statistics: 45_000,
  overview: 45_000,
  tokenInfo: 18_000,
  reference: 120_000,
  campagneMeta: 300_000,
  list: 28_000,
  lookup: 35_000,
  analysis: 70_000,
  emails: 22_000,
  phones: 22_000,
} as const;

function publicUrl(path: string) {
  const base = Config.prospectLabBaseUrl.replace(/\/+$/, '');
  const prefix = Config.prospectLabPublicPrefix.startsWith('/')
    ? Config.prospectLabPublicPrefix
    : `/${Config.prospectLabPublicPrefix}`;
  return `${base}${prefix}${path.startsWith('/') ? path : `/${path}`}`;
}

function bearerHeaders(token: string | null): Record<string, string> {
  if (!token) return {};
  return { Authorization: `Bearer ${token}` };
}

export type StatisticsOverviewData = {
  total_entreprises?: number;
  total_analyses?: number;
  total_campagnes?: number;
  total_emails?: number;
  emails_envoyes?: number;
  trend_entreprises?: Array<{ date: string; count: number }>;
};

export class ProspectLabApi {
  /** Vérifie le token (sans cache) — 200 OK ou code HTTP (ex. 401). */
  static async validateToken(token: string): Promise<
    | { ok: true; status: 200 }
    | { ok: false; status: number; message: string }
  > {
    try {
      await ProspectLabApi.getTokenInfo(token, { skipCache: true });
      return { ok: true, status: 200 };
    } catch (e: unknown) {
      if (e instanceof HttpError) {
        return { ok: false, status: e.info.status, message: e.message };
      }
      const msg = e instanceof Error ? e.message : String(e);
      return { ok: false, status: 0, message: msg };
    }
  }

  /** Enregistre un jeton Expo Push pour ce token API (notifications serveur → appareil). */
  static async registerExpoPush(
    token: string,
    payload: { expoPushToken: string; platform?: string; installationId?: string },
  ) {
    const url = publicUrl('/push/register');
    return fetchJson<{ success: boolean; error?: string }>(url, {
      method: 'POST',
      headers: bearerHeaders(token),
      body: {
        expo_push_token: payload.expoPushToken,
        platform: payload.platform ?? 'android',
        installation_id: payload.installationId,
      },
    });
  }

  static async unregisterExpoPush(token: string, expoPushToken: string) {
    const url = publicUrl('/push/register');
    return fetchJson<{ success: boolean; removed?: boolean }>(url, {
      method: 'DELETE',
      headers: bearerHeaders(token),
      body: { expo_push_token: expoPushToken },
    });
  }

  static async getTokenInfo(token: string, cache?: CacheRequestOptions) {
    const url = publicUrl('/token/info');
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.tokenInfo,
      () => fetchJson<any>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async getStatistics(token: string, cache?: CacheRequestOptions) {
    const url = publicUrl('/statistics');
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.statistics,
      () =>
        fetchJson<ProspectLabStatisticsResponse>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async getStatisticsOverview(token: string, params?: { days?: number }, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    if (params?.days != null) q.set('days', String(params.days));
    const qs = q.toString();
    const url = publicUrl(`/statistics/overview${qs ? `?${qs}` : ''}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.overview,
      () => fetchJson<{ success?: boolean; data?: StatisticsOverviewData }>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async getReferenceCiblage(token: string, cache?: CacheRequestOptions) {
    const url = publicUrl('/reference/ciblage');
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.reference,
      () => fetchJson<any>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async getReferenceCiblageCounts(token: string, cache?: CacheRequestOptions) {
    const url = publicUrl('/reference/ciblage/counts');
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.reference,
      () => fetchJson<any>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async getCampagneStatuses(token: string, cache?: CacheRequestOptions) {
    const url = publicUrl('/campagnes/statuses');
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.campagneMeta,
      () => fetchJson<any>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  /** Statuts entreprise officiels (pipeline + delivrabilite), pour filtres et formulaires. */
  static async getEntrepriseStatuses(token: string, cache?: CacheRequestOptions) {
    const url = publicUrl('/entreprises/statuses');
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.reference,
      () => fetchJson<{ success?: boolean; data?: string[] }>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async listEntreprises(
    token: string,
    params?: {
      limit?: number;
      offset?: number;
      search?: string;
      secteur?: string;
      statut?: string;
      opportunite?: string;
    },
    cache?: CacheRequestOptions,
  ) {
    const q = new URLSearchParams();
    q.set('limit', String(params?.limit ?? 50));
    q.set('offset', String(params?.offset ?? 0));
    if (params?.search) q.set('search', params.search);
    if (params?.secteur) q.set('secteur', params.secteur);
    if (params?.statut) q.set('statut', params.statut);
    if (params?.opportunite) q.set('opportunite', params.opportunite);
    const url = publicUrl(`/entreprises?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.list,
      () =>
        fetchJson<ProspectLabEntreprisesResponse>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async listCampagnes(token: string, params?: { limit?: number; offset?: number; statut?: string }, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    q.set('limit', String(params?.limit ?? 50));
    q.set('offset', String(params?.offset ?? 0));
    if (params?.statut) q.set('statut', params.statut);
    const url = publicUrl(`/campagnes?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.list,
      () =>
        fetchJson<ProspectLabCampagnesResponse>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async getCampagne(token: string, campagneId: number, cache?: CacheRequestOptions) {
    const url = publicUrl(`/campagnes/${campagneId}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.list,
      () => fetchJson<{ success?: boolean; data?: Record<string, unknown> }>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async getCampagneStatistics(token: string, campagneId: number, cache?: CacheRequestOptions) {
    const url = publicUrl(`/campagnes/${campagneId}/statistics`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.list,
      () => fetchJson<{ success?: boolean; data?: Record<string, unknown>; campagne_id?: number }>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }

  static async findEntrepriseByWebsite(token: string, website: string, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    q.set('website', website);
    const url = publicUrl(`/entreprises/by-website?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.lookup,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async findEntrepriseByEmail(token: string, email: string, includeEmails = true, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    q.set('email', email);
    if (includeEmails) q.set('include_emails', 'true');
    const url = publicUrl(`/entreprises/by-email?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.lookup,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async findEntrepriseByPhone(token: string, phone: string, includePhones = true, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    q.set('phone', phone);
    if (includePhones) q.set('include_phones', 'true');
    const url = publicUrl(`/entreprises/by-phone?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.lookup,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async launchWebsiteAnalysis(token: string, website: string, force = false) {
    return fetchJson<any>(publicUrl('/website-analysis'), {
      method: 'POST',
      headers: bearerHeaders(token),
      body: { website, force },
      timeoutMs: 30000,
    });
  }

  static async getWebsiteAnalysis(token: string, website: string, full = false, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    q.set('website', website);
    if (full) q.set('full', 'true');
    const url = publicUrl(`/website-analysis?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.analysis,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
          timeoutMs: 30000,
        }),
      cache,
    );
  }

  static async getEntreprise(token: string, entrepriseId: number, cache?: CacheRequestOptions) {
    const url = publicUrl(`/entreprises/${entrepriseId}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.lookup,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  /** Suppression définitive côté serveur (cascade sur données liées). */
  static async deleteEntreprise(token: string, entrepriseId: number) {
    const url = publicUrl(`/entreprises/${entrepriseId}`);
    return fetchJson<{ success: boolean; message?: string; deleted_id?: number; error?: string }>(url, {
      method: 'DELETE',
      headers: bearerHeaders(token),
    });
  }

  static async listCampagnesByEntreprise(
    token: string,
    entrepriseId: number,
    params?: { limit?: number; offset?: number; statut?: string },
    cache?: CacheRequestOptions,
  ) {
    const q = new URLSearchParams();
    q.set('limit', String(params?.limit ?? 50));
    q.set('offset', String(params?.offset ?? 0));
    if (params?.statut) q.set('statut', params.statut);
    const url = publicUrl(`/entreprises/${entrepriseId}/campagnes?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.list,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async listEntrepriseEmailsAll(token: string, entrepriseId: number, includePrimary = true, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    if (includePrimary) q.set('include_primary', 'true');
    const url = publicUrl(`/entreprises/${entrepriseId}/emails/all?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.emails,
      () =>
        fetchJson<any>(url, {
          headers: bearerHeaders(token),
        }),
      cache,
    );
  }

  static async listEntreprisePhones(token: string, entrepriseId: number, includePrimary = true, cache?: CacheRequestOptions) {
    const q = new URLSearchParams();
    if (includePrimary) q.set('include_primary', 'true');
    const url = publicUrl(`/entreprises/${entrepriseId}/phones?${q.toString()}`);
    return fetchJsonCached(
      prospectLabCacheKey(token, url),
      TTL.phones,
      () => fetchJson<any>(url, { headers: bearerHeaders(token) }),
      cache,
    );
  }
}
